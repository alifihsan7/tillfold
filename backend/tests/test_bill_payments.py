import json
from datetime import date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, get_strict_current_user
from app.api.v1.endpoints import subscriptions, transactions, accounts, analytics, backup, auth
from app.bot.bot import handle_batal, handle_subs
from app.db.session import Base, get_db
from app.models.account import Account
from app.models.subscription import Subscription, SubscriptionPayment
from app.models.transaction import Transaction
from app.models.jago_pocket import JagoPocket
from app.models.user import User


@pytest.fixture
def bills(monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 7, 12, tzinfo=tz)
    monkeypatch.setattr(subscriptions, "datetime", FixedDatetime)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        users = [User(id=i, username=name, full_name=name, hashed_password="unused", is_active=True)
                 for i, name in [(1, "owner"), (2, "other"), (3, "restore")]]
        db.add_all(users)
        db.flush()
        db.add_all([Account(id=1, user_id=1, name="Bank", type="operasional", initial_balance=0),
                    Account(id=2, user_id=2, name="Peer", type="operasional", initial_balance=0)])
        db.add(Transaction(user_id=1, type="income", amount=1_000_000, account="Bank",
                           category="Gaji", description="Data uji", date=date(2026, 11, 1)))
        db.add_all([Subscription(id=i, user_id=uid, name=name, amount=50_000, category="Tagihan",
                                account=account, billing_day=10)
                    for i, uid, name, account in [(1, 1, "Internet", "Bank"), (2, 1, "Telepon", "Bank"), (3, 2, "Peer bill", "Peer")]])
        db.commit()
        app = FastAPI()
        for path, router in [("subscriptions", subscriptions.router), ("transactions", transactions.router),
                             ("accounts", accounts.router), ("analytics", analytics.router), ("backup", backup.router),
                             ("auth", auth.router)]:
            app.include_router(router, prefix="/" + path)
        current = [users[0]]
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: current[0]
        app.dependency_overrides[get_strict_current_user] = lambda: current[0]
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, db, users, current
    engine.dispose()


def request(client, sub_id=1, **changes):
    preview = client.get(f"/subscriptions/{sub_id}/payment").json()
    return {"period": preview["payment_period"], "expected_amount": preview["amount"],
            "expected_account": preview["account"], "paid_date": "2026-11-07", **changes}


def status(client, sub_id=1):
    return next(row for row in client.get("/subscriptions").json()["items"] if row["id"] == sub_id)


def test_payment_is_an_expense_once_per_billing_period(bills):
    client, db, users, current = bills
    payload = request(client)
    assert status(client)["is_paid"] is False
    first = client.post("/subscriptions/1/payment", json=payload)
    assert first.status_code == 200, first.text
    assert client.post("/subscriptions/1/payment", json=payload).json() == first.json()
    assert db.query(Transaction).filter_by(user_id=1, type="expense").count() == 1
    assert client.get("/accounts").json()[0]["current_balance"] == 950_000
    row = status(client)
    assert row["is_paid"] is True
    assert row["paid_date"] == "2026-11-07"
    assert row["paid_amount"] == 50_000
    assert row["next_billing_date"] == "2026-12-10"
    report = client.get("/analytics/summary", params={"period_type": "custom", "start": "2026-11-01", "end": "2026-11-30"}).json()
    assert (report["income"], report["expense"]) == (1_000_000, 50_000)
    edited = client.put("/subscriptions/1", json={"billing_day": 15, "amount": 70_000})
    assert edited.status_code == 200
    assert edited.json()["is_paid"] is True
    assert status(client)["paid_amount"] == 50_000
    assert client.post("/subscriptions/1/payment", json=request(client)).json()["transaction_id"] == first.json()["transaction_id"]


def test_existing_expense_can_be_linked_without_charging_balance_twice(bills):
    client, db, users, current = bills
    tx = Transaction(user_id=1, type="expense", amount=50_000, account="Bank",
                     category="Lainnya", description="Internet sudah dicatat", date=date(2026, 11, 5))
    db.add(tx)
    db.commit()
    tx_id = tx.id
    candidates = client.get("/subscriptions/1/payment").json()["candidates"]
    assert candidates[0]["id"] == tx_id
    result = client.post("/subscriptions/1/payment", json=request(client, existing_transaction_id=tx_id))
    assert result.status_code == 200, result.text
    assert result.json()["paid_date"] == "2026-11-05"
    assert client.get("/accounts").json()[0]["current_balance"] == 950_000
    assert db.query(Transaction).filter_by(type="expense").count() == 1
    assert client.post("/subscriptions/2/payment", json=request(client, 2, existing_transaction_id=tx_id)).status_code == 409


def test_deleting_payment_expense_reopens_bill_and_edit_is_guarded(bills):
    client, db, users, current = bills
    tx_id = client.post("/subscriptions/1/payment", json=request(client)).json()["transaction_id"]
    assert client.put(f"/transactions/{tx_id}", json={"amount": 1}).status_code == 409
    assert client.put(f"/transactions/{tx_id}", json={"date": "2026-11-06"}).status_code == 409
    assert client.put(f"/transactions/{tx_id}", json={"description": "Catatan pembayaran"}).status_code == 200
    assert client.delete(f"/transactions/{tx_id}").status_code == 200
    assert status(client)["is_paid"] is False
    assert client.get("/accounts").json()[0]["current_balance"] == 1_000_000
    assert client.post("/subscriptions/1/payment", json=request(client)).status_code == 200
    assert db.query(SubscriptionPayment).count() == 1


def test_telegram_undo_reopens_bill_and_subs_shows_paid_status(bills, monkeypatch):
    client, db, users, current = bills
    client.post("/subscriptions/1/payment", json=request(client))
    messages = []
    monkeypatch.setattr("app.bot.bot.send_message", lambda chat_id, text, **kwargs: messages.append(text))
    handle_subs(123, db, user=users[0])
    assert "Lunas periode ini" in messages[-1]
    handle_batal(123, db, user=users[0])
    assert status(client)["is_paid"] is False
    assert db.query(SubscriptionPayment).count() == 0


def test_foreign_transaction_and_subscription_and_stale_form_are_rejected(bills):
    client, db, users, current = bills
    assert client.get("/subscriptions/3/payment").status_code == 404
    assert client.post("/subscriptions/3/payment", json=request(client)).status_code == 404
    foreign = Transaction(user_id=2, type="expense", amount=50_000, account="Bank", category="Tagihan",
                          description="Peer data", date=date(2026, 11, 1))
    db.add(foreign)
    db.commit()
    assert client.post("/subscriptions/1/payment", json=request(client, existing_transaction_id=foreign.id)).status_code == 409
    assert client.post("/subscriptions/1/payment", json=request(client, expected_amount=49_000)).status_code == 409
    assert client.post("/subscriptions/1/payment", json=request(client, period="monthly:2026-10")).status_code == 409
    assert client.post("/subscriptions/1/payment", json=request(client, paid_date="2026-11-08")).status_code == 400
    client.put("/subscriptions/1", json={"is_active": False})
    assert client.post("/subscriptions/1/payment", json=request(client)).status_code == 409
    assert db.query(SubscriptionPayment).count() == 0


def test_new_month_becomes_unpaid_without_reusing_previous_expense(bills, monkeypatch):
    client, db, users, current = bills
    old = client.post("/subscriptions/1/payment", json=request(client)).json()
    class NextMonth(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 12, 7, 12, tzinfo=tz)
    monkeypatch.setattr(subscriptions, "datetime", NextMonth)
    assert status(client)["is_paid"] is False
    assert client.post("/subscriptions/1/payment", json=request(client, existing_transaction_id=old["transaction_id"])).status_code == 409
    assert client.post("/subscriptions/1/payment", json=request(client, paid_date="2026-12-07")).status_code == 200
    assert db.query(SubscriptionPayment).count() == 2


def test_yearly_and_one_time_bills_use_separate_period_keys(bills):
    client, db, users, current = bills
    client.put("/subscriptions/1", json={"billing_cycle": "yearly", "exact_due_date": "2024-02-29"})
    preview = client.get("/subscriptions/1/payment").json()
    assert (preview["payment_period"], preview["payment_due_date"]) == ("yearly:2026", "2026-02-28")
    assert client.post("/subscriptions/1/payment", json=request(client)).status_code == 200
    assert status(client)["is_paid"] is True
    client.put("/subscriptions/2", json={"billing_type": "exact_date", "exact_due_date": "2026-11-03"})
    assert client.post("/subscriptions/2/payment", json=request(client, 2)).status_code == 200
    row = status(client, 2)
    assert row["payment_period"] == "once" and row["is_paid"] is True
    assert row["next_billing_date"] is None
    assert client.get("/subscriptions").json()["total_monthly_commitment"] == 4167


def test_payments_survive_backup_restore_and_account_rename(bills):
    client, db, users, current = bills
    client.post("/subscriptions/1/payment", json=request(client))
    assert client.put("/accounts/1", json={"name": "Bank baru"}).status_code == 200
    exported = client.get("/backup/export")
    assert exported.status_code == 200, exported.text
    assert exported.json()["version"] == 4
    current[0] = users[2]
    restored = client.post("/backup/restore", json=exported.json())
    assert restored.status_code == 200, restored.text
    payment = db.query(SubscriptionPayment).filter_by(user_id=3).one()
    assert payment.account == "Bank baru"
    assert db.get(Transaction, payment.transaction_id).user_id == 3
    assert status(client, payment.subscription_id)["is_paid"] is True


def test_deleting_bill_keeps_expense_history_and_valid_backup(bills):
    client, db, users, current = bills
    tx_id = client.post("/subscriptions/1/payment", json=request(client)).json()["transaction_id"]
    assert client.delete("/subscriptions/1").status_code == 200
    payment = db.query(SubscriptionPayment).one()
    assert payment.subscription_id is None
    assert db.get(Transaction, tx_id).amount == 50_000
    assert client.get("/backup/export").status_code == 200


def test_bill_payment_uses_its_linked_pocket_instead_of_first_matching_role(bills):
    client, db, users, current = bills
    db.add_all([
        JagoPocket(user_id=1, account_id=1, name="Tagihan lain", slug="lain", role="tagihan", target_amount=100_000),
        JagoPocket(user_id=1, account_id=1, name="Keperluan rutin", slug="rutin", role="tagihan", target_amount=50_000, subscription_id=1),
        JagoPocket(user_id=1, account_id=1, name="Utama", slug="utama-1", role="operasional", target_amount=0),
    ])
    db.commit()
    assert client.post("/subscriptions/1/payment", json=request(client)).status_code == 200
    response = client.get("/accounts/1/pockets", params={"cycle_start": "2026-11-01", "cycle_end": "2026-11-30"})
    assert response.status_code == 200, response.text
    pockets = {row["slug"]: row for row in response.json()["pockets"]}
    assert pockets["rutin"]["spent_amount"] == 50_000
    assert pockets["lain"]["spent_amount"] == 0
    report = client.get("/analytics/summary", params={"period_type": "custom", "start": "2026-11-01", "end": "2026-11-30"}).json()
    assert report["safe_to_spend"]["pocket_spent"] == 0


def test_commit_failure_rolls_back_new_expense_and_payment_together(bills, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    client, db, users, current = bills
    payload = request(client)
    original_commit = db.commit
    def fail_once():
        monkeypatch.setattr(db, "commit", original_commit)
        raise IntegrityError("injected", {}, Exception("duplicate payment"))
    monkeypatch.setattr(db, "commit", fail_once)
    assert client.post("/subscriptions/1/payment", json=payload).status_code == 409
    assert db.query(SubscriptionPayment).count() == 0
    assert db.query(Transaction).filter_by(type="expense", user_id=1).count() == 0
    assert status(client)["is_paid"] is False


def test_user_deletion_removes_payment_links_but_keeps_other_users(bills):
    client, db, users, current = bills
    client.post("/subscriptions/1/payment", json=request(client))
    assert client.delete("/auth/me").status_code == 200
    assert db.query(SubscriptionPayment).filter_by(user_id=1).count() == 0
    assert db.query(Subscription).filter_by(user_id=2).count() == 1
