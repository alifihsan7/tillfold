import copy
import json
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, get_strict_current_user
from app.api.v1.endpoints import backup, transactions, analytics, accounts
from app.db.session import Base, get_db
from app.models.account import Account
from app.models.category import Category
from app.models.goal import Goal
from app.models.pocket import Pocket
from app.models.paycheck import (
    LegacyPaycheckCycle, PaycheckBucket, PaycheckConfig, PaycheckCycle, PaycheckReceipt, PaycheckSession,
)
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.services import backup as service


@pytest.fixture
def recovery():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        users = [User(id=i, username=name, full_name=name, hashed_password="SECRET-PASSWORD",
                      telegram_chat_id=123 if i == 1 else None,
                      telegram_bot_token="SECRET-TOKEN" if i == 1 else None, is_active=True)
                 for i, name in [(1, "source"), (2, "target"), (3, "other")]]
        db.add_all(users)
        db.flush()
        db.add_all([Account(id=i, user_id=uid, name=name, type="operasional", initial_balance=0)
                    for i, uid, name in [(101, 1, "Bank"), (102, 1, "Cash"), (1, 3, "Other bank")]])
        db.flush()
        for i, kind, amount, name, raw in [
            (101, "income", 1_000_000, "Bank", None),
            (102, "transfer_out", 200_000, "Bank", "[pair_id:103] [paycheck_receipt:101]"),
            (103, "transfer_in", 200_000, "Cash", "[pair_id:102] [paycheck_receipt:101]"),
            (104, "expense", 50_000, "Cash", "test"),
        ]:
            db.add(Transaction(id=i, user_id=1, type=kind, amount=amount, account=name,
                               category="Gaji" if kind == "income" else "Test", description="Data uji",
                               raw_text=raw, date=date(2026, 11, 2)))
        db.add(Subscription(id=101, user_id=1, name="Tagihan", amount=100_000, account="Cash"))
        db.add(Category(user_id=1, name="Test", type="expense"))
        db.add(Goal(user_id=1, name="Target", target_amount=5_000_000, linked_account="Cash", manual_current_amount=100))
        db.add(PaycheckConfig(id=101, user_id=1, source_account="Bank", pocket_account="Cash", cycle_days=14))
        db.add(PaycheckSession(id=101, user_id=1, total_amount=1_000_000, date=date(2025, 11, 2),
                              status="completed", steps_json=json.dumps([{
                                  "id": "stay_bank", "phase": 1, "app": "Bank", "title": "Saldo",
                                  "description": "Data uji", "source_account": "Bank", "target_account": "Bank",
                                  "amount": 1_000_000, "is_done": True, "transaction_id": 101,
                              }])))
        db.flush()
        db.add(PaycheckBucket(config_id=101, account="Cash", percentage=20, purpose="Belanja"))
        db.add(PaycheckCycle(session_id=101, end_date=date(2025, 11, 15)))
        db.add(LegacyPaycheckCycle(user_id=1, start_date=date(2025, 10, 1), end_date=date(2025, 10, 31)))
        db.add(PaycheckReceipt(transaction_id=101, user_id=1, request_key="56c5dc5f-a240-43be-b453-6f0e066df84b",
                              cycle_end=date(2026, 11, 15), allocations_json=json.dumps([
                                  {"account_id": 102, "amount": 200_000, "transfer_id": 103},
                              ])))
        db.add(Pocket(user_id=1, account_id=102, subscription_id=101, name="Tagihan", slug="tagihan", role="tagihan", target_amount=100_000))
        db.commit()
        app = FastAPI()
        app.include_router(backup.router, prefix="/backup")
        app.include_router(transactions.router, prefix="/transactions")
        app.include_router(analytics.router, prefix="/analytics")
        app.include_router(accounts.router, prefix="/accounts")
        app.dependency_overrides[get_db] = lambda: db
        current = [users[0]]
        app.dependency_overrides[get_strict_current_user] = lambda: current[0]
        app.dependency_overrides[get_current_user] = lambda: current[0]
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, db, users, current
    engine.dispose()


def download(client):
    response = client.get("/backup/export")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert "attachment" in response.headers["content-disposition"]
    return response.json()


def test_full_restore_to_empty_account_preserves_balances_and_relationships(recovery):
    client, db, users, current = recovery
    payload = download(client)
    assert "SECRET" not in json.dumps(payload)
    assert "Other bank" not in json.dumps(payload)
    expected = client.post("/backup/preview", json=payload).json()
    source_periods = client.get("/analytics/periods").json()
    assert expected["total_balance"] == 950_000
    assert expected["balances"] == {"Bank": 800_000, "Cash": 150_000}
    current[0] = users[1]
    result = client.post("/backup/restore", json=payload)
    assert result.status_code == 200, result.text
    assert result.json() == expected
    restored = download(client)
    assert service.summary(restored["data"]) == expected
    assert client.get("/analytics/periods").json() == source_periods
    assert client.get("/analytics/summary", params={"period_type": "custom", "start": "2026-11-01", "end": "2026-11-30"}).json()["total_balance"] == 950_000
    assert {row["name"]: row["current_balance"] for row in client.get("/accounts").json()} == expected["balances"]
    pocket = db.query(Pocket).filter_by(user_id=2).one()
    assert db.get(Account, pocket.account_id).user_id == 2
    assert db.get(Subscription, pocket.subscription_id).user_id == 2
    receipt = db.query(PaycheckReceipt).filter_by(user_id=2).one()
    allocation = json.loads(receipt.allocations_json)[0]
    transfer = db.get(Transaction, allocation["transfer_id"])
    assert transfer.user_id == 2
    assert f"[paycheck_receipt:{receipt.transaction_id}]" in transfer.raw_text
    assert client.delete(f"/transactions/{transfer.id}").status_code == 200
    db.refresh(receipt)
    assert json.loads(receipt.allocations_json)[0]["transfer_id"] is None
    assert db.query(Transaction).filter_by(user_id=1).count() == 4
    assert db.query(Account).filter_by(user_id=3).one().name == "Other bank"
    assert users[1].telegram_chat_id is None


def test_restore_refuses_existing_data_and_duplicate_retry(recovery):
    client, db, users, current = recovery
    payload = download(client)
    assert client.post("/backup/restore", json=payload).status_code == 409
    assert db.query(Transaction).filter_by(user_id=1).count() == 4
    current[0] = users[1]
    assert client.post("/backup/restore", json=payload).status_code == 200
    assert client.post("/backup/restore", json=payload).status_code == 409
    assert db.query(Transaction).filter_by(user_id=2).count() == 4


@pytest.mark.parametrize("damage", ["version", "owner", "foreign_key", "duplicate", "boolean_amount", "broken_json"])
def test_invalid_backup_never_writes_data(recovery, damage):
    client, db, users, current = recovery
    payload = download(client)
    if damage == "version":
        payload["version"] = 99
    elif damage == "owner":
        payload["data"]["accounts"][0]["user_id"] = 3
    elif damage == "foreign_key":
        payload["data"]["pockets"][0]["account_id"] = 999999
    elif damage == "duplicate":
        payload["data"]["transactions"].append(copy.deepcopy(payload["data"]["transactions"][0]))
    elif damage == "boolean_amount":
        payload["data"]["transactions"][0]["amount"] = True
    else:
        payload["data"]["paycheck_receipts"][0]["allocations_json"] = "not json"
    current[0] = users[1]
    assert client.post("/backup/preview", json=payload).status_code == 400
    assert client.post("/backup/restore", json=payload).status_code == 400
    assert db.query(Account).filter_by(user_id=2).count() == 0
    assert db.query(Transaction).filter_by(user_id=1).count() == 4


def test_restore_rolls_back_every_table_when_final_verification_fails(recovery, monkeypatch):
    client, db, users, current = recovery
    payload = download(client)
    current[0] = users[1]
    db.add(Category(user_id=2, name="Default", type="expense"))
    db.add(PaycheckConfig(user_id=2, source_account="Default"))
    db.commit()
    def fail(*args):
        raise RuntimeError("Injected final verification failure")
    monkeypatch.setattr(service, "export_backup", fail)
    assert client.post("/backup/restore", json=payload).status_code == 500
    assert db.query(Account).filter_by(user_id=2).count() == 0
    assert db.query(Transaction).filter_by(user_id=2).count() == 0
    assert db.query(Category).filter_by(user_id=2).one().name == "Default"
    assert db.query(PaycheckConfig).filter_by(user_id=2).one().source_account == "Default"


def test_zero_balance_accounts_and_legacy_transfer_pairs_survive_restore(recovery):
    client, db, users, current = recovery
    db.add(Account(user_id=1, name="Empty bank", type="tabungan", initial_balance=0))
    for tx in db.query(Transaction).filter(Transaction.id.in_([102, 103])):
        tx.raw_text = "[paycheck_receipt:101]"
    db.commit()
    payload = download(client)
    current[0] = users[1]
    result = client.post("/backup/restore", json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["balances"]["Empty bank"] == 0
    incoming = db.query(Transaction).filter_by(user_id=2, type="transfer_in").one()
    outgoing = db.query(Transaction).filter_by(user_id=2, type="transfer_out").one()
    assert f"[pair_id:{outgoing.id}]" in incoming.raw_text
    assert client.delete(f"/transactions/{incoming.id}").status_code == 200
    assert db.query(Transaction).filter_by(user_id=2, type="transfer_out").count() == 0


def test_new_account_seeded_defaults_can_be_replaced_by_backup(recovery):
    client, db, users, current = recovery
    payload = download(client)
    current[0] = users[1]
    assert client.get("/analytics/summary").status_code == 200
    cfg = PaycheckConfig(user_id=2, source_account="Default")
    db.add(cfg)
    db.add(Category(user_id=2, name="Default", type="expense"))
    db.flush()
    db.add(PaycheckBucket(config_id=cfg.id, account="Default", percentage=100, purpose="Default"))
    db.commit()
    result = client.post("/backup/restore", json=payload)
    assert result.status_code == 200, result.text
    assert db.query(PaycheckConfig).filter_by(user_id=2).one().source_account == "Bank"
    restored_cfg = db.query(PaycheckConfig).filter_by(user_id=2).one()
    assert db.query(PaycheckBucket).filter_by(config_id=restored_cfg.id).one().account == "Cash"


def test_oversize_and_non_json_uploads_are_rejected_before_restore(recovery, monkeypatch):
    client, db, users, current = recovery
    current[0] = users[1]
    assert client.post("/backup/restore", content="not json").status_code == 400
    monkeypatch.setattr(backup, "MAX_BYTES", 10)
    assert client.post("/backup/restore", content="x" * 11).status_code == 413
    assert db.query(Account).filter_by(user_id=2).count() == 0


@pytest.mark.parametrize("kind, expected", [("adjustment_in", 1_000_000), ("adjustment_out", 900_000)])
def test_backup_restore_preserves_reconciliation_records(recovery, kind, expected):
    client, db, users, current = recovery
    db.add(Transaction(user_id=1, type=kind, amount=50_000, account="Bank", category="Penyesuaian saldo",
                       description="Cocokkan saldo bank", raw_text="reconciliation:test-key", date=date(2026, 11, 2)))
    db.commit()
    payload = download(client)
    current[0] = users[1]
    result = client.post("/backup/restore", json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["total_balance"] == expected
    adjustment = db.query(Transaction).filter_by(user_id=2, type=kind).one()
    assert adjustment.amount == 50_000
    assert client.delete(f"/transactions/{adjustment.id}").status_code == 409


@pytest.mark.parametrize("version", [1, 2])
def test_previous_backup_format_still_restores(recovery, version):
    client, db, users, current = recovery
    payload = download(client)
    payload["version"] = version
    payload["data"].pop("subscription_payments")
    current[0] = users[1]
    assert client.post("/backup/restore", json=payload).status_code == 200
