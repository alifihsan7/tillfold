from calendar import monthrange
from datetime import date

from app.models.subscription import SubscriptionPayment
from app.models.transaction import Transaction


def billing_period(sub, today: date):
    if sub.billing_type == "exact_date":
        return ("once", sub.exact_due_date) if sub.exact_due_date else (None, None)
    if sub.billing_cycle == "yearly":
        anchor = sub.exact_due_date
        if anchor is None:
            return None, None
        year = max(today.year, anchor.year)
        due = date(year, anchor.month, min(anchor.day, monthrange(year, anchor.month)[1]))
        return f"yearly:{year}", due
    due = date(today.year, today.month, min(sub.billing_day or 1, monthrange(today.year, today.month)[1]))
    return f"monthly:{today:%Y-%m}", due


def payment_for_period(db, user_id, subscription_id, period):
    return db.query(SubscriptionPayment).join(
        Transaction, Transaction.id == SubscriptionPayment.transaction_id,
    ).filter(
        SubscriptionPayment.user_id == user_id, SubscriptionPayment.subscription_id == subscription_id,
        SubscriptionPayment.period_key == period, Transaction.user_id == user_id, Transaction.type == "expense",
    ).first()


def payment_status(db, sub, today):
    period, due = billing_period(sub, today)
    payment = payment_for_period(db, sub.user_id, sub.id, period) if period else None
    return {
        "payment_period": period, "payment_due_date": due, "is_paid": payment is not None,
        "paid_date": payment.paid_date if payment else None,
        "payment_transaction_id": payment.transaction_id if payment else None,
        "paid_amount": payment.amount if payment else None,
    }


def payment_pocket_slugs(db, user_id, pockets):
    by_subscription = {p.subscription_id: p.slug for p in pockets if p.subscription_id}
    if not by_subscription:
        return {}
    payments = db.query(SubscriptionPayment.transaction_id, SubscriptionPayment.subscription_id).filter(
        SubscriptionPayment.user_id == user_id, SubscriptionPayment.subscription_id.in_(by_subscription),
    ).all()
    return {row.transaction_id: by_subscription[row.subscription_id] for row in payments}
