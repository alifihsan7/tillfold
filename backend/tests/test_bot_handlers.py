import pytest
from datetime import date, datetime, timedelta
import zoneinfo
import json
from unittest.mock import MagicMock

from app.models.user import User
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.pocket import Pocket
from app.models.subscription import Subscription
from app.models.goal import Goal
from app.models.paycheck import PaycheckConfig, PaycheckBucket, PaycheckReceipt
from app.bot.bot import (
    handle_start,
    handle_menu,
    handle_saldo,
    handle_pacing,
    handle_subs,
    handle_goals,
    handle_rekap,
    handle_gajian,
    handle_transfer,
    handle_batal,
    process_update,
    get_user_cycle_info,
    get_safe_to_spend_snippet,
    get_acc_balance,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.session import Base

WIB = zoneinfo.ZoneInfo("Asia/Jakarta")

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def bot_user(db_session):
    u = User(
        username="bot_test_user",
        email="bot_user@ai7.local",
        hashed_password="fakehashedpassword",
        telegram_chat_id=889977,
        full_name="Alif Test",
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def capture_messages(monkeypatch):
    messages = []

    def fake_send(chat_id, text, **kwargs):
        messages.append({"chat_id": chat_id, "text": text, "kwargs": kwargs})
        return {"ok": True}

    import app.bot.bot as bot_module

    monkeypatch.setattr(bot_module, "send_message", fake_send)
    return messages


def test_bot_start_and_menu(bot_user, capture_messages):
    handle_start(chat_id=bot_user.telegram_chat_id, user=bot_user)
    assert len(capture_messages) == 1
    assert "Selamat datang di Tillfold" in capture_messages[0]["text"]
    assert "/pacing" in capture_messages[0]["text"]
    assert "/saldo" in capture_messages[0]["text"]

    handle_menu(chat_id=bot_user.telegram_chat_id)
    assert len(capture_messages) == 2
    assert "Menu Tillfold" in capture_messages[1]["text"]
    kb = capture_messages[1]["kwargs"].get("reply_markup", {}).get("keyboard", [])
    flat_kb = [btn["text"] for row in kb for btn in row]
    assert "🎯 Pacing" in flat_kb
    assert "💳 Saldo" in flat_kb


def test_bot_saldo_accounts_and_pockets(db_session, bot_user, capture_messages):
    acc1 = Account(user_id=bot_user.id, name="Bank Mandiri", type="operasional", tag="saku")
    acc2 = Account(user_id=bot_user.id, name="Bank Jago", type="secondary", tag="bills")
    db_session.add_all([acc1, acc2])
    db_session.commit()

    pocket1 = Pocket(
        user_id=bot_user.id,
        account_id=acc2.id,
        name="Kantong Tagihan",
        slug="kantong-tagihan",
        role="bills",
        target_amount=1500000,
        is_active=True,
    )
    db_session.add(pocket1)

    t1 = Transaction(
        user_id=bot_user.id,
        type="income",
        amount=5000000,
        account="Bank Mandiri",
        category="Gaji",
        description="Gaji Bulanan",
        date=date.today(),
    )
    t2 = Transaction(
        user_id=bot_user.id,
        type="expense",
        amount=500000,
        account="Bank Mandiri",
        category="Makan",
        description="Makan Siang",
        date=date.today(),
    )
    t3 = Transaction(
        user_id=bot_user.id,
        type="income",
        amount=2000000,
        account="Bank Jago",
        category="Pemasukan",
        description="Transfer Masuk",
        date=date.today(),
    )
    db_session.add_all([t1, t2, t3])
    db_session.commit()

    handle_saldo(chat_id=bot_user.telegram_chat_id, db=db_session, user=bot_user)
    assert len(capture_messages) == 1
    text = capture_messages[0]["text"]
    assert "Bank Mandiri" in text
    assert "Rp 4.500.000" in text
    assert "Bank Jago" in text
    assert "Kantong Tagihan" in text
    assert "Total Keseluruhan" in text
    assert "Safe-to-Spend" in text


def test_bot_pacing_and_cycle_bounds(db_session, bot_user, capture_messages):
    today = date.today()
    cfg = PaycheckConfig(
        user_id=bot_user.id,
        cycle_type="monthly_date",
        paycheck_day=today.day,
        cycle_days=30,
        pocket_account="Bank Mandiri",
        source_account="Bank Mandiri",
    )
    db_session.add(cfg)
    acc = Account(user_id=bot_user.id, name="Bank Mandiri", type="operasional", tag="saku")
    db_session.add(acc)

    t_inc = Transaction(
        user_id=bot_user.id,
        type="income",
        amount=3000000,
        account="Bank Mandiri",
        category="Gaji",
        description="Gaji",
        date=today,
    )
    t_exp = Transaction(
        user_id=bot_user.id,
        type="expense",
        amount=300000,
        account="Bank Mandiri",
        category="Makanan",
        description="Makan",
        date=today,
    )
    db_session.add_all([t_inc, t_exp])
    db_session.commit()

    cycle_info = get_user_cycle_info(db_session, bot_user.id)
    assert cycle_info["cycle_start"] <= today <= cycle_info["cycle_end"]
    assert (cycle_info["cycle_end"] - cycle_info["cycle_start"]).days >= 27

    handle_pacing(chat_id=bot_user.telegram_chat_id, db=db_session, user=bot_user)
    assert len(capture_messages) == 1
    text = capture_messages[0]["text"]
    assert "Status Pacing Belanja" in text
    assert "Bank Mandiri" in text
    assert "Burn Rate" in text
    assert "Batas Aman Belanja" in text


def test_bot_subs_yearly_and_exact_date(db_session, bot_user, capture_messages):
    today = date.today()
    s1 = Subscription(
        user_id=bot_user.id,
        name="Spotify Premium",
        amount=55000,
        category="Entertainment",
        account="Bank Jago",
        billing_cycle="monthly",
        billing_type="fixed_day",
        billing_day=today.day,
        is_active=True,
    )
    s2 = Subscription(
        user_id=bot_user.id,
        name="Hosting VPS",
        amount=1200000,
        category="Servers",
        account="Bank Mandiri",
        billing_cycle="yearly",
        billing_type="fixed_day",
        billing_day=15,
        is_active=True,
    )
    s3 = Subscription(
        user_id=bot_user.id,
        name="Domain Name",
        amount=150000,
        category="Tech",
        account="Bank Mandiri",
        billing_type="exact_date",
        exact_due_date=today + timedelta(days=5),
        is_active=True,
    )
    db_session.add_all([s1, s2, s3])
    db_session.commit()

    handle_subs(chat_id=bot_user.telegram_chat_id, db=db_session, user=bot_user)
    assert len(capture_messages) == 1
    text = capture_messages[0]["text"]
    assert "Spotify Premium" in text
    assert "Hosting VPS" in text
    assert "[Tahunan]" in text
    assert "Domain Name" in text
    assert "Total Komitmen Bulanan" in text


def test_bot_gajian_recording_and_allocations(db_session, bot_user, capture_messages):
    acc_main = Account(user_id=bot_user.id, name="Rekening Utama", type="operasional", tag="saku")
    acc_sav = Account(user_id=bot_user.id, name="Tabungan", type="savings", tag="tabungan")
    acc_inv = Account(user_id=bot_user.id, name="Investasi", type="investment", tag="investasi")
    db_session.add_all([acc_main, acc_sav, acc_inv])
    db_session.commit()

    cfg = PaycheckConfig(
        user_id=bot_user.id,
        source_account="Rekening Utama",
        cycle_type="biweekly",
        cycle_days=14,
    )
    db_session.add(cfg)
    db_session.flush()

    b1 = PaycheckBucket(config_id=cfg.id, account="Rekening Utama", percentage=50.0, purpose="Operasional", sort_order=1)
    b2 = PaycheckBucket(config_id=cfg.id, account="Tabungan", percentage=30.0, purpose="Nabung", sort_order=2)
    b3 = PaycheckBucket(config_id=cfg.id, account="Investasi", percentage=20.0, purpose="Investasi", sort_order=3)
    db_session.add_all([b1, b2, b3])
    db_session.commit()

    handle_gajian(chat_id=bot_user.telegram_chat_id, text="/gajian 10000000", db=db_session, user=bot_user)
    assert len(capture_messages) == 1
    text = capture_messages[0]["text"]
    assert "GAJIAN MASUK & ALUR ANGGARAN TERCATAT" in text
    assert "Rekening Utama" in text
    assert "Rp 10.000.000" in text

    # Verify single income transaction recorded
    incomes = db_session.query(Transaction).filter(
        Transaction.user_id == bot_user.id,
        Transaction.type == "income",
    ).all()
    assert len(incomes) == 1
    assert incomes[0].amount == 10000000
    assert incomes[0].account == "Rekening Utama"

    # Verify PaycheckReceipt and secondary transfer allocations
    receipt = db_session.query(PaycheckReceipt).filter(PaycheckReceipt.transaction_id == incomes[0].id).first()
    assert receipt is not None
    allocs = json.loads(receipt.allocations_json)
    assert len(allocs) == 2
    assert {a["amount"] for a in allocs} == {3000000, 2000000}

    # Verify querying status without nominal
    handle_gajian(chat_id=bot_user.telegram_chat_id, text="/gajian", db=db_session, user=bot_user)
    assert len(capture_messages) == 2
    status_text = capture_messages[1]["text"]
    assert "Status Payroll & Gajian Terakhir" in status_text
    assert "Rp 10.000.000" in status_text
    assert "Belum ditransfer" in status_text


def test_bot_transfer_pair_workflow(db_session, bot_user, capture_messages):
    acc1 = Account(user_id=bot_user.id, name="Utama", type="operasional", tag="saku")
    acc2 = Account(user_id=bot_user.id, name="Tabungan", type="savings", tag="tabungan")
    db_session.add_all([acc1, acc2])
    db_session.commit()

    # Initial funding
    t_fund = Transaction(
        user_id=bot_user.id,
        type="income",
        amount=1000000,
        account="Utama",
        category="Gaji",
        description="Setoran Awal",
        date=date.today(),
    )
    db_session.add(t_fund)
    db_session.commit()

    # 1. Guide trigger
    handle_transfer(chat_id=bot_user.telegram_chat_id, text="/transfer", db=db_session, user=bot_user)
    assert len(capture_messages) == 1
    assert "Panduan Transfer Antar Rekening" in capture_messages[0]["text"]
    assert "Utama" in capture_messages[0]["text"]

    # 2. Execute transfer
    handle_transfer(chat_id=bot_user.telegram_chat_id, text="tf 250k Utama ke Tabungan Dana Nikah", db=db_session, user=bot_user)
    assert len(capture_messages) == 2
    success_text = capture_messages[1]["text"]
    assert "Transfer Antar Rekening Berhasil" in success_text
    assert "Rp 250.000" in success_text

    bal_from = get_acc_balance("Utama", db_session, bot_user.id)
    bal_to = get_acc_balance("Tabungan", db_session, bot_user.id)
    assert bal_from == 750000
    assert bal_to == 250000

    # 3. Reject invalid/same account
    handle_transfer(chat_id=bot_user.telegram_chat_id, text="tf 50k Utama ke Utama", db=db_session, user=bot_user)
    assert len(capture_messages) == 3
    assert "tidak boleh sama" in capture_messages[2]["text"]

    handle_transfer(chat_id=bot_user.telegram_chat_id, text="tf 50k AsalAsalan ke Tabungan", db=db_session, user=bot_user)
    assert len(capture_messages) == 4
    assert "tidak dikenali" in capture_messages[3]["text"]


def test_bot_goals_progress_metrics(db_session, bot_user, capture_messages):
    acc = Account(user_id=bot_user.id, name="Bibit", type="investment", tag="investasi")
    db_session.add(acc)
    t = Transaction(
        user_id=bot_user.id,
        type="income",
        amount=3000000,
        account="Bibit",
        category="Investasi",
        description="Top up Bibit",
        date=date.today(),
    )
    db_session.add(t)

    goal = Goal(
        user_id=bot_user.id,
        name="Dana Liburan",
        target_amount=10000000,
        linked_account="Bibit",
        icon="🏖️",
        is_active=True,
    )
    db_session.add(goal)
    db_session.commit()

    handle_goals(chat_id=bot_user.telegram_chat_id, db=db_session, user=bot_user)
    assert len(capture_messages) == 1
    text = capture_messages[0]["text"]
    assert "Dana Liburan" in text
    assert "30.0%" in text
    assert "Rp 3.000.000" in text


def test_bot_rekap_monthly_cashflow(db_session, bot_user, capture_messages):
    today = date.today()
    t_inc = Transaction(user_id=bot_user.id, type="income", amount=2000000, account="Cash", category="Gaji", description="Gaji", date=today)
    t_exp = Transaction(user_id=bot_user.id, type="expense", amount=400000, account="Cash", category="Makanan", description="Makan", date=today)
    t_out = Transaction(user_id=bot_user.id, type="transfer_out", amount=300000, account="Cash", category="Transfer", description="TF", date=today)
    t_in = Transaction(user_id=bot_user.id, type="transfer_in", amount=300000, account="Bank", category="Transfer", description="TF", date=today)
    db_session.add_all([t_inc, t_exp, t_out, t_in])
    db_session.commit()

    handle_rekap(chat_id=bot_user.telegram_chat_id, db=db_session, user=bot_user)
    assert len(capture_messages) == 1
    text = capture_messages[0]["text"]
    assert "Rekap Keuangan" in text
    assert "Total Pemasukan" in text
    assert "Rp 2.000.000" in text
    assert "Total Pengeluaran" in text
    assert "Rp 400.000" in text
    assert "Net Cashflow" in text
    assert "Rp 1.600.000" in text
    assert "Tips: Ketik `/rekap bulan`" in text


def test_bot_rekap_cycle_modes(db_session, bot_user, capture_messages):
    today = date.today()
    # Pemasukan dan pengeluaran di hari ini (siklus aktif)
    t_inc = Transaction(user_id=bot_user.id, type="income", amount=3000000, account="Cash", category="Gaji", description="Gaji Siklus", date=today)
    t_exp = Transaction(user_id=bot_user.id, type="expense", amount=500000, account="Cash", category="Makanan", description="Makan", date=today)
    db_session.add_all([t_inc, t_exp])
    db_session.commit()

    # 1. Mode Siklus Aktif (Default /rekap)
    capture_messages.clear()
    handle_rekap(chat_id=bot_user.telegram_chat_id, db=db_session, text="/rekap", user=bot_user)
    assert len(capture_messages) == 1
    text_cycle = capture_messages[0]["text"]
    assert "Rekap Keuangan" in text_cycle
    assert "Siklus" in text_cycle
    assert "Rp 3.000.000" in text_cycle
    assert "Rp 500.000" in text_cycle
    assert "Safe-to-Spend" in text_cycle

    # 2. Mode Bulan Kalender (/rekap bulan)
    capture_messages.clear()
    handle_rekap(chat_id=bot_user.telegram_chat_id, db=db_session, text="/rekap bulan", user=bot_user)
    assert len(capture_messages) == 1
    text_month = capture_messages[0]["text"]
    assert "Bulan Kalender" in text_month
    assert "Rp 3.000.000" in text_month
    assert "Rp 500.000" in text_month

    # 3. Mode Siklus Lalu (/rekap lalu)
    capture_messages.clear()
    handle_rekap(chat_id=bot_user.telegram_chat_id, db=db_session, text="/rekap lalu", user=bot_user)
    assert len(capture_messages) == 1
    text_prev = capture_messages[0]["text"]
    assert "Siklus Sebelumnya" in text_prev


def test_bot_process_update_command_routing(db_session, bot_user, capture_messages, monkeypatch):
    monkeypatch.setattr("app.bot.bot.SessionLocal", lambda: TestingSessionLocal(expire_on_commit=False))

    payload_pacing = {
        "update_id": 1,
        "message": {
            "message_id": 101,
            "chat": {"id": bot_user.telegram_chat_id, "type": "private"},
            "from": {"id": bot_user.telegram_chat_id},
            "text": "/pacing",
        },
    }
    process_update(payload_pacing)
    assert len(capture_messages) == 1
    assert "Status Pacing Belanja" in capture_messages[0]["text"]

    payload_saldo = {
        "update_id": 2,
        "message": {
            "message_id": 102,
            "chat": {"id": bot_user.telegram_chat_id, "type": "private"},
            "from": {"id": bot_user.telegram_chat_id},
            "text": "💳 Saldo",
        },
    }
    process_update(payload_saldo)
    assert len(capture_messages) == 2
    assert "Estimasi Saldo per Rekening" in capture_messages[1]["text"]

    payload_rekap = {
        "update_id": 3,
        "message": {
            "message_id": 103,
            "chat": {"id": bot_user.telegram_chat_id, "type": "private"},
            "from": {"id": bot_user.telegram_chat_id},
            "text": "📊 Rekap",
        },
    }
    process_update(payload_rekap)
    assert len(capture_messages) == 3
    assert "Rekap Keuangan" in capture_messages[2]["text"]

    payload_rekap_bulan = {
        "update_id": 4,
        "message": {
            "message_id": 104,
            "chat": {"id": bot_user.telegram_chat_id, "type": "private"},
            "from": {"id": bot_user.telegram_chat_id},
            "text": "/rekap bulan",
        },
    }
    process_update(payload_rekap_bulan)
    assert len(capture_messages) == 4
    assert "Bulan Kalender" in capture_messages[3]["text"]
