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
from app.api.v1.endpoints import accounts, paycheck, subscriptions, auth, transactions
from app.bot import bot
from app.db.session import Base, get_db
from app.models.account import Account
from app.models.paycheck import PaycheckConfig, PaycheckBucket, PaycheckReceipt
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import TelegramProcessedMessage, User


real_send_message = bot.send_message


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
        for name, router in [("accounts", accounts.router), ("paycheck", paycheck.router), ("subscriptions", subscriptions.router), ("auth", auth.router), ("transactions", transactions.router)]:
            app.include_router(router, prefix="/" + name)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: db.get(User, 2)
        app.dependency_overrides[get_strict_current_user] = lambda: db.get(User, 2)
        monkeypatch.setattr(bot, "SessionLocal", lambda: Session(engine))
        send = Mock()
        monkeypatch.setattr(bot, "send_message", send)
        monkeypatch.setattr(bot, "get_safe_to_spend_snippet", lambda *args, **kwargs: "Status belanja")
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
    actions = [button for row in send.call_args.kwargs["reply_markup"]["inline_keyboard"] for button in row]
    assert {button["text"] for button in actions} == {"Ubah kategori", "Ubah rekening", "Batalkan"}
    assert all(button["callback_data"].startswith(f"txn:{saved[2].id}:") for button in actions)


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
    send.side_effect = [None, RuntimeError("reply unavailable")]
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


def test_telegram_expense_appears_in_web_history_outside_dashboard_period(telegram):
    db, engine, client, send, extract = telegram
    bot.process_update(update(1, "makan 20k Cash"))
    assert client.get("/transactions", params={"start_date": "2020-01-01", "end_date": "2020-01-31"}).json() == []
    history = client.get("/transactions/history").json()
    assert history["total"] == 1
    assert history["expense"] == 20000
    assert history["items"][0]["account"] == "Cash"
    assert next(row for row in client.get("/accounts").json() if row["name"] == "Cash")["current_balance"] == -20000


def test_transaction_buttons_edit_and_cancel_only_the_selected_transaction(telegram, monkeypatch):
    from app.models.category import Category

    db, _, client, send, _ = telegram
    db.add_all([
        Category(user_id=2, name="Makanan uji", type="expense"),
        Category(user_id=2, name="Pendapatan uji", type="income"),
        Category(user_id=3, name="Kategori akun lain", type="expense"),
    ])
    db.commit()
    edits = []

    def telegram_post(url, *, json, timeout):
        if url.endswith("/editMessageText"):
            edits.append(json)

    def buttons(markup):
        return {button["text"]: button["callback_data"]
                for row in markup["inline_keyboard"] for button in row}

    def press(data, chat=222, chat_type="private"):
        bot.process_update({"callback_query": {
            "id": "test-correction", "from": {"id": chat}, "data": data,
            "message": {"chat": {"id": chat, "type": chat_type}, "message_id": 100},
        }})

    monkeypatch.setattr(bot.requests, "post", telegram_post)
    bot.process_update(update(1, "makan 20k Bank Uji"))
    first_id = rows(db)[0].id
    actions = buttons(send.call_args.kwargs["reply_markup"])
    assert all(len(data.encode()) <= 64 for data in actions.values())

    bot.process_update(update(2, "kopi 15k Bank Uji"))
    second_id = rows(db)[-1].id
    press(actions["Ubah kategori"], chat_type="group")
    assert not edits
    press(actions["Ubah kategori"])
    categories = buttons(edits[-1]["reply_markup"])
    assert "Pendapatan uji" not in categories
    assert "Kategori akun lain" not in categories
    press(categories["Makanan uji"])
    assert db.get(Transaction, first_id).category == "Makanan uji"
    assert db.get(Transaction, second_id).category != "Makanan uji"

    press(actions["Ubah rekening"])
    accounts = buttons(edits[-1]["reply_markup"])
    assert "Peer Bank" not in accounts
    press(accounts["Cash"])
    assert db.get(Transaction, first_id).account == "Cash"
    assert db.get(Transaction, second_id).account == "Bank Uji"
    balances = client.get("/accounts").json()
    assert {item["name"]: item["current_balance"] for item in balances} == {"Bank Uji": -15000, "Cash": -20000}

    press(actions["Batalkan"])
    assert len(rows(db)) == 2
    confirm = buttons(edits[-1]["reply_markup"])["Ya, batalkan"]
    press(confirm, chat=333)
    assert len(rows(db)) == 2
    press(confirm)
    assert [tx.id for tx in rows(db)] == [second_id]
    press(confirm)
    assert [tx.id for tx in rows(db)] == [second_id]
    bot.process_update(update(1, "makan 20k Bank Uji"))
    assert [tx.id for tx in rows(db)] == [second_id]


def test_ambiguous_amount_waits_for_confirmation_and_records_once(telegram, monkeypatch):
    from app.models.user import TelegramAmountDraft

    db, _, _, send, _ = telegram
    edits = []
    monkeypatch.setattr(bot.requests, "post", lambda url, **kwargs: edits.append(kwargs["json"]))
    message = update(1, "kopi 15 ribu atau 50 ribu Cash; makan 25k Bank Uji")
    bot.process_update(message)
    bot.process_update(message)
    assert rows(db) == []
    assert db.query(TelegramAmountDraft).count() == 1
    assert send.call_count == 1
    assert "Rp 25.000" in send.call_args.args[1]
    keyboard = send.call_args.kwargs["reply_markup"]["inline_keyboard"]
    actions = {button["text"]: button["callback_data"] for row in keyboard for button in row}
    assert set(actions) == {"Rp 15.000", "Rp 50.000", "Buang draf"}

    def press(chat, text):
        bot.process_update({"callback_query": {
            "id": "amount-choice", "from": {"id": chat}, "data": actions[text],
            "message": {"chat": {"id": chat, "type": "private"}, "message_id": 100},
        }})

    press(333, "Rp 50.000")
    assert rows(db) == []
    press(222, "Rp 50.000")
    press(222, "Rp 15.000")
    assert [(tx.amount, tx.account) for tx in rows(db)] == [(50000, "Cash"), (25000, "Bank Uji")]
    assert db.query(TelegramAmountDraft).count() == 0
    assert any(edit.get("text") == "Draf sudah dikonfirmasi." for edit in edits)


def test_amount_draft_cancel_expiry_and_clear_chat(telegram, monkeypatch):
    from app.models.user import TelegramAmountDraft

    db, _, _, send, _ = telegram
    monkeypatch.setattr(bot.requests, "post", Mock())

    def press(label):
        result = next(button["callback_data"] for row in send.call_args.kwargs["reply_markup"]["inline_keyboard"]
                      for button in row if button["text"] == label)
        bot.process_update({"callback_query": {
            "id": "amount-choice", "from": {"id": 222}, "data": result,
            "message": {"chat": {"id": 222, "type": "private"}, "message_id": 100},
        }})

    bot.process_update(update(1, "kopi 15k/50k Cash"))
    press("Buang draf")
    assert db.query(TelegramAmountDraft).count() == 0
    bot.process_update(update(2, "kopi 15000 atau 50000 Cash"))
    db.query(TelegramAmountDraft).one().expires_at = 0
    db.commit()
    press("Rp 50.000")
    assert rows(db) == []
    bot.process_update(update(3, "kopi 15k Cash"))
    bot.process_update(update(4, "/transfer 15k atau 50k dari Cash ke Bank Uji"))
    assert [tx.amount for tx in rows(db)] == [15000]


def test_voice_alternative_drafts_instead_of_accepting_extractor_guess(telegram, monkeypatch):
    import httpx

    db, _, _, send, extract = telegram
    monkeypatch.setattr(httpx, "post", Mock(return_value=Mock(status_code=503)))
    extract.return_value = {
        **extracted([{"type": "expense", "amount": 15000, "account": "Cash"}]),
        "transcription": "kopi 15 ribu apa 50 ribu Cash",
    }
    bot.process_update(update(1, voice={"file_id": "sample"}))
    assert rows(db) == []
    assert "Draf belum dicatat" in send.call_args.args[1]


@pytest.mark.parametrize("mode", ["success", "download_failed", "edit_failed", "voice_draft"])
def test_media_progress_updates_result_and_keeps_buttons(telegram, monkeypatch, caplog, mode):
    import httpx

    db, _, _, send, extract = telegram
    send.side_effect = real_send_message
    requests_seen = []

    def post(url, *, json, timeout):
        method = url.rsplit("/", 1)[-1]
        requests_seen.append((method, json))
        if method == "editMessageText" and mode == "edit_failed":
            return Mock(json=lambda: {"ok": False, "description": "message to edit not found"})
        return Mock(json=lambda: {"ok": True, "result": {"message_id": 4321}})

    monkeypatch.setattr(bot.requests, "post", post)
    extract.return_value = extracted([{"type": "expense", "amount": 15000, "account": "Cash"}])
    if mode == "download_failed":
        monkeypatch.setattr(bot, "download_telegram_file", Mock(return_value=(None, None)))
    if mode == "voice_draft":
        monkeypatch.setattr(httpx, "post", Mock(return_value=Mock(status_code=200, json=lambda: {"text": "kopi 15k atau 50k Cash"})))
        message = update(1, voice={"file_id": "test"})
    else:
        message = update(1, photo=[{"file_id": "test"}])

    with caplog.at_level("INFO", logger=bot.media_logger.name):
        bot.process_update(message)
    assert bot.media_reply.get() is None
    assert requests_seen[0][0] == "sendMessage"
    assert "Lagi" in requests_seen[0][1]["text"]
    assert requests_seen[1][0] == "editMessageText"
    assert requests_seen[1][1]["message_id"] == 4321
    assert "reply_to_message_id" not in requests_seen[1][1]
    assert "stage=download" in caplog.text and "stage=total" in caplog.text
    assert "kopi" not in caplog.text.lower()
    final = requests_seen[-1][1]
    if mode == "download_failed":
        assert "Gagal mengunduh" in final["text"]
        assert not rows(db)
    elif mode == "voice_draft":
        assert "Draf belum dicatat" in final["text"]
        assert final["reply_markup"]["inline_keyboard"]
        assert "stage=local_transcription" in caplog.text
        assert not rows(db)
    else:
        assert [tx.amount for tx in rows(db)] == [15000]
        assert "Tercatat" in final["text"]
        assert final["reply_markup"]["inline_keyboard"]
        assert "stage=extraction" in caplog.text and "stage=persist" in caplog.text
    assert len(requests_seen) == (3 if mode == "edit_failed" else 2)
