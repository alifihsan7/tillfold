import json
from datetime import date
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, get_strict_current_user
from app.api.v1.endpoints import accounts, paycheck, subscriptions, auth
from app.bot import bot
from app.db.session import Base, get_db
from app.models.account import Account
from app.models.paycheck import PaycheckConfig, PaycheckBucket, PaycheckReceipt
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import TelegramProcessedMessage, User


@pytest.fixture
def telegram(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(id=2, username="telegram-ledger", full_name="Test", hashed_password="unused",
                    telegram_chat_id=222, is_active=True, telegram_mode="shared")
        peer = User(id=3, username="peer", full_name="Peer", hashed_password="unused", telegram_chat_id=333,
                    is_active=True, telegram_mode="shared")
        db.add_all([user, peer])
        db.flush()
        db.add_all([Account(id=21, user_id=2, name="Bank Uji", type="operasional", initial_balance=0),
                    Account(id=22, user_id=2, name="Cash", type="operasional", initial_balance=0),
                    Account(id=31, user_id=3, name="Peer Bank", type="operasional", initial_balance=0)])
        db.add(PaycheckConfig(id=2, user_id=2, source_account="Bank Uji", pocket_account="Cash", cycle_days=7,
                             cycle_type="weekly"))
        db.flush()
        db.add(PaycheckBucket(config_id=2, account="Cash", percentage=50, purpose="Belanja"))
        db.commit()
        app = FastAPI()
        for name, router in [("accounts", accounts.router), ("paycheck", paycheck.router), ("subscriptions", subscriptions.router), ("auth", auth.router)]:
            app.include_router(router, prefix="/" + name)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: db.get(User, 2)
        app.dependency_overrides[get_strict_current_user] = lambda: db.get(User, 2)
        monkeypatch.setattr(bot, "SessionLocal", lambda: Session(engine))
        send = Mock()
        monkeypatch.setattr(bot, "send_message", send)
        monkeypatch.setattr(bot, "get_safe_to_spend_snippet", lambda *args, **kwargs: "Status belanja")
        monkeypatch.setattr(bot, "send_chat_action", Mock())
        monkeypatch.setattr(bot, "download_telegram_file", Mock(return_value=(b"test", "test.png")))
        from app.services import ai_extractor
        extract = Mock()
        monkeypatch.setattr(ai_extractor, "extract_from_media", extract)
        with TestClient(app) as client:
            yield db, engine, client, send, extract
    engine.dispose()


def update(message_id, text="", chat_id=222, **media):
    return {"update_id": message_id + 1000, "message": {
        "message_id": message_id, "chat": {"id": chat_id, "type": "private"},
        "from": {"id": chat_id}, "text": text, **media,
    }}


def rows(db):
    db.expire_all()
    return db.query(Transaction).order_by(Transaction.id).all()


def extracted(items):
    return {"success": True, "detected": True, "transactions": items}


def test_same_message_is_once_but_new_messages_are_independent(telegram):
    db, engine, client, send, extract = telegram
    first = update(1, "makan 20k Bank Uji")
    bot.process_update(first)
    first["update_id"] += 10
    bot.process_update(first)
    assert [(tx.account, tx.amount) for tx in rows(db)] == [("Bank Uji", 20000)]
    bot.process_update(update(2, "makan 20k Bank Uji"))
    assert len(rows(db)) == 2
    assert db.query(TelegramProcessedMessage).count() == 2
    assert send.call_count == 2
    # Message IDs are scoped to a chat, not globally.
    bot.process_update(update(1, "makan 10k Peer Bank", chat_id=333))
    assert rows(db)[-1].user_id == 3


def test_transfer_and_undo_retries_do_not_repeat_financial_changes(telegram):
    db, engine, client, send, extract = telegram
    bot.process_update(update(1, "/gajian 1000"))
    bot.process_update(update(2, "tf 200 Bank Uji ke Cash"))
    bot.process_update(update(2, "tf 200 Bank Uji ke Cash"))
    assert len(rows(db)) == 3
    bot.process_update(update(3, "/batal"))
    bot.process_update(update(3, "/batal"))
    assert [tx.type for tx in rows(db)] == ["income"]
    bot.process_update(update(4, "/batal"))
    assert rows(db) == []
    assert db.query(PaycheckReceipt).count() == 0


def test_undo_allocation_reopens_paycheck_and_then_removes_income(telegram):
    db, engine, client, send, extract = telegram
    bot.process_update(update(1, "/gajian 1000"))
    receipt = db.query(PaycheckReceipt).one()
    receipt_id = receipt.transaction_id
    assert client.post(f"/paycheck/record/{receipt_id}/transfer/22").status_code == 200
    assert len(rows(db)) == 3
    bot.process_update(update(2, "/batal"))
    assert len(rows(db)) == 1
    db.expire_all()
    assert json.loads(db.get(PaycheckReceipt, receipt_id).allocations_json)[0]["transfer_id"] is None
    assert client.post(f"/paycheck/record/{receipt_id}/transfer/22").status_code == 200
    bot.process_update(update(3, "/batal"))
    bot.process_update(update(4, "/batal"))
    assert rows(db) == []
    assert client.get("/paycheck/record/latest").json() is None


def test_undo_bill_payment_reopens_bill_once(telegram):
    db, engine, client, send, extract = telegram
    db.add(Subscription(id=1, user_id=2, name="Internet", account="Bank Uji", amount=100, billing_day=10))
    db.commit()
    preview = client.get("/subscriptions/1/payment").json()
    response = client.post("/subscriptions/1/payment", json={
        "period": preview["payment_period"], "expected_amount": 100, "expected_account": "Bank Uji",
    })
    assert response.status_code == 200, response.text
    bot.process_update(update(1, "/batal"))
    bot.process_update(update(1, "/batal"))
    assert rows(db) == []
    assert client.get("/subscriptions").json()["items"][0]["is_paid"] is False


@pytest.mark.parametrize("amount", [-1, 0, 1.5, True, 9000000000000001, "abc"])
def test_media_batch_is_rejected_before_any_write(telegram, amount):
    db, engine, client, send, extract = telegram
    extract.return_value = extracted([
        {"type": "expense", "amount": 100, "account": "Cash"},
        {"type": "expense", "amount": amount, "account": "Cash"},
    ])
    bot.process_update(update(1, photo=[{"file_id": "test"}]))
    assert rows(db) == []
    assert "Nominal" in send.call_args.args[1]


def test_mixed_media_transfers_are_paired_and_retries_skip_extraction(telegram):
    db, engine, client, send, extract = telegram
    extract.return_value = extracted([
        {"type": "transfer", "amount": 300, "from_account": "Bank Uji", "to_account": "Cash"},
        {"type": "expense", "amount": 100, "account": "Cash"},
    ])
    payload = update(1, photo=[{"file_id": "test"}])
    bot.process_update(payload)
    bot.process_update(payload)
    saved = rows(db)
    assert [tx.type for tx in saved] == ["transfer_out", "transfer_in", "expense"]
    assert bot.find_paired_transfer(db, saved[0]).id == saved[1].id
    assert bot.get_acc_balance("Bank Uji", db, 2) == -300
    assert bot.get_acc_balance("Cash", db, 2) == 200
    assert extract.call_count == 1
    assert extract.call_args.kwargs["accounts"] == ["Bank Uji", "Cash"]


@pytest.mark.parametrize("item", [
    {"type": "expense", "amount": 100, "account": "Peer Bank"},
    {"type": "transfer", "amount": 100, "from_account": "Cash", "to_account": "Cash"},
    {"type": "transfer", "amount": 100, "from_account": "Bank Uji", "to_account": "Mandiri"},
    {"type": "transfer_out", "amount": 100, "account": "Cash"},
])
def test_invalid_media_accounts_and_types_leave_ledger_unchanged(telegram, item):
    db, engine, client, send, extract = telegram
    extract.return_value = extracted([item])
    bot.process_update(update(1, photo=[{"file_id": "test"}]))
    assert rows(db) == []


def test_text_defaults_use_config_and_explicit_unknown_bank_is_rejected(telegram):
    db, engine, client, send, extract = telegram
    bot.process_update(update(1, "makan 20k"))
    bot.process_update(update(2, "pemasukan 100k"))
    bot.process_update(update(3, "makan 30k mandiri"))
    saved = rows(db)
    assert [(tx.type, tx.account, tx.amount) for tx in saved] == [("expense", "Cash", 20000), ("income", "Bank Uji", 100000)]
    assert "Rekening" in send.call_args.args[1]


def test_reply_failure_after_commit_does_not_repeat_expense(telegram):
    db, engine, client, send, extract = telegram
    send.side_effect = RuntimeError("reply unavailable")
    with pytest.raises(RuntimeError):
        bot.process_update(update(1, "makan 20k"))
    assert len(rows(db)) == 1
    send.side_effect = None
    bot.process_update(update(1, "makan 20k"))
    assert len(rows(db)) == 1


def test_failed_salary_commit_can_retry_after_config_seed(telegram, monkeypatch):
    db, engine, client, send, extract = telegram
    db.query(PaycheckBucket).delete()
    db.query(PaycheckConfig).delete()
    db.commit()
    session_factory = bot.SessionLocal
    def fail_receipt(session):
        if any(isinstance(obj, PaycheckReceipt) for obj in session.new):
            raise RuntimeError("database commit unavailable")
    def failing_session():
        session = session_factory()
        event.listen(session, "before_commit", fail_receipt)
        return session
    monkeypatch.setattr(bot, "SessionLocal", failing_session)
    with pytest.raises(RuntimeError):
        bot.process_update(update(1, "/gajian 1000"))
    assert rows(db) == []
    assert db.query(TelegramProcessedMessage).count() == 0
    monkeypatch.setattr(bot, "SessionLocal", session_factory)
    bot.process_update(update(1, "/gajian 1000"))
    assert len(rows(db)) == 1
    assert db.query(PaycheckReceipt).count() == 1


def test_unique_message_constraint_rolls_back_stale_duplicate_undo(telegram, monkeypatch):
    db, engine, client, send, extract = telegram
    bot.process_update(update(1, "makan 10k"))
    bot.process_update(update(2, "makan 20k"))
    bot.process_update(update(3, "/batal"))
    factory = bot.SessionLocal
    def stale_session():
        session = factory()
        original_get = session.get
        first = [True]
        def stale_get(model, key, *args, **kwargs):
            if model is TelegramProcessedMessage and first[0]:
                first[0] = False
                return None
            return original_get(model, key, *args, **kwargs)
        session.get = stale_get
        return session
    monkeypatch.setattr(bot, "SessionLocal", stale_session)
    bot.process_update(update(3, "/batal"))
    assert [tx.amount for tx in rows(db)] == [10000]


def test_no_accounts_never_creates_fallback_bank(telegram):
    db, engine, client, send, extract = telegram
    db.query(Account).filter_by(user_id=2).delete()
    db.commit()
    for message_id, text in enumerate(["makan 20k", "tf 20k mandiri ke bibit", "/gajian 1000"], 1):
        bot.process_update(update(message_id, text))
    assert rows(db) == []


@pytest.mark.parametrize("command", ["tf", "/tf", "/transfer"])
def test_transfer_prefers_full_destination_name_and_accepts_custom_symbols(telegram, command):
    db, engine, client, send, extract = telegram
    db.add_all([Account(user_id=2, name="Cash Main", type="operasional", initial_balance=0),
                Account(user_id=2, name="Bank-A & B", type="operasional", initial_balance=0)])
    db.commit()
    bot.process_update(update(1, f"{command} 100 Bank-A & B ke Cash Main : catatan uji"))
    saved = rows(db)
    assert [(tx.account, tx.amount) for tx in saved] == [("Bank-A & B", 100), ("Cash Main", 100)]
    assert saved[0].description.endswith("catatan uji")


def test_number_in_account_name_is_not_a_transaction_amount(telegram):
    db, engine, client, send, extract = telegram
    db.add(Account(user_id=2, name="Rekening 123", type="operasional", initial_balance=0))
    db.commit()
    bot.process_update(update(1, "makan Rekening 123"))
    assert rows(db) == []
    bot.process_update(update(2, "makan 20k Rekening 123"))
    assert [(tx.account, tx.amount) for tx in rows(db)] == [("Rekening 123", 20000)]


def test_voice_reply_failure_does_not_fall_back_to_second_extraction(telegram, monkeypatch):
    db, engine, client, send, extract = telegram
    import httpx
    response = Mock(status_code=200)
    response.json.return_value = {"text": "makan 20k Cash"}
    monkeypatch.setattr(httpx, "post", Mock(return_value=response))
    send.side_effect = RuntimeError("reply unavailable")
    payload = update(1, voice={"file_id": "test"})
    with pytest.raises(RuntimeError):
        bot.process_update(payload)
    assert len(rows(db)) == 1
    extract.assert_not_called()
    send.side_effect = None
    bot.process_update(payload)
    assert len(rows(db)) == 1


def test_salary_undo_is_blocked_while_paid_allocations_exist(telegram):
    db, engine, client, send, extract = telegram
    from app.api.v1.endpoints.transactions import add_transfer_pair
    outgoing, incoming = add_transfer_pair(db, 2, "Bank Uji", "Cash", 200, date.today(), "Alokasi")
    salary = Transaction(user_id=2, type="income", amount=1000, account="Bank Uji", category="Gaji",
                         description="Gaji", date=date.today())
    db.add(salary)
    db.flush()
    for transfer in (outgoing, incoming):
        transfer.raw_text += f" [paycheck_receipt:{salary.id}]"
    db.add(PaycheckReceipt(transaction_id=salary.id, user_id=2, request_key="test", allocations_json=json.dumps([
        {"account_id": 22, "amount": 200, "transfer_id": incoming.id},
    ])))
    db.commit()
    bot.process_update(update(1, "/batal"))
    assert len(rows(db)) == 3
    assert "Hapus transfer pembagian gaji terlebih dahulu" in send.call_args.args[1]


@pytest.mark.parametrize("text", ["makan {amount}k", "/gajian {amount}k", "tf {amount}k Bank Uji ke Cash"])
def test_unparseable_huge_amount_does_not_block_following_messages(telegram, text):
    db, engine, client, send, extract = telegram
    bot.process_update(update(1, text.format(amount="9" * 350)))
    assert rows(db) == []
    bot.process_update(update(2, "makan 20k Cash"))
    assert len(rows(db)) == 1


def test_account_erasure_removes_only_its_message_keys(telegram):
    db, engine, client, send, extract = telegram
    bot.process_update(update(1, "/saldo"))
    bot.process_update(update(1, "/saldo", chat_id=333))
    assert db.query(TelegramProcessedMessage).count() == 2
    response = client.delete("/auth/me")
    assert response.status_code == 200, response.text
    db.expire_all()
    keys = db.query(TelegramProcessedMessage).all()
    assert [(key.chat_id, key.user_id) for key in keys] == [(333, 3)]


def test_media_failure_rolls_back_transfers_expenses_and_message_key(telegram, monkeypatch):
    db, engine, client, send, extract = telegram
    extract.return_value = extracted([
        {"type": "transfer", "amount": 300, "from_account": "Bank Uji", "to_account": "Cash"},
        {"type": "expense", "amount": 100, "account": "Cash"},
    ])
    factory = bot.SessionLocal
    def fail_commit(session):
        raise RuntimeError("database commit unavailable")
    def failing_session():
        session = factory()
        event.listen(session, "before_commit", fail_commit)
        return session
    monkeypatch.setattr(bot, "SessionLocal", failing_session)
    payload = update(1, photo=[{"file_id": "test"}])
    with pytest.raises(RuntimeError):
        bot.process_update(payload)
    assert rows(db) == []
    assert db.query(TelegramProcessedMessage).count() == 0
    monkeypatch.setattr(bot, "SessionLocal", factory)
    bot.process_update(payload)
    assert len(rows(db)) == 3
