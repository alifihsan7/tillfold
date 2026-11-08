import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, text, inspect

from app.db.account_schema import ensure_account_archive_schema
from app.models.account import Account
from app.models.user import User
from app.models.paycheck import PaycheckConfig
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from test_ledger_workflow import ledger, balances, create, summary, custom_salary
from test_telegram_ledger import telegram, update, rows
from test_backup_restore import recovery, download


def archive(client, account_id, status=True):
    return client.put(f"/accounts/{account_id}/archive", json={"is_archived": status})


def test_archive_keeps_balances_transfer_pairs_and_history(ledger):
    client, db = ledger
    create(client, "income", 1000)
    pair = client.post("/transactions/transfer", json={"from_account": "Bank", "to_account": "Cash", "amount": 200}).json()
    bank = db.query(Account).filter_by(user_id=1, name="Bank").one()
    before = balances(client)
    assert archive(client, bank.id).status_code == 200
    assert balances(client) == before == {"Bank": 800, "Cash": 200}
    assert summary(client)["total_balance"] == 1000
    assert client.get("/transactions/history", params={"account": "Bank"}).json()["total"] == 2
    assert db.get(Transaction, pair["out_transaction_id"]) is not None
    assert db.get(Transaction, pair["in_transaction_id"]) is not None
    assert next(row for row in client.get("/accounts").json() if row["id"] == bank.id)["is_archived"] is True
    assert archive(client, bank.id, False).status_code == 200
    assert balances(client) == before
    assert client.post("/transactions", json={"type": "expense", "amount": 10, "account": "Bank", "category": "Test", "description": "Restored"}).status_code == 200


def test_archive_rejects_last_active_account_and_foreign_account(ledger):
    client, db = ledger
    ids = {row["name"]: row["id"] for row in client.get("/accounts").json()}
    assert archive(client, ids["Bank"]).status_code == 200
    assert archive(client, ids["Bank"]).status_code == 200
    assert archive(client, ids["Cash"]).status_code == 409
    assert client.delete(f"/accounts/{ids['Cash']}").status_code == 400
    db.add(User(id=2, username="archive-peer", full_name="Peer", hashed_password="unused", is_active=True))
    db.flush()
    peer = Account(user_id=2, name="Peer", type="operasional")
    db.add(peer)
    db.commit()
    assert archive(client, peer.id).status_code == 404
    assert archive(client, 99999, False).status_code == 404


def test_archived_account_rejects_new_writes_but_allows_historical_edit(ledger):
    client, db = ledger
    tx = create(client, "income", 1000)
    cash_tx = create(client, "expense", 10, "Cash")
    bank = db.query(Account).filter_by(user_id=1, name="Bank").one()
    assert archive(client, bank.id).status_code == 200
    assert client.post("/transactions", json={"type": "expense", "amount": 20, "account": "Bank", "category": "Test", "description": "Blocked"}).status_code == 400
    for source, target in [("Bank", "Cash"), ("Cash", "Bank")]:
        assert client.post("/transactions/transfer", json={"from_account": source, "to_account": target, "amount": 100}).status_code == 400
    assert client.put(f"/transactions/{cash_tx['id']}", json={"account": "Bank"}).status_code == 400
    assert client.put(f"/transactions/{tx['id']}", json={"account": "Bank", "description": "Corrected note"}).status_code == 200
    snapshot = client.get(f"/accounts/{bank.id}/reconciliation").json()
    assert client.post(f"/accounts/{bank.id}/reconciliation", json={"request_key": str(uuid.uuid4()), "actual_balance": 1200,
        "expected_balance": snapshot["balance"], "latest_transaction_id": snapshot["latest_transaction_id"], "note": "Test"}).status_code == 409
    assert balances(client) == {"Bank": 1000, "Cash": -10}


def test_archiving_default_moves_config_to_active_account_without_ledger_changes(ledger):
    client, db = ledger
    cfg = PaycheckConfig(user_id=1, source_account="Bank", pocket_account="Bank", cycle_days=7)
    db.add(cfg)
    db.commit()
    bank = db.query(Account).filter_by(name="Bank").one()
    assert archive(client, bank.id).status_code == 200
    config = client.get("/paycheck/config").json()["config"]
    assert config["source_account"] == config["pocket_account"] == "Cash"
    assert db.query(Transaction).count() == 0
    report = summary(client)
    assert report["safe_to_spend"]["pocket_account"] == "Cash"
    assert client.post("/paycheck/record", json={"request_key": str(uuid.uuid4()), "total_amount": 1000,
        "account": "Bank", "date": date.today().isoformat()}).status_code == 400


def test_pending_paycheck_transfer_blocks_archived_source_or_destination(ledger):
    client, db = ledger
    salary = custom_salary(client)
    account = salary["allocations"][0]
    bank = db.query(Account).filter_by(name="Bank").one()
    url = f"/paycheck/record/{salary['id']}/transfer/{account['account_id']}"
    assert archive(client, bank.id).status_code == 200
    assert client.post(url).status_code == 409
    assert archive(client, bank.id, False).status_code == 200
    assert archive(client, account["account_id"]).status_code == 200
    assert client.post(url).status_code == 409
    resumed = client.get("/paycheck/record/latest").json()
    assert resumed["id"] == salary["id"]
    assert resumed["allocations"][0]["account_archived"] is True
    assert db.query(Transaction).count() == 1


def test_archive_blocks_bill_payment_and_new_bill_assignment(ledger):
    client, db = ledger
    from app.api.v1.endpoints import subscriptions
    from app.schemas.subscription import SubscriptionCreate
    user = db.get(User, 1)
    db.add(Subscription(id=1, user_id=1, name="Internet", amount=100, account="Bank", billing_day=10))
    db.commit()
    preview = subscriptions.preview_payment(1, current_user=user, db=db)
    bank = db.query(Account).filter_by(name="Bank").one()
    assert archive(client, bank.id).status_code == 200
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        subscriptions.create_subscription(SubscriptionCreate(name="New", amount=100, account="Bank"), current_user=user, db=db)
    assert error.value.status_code == 400
    with pytest.raises(HTTPException) as payment_error:
        subscriptions.record_payment(1, subscriptions.RecordBillPayment(period=preview["payment_period"],
            expected_amount=100, expected_account="Bank"), current_user=user, db=db)
    assert payment_error.value.status_code == 409
    assert db.query(Transaction).count() == 0


@pytest.mark.parametrize("message", ["makan 20k Bank Uji", "tf 20k Bank Uji ke Cash"])
def test_telegram_does_not_redirect_explicit_archived_account_to_default(telegram, message):
    db, engine, client, send, extract = telegram
    assert archive(client, 21).status_code == 200
    from app.bot.bot import process_update
    process_update(update(1, message))
    assert rows(db) == []
    assert archive(client, 21, False).status_code == 200
    process_update(update(2, message))
    assert len(rows(db)) == (2 if message.startswith("tf") else 1)


def test_archive_schema_migration_is_repeatable_and_preserves_existing_rows():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE accounts (id INTEGER PRIMARY KEY, name VARCHAR(50))"))
        connection.execute(text("INSERT INTO accounts (id, name) VALUES (1, 'Old')"))
    ensure_account_archive_schema(engine)
    ensure_account_archive_schema(engine)
    assert "is_archived" in {column["name"] for column in inspect(engine).get_columns("accounts")}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT name, is_archived FROM accounts")).one() == ("Old", 0)
    engine.dispose()


def test_backup_preserves_archive_status_and_balances(recovery):
    client, db, users, current = recovery
    bank = db.query(Account).filter_by(user_id=users[0].id, name="Bank").one()
    bank.is_archived = True
    db.commit()
    payload = download(client)
    assert payload["version"] == 4
    current[0] = users[1]
    response = client.post("/backup/restore", json=payload)
    assert response.status_code == 200, response.text
    restored = db.query(Account).filter_by(user_id=users[1].id, name="Bank").one()
    assert restored.is_archived is True
    assert response.json()["balances"]["Bank"] == 800000


@pytest.mark.parametrize("version", [1, 2, 3])
def test_old_backups_restore_accounts_as_active(recovery, version):
    client, db, users, current = recovery
    payload = download(client)
    payload["version"] = version
    for account in payload["data"]["accounts"]:
        account.pop("is_archived")
    if version < 3:
        payload["data"].pop("subscription_payments")
    current[0] = users[1]
    response = client.post("/backup/restore", json=payload)
    assert response.status_code == 200, response.text
    assert all(not account.is_archived for account in db.query(Account).filter_by(user_id=users[1].id))


def test_legacy_salary_flows_skip_archived_default_buckets(ledger):
    client, db = ledger
    salary = custom_salary(client)
    cash = db.query(Account).filter_by(name="Cash").one()
    assert archive(client, cash.id).status_code == 200
    response = client.post("/transactions/paycheck", json={"total_amount": 1000})
    assert response.status_code == 200, response.text
    assert all(row["account"] == "Bank" for row in response.json()["created_transactions"])
    session = client.post("/paycheck/session/start", json={"total_amount": 1000})
    assert session.status_code == 200, session.text
    assert db.query(Transaction).filter_by(account="Cash").count() == 0


def test_archived_media_account_is_rejected_and_salary_uses_replacement(telegram):
    db, engine, client, send, extract = telegram
    from app.bot.bot import process_update
    assert archive(client, 21).status_code == 200
    extract.return_value = {"success": True, "detected": True, "transactions": [
        {"type": "expense", "amount": 100, "account": "Bank Uji"},
    ]}
    process_update(update(1, photo=[{"file_id": "test"}]))
    assert rows(db) == []
    process_update(update(2, "/gajian 1000"))
    assert [(row.type, row.account, row.amount) for row in rows(db)] == [("income", "Cash", 1000)]


def test_restore_cannot_import_only_archived_accounts(recovery):
    client, db, users, current = recovery
    payload = download(client)
    for account in payload["data"]["accounts"]:
        account["is_archived"] = True
    current[0] = users[1]
    assert client.post("/backup/restore", json=payload).status_code == 400
