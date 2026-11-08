from typing import List, Optional
from datetime import datetime, date, timedelta
from calendar import monthrange
import zoneinfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.models.account import Account
from app.models.subscription import Subscription, SubscriptionPayment
from app.models.transaction import Transaction
from app.services.subscription_payments import billing_period, payment_for_period, payment_status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from app.models.jago_pocket import JagoPocket
from app.models.user import User
from app.api.deps import get_current_user
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    SubscriptionsSummary,
)
from app.core.config import settings

router = APIRouter()
WIB = zoneinfo.ZoneInfo(settings.TIMEZONE)


class RecordBillPayment(BaseModel):
    period: str
    expected_amount: int = Field(gt=0, le=9_000_000_000_000_000)
    expected_account: str
    paid_date: Optional[date] = None
    existing_transaction_id: Optional[int] = Field(default=None, gt=0)


def payment_result(payment):
    return {"transaction_id": payment.transaction_id, "paid_date": payment.paid_date,
            "amount": payment.amount, "account": payment.account, "period": payment.period_key}


@router.get("/{sub_id}/payment")
def preview_payment(sub_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter(Subscription.id == sub_id, Subscription.user_id == current_user.id).first()
    if sub is None:
        raise HTTPException(404, "Tagihan tidak ditemukan.")
    today = datetime.now(WIB).date()
    candidates = db.query(Transaction).filter(
        Transaction.user_id == current_user.id, Transaction.type == "expense",
        Transaction.amount == sub.amount, Transaction.account == sub.account, Transaction.date <= today,
        ~Transaction.id.in_(db.query(SubscriptionPayment.transaction_id)),
    ).order_by(Transaction.date.desc(), Transaction.id.desc()).limit(20).all()
    return {"name": sub.name, "amount": sub.amount, "account": sub.account, "is_active": sub.is_active,
            **payment_status(db, sub, today),
            "candidates": [{"id": tx.id, "date": tx.date, "description": tx.description} for tx in candidates]}


@router.post("/{sub_id}/payment")
def record_payment(sub_id: int, payload: RecordBillPayment,
                   current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter(
        Subscription.id == sub_id, Subscription.user_id == current_user.id,
    ).with_for_update().first()
    if sub is None:
        raise HTTPException(404, "Tagihan tidak ditemukan.")
    today = datetime.now(WIB).date()
    period, due = billing_period(sub, today)
    if period is None or period != payload.period:
        raise HTTPException(409, "Periode tagihan berubah atau tanggalnya belum lengkap. Muat ulang tagihan.")
    existing = payment_for_period(db, current_user.id, sub.id, period)
    if existing:
        return payment_result(existing)
    if not sub.is_active:
        raise HTTPException(409, "Aktifkan tagihan sebelum mencatat pembayaran.")
    if sub.amount != payload.expected_amount or sub.account != payload.expected_account:
        raise HTTPException(409, "Nominal atau rekening tagihan berubah. Muat ulang sebelum melanjutkan.")
    if not db.query(Account.id).filter(Account.user_id == current_user.id, Account.name == sub.account, Account.is_archived == False).with_for_update().first():
        raise HTTPException(409, "Rekening pembayaran tidak tersedia. Ubah rekening tagihan terlebih dahulu.")
    if payload.existing_transaction_id is not None:
        tx = db.query(Transaction).filter(
            Transaction.id == payload.existing_transaction_id, Transaction.user_id == current_user.id,
        ).with_for_update().first()
        if tx is None or tx.type != "expense" or tx.amount != sub.amount or tx.account != sub.account or tx.date > today:
            raise HTTPException(409, "Transaksi tidak sesuai dengan rekening dan nominal tagihan.")
        if db.query(SubscriptionPayment.id).filter(SubscriptionPayment.transaction_id == tx.id).first():
            raise HTTPException(409, "Transaksi ini sudah dipakai untuk pembayaran tagihan.")
    else:
        paid_date = payload.paid_date or today
        if paid_date > today:
            raise HTTPException(400, "Tanggal pembayaran belum terjadi.")
        tx = Transaction(user_id=current_user.id, type="expense", amount=sub.amount,
                         account=sub.account, category=sub.category, description=f"Pembayaran {sub.name}",
                         date=paid_date, raw_text=f"bill-payment:{sub.id}:{period}")
        db.add(tx)
        db.flush()
    payment = SubscriptionPayment(user_id=current_user.id, subscription_id=sub.id, transaction_id=tx.id,
                                  subscription_name=sub.name, period_key=period, due_date=due,
                                  paid_date=tx.date, amount=tx.amount, account=tx.account)
    db.add(payment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Pembayaran sudah dicatat atau transaksi sudah digunakan. Muat ulang tagihan.")
    return payment_result(payment)

def compute_due_info(sub_or_day, now_date: date, billing_type: str = "fixed_day", exact_due_date: Optional[date] = None):
    if isinstance(sub_or_day, Subscription):
        b_type = sub_or_day.billing_type or "fixed_day"
        e_date = sub_or_day.exact_due_date
        b_day = sub_or_day.billing_day or 1
    else:
        b_type = billing_type
        e_date = exact_due_date
        b_day = sub_or_day or 1

    if b_type == "exact_date" and e_date:
        days_until = (e_date - now_date).days
        return days_until, str(e_date)

    if isinstance(sub_or_day, Subscription) and sub_or_day.billing_cycle == "yearly":
        if not e_date:
            return None, None
        year = max(e_date.year, now_date.year)
        due = date(year, e_date.month, min(e_date.day, monthrange(year, e_date.month)[1]))
        if due < now_date:
            year += 1
            due = date(year, e_date.month, min(e_date.day, monthrange(year, e_date.month)[1]))
        return (due - now_date).days, str(due)

    # Determine next billing date for fixed_day
    year = now_date.year
    month = now_date.month

    # If billing day is today or earlier this month, next billing date is next month
    try:
        cur_month_due = date(year, month, b_day)
    except ValueError:
        import calendar
        _, last_day = calendar.monthrange(year, month)
        cur_month_due = date(year, month, last_day)

    if cur_month_due >= now_date:
        next_due = cur_month_due
    else:
        if month == 12:
            next_year = year + 1
            next_month = 1
        else:
            next_year = year
            next_month = month + 1
        try:
            next_due = date(next_year, next_month, b_day)
        except ValueError:
            import calendar
            _, last_day = calendar.monthrange(next_year, next_month)
            next_due = date(next_year, next_month, last_day)

    days_until = (next_due - now_date).days
    return days_until, str(next_due)

def monthly_commitment_twelfths(subscription: Subscription) -> int:
    return subscription.amount if subscription.billing_cycle == "yearly" else subscription.amount * 12


@router.get("", response_model=SubscriptionsSummary)
def get_subscriptions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    subs = db.query(Subscription).filter(Subscription.user_id == current_user.id).order_by(Subscription.is_active.desc(), Subscription.id.asc()).all()
    now_date = datetime.now(WIB).date()

    items = []
    monthly_twelfths = 0
    active_cnt = 0
    upcoming_week = 0

    for s in subs:
        days_until, next_date = compute_due_info(s, now_date)
        paid_status = payment_status(db, s, now_date)
        completed_once = s.billing_type == "exact_date" and paid_status["is_paid"]
        if completed_once:
            days_until, next_date = None, None
        elif paid_status["is_paid"] and next_date == str(paid_status["payment_due_date"]):
            days_until, next_date = compute_due_info(s, paid_status["payment_due_date"] + timedelta(days=1))
            if next_date:
                days_until = (date.fromisoformat(next_date) - now_date).days
        if s.is_active and not completed_once:
            monthly_twelfths += monthly_commitment_twelfths(s)
            active_cnt += 1
            if days_until is not None and 0 <= days_until <= 7:
                upcoming_week += 1

        items.append(SubscriptionResponse(
            id=s.id,
            name=s.name,
            amount=s.amount,
            category=s.category,
            account=s.account,
            billing_cycle=s.billing_cycle,
            billing_day=s.billing_day,
            billing_type=s.billing_type or "fixed_day",
            exact_due_date=s.exact_due_date,
            is_active=s.is_active,
            notes=s.notes,
            created_at=s.created_at,
            days_until_due=days_until,
            next_billing_date=next_date,
            **paid_status,
        ))

    # Sort items: active first, then soonest days_until_due
    items.sort(key=lambda x: (not x.is_active, x.days_until_due is None, x.days_until_due or 0))

    return SubscriptionsSummary(
        total_monthly_commitment=(monthly_twelfths + 6) // 12,
        active_count=active_cnt,
        upcoming_this_week=upcoming_week,
        items=items
    )

@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def create_subscription(
    sub_in: SubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    account_name = sub_in.account.strip()
    if not account_name:
        account = db.query(Account).filter(Account.user_id == current_user.id, Account.is_archived == False).order_by(Account.id).first()
        if account is None:
            raise HTTPException(status_code=400, detail="Tambahkan rekening terlebih dahulu.")
        account_name = account.name

    from app.api.v1.endpoints.transactions import require_owned_accounts
    require_owned_accounts(db, current_user.id, account_name)

    sub = Subscription(
        user_id=current_user.id,
        name=sub_in.name.strip(),
        amount=sub_in.amount,
        category=sub_in.category.strip(),
        account=account_name,
        billing_cycle=sub_in.billing_cycle,
        billing_day=sub_in.billing_day or 1,
        billing_type=sub_in.billing_type or "fixed_day",
        exact_due_date=sub_in.exact_due_date,
        is_active=sub_in.is_active,
        notes=sub_in.notes.strip() if sub_in.notes else None
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    now_date = datetime.now(WIB).date()
    days_until, next_date = compute_due_info(sub, now_date)

    return SubscriptionResponse(
        id=sub.id,
        name=sub.name,
        amount=sub.amount,
        category=sub.category,
        account=sub.account,
        billing_cycle=sub.billing_cycle,
        billing_day=sub.billing_day,
        billing_type=sub.billing_type or "fixed_day",
        exact_due_date=sub.exact_due_date,
        is_active=sub.is_active,
        notes=sub.notes,
        created_at=sub.created_at,
        days_until_due=days_until,
        next_billing_date=next_date,
        **payment_status(db, sub, now_date),
    )

@router.put("/{sub_id}", response_model=SubscriptionResponse)
def update_subscription(
    sub_id: int,
    sub_in: SubscriptionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sub = db.query(Subscription).filter(Subscription.id == sub_id, Subscription.user_id == current_user.id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Langganan tidak ditemukan")

    update_data = sub_in.model_dump(exclude_unset=True)
    if update_data.get("account") and update_data["account"] != sub.account:
        from app.api.v1.endpoints.transactions import require_owned_accounts
        require_owned_accounts(db, current_user.id, update_data["account"])
    if "account" in update_data and (not update_data["account"] or not update_data["account"].strip()):
        raise HTTPException(status_code=400, detail="Rekening tagihan tidak boleh kosong")
    if "account" in update_data and update_data["account"].strip().casefold() != sub.account.strip().casefold():
        if db.query(JagoPocket.id).filter(JagoPocket.subscription_id == sub.id).first():
            raise HTTPException(status_code=409, detail="Lepaskan hubungan kantong sebelum memindahkan rekening tagihan")
    for field, value in update_data.items():
        setattr(sub, field, value)
    for pocket in db.query(JagoPocket).filter(JagoPocket.user_id == current_user.id, JagoPocket.subscription_id == sub.id).all():
        pocket.target_amount = int(sub.amount) if sub.is_active else 0

    db.commit()
    db.refresh(sub)

    now_date = datetime.now(WIB).date()
    days_until, next_date = compute_due_info(sub, now_date)

    return SubscriptionResponse(
        id=sub.id,
        name=sub.name,
        amount=sub.amount,
        category=sub.category,
        account=sub.account,
        billing_cycle=sub.billing_cycle,
        billing_day=sub.billing_day,
        billing_type=sub.billing_type or "fixed_day",
        exact_due_date=sub.exact_due_date,
        is_active=sub.is_active,
        notes=sub.notes,
        created_at=sub.created_at,
        days_until_due=days_until,
        next_billing_date=next_date,
        **payment_status(db, sub, now_date),
    )

@router.delete("/{sub_id}")
def delete_subscription(
    sub_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sub = db.query(Subscription).filter(Subscription.id == sub_id, Subscription.user_id == current_user.id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Langganan tidak ditemukan")

    if db.query(JagoPocket.id).filter(JagoPocket.subscription_id == sub.id).first():
        raise HTTPException(status_code=409, detail="Lepaskan hubungan kantong sebelum menghapus tagihan")
    db.query(SubscriptionPayment).filter(
        SubscriptionPayment.user_id == current_user.id, SubscriptionPayment.subscription_id == sub.id,
    ).update({"subscription_id": None}, synchronize_session=False)
    db.delete(sub)
    db.commit()
    return {"status": "success", "message": f"Langganan '{sub.name}' berhasil dihapus"}
