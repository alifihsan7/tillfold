from datetime import date, datetime, timedelta
from typing import List, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import case, func

from app.models.account import Account
from app.models.jago_pocket import JagoPocket
from app.models.transaction import Transaction
from app.models.paycheck import PaycheckConfig, PaycheckBucket, PaycheckReceipt
from app.schemas.transaction import CycleBurnDay, SafeToSpendInfo

SUPPORTED_ACCOUNT_TYPES: Set[str] = {
    "operasional",
    "tagihan",
    "gajian",
    "tabungan",
    "investasi",
    "darurat",
    "ewallet",
}

PROTECTED_ACCOUNT_TYPES: Set[str] = {
    "tagihan",
    "tabungan",
    "investasi",
    "darurat",
}

SPENDING_ACCOUNT_TYPES: Set[str] = {
    "operasional",
    "ewallet",
}


def is_account_protected(acc_type: Optional[str]) -> bool:
    """Check if account type is protected from general operational safe-to-spend deductions."""
    if not acc_type:
        return False
    return acc_type.strip().lower() in PROTECTED_ACCOUNT_TYPES


def resolve_pocket_account(
    db: Session,
    user_id: int,
    user_accs: Optional[List[Account]] = None,
    cfg: Optional[PaycheckConfig] = None
) -> str:
    """
    Deterministically resolves the active operational pocket account for safe-to-spend.
    Protected accounts (tagihan, tabungan, investasi, darurat) and income hubs (gajian)
    are protected from accidental selection as the default operational pocket.
    """
    accounts_list: List[Account] = user_accs if user_accs is not None else db.query(Account).filter(Account.user_id == user_id).all()
    accounts_list = [account for account in accounts_list if not account.is_archived]
    user_acc_names = [a.name for a in accounts_list]

    if cfg is None:
        cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == user_id).first()

    if cfg and cfg.pocket_account and cfg.pocket_account in user_acc_names:
        return cfg.pocket_account

    # 1. Prefer accounts explicitly designated as 'operasional'
    op_acc = next((a for a in accounts_list if (a.type or "").strip().lower() == "operasional"), None)
    if op_acc:
        return op_acc.name

    # 2. Prefer ewallet accounts
    ewallet_acc = next((a for a in accounts_list if (a.type or "").strip().lower() == "ewallet"), None)
    if ewallet_acc:
        return ewallet_acc.name

    # 3. Prefer non-protected, non-gajian accounts
    non_protected = next(
        (a for a in accounts_list if (a.type or "").strip().lower() not in PROTECTED_ACCOUNT_TYPES and (a.type or "").strip().lower() != "gajian"),
        None
    )
    if non_protected:
        return non_protected.name

    # 4. Fallback to first user account or default label
    if accounts_list:
        return accounts_list[0].name
    return "Rekening Utama"


def compute_safe_to_spend_metrics(
    db: Session,
    user_id: int,
    start_date: date,
    end_date: date,
    period_type: str,
    today_wib: date,
    user_accs: Optional[List[Account]] = None,
    cfg: Optional[PaycheckConfig] = None,
) -> SafeToSpendInfo:
    """
    Calculates deterministic Safe-to-Spend metrics and daily burn pace for a user.
    Guarantees that protected accounts (tagihan, tabungan, investasi, darurat) do NOT
    deplete the operational pocket budget unless explicitly designated or targeted.
    """
    accounts_list: List[Account] = user_accs if user_accs is not None else db.query(Account).filter(Account.user_id == user_id).all()
    if cfg is None:
        cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == user_id).first()

    cycle_start = start_date
    cycle_end = end_date
    total_days = max(1, (cycle_end - cycle_start).days + 1)

    if today_wib < cycle_start:
        day_of_cycle = 1
        days_remaining = total_days
    elif today_wib > cycle_end:
        day_of_cycle = total_days
        days_remaining = 0
    else:
        day_of_cycle = (today_wib - cycle_start).days + 1
        days_remaining = max(1, total_days - day_of_cycle + 1)

    cycle_days = cfg.cycle_days if cfg and cfg.cycle_days > 0 else 30
    cycle_type = cfg.cycle_type if cfg and cfg.cycle_type else "monthly_date"

    pocket_account = resolve_pocket_account(db, user_id, user_accs=accounts_list, cfg=cfg)

    pocket_income, pocket_entries = db.query(
        func.coalesce(func.sum(case(
            (Transaction.type == "transfer_out", -Transaction.amount),
            else_=Transaction.amount,
        )), 0),
        func.count(Transaction.id),
    ).filter(
        Transaction.user_id == user_id,
        Transaction.account == pocket_account,
        (Transaction.type == "income") | (
            Transaction.type.in_(["transfer_in", "transfer_out"])
            & Transaction.raw_text.contains("[paycheck_receipt:")
        ),
        Transaction.date >= cycle_start,
        Transaction.date <= cycle_end
    ).one()

    base_pocket_budget = max(0, int(pocket_income))
    if pocket_entries == 0 and cfg:
        p_bucket = db.query(PaycheckBucket).filter(
            PaycheckBucket.config_id == cfg.id,
            PaycheckBucket.account == pocket_account
        ).first()
        pct = (p_bucket.percentage / 100.0) if p_bucket else 0.5
        salary = getattr(cfg, "total_salary", None)
        salary = salary if (salary and salary > 0) else 0
        if salary > 0:
            base_pocket_budget = int(round(salary * pct))
        elif accounts_list:
            all_inc = db.query(
                func.coalesce(func.sum(Transaction.amount), 0)
            ).filter(
                Transaction.user_id == user_id,
                Transaction.type == "income",
                ~db.query(PaycheckReceipt.transaction_id).filter(
                    PaycheckReceipt.transaction_id == Transaction.id,
                ).exists(),
                Transaction.date >= cycle_start,
                Transaction.date <= cycle_end
            ).scalar() or 0
            if all_inc > 0:
                base_pocket_budget = int(round(all_inc * pct))

    pocket_budget = base_pocket_budget if period_type == "cycle" else int(base_pocket_budget / cycle_days * total_days)

    # Safe-to-Spend pocket role filtering:
    # Resolve pockets configured on pocket_account
    pocket_acc_obj = next((a for a in accounts_list if a.name.lower() == pocket_account.lower()), None)
    account_pockets = []
    if pocket_acc_obj:
        account_pockets = db.query(JagoPocket).filter(
            JagoPocket.user_id == user_id,
            JagoPocket.account_id == pocket_acc_obj.id,
            JagoPocket.is_active == True,
        ).all()
    if not account_pockets and any(k in pocket_account.lower() for k in ["jago", "pocket"]):
        account_pockets = db.query(JagoPocket).filter(
            JagoPocket.user_id == user_id,
            JagoPocket.account_id == None,
            JagoPocket.is_active == True,
        ).all()

    expenses_on_pocket_acc = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.account == pocket_account,
        Transaction.type == "expense",
        Transaction.date >= cycle_start,
        Transaction.date <= cycle_end
    ).all()

    has_non_operasional_pockets = any(p.role != "operasional" for p in account_pockets)
    if has_non_operasional_pockets and account_pockets:
        from app.api.v1.endpoints.jago_pockets import classify_pocket_transaction_for_account
        from app.services.subscription_payments import payment_pocket_slugs
        pocket_by_slug = {p.slug: p for p in account_pockets}
        payment_pockets = payment_pocket_slugs(db, user_id, account_pockets)

        pocket_spent = 0
        spent_by_date: dict[str, int] = {}
        for tx in expenses_on_pocket_acc:
            matched_slug = classify_pocket_transaction_for_account(tx, account_pockets, payment_pockets)
            matched_p = pocket_by_slug.get(matched_slug)
            p_role = matched_p.role if matched_p else "operasional"
            if p_role == "operasional":
                pocket_spent += int(tx.amount)
                d_str = str(tx.date)
                spent_by_date[d_str] = spent_by_date.get(d_str, 0) + int(tx.amount)
    else:
        pocket_spent = sum(int(tx.amount) for tx in expenses_on_pocket_acc)
        spent_by_date = {}
        for tx in expenses_on_pocket_acc:
            d_str = str(tx.date)
            spent_by_date[d_str] = spent_by_date.get(d_str, 0) + int(tx.amount)

    pocket_remaining = max(0, pocket_budget - pocket_spent)

    if days_remaining > 0:
        safe_daily = int(pocket_remaining / days_remaining)
    elif pocket_remaining > 0:
        overdue_days = max(1, (today_wib - cycle_end).days)
        grace_divisor = max(1, 3 - overdue_days + 1)
        safe_daily = int(pocket_remaining / grace_divisor)
    else:
        safe_daily = 0

    ideal_daily_rate = pocket_budget / total_days
    ideal_pace_today = int(round(ideal_daily_rate * day_of_cycle / 100) * 100)

    if pocket_spent < ideal_pace_today * 0.9:
        pace_status = "ahead"
    elif pocket_spent <= ideal_pace_today * 1.1:
        pace_status = "on_track"
    else:
        pace_status = "warning"

    burn_chart: List[CycleBurnDay] = []
    cumulative = 0
    for d in range(1, total_days + 1):
        day_date = cycle_start + timedelta(days=d-1)
        day_str = str(day_date)
        day_spent = spent_by_date.get(day_str, 0)
        day_ideal = int(round(ideal_daily_rate * d / 100) * 100)

        if day_date <= today_wib:
            cumulative += day_spent
            burn_chart.append(CycleBurnDay(
                day=d,
                date=day_str,
                spent=day_spent,
                cumulative_spent=cumulative,
                ideal_pace=day_ideal
            ))
        else:
            burn_chart.append(CycleBurnDay(
                day=d,
                date=day_str,
                spent=0,
                cumulative_spent=cumulative,
                ideal_pace=day_ideal
            ))

    return SafeToSpendInfo(
        cycle_start=cycle_start,
        cycle_end=cycle_end,
        cycle_type=cycle_type,
        cycle_days=total_days if period_type == "cycle" else cycle_days,
        pocket_account=pocket_account,
        day_of_cycle=day_of_cycle,
        days_remaining=days_remaining,
        pocket_budget=pocket_budget,
        pocket_spent=pocket_spent,
        pocket_remaining=pocket_remaining,
        safe_daily=safe_daily,
        pace_status=pace_status,
        ideal_pace_today=ideal_pace_today,
        burn_chart=burn_chart
    )
