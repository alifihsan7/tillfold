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
from app.api.v1.endpoints import backup, transactions, analytics, accounts, internal_loans, pockets
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
        db.add(Pocket(user_id=1, account_id=102, subscription_id=101, name="Tagihan", slug="tagihan", role="tagihan", target_amount=100_000, allocation_amount=100_000))
        db.commit()
        app = FastAPI()
        app.include_router(backup.router, prefix="/backup")
        app.include_router(transactions.router, prefix="/transactions")
        app.include_router(analytics.router, prefix="/analytics")
        app.include_router(accounts.router, prefix="/accounts")
        app.include_router(internal_loans.router, prefix="/internal-loans")
        app.include_router(pockets.router, prefix="/pockets")
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


def test_loan_correction_and_pocket_history_survive_restore(recovery):
    client, db, users, current = recovery
    bill = db.query(Pocket).filter_by(user_id=1, slug="tagihan").one()
    db.add(Pocket(user_id=1, account_id=102, slug="utama-102", name="Kantong Utama", target_amount=0))
    db.commit()
    parent = {"account_id": 102}
    summary = client.get("/pockets", params=parent).json()
    main = next(p for p in summary["pockets"] if p["slug"].startswith("utama"))
    moved = client.post("/pockets/transfer", json={
        **parent, "from_pocket_id": main["id"], "to_pocket_id": bill.id, "amount": 25_000,
    })
    assert moved.status_code == 200, moved.text
    refreshed = next(p for p in client.get("/pockets", params=parent).json()["pockets"] if p["id"] == bill.id)
    assert (refreshed["target_amount"], refreshed["balance"]) == (100_000, 125_000)

    created = client.post("/internal-loans", json={
        "source_account_id": 101, "target_account_id": 102, "target_pocket_id": bill.id,
        "amount": 50_000,
    })
    assert created.status_code == 201, created.text
    loan = f"/internal-loans/{created.json()['id']}"
    partial = client.post(f"{loan}/settle", json={"amount": 20_000})
    assert partial.json()["remaining_amount"] == 30_000
    full = client.post(f"{loan}/settle", json={})
    assert full.json()["status"] == "settled"
    latest = client.get(f"{loan}/settlements/latest").json()
    assert latest["amount"] == 30_000
    reversal = f"{loan}/settlements/{latest['id']}/reverse"
    corrected = client.post(reversal)
    assert corrected.status_code == 200, corrected.text
    assert (corrected.json()["status"], corrected.json()["remaining_amount"]) == ("active", 30_000)
    assert client.post(reversal).status_code == 409

    payload = download(client)
    assert len(payload["data"]["pocket_mutations"]) == 6
    current[0] = users[1]
    # Legacy completed accounts can still have automatically seeded empty defaults.
    # Fresh unfinished accounts intentionally remain empty until onboarding completes.
    users[1].is_onboarded = True
    db.commit()
    defaults = client.get("/accounts").json()
    assert len(defaults) == 5
    client.get("/pockets")
    restored = client.post("/backup/restore", json=payload)
    assert restored.status_code == 200, restored.text
    assert restored.json()["balances"] == {"Bank": 770_000, "Cash": 180_000}
    replay = download(client)["data"]
    restored_loan = replay["internal_loans"][0]
    assert restored_loan["id"] != created.json()["id"]
    assert restored_loan["remaining_amount"] == 30_000
    tx_by_id = {tx["id"]: tx for tx in replay["transactions"]}
    for mutation in replay["pocket_mutations"]:
        if mutation["transaction_id"]:
            assert tx_by_id[mutation["transaction_id"]]["pocket_id"] == mutation["pocket_id"]
    correction = next(tx for tx in replay["transactions"] if "internal_loan_reversal_of" in (tx["raw_text"] or ""))
    assert client.delete(f"/transactions/{correction['id']}").status_code == 409
    restored_url = f"/internal-loans/{restored_loan['id']}"
    remaining_payment = client.get(f"{restored_url}/settlements/latest").json()
    assert remaining_payment["amount"] == 20_000
    assert client.post(f"{restored_url}/settlements/{remaining_payment['id']}/reverse").json()["remaining_amount"] == 50_000


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


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5, 6])
def test_previous_backup_format_still_restores(recovery, version):
    client, db, users, current = recovery
    payload = download(client)
    payload["version"] = version
    for pocket in payload["data"]["pockets"]:
        pocket.pop("allocation_start_date")
        if version < 6:
            pocket.pop("allocation_amount")
    if version < 5:
        payload["data"].pop("internal_loans")
        payload["data"].pop("pocket_mutations")
    if version < 3:
        payload["data"].pop("subscription_payments")
    current[0] = users[1]
    assert client.post("/backup/restore", json=payload).status_code == 200
    restored_pocket = db.query(Pocket).filter_by(user_id=users[1].id, slug="tagihan").one()
    assert restored_pocket.allocation_amount == 100_000
