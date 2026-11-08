import io
import csv
import json
import re
from calendar import monthrange
from typing import Optional, List
from datetime import datetime, date, timedelta
import zoneinfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, case, extract

from app.db.session import get_db
from app.models.transaction import Transaction
from app.models.paycheck import PaycheckConfig, PaycheckBucket, PaycheckReceipt
from app.models.account import Account
from app.models.user import User
from app.models.subscription import SubscriptionPayment
from app.api.deps import get_current_user
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransactionOut,
    PaycheckRequest,
    PaycheckResponse,
    PaycheckAllocationItem,
    TransferCreate,
    TransferResponse,
)
from app.core.config import settings
from app.core.transfer import find_paired_transfer
from app.services.paycheck_cycles import receipt_allocations

router = APIRouter()
WIB = zoneinfo.ZoneInfo(settings.TIMEZONE)

@router.get("", response_model=List[TransactionOut])
def get_transactions(
    skip: int = 0,
    limit: int = 50,
    month: Optional[str] = Query(None, description="Format YYYY-MM"),
    start_date: Optional[str] = Query(None, description="Format YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Format YYYY-MM-DD"),
    category: Optional[str] = None,
    account: Optional[str] = None,
    type: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = filtered_transactions(db, current_user.id, month, start_date, end_date, category, account, type, search)
    return query.order_by(Transaction.date.desc(), Transaction.id.desc()).offset(skip).limit(limit).all()


def filtered_transactions(db, user_id, month=None, start_date=None, end_date=None, category=None, account=None, type=None, search=None):
    query = db.query(Transaction).filter(Transaction.user_id == user_id)

    if start_date or end_date:
        try:
            s_dt = date.fromisoformat(start_date) if start_date else None
            e_dt = date.fromisoformat(end_date) if end_date else None
            if s_dt and e_dt and s_dt > e_dt:
                raise ValueError("Tanggal terbalik")
            if s_dt:
                query = query.filter(Transaction.date >= s_dt)
            if e_dt:
                query = query.filter(Transaction.date <= e_dt)
        except (ValueError, TypeError):
            raise HTTPException(400, "Rentang tanggal tidak valid. Gunakan YYYY-MM-DD dan tanggal awal sebelum tanggal akhir.")
    elif month and month != "all":
        try:
            yr, mo = map(int, month.split("-"))
            s_dt = date(yr, mo, 1)
            if mo == 12:
                e_dt = date(yr + 1, 1, 1)
            else:
                e_dt = date(yr, mo + 1, 1)
            query = query.filter(Transaction.date >= s_dt, Transaction.date < e_dt)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid month format, use YYYY-MM")

    if category and category != "all":
        query = query.filter(Transaction.category == category)
    if account and account != "all":
        query = query.filter(Transaction.account == account)
    if type and type != "all":
        types = {"transfer": ("transfer_in", "transfer_out"), "adjustment": ("adjustment_in", "adjustment_out")}
        query = query.filter(Transaction.type.in_(types[type])) if type in types else query.filter(Transaction.type == type)
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Transaction.description.ilike(search_filter)) | 
            (Transaction.raw_text.ilike(search_filter)) |
            (Transaction.category.ilike(search_filter)) | (Transaction.account.ilike(search_filter))
        )

    return query


@router.get("/history")
def transaction_history(
    skip: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100),
    start_date: Optional[date] = None, end_date: Optional[date] = None,
    category: Optional[str] = None, account: Optional[str] = None,
    type: Optional[str] = None, search: Optional[str] = None,
    sort: str = Query("date-desc", pattern="^(date|amount)-(asc|desc)$"),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    query = filtered_transactions(db, current_user.id, start_date=str(start_date) if start_date else None,
                                  end_date=str(end_date) if end_date else None, category=category,
                                  account=account, type=type, search=search)
    count, income, expense = query.with_entities(
        func.count(Transaction.id),
        func.coalesce(func.sum(case((Transaction.type == "income", Transaction.amount), else_=0)), 0),
        func.coalesce(func.sum(case((Transaction.type == "expense", Transaction.amount), else_=0)), 0),
    ).one()
    column = Transaction.amount if sort.startswith("amount") else Transaction.date
    order = column.asc() if sort.endswith("asc") else column.desc()
    items = query.order_by(order, Transaction.id.desc()).offset(skip).limit(limit).all()
    return {"items": [TransactionOut.model_validate(item) for item in items], "total": count,
            "income": int(income), "expense": int(expense), "net": int(income - expense)}


@router.get("/calendar")
def transaction_calendar(
    year: int = Query(..., ge=1, le=9999), month: int = Query(..., ge=1, le=12),
    account: Optional[str] = None,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    query = filtered_transactions(db, current_user.id, start_date=str(start), end_date=str(end), account=account)
    kinds = ("income", "expense", "transfer_in", "transfer_out", "adjustment_in", "adjustment_out")
    rows = query.with_entities(
        Transaction.date, func.count(Transaction.id),
        *(func.coalesce(func.sum(case((Transaction.type == kind, Transaction.amount), else_=0)), 0) for kind in kinds),
        func.coalesce(func.sum(case((Transaction.type.in_(("transfer_in", "transfer_out")), 1), else_=0)), 0),
        func.coalesce(func.sum(case((Transaction.type.in_(("adjustment_in", "adjustment_out")), 1), else_=0)), 0),
    ).group_by(Transaction.date).order_by(Transaction.date).all()
    by_date = {row[0]: {"count": int(row[1]), **{kind: int(row[index + 2]) for index, kind in enumerate(kinds)},
                        "transfer_count": int(row[-2]), "adjustment_count": int(row[-1])} for row in rows}
    keys = ("count", *kinds, "transfer_count", "adjustment_count")
    days = []
    for day in range(1, end.day + 1):
        day_date = date(year, month, day)
        item = {key: by_date.get(day_date, {}).get(key, 0) for key in keys}
        days.append({"date": day_date, **item, "net": item["income"] - item["expense"]})
    totals = {key: sum(day[key] for day in days) for key in (*keys, "net")}
    years_query = db.query(extract("year", Transaction.date)).filter(Transaction.user_id == current_user.id)
    if account and account != "all":
        years_query = years_query.filter(Transaction.account == account)
    years = sorted({int(row[0]) for row in years_query.distinct()})
    return {"year": year, "month": month, "days": days, "totals": totals, "available_years": years}


def require_owned_accounts(db: Session, user_id: int, *names: str):
    owned = {row.name for row in db.query(Account).filter(
        Account.user_id == user_id, Account.name.in_(names), Account.is_archived == False,
    ).order_by(Account.id).with_for_update().all()}
    if any(name not in owned for name in names):
        raise HTTPException(400, "Pilih rekening aktif yang terdaftar di akun Anda.")


@router.post("", response_model=TransactionOut)
def create_transaction(
    payload: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    now_wib = datetime.now(WIB)
    tx_date = payload.date or now_wib.date()
    if payload.type in ("transfer_in", "transfer_out"):
        raise HTTPException(400, "Gunakan fitur transfer agar saldo asal dan tujuan tercatat berpasangan.")
    require_owned_accounts(db, current_user.id, payload.account)

    tx = Transaction(
        user_id=current_user.id,
        type=payload.type,
        amount=payload.amount,
        account=payload.account,
        category=payload.category,
        description=payload.description,
        raw_text=f"manual web: {payload.description}",
        date=tx_date
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx

@router.post("/transfer", response_model=TransferResponse)
def execute_transfer(
    payload: TransferCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Nominal transfer harus lebih besar dari 0")
    if payload.from_account == payload.to_account:
        raise HTTPException(status_code=400, detail="Rekening asal dan tujuan tidak boleh sama")

    require_owned_accounts(db, current_user.id, payload.from_account, payload.to_account)
    now_wib = datetime.now(WIB)
    tx_date = payload.date or now_wib.date()
    desc = payload.description or f"Transfer {payload.from_account} -> {payload.to_account}"

    tx_out, tx_in = add_transfer_pair(
        db, current_user.id, payload.from_account, payload.to_account, payload.amount, tx_date, desc,
    )
    db.commit()
    db.refresh(tx_out)
    db.refresh(tx_in)

    return TransferResponse(
        status="success",
        from_account=payload.from_account,
        to_account=payload.to_account,
        amount=payload.amount,
        out_transaction_id=tx_out.id,
        in_transaction_id=tx_in.id,
        date=tx_date
    )


def add_transfer_pair(db, user_id, from_account, to_account, amount, tx_date, desc):
    tx_out = Transaction(
        user_id=user_id,
        type="transfer_out",
        amount=amount,
        account=from_account,
        category="Transfer",
        description=f"Transfer ke {to_account}: {desc}",
        raw_text=f"transfer out: {from_account} -> {to_account} ({desc})",
        date=tx_date
    )
    tx_in = Transaction(
        user_id=user_id,
        type="transfer_in",
        amount=amount,
        account=to_account,
        category="Transfer",
        description=f"Transfer dari {from_account}: {desc}",
        raw_text=f"transfer in: {from_account} -> {to_account} ({desc})",
        date=tx_date
    )

    db.add(tx_out)
    db.add(tx_in)
    db.flush()

    # Link both records explicitly via raw_text tag for unambiguous paired operations
    tx_out.raw_text = f"{tx_out.raw_text} [pair_id:{tx_in.id}]"
    tx_in.raw_text = f"{tx_in.raw_text} [pair_id:{tx_out.id}]"

    return tx_out, tx_in

@router.post("/paycheck", response_model=PaycheckResponse)
def execute_paycheck_split(
    payload: PaycheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    now_wib = datetime.now(WIB)
    cycle_start = payload.date or now_wib.date()
    cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == current_user.id).first()
    cycle_days = cfg.cycle_days if cfg and cfg.cycle_days > 0 else 30
    cycle_end = cycle_start + timedelta(days=cycle_days - 1)
    total = payload.total_amount

    # Synchronize cycle_start_date so Safe-to-Spend telemetry tracks the new cycle
    if cfg:
        cfg.cycle_start_date = cycle_start
        db.add(cfg)
    else:
        cfg = PaycheckConfig(
            user_id=current_user.id,
            cycle_start_date=cycle_start,
            cycle_days=cycle_days
        )
        db.add(cfg)

    buckets = db.query(PaycheckBucket).filter(PaycheckBucket.config_id == cfg.id).order_by(PaycheckBucket.sort_order.asc()).all() if cfg else []
    if not buckets:
        user_accs = db.query(Account).filter(Account.user_id == current_user.id, Account.is_archived == False).all()
        if user_accs:
            n = len(user_accs)
            even_pct = round(100.0 / n, 1)
            buckets = [
                PaycheckBucket(
                    account=acc.name,
                    percentage=even_pct if i < n - 1 else round(100.0 - even_pct * (n - 1), 1),
                    purpose="Operasional" if acc.type == "operasional" else "Alokasi Pos"
                )
                for i, acc in enumerate(user_accs)
            ]
        else:
            buckets = [
                PaycheckBucket(account="Rekening Utama", percentage=100.0, purpose="Kebutuhan Pokok")
            ]

    active_names = {row.name for row in db.query(Account).filter(Account.user_id == current_user.id, Account.is_archived == False)}
    buckets = [bucket for bucket in buckets if bucket.account in active_names]

    allocations_plan = []
    allocated_sum = 0
    for idx, b in enumerate(buckets):
        if idx == len(buckets) - 1:
            amt = max(0, total - allocated_sum)
        else:
            amt = int(round(total * (b.percentage / 100.0)))
            allocated_sum += amt
        pct = round(amt / total * 100, 1) if total > 0 else 0.0
        allocations_plan.append({
            "account": b.account,
            "amount": amt,
            "percentage": pct,
            "purpose": b.purpose,
            "desc": f"Gajian (Alokasi {b.account})",
        })

    created_txs = []
    for item in allocations_plan:
        if item["amount"] <= 0:
            continue
        tx = Transaction(
            user_id=current_user.id,
            type="income",
            amount=item["amount"],
            account=item["account"],
            category="Gajian",
            description=item["desc"],
            raw_text=f"paycheck-split: total {total} -> {item['account']} {item['amount']}",
            date=cycle_start
        )
        db.add(tx)
        created_txs.append(tx)

    db.commit()
    for tx in created_txs:
        db.refresh(tx)

    return PaycheckResponse(
        success=True,
        total_amount=total,
        cycle_start=cycle_start,
        cycle_end=cycle_end,
        allocations=[
            PaycheckAllocationItem(
                account=item["account"],
                amount=item["amount"],
                percentage=item["percentage"],
                purpose=item["purpose"]
            )
            for item in allocations_plan
        ],
        created_transactions=created_txs
    )

def lock_paycheck_receipt(db: Session, tx: Transaction):
    receipt_tag = re.search(r"\[paycheck_receipt:(\d+)\]$", tx.raw_text or "")
    receipt_id = int(receipt_tag.group(1)) if receipt_tag else tx.id
    return db.query(PaycheckReceipt).filter(
        PaycheckReceipt.transaction_id == receipt_id, PaycheckReceipt.user_id == tx.user_id,
    ).with_for_update().first()


@router.put("/{tx_id}", response_model=TransactionOut)
def update_transaction(
    tx_id: int,
    payload: TransactionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tx = db.query(Transaction).filter(Transaction.id == tx_id, Transaction.user_id == current_user.id).with_for_update().first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if tx.type in ("adjustment_in", "adjustment_out"):
        raise HTTPException(409, "Catatan penyesuaian disimpan sebagai riwayat. Gunakan rekonsiliasi baru untuk koreksi.")
    update_data = payload.model_dump(exclude_unset=True)
    if update_data.get("account") is not None and update_data["account"] != tx.account:
        require_owned_accounts(db, current_user.id, update_data["account"])
    payment = db.query(SubscriptionPayment).filter(
        SubscriptionPayment.user_id == current_user.id, SubscriptionPayment.transaction_id == tx.id,
    ).with_for_update().first()
    if payment and any(update_data.get(field) not in (None, getattr(tx, field))
                       for field in ("type", "amount", "account", "category", "date")):
        raise HTTPException(409, "Hapus transaksi pembayaran lalu catat ulang tagihan untuk mengoreksi nominal, rekening, atau tanggal.")
    transfer_types = ("transfer_out", "transfer_in")
    requested_type = update_data.get("type") or tx.type
    receipt = lock_paycheck_receipt(db, tx)
    if receipt and receipt.transaction_id == tx.id:
        if any(update_data.get(field) not in (None, getattr(tx, field))
               for field in ("type", "account", "category", "date")):
            raise HTTPException(409, "Catatan gaji hanya bisa diubah nominal dan keterangannya.")
        new_amount = update_data.get("amount")
        if new_amount is not None and new_amount != tx.amount:
            allocations = receipt_allocations(db, receipt)
            transferred = sum(item["amount"] for item in allocations if item["transfer_id"])
            if new_amount < transferred:
                raise HTTPException(409, f"Nominal gaji tidak boleh kurang dari Rp{transferred:,} yang sudah dibagi.".replace(",", "."))
            pending = [item for item in allocations if not item["transfer_id"]]
            old_remaining = max(tx.amount - transferred, sum(item["amount"] for item in pending))
            if old_remaining > 0:
                new_remaining = new_amount - transferred
                for item in pending:
                    item["amount"] = item["amount"] * new_remaining // old_remaining
            receipt.allocations_json = json.dumps(allocations)
    if tx.type in transfer_types:
        if receipt and any(update_data.get(field) not in (None, getattr(tx, field)) for field in ("amount", "account")):
            raise HTTPException(409, "Untuk mengubah nominal atau rekening, hapus transfer ini lalu catat ulang pembagian gaji.")
        if requested_type != tx.type:
            raise HTTPException(status_code=400, detail="Tipe transfer tidak dapat diubah menjadi transaksi biasa")
        pair = find_paired_transfer(db, tx)
        if not pair:
            raise HTTPException(status_code=400, detail="Pasangan transfer tidak ditemukan; transfer belum dapat diedit")
        if (update_data.get("account") or tx.account) == pair.account:
            raise HTTPException(status_code=400, detail="Rekening asal dan tujuan tidak boleh sama")
        if update_data.get("category") not in (None, "Transfer"):
            raise HTTPException(status_code=400, detail="Kategori transfer harus tetap Transfer")
        for field in ("amount", "date"):
            if update_data.get(field) is not None:
                setattr(pair, field, update_data[field])
    elif requested_type in transfer_types:
        raise HTTPException(status_code=400, detail="Gunakan fitur transfer untuk memindahkan saldo antar rekening")
    for field, value in update_data.items():
        if value is not None:
            setattr(tx, field, value)
            
    db.commit()
    db.refresh(tx)
    return tx

@router.delete("/{tx_id}")
def delete_transaction(
    tx_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tx = db.query(Transaction).filter(Transaction.id == tx_id, Transaction.user_id == current_user.id).with_for_update().first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if tx.type in ("adjustment_in", "adjustment_out"):
        raise HTTPException(409, "Catatan penyesuaian disimpan sebagai riwayat. Gunakan rekonsiliasi baru untuk koreksi.")
    receipt = lock_paycheck_receipt(db, tx)
    if receipt and receipt.transaction_id == tx.id:
        if any(item["transfer_id"] for item in receipt_allocations(db, receipt)):
            raise HTTPException(409, "Hapus transfer pembagian gaji terlebih dahulu. Saldo rekening dan siklus belum berubah.")
        db.delete(receipt)

    deleted_ids = [tx.id]
    db.query(SubscriptionPayment).filter(
        SubscriptionPayment.user_id == current_user.id, SubscriptionPayment.transaction_id == tx.id,
    ).delete(synchronize_session=False)
    if tx.type in ("transfer_out", "transfer_in"):
        allocations = receipt_allocations(db, receipt) if receipt else []
        pair = find_paired_transfer(db, tx)
        if pair:
            db.delete(pair)
            deleted_ids.append(pair.id)
        if receipt:
            for item in allocations:
                if item["transfer_id"] in deleted_ids:
                    item["transfer_id"] = None
            receipt.allocations_json = json.dumps(allocations)

    db.delete(tx)
    db.commit()
    return {"success": True, "deleted_id": tx_id, "deleted_ids": deleted_ids}

@router.get("/export")
def export_csv(
    month: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)
    if month:
        yr, mo = map(int, month.split("-"))
        start_date = date(yr, mo, 1)
        end_date = date(yr + 1, 1, 1) if mo == 12 else date(yr, mo + 1, 1)
        query = query.filter(Transaction.date >= start_date, Transaction.date < end_date)
        filename = f"finance_{month}.csv"
    else:
        filename = "finance_all.csv"

    rows = query.order_by(desc(Transaction.date), desc(Transaction.id)).all()

    def _sanitize(val):
        if val is None:
            return ""
        s = str(val)
        if s and s[0] in ("=", "+", "-", "@", "\t"):
            return f"'{s}"
        return s

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Tanggal", "Tipe", "Kategori", "Rekening", "Nominal", "Keterangan", "Waktu"])
    for r in rows:
        writer.writerow([
            r.id,
            r.date,
            r.type,
            _sanitize(r.category),
            _sanitize(r.account),
            r.amount,
            _sanitize(r.description),
            r.created_at
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
