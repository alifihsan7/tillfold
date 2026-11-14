import pytest
from datetime import date, datetime
import zoneinfo
from unittest.mock import MagicMock

from app.models.user import User
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.internal_loan import InternalLoan
from app.models.paycheck import PaycheckConfig, PaycheckBucket
from app.bot.bot import (
    handle_pinjam,
    handle_lunasi,
    handle_saldo,
    handle_gajian,
    process_update,
    get_acc_balance,
)
from app.services.internal_loans import (
    create_internal_loan,
    settle_internal_loan,
    get_active_internal_loans,
    get_total_active_loan_amount,
)
from app.schemas.internal_loan import InternalLoanCreate
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
        username="alif_bot_user",
        email="alif_bot@ai7.local",
        hashed_password="fakehashedpassword",
        telegram_chat_id=998877,
        full_name="Alif Ihsan",
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def other_user(db_session):
    u = User(
        username="other_bot_user",
        email="other_bot@ai7.local",
        hashed_password="fakehashedpassword",
        telegram_chat_id=112233,
        full_name="Other User",
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def user_accounts(db_session, bot_user):
    acc1 = Account(user_id=bot_user.id, name="BRI 2", tag="Savings")
    acc2 = Account(user_id=bot_user.id, name="Mandiri", tag="Operasional")
    acc3 = Account(user_id=bot_user.id, name="Bank Jago", tag="Pockets")
    acc4 = Account(user_id=bot_user.id, name="Bibit", tag="Investasi")
    db_session.add_all([acc1, acc2, acc3, acc4])
    db_session.commit()

    # Seed initial balances: BRI 2 = 1,000,000, Mandiri = 200,000
    tx1 = Transaction(
        user_id=bot_user.id,
        type="income",
        amount=1000000,
        account="BRI 2",
        category="Gaji",
        description="Saldo awal BRI 2",
        date=date.today(),
    )
    tx2 = Transaction(
        user_id=bot_user.id,
        type="income",
        amount=200000,
        account="Mandiri",
        category="Gaji",
        description="Saldo awal Mandiri",
        date=date.today(),
    )
    db_session.add_all([tx1, tx2])
    db_session.commit()
    return {"bri": acc1, "mandiri": acc2, "jago": acc3, "bibit": acc4}


@pytest.fixture
def capture_messages(monkeypatch):
    messages = []

    def fake_send(chat_id, text, **kwargs):
        messages.append({"chat_id": chat_id, "text": text, "kwargs": kwargs})
        return {"ok": True}

    import app.bot.bot as bot_module

    monkeypatch.setattr(bot_module, "send_message", fake_send)
    return messages


def test_pinjam_no_args_empty(db_session, bot_user, user_accounts, capture_messages):
    """When no active loans exist, /pinjam shows guide and empty status."""
    handle_pinjam(bot_user.telegram_chat_id, "/pinjam", db_session, user=bot_user)
    assert len(capture_messages) == 1
    msg = capture_messages[0]["text"]
    assert "Tidak Ada Dana Talangan Aktif" in msg
    assert "/pinjam <nominal> dari <asal> ke <tujuan>" in msg
    assert "BRI 2" in msg
    assert "Mandiri" in msg


def test_pinjam_success_standard_format(db_session, bot_user, user_accounts, capture_messages):
    """Standard format /pinjam 300k dari BRI 2 ke Mandiri ganti ban bocor."""
    handle_pinjam(
        bot_user.telegram_chat_id,
        "/pinjam 300k dari BRI 2 ke Mandiri ganti ban bocor",
        db_session,
        user=bot_user,
    )
    assert len(capture_messages) == 1
    msg = capture_messages[0]["text"]
    assert "Dana Talangan Berhasil Dicatat" in msg
    assert "ID Pinjaman: #1" in msg
    assert "Nominal: Rp 300.000" in msg
    assert "Dari: BRI 2 (Kreditor)" in msg
    assert "Ke: Mandiri (Debitur)" in msg
    assert "Catatan: ganti ban bocor" in msg
    assert "BRI 2: Rp 700.000" in msg
    assert "Mandiri: Rp 500.000" in msg
    assert "/lunasi 1" in msg

    # Verify DB records
    loan = db_session.query(InternalLoan).filter(InternalLoan.user_id == bot_user.id).first()
    assert loan is not None
    assert loan.id == 1
    assert loan.amount == 300000
    assert loan.remaining_amount == 300000
    assert loan.status == "active"
    assert loan.note == "ganti ban bocor"

    # Verify ledger transactions
    tx_out = db_session.query(Transaction).filter(
        Transaction.user_id == bot_user.id,
        Transaction.type == "transfer_out",
        Transaction.account == "BRI 2",
    ).first()
    tx_in = db_session.query(Transaction).filter(
        Transaction.user_id == bot_user.id,
        Transaction.type == "transfer_in",
        Transaction.account == "Mandiri",
    ).first()
    assert tx_out is not None and tx_out.amount == 300000
    assert tx_in is not None and tx_in.amount == 300000
    assert f"[internal_loan_id:{loan.id}]" in tx_out.raw_text
    assert f"[internal_loan_id:{loan.id}]" in tx_in.raw_text


def test_pinjam_flexible_formats_and_account_aliases(db_session, bot_user, user_accounts, capture_messages):
    """Test flexible patterns: without 'dari', fuzzy alias 'bri2' -> 'BRI 2', and 'jago' -> 'Bank Jago'."""
    # 1. Fuzzy alias 'bri2' without 'dari'
    handle_pinjam(
        bot_user.telegram_chat_id,
        "/pinjam 200k bri2 ke mandiri keperluan mendesak",
        db_session,
        user=bot_user,
    )
    assert len(capture_messages) == 1
    assert "Dana Talangan Berhasil Dicatat" in capture_messages[0]["text"]
    assert "Dari: BRI 2" in capture_messages[0]["text"]
    assert "Ke: Mandiri" in capture_messages[0]["text"]
    assert "Catatan: keperluan mendesak" in capture_messages[0]["text"]

    # 2. Alias 'jago' and prefix 'untuk'
    handle_pinjam(
        bot_user.telegram_chat_id,
        "/talangan 100k dari Mandiri ke jago untuk top up darurat",
        db_session,
        user=bot_user,
    )
    assert len(capture_messages) == 2
    assert "Dari: Mandiri" in capture_messages[1]["text"]
    assert "Ke: Bank Jago" in capture_messages[1]["text"]
    assert "Catatan: top up darurat" in capture_messages[1]["text"]

    # 3. Without note
    handle_pinjam(
        bot_user.telegram_chat_id,
        "/pinjam 50k dari BRI 2 ke Mandiri",
        db_session,
        user=bot_user,
    )
    assert len(capture_messages) == 3
    assert "Dana Talangan Berhasil Dicatat" in capture_messages[2]["text"]


def test_pinjam_validations(db_session, bot_user, user_accounts, capture_messages):
    """Validation test: unknown account, same account, insufficient balance, invalid amount."""
    # 1. Unknown account
    handle_pinjam(bot_user.telegram_chat_id, "/pinjam 100k dari BCA ke Mandiri", db_session, user=bot_user)
    assert "Rekening sumber 'BCA' tidak dikenali" in capture_messages[-1]["text"]

    # 2. Same account
    handle_pinjam(bot_user.telegram_chat_id, "/pinjam 100k dari Mandiri ke Mandiri", db_session, user=bot_user)
    assert "Rekening asal dan tujuan tidak boleh sama" in capture_messages[-1]["text"]

    # 3. Insufficient balance (BRI 2 balance is 1,000,000; asking 5,000,000)
    handle_pinjam(bot_user.telegram_chat_id, "/pinjam 5jt dari BRI 2 ke Mandiri", db_session, user=bot_user)
    assert "tidak mencukupi" in capture_messages[-1]["text"]

    # 4. Invalid amount
    handle_pinjam(bot_user.telegram_chat_id, "/pinjam gratis dari BRI 2 ke Mandiri", db_session, user=bot_user)
    assert "Format perintah talangan tidak dikenali" in capture_messages[-1]["text"] or "tidak valid" in capture_messages[-1]["text"]


def test_pinjam_no_args_with_active_loans(db_session, bot_user, user_accounts, capture_messages):
    """When active loans exist, /pinjam without args lists all active loans with summary."""
    # Create two loans
    handle_pinjam(bot_user.telegram_chat_id, "/pinjam 300k dari BRI 2 ke Mandiri ban bocor", db_session, user=bot_user)
    handle_pinjam(bot_user.telegram_chat_id, "/pinjam 150k dari BRI 2 ke Mandiri beli bensin", db_session, user=bot_user)
    capture_messages.clear()

    handle_pinjam(bot_user.telegram_chat_id, "/pinjam", db_session, user=bot_user)
    assert len(capture_messages) == 1
    msg = capture_messages[0]["text"]
    assert "Daftar Dana Talangan Internal Aktif" in msg
    assert "Pinjaman #1" in msg
    assert "Pinjaman #2" in msg
    assert "Total Dana Talangan Belum Dilunasi:" in msg
    assert "Rp 450.000" in msg
    assert "/lunasi" in msg


def test_lunasi_no_args(db_session, bot_user, user_accounts, capture_messages):
    """Test /lunasi without arguments."""
    # When empty
    handle_lunasi(bot_user.telegram_chat_id, "/lunasi", db_session, user=bot_user)
    assert "Tidak Ada Pinjaman Aktif" in capture_messages[-1]["text"]

    # When loans exist
    handle_pinjam(bot_user.telegram_chat_id, "/pinjam 300k dari BRI 2 ke Mandiri", db_session, user=bot_user)
    capture_messages.clear()

    handle_lunasi(bot_user.telegram_chat_id, "/lunasi", db_session, user=bot_user)
    assert "Daftar Dana Talangan yang Perlu Dilunasi" in capture_messages[-1]["text"]
    assert "#1" in capture_messages[-1]["text"]
    assert "Mandiri" in capture_messages[-1]["text"]
    assert "Rp 300.000" in capture_messages[-1]["text"]


def test_lunasi_full_settlement(db_session, bot_user, user_accounts, capture_messages):
    """Test full settlement: /lunasi 1 without amount."""
    handle_pinjam(bot_user.telegram_chat_id, "/pinjam 300k dari BRI 2 ke Mandiri ganti ban", db_session, user=bot_user)
    capture_messages.clear()

    # Mandiri received 300k (200k + 300k = 500k). Settle 300k back to BRI 2.
    handle_lunasi(bot_user.telegram_chat_id, "/lunasi 1", db_session, user=bot_user)
    assert len(capture_messages) == 1
    msg = capture_messages[0]["text"]
    assert "Pelunasan Dana Talangan Berhasil" in msg
    assert "ID Pinjaman: #1" in msg
    assert "Nominal Dilunasi: Rp 300.000" in msg
    assert "LUNAS" in msg
    assert "Mandiri: Rp 200.000" in msg
    assert "BRI 2: Rp 1.000.000" in msg

    # Verify DB state
    loan = db_session.get(InternalLoan, 1)
    assert loan.remaining_amount == 0
    assert loan.status == "settled"
    assert loan.settled_at is not None


def test_lunasi_partial_settlement(db_session, bot_user, user_accounts, capture_messages):
    """Test partial settlement: /lunasi 1 100k, then /bayar_pinjam 1 200k."""
    handle_pinjam(bot_user.telegram_chat_id, "/pinjam 300k dari BRI 2 ke Mandiri talangan servis", db_session, user=bot_user)
    capture_messages.clear()

    # Partial 1: Pay 100k
    handle_lunasi(bot_user.telegram_chat_id, "/lunasi 1 100k", db_session, user=bot_user)
    assert "Nominal Dilunasi: Rp 100.000" in capture_messages[-1]["text"]
    assert "Sisa: Rp 200.000" in capture_messages[-1]["text"]

    loan = db_session.get(InternalLoan, 1)
    assert loan.remaining_amount == 200000
    assert loan.status == "active"

    # Partial 2: Pay remaining 200k via /bayar_pinjam alias
    handle_lunasi(bot_user.telegram_chat_id, "/bayar_pinjam 1 200k", db_session, user=bot_user)
    assert "Nominal Dilunasi: Rp 200.000" in capture_messages[-1]["text"]
    assert "LUNAS" in capture_messages[-1]["text"]

    db_session.refresh(loan)
    assert loan.remaining_amount == 0
    assert loan.status == "settled"


def test_lunasi_validations(db_session, bot_user, user_accounts, capture_messages):
    """Test /lunasi edge cases: invalid ID, not found, already settled, insufficient debtor balance."""
    # 1. Invalid ID
    handle_lunasi(bot_user.telegram_chat_id, "/lunasi abc", db_session, user=bot_user)
    assert "ID pinjaman tidak valid" in capture_messages[-1]["text"]

    # 2. Not found
    handle_lunasi(bot_user.telegram_chat_id, "/lunasi 999", db_session, user=bot_user)
    assert "tidak ditemukan" in capture_messages[-1]["text"]

    # 3. Create loan and settle it
    handle_pinjam(bot_user.telegram_chat_id, "/pinjam 100k dari BRI 2 ke Mandiri", db_session, user=bot_user)
    handle_lunasi(bot_user.telegram_chat_id, "/lunasi 1", db_session, user=bot_user)
    capture_messages.clear()

    # Try settling again
    handle_lunasi(bot_user.telegram_chat_id, "/lunasi 1", db_session, user=bot_user)
    assert "sudah tidak aktif" in capture_messages[-1]["text"]

    # 4. Insufficient debtor balance
    # Drain Mandiri balance with an expense
    drain_tx = Transaction(
        user_id=bot_user.id,
        type="expense",
        amount=200000,
        account="Mandiri",
        category="Makanan",
        description="Drain",
        date=date.today(),
    )
    db_session.add(drain_tx)
    db_session.commit()

    # Now borrow 100k from BRI 2 to Mandiri, and drain Mandiri to 0
    handle_pinjam(bot_user.telegram_chat_id, "/pinjam 100k dari BRI 2 ke Mandiri", db_session, user=bot_user)
    drain_tx2 = Transaction(
        user_id=bot_user.id,
        type="expense",
        amount=100000,
        account="Mandiri",
        category="Makanan",
        description="Drain all",
        date=date.today(),
    )
    db_session.add(drain_tx2)
    db_session.commit()
    capture_messages.clear()

    # Mandiri balance is 0. Try to settle loan #2 (100k)
    handle_lunasi(bot_user.telegram_chat_id, "/lunasi 2", db_session, user=bot_user)
    assert "tidak mencukupi" in capture_messages[-1]["text"]


def test_saldo_active_loan_warning(db_session, bot_user, user_accounts, capture_messages):
    """Test /saldo shows active internal loan warning only when loans exist."""
    # 1. No active loans -> no warning
    handle_saldo(bot_user.telegram_chat_id, db_session, user=bot_user)
    assert len(capture_messages) == 1
    assert "Dana Talangan Aktif:" not in capture_messages[0]["text"]

    # 2. Create active loan of 300k
    handle_pinjam(bot_user.telegram_chat_id, "/pinjam 300k dari BRI 2 ke Mandiri", db_session, user=bot_user)
    capture_messages.clear()

    handle_saldo(bot_user.telegram_chat_id, db_session, user=bot_user)
    assert len(capture_messages) == 1
    msg = capture_messages[0]["text"]
    assert "⚠️ **Dana Talangan Aktif:** Rp 300.000" in msg
    assert "(Ketik /pinjam untuk melihat rincian kewajiban)" in msg

    # 3. Settle loan -> warning disappears
    handle_lunasi(bot_user.telegram_chat_id, "/lunasi 1", db_session, user=bot_user)
    capture_messages.clear()

    handle_saldo(bot_user.telegram_chat_id, db_session, user=bot_user)
    assert "Dana Talangan Aktif:" not in capture_messages[0]["text"]


def test_gajian_active_debt_reminder(db_session, bot_user, user_accounts, capture_messages):
    """Test /gajian includes recommendation when paycheck receiver account is an active debtor."""
    # Mandiri receives gajian
    cfg = PaycheckConfig(user_id=bot_user.id, source_account="Mandiri", cycle_type="biweekly", cycle_days=14)
    db_session.add(cfg)
    db_session.commit()
    db_session.refresh(cfg)
    b1 = PaycheckBucket(config_id=cfg.id, account="Mandiri", percentage=50, purpose="Operasional")
    b2 = PaycheckBucket(config_id=cfg.id, account="BRI 2", percentage=50, purpose="Tabungan")
    db_session.add_all([b1, b2])
    db_session.commit()

    # Create active loan where Mandiri (debtor) owes 300k to BRI 2 (creditor)
    handle_pinjam(bot_user.telegram_chat_id, "/pinjam 300k dari BRI 2 ke Mandiri servis motor", db_session, user=bot_user)
    capture_messages.clear()

    # 1. Status view /gajian
    handle_gajian(bot_user.telegram_chat_id, "/gajian", db_session, user=bot_user)
    assert "Pengingat Dana Talangan Internal:" in capture_messages[0]["text"]
    assert "Rekening `Mandiri` memiliki kewajiban talangan aktif sebesar **Rp 300.000**" in capture_messages[0]["text"]
    assert "/lunasi" in capture_messages[0]["text"]

    # 2. Record new salary /gajian 5.000.000
    capture_messages.clear()
    handle_gajian(bot_user.telegram_chat_id, "/gajian 5.000.000", db_session, user=bot_user)
    assert len(capture_messages) == 1
    msg = capture_messages[0]["text"]
    assert "GAJIAN MASUK & ALUR ANGGARAN TERCATAT!" in msg
    assert "Pengingat Pelunasan Dana Talangan Internal:" in msg
    assert "Rekening operasional `Mandiri` memiliki kewajiban talangan aktif sebesar **Rp 300.000**" in msg
    assert "Pinjaman #1: Rp 300.000 ke `BRI 2`" in msg
    assert "Kembalikan uang dingin segera" in msg
    assert "/lunasi <ID>" in msg


def test_tenant_isolation_internal_loans_bot(db_session, bot_user, other_user, user_accounts, capture_messages):
    """User 2 cannot see or settle User 1's internal loans."""
    # User 1 creates loan #1
    handle_pinjam(bot_user.telegram_chat_id, "/pinjam 300k dari BRI 2 ke Mandiri", db_session, user=bot_user)
    capture_messages.clear()

    # User 2 calls /pinjam
    handle_pinjam(other_user.telegram_chat_id, "/pinjam", db_session, user=other_user)
    assert "Tidak Ada Dana Talangan Aktif" in capture_messages[0]["text"]

    # User 2 attempts to settle loan #1
    handle_lunasi(other_user.telegram_chat_id, "/lunasi 1", db_session, user=other_user)
    assert "tidak ditemukan" in capture_messages[1]["text"]


def test_bot_process_update_command_routing_internal_loans(db_session, bot_user, user_accounts, capture_messages, monkeypatch):
    """Test process_update webhook routing for /pinjam and /lunasi commands."""
    monkeypatch.setattr("app.bot.bot.SessionLocal", lambda: TestingSessionLocal(expire_on_commit=False))

    # 1. Routing /pinjam
    payload_pinjam = {
        "update_id": 1,
        "message": {
            "message_id": 201,
            "chat": {"id": bot_user.telegram_chat_id, "type": "private"},
            "from": {"id": bot_user.telegram_chat_id},
            "text": "/pinjam 250k dari BRI 2 ke Mandiri tambal ban",
        },
    }
    process_update(payload_pinjam)
    assert len(capture_messages) == 1
    assert "Dana Talangan Berhasil Dicatat" in capture_messages[0]["text"]
    assert "Rp 250.000" in capture_messages[0]["text"]

    # 2. Routing /lunasi
    payload_lunasi = {
        "update_id": 2,
        "message": {
            "message_id": 202,
            "chat": {"id": bot_user.telegram_chat_id, "type": "private"},
            "from": {"id": bot_user.telegram_chat_id},
            "text": "/lunasi 1",
        },
    }
    process_update(payload_lunasi)
    assert len(capture_messages) == 2
    assert "Pelunasan Dana Talangan Berhasil" in capture_messages[1]["text"]
    assert "LUNAS" in capture_messages[1]["text"]
