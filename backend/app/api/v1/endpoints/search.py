import re
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.ledger import signed_amount
from app.db.session import get_db
from app.models.account import Account
from app.models.goal import Goal
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.subscription import SubscriptionResponse
from app.schemas.transaction import TransactionOut
from app.api.v1.endpoints.goals import compute_goal_metrics

router = APIRouter()


def literal_pattern(value):
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@router.get("")
def global_search(q: str = Query(..., min_length=2, max_length=120),
                  limit: int = Query(5, ge=1, le=10),
                  current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = q.strip()
    if len(query) < 2:
        return {"query": query, "groups": []}
    pattern = literal_pattern(query)
    groups = []

    def matches(model, fields, *extra):
        return db.query(model).filter(model.user_id == current_user.id, or_(
            *(field.ilike(pattern, escape="\\") for field in fields), *extra,
        ))

    def add(kind, label, records, serialize):
        if records:
            groups.append({"kind": kind, "label": label, "has_more": len(records) > limit,
                           "items": [serialize(record) for record in records[:limit]]})

    extra = []
    number = re.sub(r"^rp\s*", "", query, flags=re.IGNORECASE)
    if re.fullmatch(r"\d+(?:[.,]\d{3})*", number):
        amount = int(re.sub(r"[.,]", "", number))
        if amount <= 9_000_000_000_000_000:
            extra.append(Transaction.amount == amount)
    try:
        extra.append(Transaction.date == date.fromisoformat(query))
    except ValueError:
        pass
    transactions = matches(Transaction, [Transaction.description, Transaction.category, Transaction.account], *extra).order_by(
        Transaction.date.desc(), Transaction.id.desc()).limit(limit + 1).all()
    add("transaction", "Transaksi", transactions, lambda tx: {
        "kind": "transaction", "id": tx.id, "title": tx.description or tx.category,
        "subtitle": f"{tx.date} · {tx.account} · {tx.category}", "amount": tx.amount,
        "data": TransactionOut.model_validate(tx),
    })

    accounts = matches(Account, [Account.name, Account.tag, Account.type]).order_by(Account.is_archived, Account.id).limit(limit + 1).all()
    balances = dict(db.query(Transaction.account, func.coalesce(func.sum(signed_amount()), 0)).filter(
        Transaction.user_id == current_user.id, Transaction.account.in_([row.name for row in accounts[:limit]]),
    ).group_by(Transaction.account)) if accounts else {}
    add("account", "Rekening", accounts, lambda account: {
        "kind": "account", "id": account.id, "title": account.name,
        "subtitle": f"{account.type} · {'Arsip' if account.is_archived else 'Aktif'}", "amount": int(balances.get(account.name, 0)),
        "data": {"id": account.id, "name": account.name, "type": account.type, "tag": account.tag,
                 "color": account.color, "is_archived": account.is_archived, "current_balance": int(balances.get(account.name, 0))},
    })
    bills = matches(Subscription, [Subscription.name, Subscription.account, Subscription.category, Subscription.notes]).order_by(
        Subscription.is_active.desc(), Subscription.id.desc()).limit(limit + 1).all()
    add("bill", "Tagihan", bills, lambda bill: {
        "kind": "bill", "id": bill.id, "title": bill.name,
        "subtitle": f"{bill.account} · {'Aktif' if bill.is_active else 'Nonaktif'}", "amount": bill.amount,
        "data": SubscriptionResponse.model_validate(bill),
    })
    goals = matches(Goal, [Goal.name, Goal.category, Goal.linked_account, Goal.notes]).order_by(
        Goal.is_active.desc(), Goal.id.desc()).limit(limit + 1).all()
    add("goal", "Target tabungan", goals, lambda goal: {
        "kind": "goal", "id": goal.id, "title": goal.name,
        "subtitle": f"{goal.category} · {'Aktif' if goal.is_active else 'Nonaktif'}", "amount": goal.target_amount,
        "data": compute_goal_metrics(goal, current_user.id, db),
    })
    return {"query": query, "groups": groups}
