from typing import Optional
from datetime import datetime, date, timedelta
import zoneinfo
import calendar

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, desc

from app.db.session import get_db
from app.models.transaction import Transaction
from app.core.ledger import POSITIVE_TYPES, NEGATIVE_TYPES
from app.models.paycheck import PaycheckConfig, PaycheckBucket
from app.services.paycheck_cycles import legacy_cycle_covers, recorded_cycle_ends
from app.models.account import Account
from app.models.user import User
from app.api.deps import get_current_user
from app.schemas.transaction import (
    MonthlySummary,
    CategorySummary,
    AccountBalance,
    DailyTrendItem,
    CycleBurnDay,
    SafeToSpendInfo,
)
from app.services.analytics import compute_safe_to_spend_metrics
from app.core.config import settings

router = APIRouter()
WIB = zoneinfo.ZoneInfo(settings.TIMEZONE)

def get_monthly_date_bounds(ref_date: date, payday: int) -> tuple[date, date]:
    """
    Returns (cycle_start, cycle_end) for a recurring payday (1-31).
    Clamps day to max days of month if necessary.
    """
    last_day = calendar.monthrange(ref_date.year, ref_date.month)[1]
    if ref_date.day >= min(payday, last_day):
        start_year, start_month = ref_date.year, ref_date.month
    else:
        if ref_date.month == 1:
            start_year, start_month = ref_date.year - 1, 12
        else:
            start_year, start_month = ref_date.year, ref_date.month - 1
            
    _, max_days_start = calendar.monthrange(start_year, start_month)
    start_date = date(start_year, start_month, min(payday, max_days_start))
    
    if start_month == 12:
        next_year, next_month = start_year + 1, 1
    else:
        next_year, next_month = start_year, start_month + 1
        
    _, max_days_next = calendar.monthrange(next_year, next_month)
    end_date = date(next_year, next_month, min(payday, max_days_next)) - timedelta(days=1)
    return start_date, end_date

@router.get("/periods")
def get_available_periods(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    now_wib = datetime.now(WIB)
    today_wib = now_wib.date()

    cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == current_user.id).first()
    cycle_days = cfg.cycle_days if cfg and cfg.cycle_days > 0 else 14
    cycle_type = cfg.cycle_type if cfg and cfg.cycle_type else "biweekly"
    anchor_start = cfg.cycle_start_date if cfg and cfg.cycle_start_date else None
    paycheck_day = cfg.paycheck_day if cfg and cfg.paycheck_day else (anchor_start.day if anchor_start else 25)

    if cycle_type == "monthly_date":
        label_prefix = f"Siklus Bulanan (Tgl {paycheck_day})"
    elif cycle_days == 30 or cycle_type == "monthly":
        label_prefix = "Siklus Bulanan (30 Hari)"
    elif cycle_days == 14 or cycle_type == "biweekly":
        label_prefix = "Siklus 2-Mingguan"
    elif cycle_days == 7 or cycle_type == "weekly":
        label_prefix = "Siklus Mingguan"
    else:
        label_prefix = f"Siklus {cycle_days} Hari"

    # 1. Ambil semua gajian unik milik user
    paycheck_rows = db.query(Transaction.date).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "income",
        ~legacy_cycle_covers(db, current_user.id),
        Transaction.category.in_(["Gajian", "Gaji", "Pemasukan", "Uang Saku Ortu", "Income"]) | Transaction.description.ilike("%gajian%") | Transaction.description.ilike("%pemasukan%")
    ).order_by(Transaction.date.desc()).distinct().all()

    cycle_ends = recorded_cycle_ends(db, current_user.id)
    paycheck_dates = sorted({row.date for row in paycheck_rows} | cycle_ends.keys(), reverse=True)
    cycles = []
    # Jika tidak ada riwayat gajian, gunakan anchor onboarding atau hari ini
    if not paycheck_dates:
        if cycle_type == "monthly_date":
            default_start, default_end = get_monthly_date_bounds(today_wib, paycheck_day)
        else:
            default_start = anchor_start or today_wib
            default_end = default_start + timedelta(days=cycle_days - 1)
        cycles.append({
            "id": f"cycle_{default_start}",
            "type": "cycle",
            "start": str(default_start),
            "end": str(default_end),
            "label": f"{label_prefix} ({default_start.strftime('%d %b')} – {default_end.strftime('%d %b %Y')})",
            "is_current": False
        })
    else:
        seen_starts = set()
        for paycheck_date in paycheck_dates:
            cycle_label = label_prefix
            if paycheck_date in cycle_ends:
                c_start, c_end = paycheck_date, cycle_ends[paycheck_date]
            elif cycle_type == "monthly_date":
                c_start, c_end = get_monthly_date_bounds(paycheck_date, paycheck_day)
            else:
                c_start = paycheck_date
                c_end = c_start + timedelta(days=cycle_days - 1)
            if c_start in cycle_ends:
                c_end = cycle_ends[c_start]
                cycle_label = f"Siklus {(c_end - c_start).days + 1} Hari"
            if c_start in seen_starts:
                continue
            seen_starts.add(c_start)
            cycles.append({
                "id": f"cycle_{c_start}",
                "type": "cycle",
                "start": str(c_start),
                "end": str(c_end),
                "label": f"{cycle_label} ({c_start.strftime('%d %b')} – {c_end.strftime('%d %b %Y')})",
                "is_current": False
            })

    cycles.sort(key=lambda cycle: cycle["start"], reverse=True)
    today_key = today_wib.isoformat()
    current_cycle = next((cycle for cycle in cycles if cycle["start"] <= today_key <= cycle["end"]), None)
    if current_cycle:
        current_cycle["is_current"] = True
        current_cycle["label"] += " (Aktif)"

    # 2. Minggu ini & minggu lalu
    this_week_start = today_wib - timedelta(days=today_wib.weekday())
    this_week_end = this_week_start + timedelta(days=6)
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = last_week_start + timedelta(days=6)

    weeks = [
        {
            "id": f"week_{this_week_start}",
            "type": "week",
            "start": str(this_week_start),
            "end": str(this_week_end),
            "label": f"Minggu Ini ({this_week_start.strftime('%d %b')} – {this_week_end.strftime('%d %b %Y')})",
            "is_current": True
        },
        {
            "id": f"week_{last_week_start}",
            "type": "week",
            "start": str(last_week_start),
            "end": str(last_week_end),
            "label": f"Minggu Lalu ({last_week_start.strftime('%d %b')} – {last_week_end.strftime('%d %b %Y')})",
            "is_current": False
        }
    ]

    # 3. Bulan (bulan ini & 5 bulan ke belakang)
    months = []
    curr_yr = now_wib.year
    curr_mo = now_wib.month
    for i in range(6):
        target_mo = curr_mo - i
        target_yr = curr_yr
        while target_mo <= 0:
            target_mo += 12
            target_yr -= 1
        m_start = date(target_yr, target_mo, 1)
        next_m = date(target_yr + 1, 1, 1) if target_mo == 12 else date(target_yr, target_mo + 1, 1)
        m_end = next_m - timedelta(days=1)
        is_cur = (target_yr == curr_yr and target_mo == curr_mo)
        months.append({
            "id": f"month_{target_yr:04d}_{target_mo:02d}",
            "type": "month",
            "month": f"{target_yr:04d}-{target_mo:02d}",
            "start": str(m_start),
            "end": str(m_end),
            "label": f"Bulan {m_start.strftime('%B %Y')}{' (Bulan Ini)' if is_cur else ''}",
            "is_current": is_cur
        })

    return {
        "cycles": cycles,
        "weeks": weeks,
        "months": months
    }

@router.get("/summary", response_model=MonthlySummary)
def get_monthly_summary(
    month: Optional[str] = Query(None, description="Format YYYY-MM"),
    period_type: Optional[str] = Query("cycle", description="cycle | week | month | custom"),
    start: Optional[str] = Query(None, description="Format YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="Format YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    now_wib = datetime.now(WIB)
    today_wib = now_wib.date()

    # Cari daftar seluruh gajian milik user yang ada di database untuk referensi siklus
    paychecks = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "income",
        Transaction.date <= today_wib,
        ~legacy_cycle_covers(db, current_user.id),
        Transaction.category.in_(["Gajian", "Gaji", "Pemasukan", "Uang Saku Ortu", "Income"]) | Transaction.description.ilike("%gajian%") | Transaction.description.ilike("%pemasukan%")
    ).order_by(desc(Transaction.date), desc(Transaction.id)).all()

    # Default cycle anchor
    if paychecks:
        latest_cycle_start = paychecks[0].date
    else:
        latest_cycle_start = today_wib

    # Tentukan start_date & end_date berdasarkan period_type
    period_label = ""
    if period_type == "custom" and start and end:
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d").date()
            end_date = datetime.strptime(end, "%Y-%m-%d").date()
            period_label = f"Kustom: {start_date.strftime('%d %b')} – {end_date.strftime('%d %b %Y')}"
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid start/end date format, use YYYY-MM-DD")
    elif period_type == "week":
        this_week_start = today_wib - timedelta(days=today_wib.weekday())
        try:
            start_date = date.fromisoformat(start) if start else this_week_start
            end_date = start_date + timedelta(days=6)
        except (ValueError, OverflowError):
            raise HTTPException(status_code=400, detail="Tanggal awal minggu tidak valid.")
        week_label = "Minggu"
        if start_date == this_week_start:
            week_label = "Minggu Ini"
        elif start_date == this_week_start - timedelta(days=7):
            week_label = "Minggu Lalu"
        period_label = f"{week_label} ({start_date.strftime('%d %b')} – {end_date.strftime('%d %b %Y')})"
    elif period_type == "month":
        if month:
            try:
                yr, mo = map(int, month.split("-"))
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid month format, use YYYY-MM")
        else:
            yr = now_wib.year
            mo = now_wib.month
        start_date = date(yr, mo, 1)
        next_month = date(yr + 1, 1, 1) if mo == 12 else date(yr, mo + 1, 1)
        end_date = next_month - timedelta(days=1)
        period_label = f"Bulan {start_date.strftime('%B %Y')}"
    else:
        # Default: Siklus gajian dinamis (sesuai PaycheckConfig)
        period_type = "cycle"
        if start:
            try:
                start_date = datetime.strptime(start, "%Y-%m-%d").date()
            except Exception:
                start_date = latest_cycle_start
        else:
            start_date = latest_cycle_start

        cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == current_user.id).first()
        cycle_days = cfg.cycle_days if cfg and cfg.cycle_days > 0 else 14
        cycle_type = cfg.cycle_type if cfg and cfg.cycle_type else "biweekly"
        anchor_start = cfg.cycle_start_date if cfg and cfg.cycle_start_date else None
        paycheck_day = cfg.paycheck_day if cfg and cfg.paycheck_day else (anchor_start.day if anchor_start else 25)

        if cycle_type == "monthly_date":
            cur_start, cur_end = get_monthly_date_bounds(today_wib, paycheck_day)
            latest_cycle_start = cur_start
        elif paychecks:
            latest_cycle_start = paychecks[0].date
        elif anchor_start:
            latest_cycle_start = anchor_start
        else:
            latest_cycle_start = today_wib

        cycle_ends = recorded_cycle_ends(db, current_user.id)
        latest_recorded_start = max((day for day in cycle_ends if day <= today_wib), default=None)
        if latest_recorded_start and latest_recorded_start >= latest_cycle_start:
            latest_cycle_start = latest_recorded_start
        elif latest_recorded_start and not paychecks:
            latest_cycle_start = latest_recorded_start

        if start:
            try:
                start_date = datetime.strptime(start, "%Y-%m-%d").date()
            except Exception:
                start_date = latest_cycle_start
        else:
            start_date = latest_cycle_start

        if not end and start_date in cycle_ends:
            end_date = cycle_ends[start_date]
        elif end:
            try:
                end_date = datetime.strptime(end, "%Y-%m-%d").date()
            except Exception:
                if cycle_type == "monthly_date":
                    _, end_date = get_monthly_date_bounds(start_date, paycheck_day)
                else:
                    end_date = start_date + timedelta(days=cycle_days - 1)
        else:
            if cycle_type == "monthly_date":
                _, end_date = get_monthly_date_bounds(start_date, paycheck_day)
            else:
                end_date = start_date + timedelta(days=cycle_days - 1)

        if start_date in cycle_ends:
            label_prefix = f"Siklus {(end_date - start_date).days + 1} Hari"
        elif cycle_type == "monthly_date":
            cycle_days = (end_date - start_date).days + 1
            label_prefix = f"Siklus Bulanan (Tgl {paycheck_day})"
        elif cycle_days == 30 or cycle_type == "monthly":
            label_prefix = "Siklus Bulanan (30 Hari)"
        elif cycle_days == 14 or cycle_type == "biweekly":
            label_prefix = "Siklus 2-Mingguan"
        elif cycle_days == 7 or cycle_type == "weekly":
            label_prefix = "Siklus Mingguan"
        else:
            label_prefix = f"Siklus {cycle_days} Hari"

        period_label = f"{label_prefix} ({start_date.strftime('%d %b')} – {end_date.strftime('%d %b %Y')})"

    query_end_date = end_date + timedelta(days=1)

    # Monthly totals (income and expense) dalam rentang periode terpilih
    totals = db.query(
        Transaction.type,
        func.coalesce(func.sum(Transaction.amount), 0).label("total")
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= start_date,
        Transaction.date < query_end_date
    ).group_by(Transaction.type).all()

    income_total = 0
    expense_total = 0
    for r in totals:
        if r.type == "income":
            income_total = int(r.total)
        elif r.type == "expense":
            expense_total = int(r.total)

    net_total = income_total - expense_total
    savings_rate = round((net_total / income_total * 100), 1) if income_total > 0 else 0.0

    # Keep expense categories compatible with existing charts; report income separately.
    cat_rows = db.query(
        Transaction.category,
        Transaction.type,
        func.sum(Transaction.amount).label("total"),
        func.count(Transaction.id).label("count")
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= start_date,
        Transaction.date < query_end_date,
        Transaction.type.in_(["expense", "income"])
    ).group_by(Transaction.category, Transaction.type).order_by(func.sum(Transaction.amount).desc()).all()

    categories = []
    income_categories = []
    for c in cat_rows:
        tot = int(c.total)
        denominator = income_total if c.type == "income" else expense_total
        pct = round((tot / denominator * 100), 1) if denominator > 0 else 0.0
        group = income_categories if c.type == "income" else categories
        group.append(CategorySummary(
            category=c.category,
            total=tot,
            count=c.count,
            percentage=pct
        ))

    # All-time account balances (selalu all-time agar saldo rekening akurat)
    acc_rows = db.query(
        Transaction.account,
        func.sum(
            case(
                (Transaction.type.in_(POSITIVE_TYPES), Transaction.amount),
                (Transaction.type.in_(NEGATIVE_TYPES), -Transaction.amount),
                else_=0
            )
        ).label("balance")
    ).filter(Transaction.user_id == current_user.id).group_by(Transaction.account).order_by(
        func.sum(
            case(
                (Transaction.type.in_(POSITIVE_TYPES), Transaction.amount),
                (Transaction.type.in_(NEGATIVE_TYPES), -Transaction.amount),
                else_=0
            )
        ).desc()
    ).all()

    # Expense per account dalam periode
    acc_expense_rows = db.query(
        Transaction.account,
        func.coalesce(func.sum(Transaction.amount), 0).label("spent")
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "expense",
        Transaction.date >= start_date,
        Transaction.date < query_end_date
    ).group_by(Transaction.account).all()
    expense_by_acc = {r.account: int(r.spent) for r in acc_expense_rows}

    accounts = [
        AccountBalance(
            account=a.account,
            balance=int(a.balance or 0),
            expense=expense_by_acc.get(a.account, 0)
        )
        for a in acc_rows
    ]
    total_balance = sum(a.balance for a in accounts)

    # Daily trend dalam periode
    trend_rows = db.query(
        Transaction.date,
        func.sum(case((Transaction.type == "income", Transaction.amount), else_=0)).label("income"),
        func.sum(case((Transaction.type == "expense", Transaction.amount), else_=0)).label("expense")
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= start_date,
        Transaction.date < query_end_date
    ).group_by(Transaction.date).order_by(Transaction.date.asc()).all()

    daily_trend = [
        DailyTrendItem(
            date=str(t.date),
            income=int(t.income or 0),
            expense=int(t.expense or 0)
        ) for t in trend_rows
    ]

    # Safe to spend calculation via dedicated analytics service
    safe_info = compute_safe_to_spend_metrics(
        db=db,
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        period_type=period_type,
        today_wib=today_wib,
    )

    return MonthlySummary(
        period_type=period_type,
        period_label=period_label,
        start_date=str(start_date),
        end_date=str(end_date),
        month=f"{start_date.year:04d}-{start_date.month:02d}",
        year=start_date.year,
        month_num=start_date.month,
        income=income_total,
        expense=expense_total,
        net=net_total,
        savings_rate=savings_rate,
        categories=categories,
        income_categories=income_categories,
        accounts=accounts,
        total_balance=total_balance,
        daily_trend=daily_trend,
        safe_to_spend=safe_info
    )

@router.post("/sync-sheets")
def sync_sheets_endpoint(
    cycle_start: Optional[str] = Query(None, description="Format YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.services.sheets_sync import sync_cycle_snapshot
    start_d = None
    if cycle_start:
        try:
            start_d = datetime.strptime(cycle_start, "%Y-%m-%d").date()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")
    try:
        res = sync_cycle_snapshot(db, user_id=current_user.id, cycle_start_date=start_d)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google Sheets sync failed: {str(e)}")

