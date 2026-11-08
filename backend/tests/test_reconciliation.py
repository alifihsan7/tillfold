from datetime import date
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, get_strict_current_user
from app.api.v1.endpoints import accounts, analytics, transactions, backup, goals, categories
from app.bot.bot import get_acc_balance, handle_batal
from app.db.session import Base, get_db
from app.models.account import Account
from app.models.goal import Goal
from app.models.transaction import Transaction
from app.models.user import User


@pytest.fixture
def reconcile():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(id=1, username="reconcile", full_name="Test", hashed_password="unused", is_active=True)
        db.add_all([user, User(id=2, username="other", full_name="Other", hashed_password="unused", is_active=True)])
        db.flush()
        db.add_all([Account(id=1, user_id=1, name="Bank", type="operasional", initial_balance=0),
                    Account(id=2, user_id=2, name="Other", type="operasional", initial_balance=0)])
        db.add_all([Transaction(user_id=1, type=kind, amount=amount, account="Bank", category="Test",
                               description="Data uji", date=date.today())
                    for kind, amount in [("income", 1_000_000), ("expense", 100_000)]])
        db.add(Goal(user_id=1, name="Target", target_amount=5_000_000, linked_account="Bank"))
        db.commit()
        app = FastAPI()
        for path, router in [("accounts", accounts.router), ("analytics", analytics.router),
                             ("transactions", transactions.router), ("backup", backup.router), ("goals", goals.router)]:
            app.include_router(router, prefix="/" + path)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_strict_current_user] = lambda: user
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, db, user
    engine.dispose()


def payload(client, actual):
    snapshot = client.get("/accounts/1/reconciliation").json()
    return {"request_key": str(uuid4()), "actual_balance": actual,
            "expected_balance": snapshot["balance"], "latest_transaction_id": snapshot["latest_transaction_id"],
            "note": "Cocokkan dengan saldo bank"}


@pytest.mark.parametrize("actual", [1_200_000, 800_000, 0, -100_000])
def test_adjustments_change_balances_without_changing_reports(reconcile, actual):
    client, db, user = reconcile
    request = payload(client, actual)
    response = client.post("/accounts/1/reconciliation", json=request)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["difference"] == actual - 900_000
    assert client.post("/accounts/1/reconciliation", json=request).json() == data
    assert db.query(Transaction).count() == 3
    assert client.get("/accounts/1/reconciliation").json()["balance"] == actual
    assert client.get("/accounts").json()[0]["current_balance"] == actual
    assert get_acc_balance("Bank", db, user_id=1) == actual
    assert goals.get_account_balance("Bank", 1, db) == actual
    report = client.get("/analytics/summary", params={
        "period_type": "custom", "start": date.today().isoformat(), "end": date.today().isoformat(),
    }).json()
    assert (report["income"], report["expense"], report["total_balance"]) == (1_000_000, 100_000, actual)
    assert report["daily_trend"][0]["income"] == 1_000_000
    assert "Penyesuaian saldo" not in [item["category"] for item in report["categories"]]
    rows = client.get("/transactions").json()
    assert rows[0]["type"] == ("adjustment_in" if actual > 900_000 else "adjustment_out")
    assert client.put(f"/transactions/{data['transaction_id']}", json={"amount": 1}).status_code == 409
    assert client.delete(f"/transactions/{data['transaction_id']}").status_code == 409
    exported = client.get("/backup/export")
    assert exported.status_code == 200
    assert exported.json()["version"] == 3
    assert client.post("/backup/preview", json=exported.json()).json()["total_balance"] == actual
    categories.sync_transaction_categories(db, 1)
    from app.models.category import Category
    assert db.query(Category).filter_by(user_id=1, name="Penyesuaian saldo").count() == 0


def test_same_balance_does_not_create_a_transaction(reconcile):
    client, db, user = reconcile
    result = client.post("/accounts/1/reconciliation", json=payload(client, 900_000))
    assert result.json() == {"transaction_id": None, "difference": 0}
    assert db.query(Transaction).count() == 2


def test_stale_snapshot_is_rejected_until_reviewed_again(reconcile):
    client, db, user = reconcile
    stale = payload(client, 1_000_000)
    db.add(Transaction(user_id=1, type="expense", amount=50_000, account="Bank",
                       category="Test", description="Belanja baru", date=date.today()))
    db.commit()
    assert client.post("/accounts/1/reconciliation", json=stale).status_code == 409
    assert db.query(Transaction).count() == 3
    fresh = payload(client, 1_000_000)
    assert client.post("/accounts/1/reconciliation", json=fresh).json()["difference"] == 150_000


def test_foreign_accounts_and_blank_notes_are_rejected(reconcile):
    client, db, user = reconcile
    request = payload(client, 1_000_000)
    assert client.get("/accounts/2/reconciliation").status_code == 404
    assert client.post("/accounts/2/reconciliation", json=request).status_code == 404
    request["note"] = "   "
    assert client.post("/accounts/1/reconciliation", json=request).status_code == 400
    assert db.query(Transaction).count() == 2


def test_telegram_cannot_undo_adjustment(reconcile, monkeypatch):
    client, db, user = reconcile
    assert client.post("/accounts/1/reconciliation", json=payload(client, 1_000_000)).status_code == 200
    messages = []
    monkeypatch.setattr("app.bot.bot.send_message", lambda chat_id, text, **kwargs: messages.append(text))
    handle_batal(123, db, user=user)
    assert db.query(Transaction).count() == 3
    assert "rekonsiliasi baru" in messages[0]


def test_adjustments_cannot_be_created_through_regular_transaction_form(reconcile):
    client, db, user = reconcile
    result = client.post("/transactions", json={
        "type": "adjustment_in", "amount": 50_000, "account": "Bank",
        "category": "Penyesuaian saldo", "description": "Bypass", "date": date.today().isoformat(),
    })
    assert result.status_code == 422
    assert db.query(Transaction).count() == 2
