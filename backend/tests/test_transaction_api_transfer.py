import pytest
from datetime import date
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.models.user import User
from app.models.transaction import Transaction
from app.models.account import Account
from app.models.paycheck import PaycheckConfig, PaycheckBucket
from app.api.deps import get_current_user
from app.bot.bot import handle_batal
from app.api.v1.endpoints.transactions import router

app = FastAPI()
app.include_router(router, prefix="/api/v1/transactions")

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
def test_user(db_session):
    user = User(
        id=1,
        username="testuser",
        hashed_password="dummy_hashed_password",
        telegram_chat_id=123456,
        full_name="Test User",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add_all([Account(user_id=user.id, name=name, type="operasional", initial_balance=0)
                        for name in ("Mandiri", "BRI 1", "Bank Jago", "Bibit")])
    db_session.commit()
    return user

@pytest.fixture
def client(test_user, db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_transaction_type_whitelist_rejection(client):
    """TransactionBase memvalidasi whitelist tipe transaksi dan menolak tipe ilegal dengan HTTP 422."""
    # Illegal transaction types must be rejected with HTTP 422
    for illegal_type in ["deposit", "withdrawal", "unknown", "hutang"]:
        payload = {
            "type": illegal_type,
            "amount": 25000,
            "account": "Mandiri",
            "category": "Makanan & Minuman",
            "description": "Nasi Goreng"
        }
        res = client.post("/api/v1/transactions", json=payload)
        assert res.status_code == 422, f"Type '{illegal_type}' should be rejected with 422, got {res.status_code}"

    # Valid transaction types must be accepted
    for valid_type in ["expense", "income"]:
        payload = {
            "type": valid_type,
            "amount": 25000,
            "account": "Mandiri",
            "category": "Makanan & Minuman",
            "description": f"Valid {valid_type}"
        }
        res = client.post("/api/v1/transactions", json=payload)
        assert res.status_code == 200, f"Type '{valid_type}' should be accepted with 200, got {res.status_code}"
        assert res.json()["type"] == valid_type


def test_transaction_amount_boundaries(client):
    """Nominal transaksi dibatasi eksplisit (le=9_000_000_000_000_000) dan gt=0."""
    # Boundary: Exactly maximum allowed amount
    payload_max = {
        "type": "income",
        "amount": 9_000_000_000_000_000,
        "account": "BRI 1",
        "category": "Gaji",
        "description": "Max allowed amount"
    }
    res_max = client.post("/api/v1/transactions", json=payload_max)
    assert res_max.status_code == 200
    assert res_max.json()["amount"] == 9_000_000_000_000_000

    # Overflow: 1 above maximum allowed
    payload_overflow = {
        "type": "income",
        "amount": 9_000_000_000_000_001,
        "account": "BRI 1",
        "category": "Gaji",
        "description": "Overflow amount"
    }
    res_overflow = client.post("/api/v1/transactions", json=payload_overflow)
    assert res_overflow.status_code == 422

    # Zero amount
    payload_zero = {
        "type": "expense",
        "amount": 0,
        "account": "Mandiri",
        "category": "Makanan",
        "description": "Zero amount"
    }
    res_zero = client.post("/api/v1/transactions", json=payload_zero)
    assert res_zero.status_code == 422

    # Negative amount
    payload_neg = {
        "type": "expense",
        "amount": -5000,
        "account": "Mandiri",
        "category": "Makanan",
        "description": "Negative amount"
    }
    res_neg = client.post("/api/v1/transactions", json=payload_neg)
    assert res_neg.status_code == 422


def test_transfer_creation_and_paired_cascade_deletion(client, db_session, test_user):
    """Menghapus transfer_out otomatis menghapus transfer_in pasangannya tanpa orphan transfer."""
    transfer_payload = {
        "from_account": "Mandiri",
        "to_account": "Bank Jago",
        "amount": 250000,
        "description": "Top up saldo pos langganan"
    }
    res = client.post("/api/v1/transactions/transfer", json=transfer_payload)
    assert res.status_code == 200
    data = res.json()
    out_id = data["out_transaction_id"]
    in_id = data["in_transaction_id"]

    # Verify both transactions exist in the database
    out_tx = db_session.query(Transaction).filter(Transaction.id == out_id).first()
    in_tx = db_session.query(Transaction).filter(Transaction.id == in_id).first()
    assert out_tx is not None
    assert in_tx is not None
    assert out_tx.type == "transfer_out"
    assert in_tx.type == "transfer_in"

    # Delete from the 'transfer_out' side
    del_res = client.delete(f"/api/v1/transactions/{out_id}")
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["success"] is True
    assert in_id in del_data["deleted_ids"]
    assert out_id in del_data["deleted_ids"]

    # Verify neither transaction remains in the database (no orphan transfer)
    remaining_count = db_session.query(Transaction).filter(Transaction.id.in_([out_id, in_id])).count()
    assert remaining_count == 0


def test_transfer_paired_cascade_deletion_from_in_side(client, db_session, test_user):
    """Menghapus transfer_in otomatis menghapus transfer_out pasangannya secara simetris."""
    transfer_payload = {
        "from_account": "BRI 1",
        "to_account": "Bibit",
        "amount": 1000000,
        "description": "Investasi Bibit bulanan"
    }
    res = client.post("/api/v1/transactions/transfer", json=transfer_payload)
    assert res.status_code == 200
    data = res.json()
    out_id = data["out_transaction_id"]
    in_id = data["in_transaction_id"]

    # Delete from the 'transfer_in' side
    del_res = client.delete(f"/api/v1/transactions/{in_id}")
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["success"] is True
    assert out_id in del_data["deleted_ids"]

    # Both deleted cleanly
    assert db_session.query(Transaction).filter(Transaction.id.in_([out_id, in_id])).count() == 0


def test_transfer_cascade_deletion_legacy_unlinked(client, db_session, test_user):
    """Transfér lawas tanpa tag pair_id tetap terhapus berpasangan via ID berdekatan / atribut transaksi."""
    today = date(2026, 4, 1)
    tx_out = Transaction(
        user_id=test_user.id,
        type="transfer_out",
        amount=300000,
        account="Mandiri",
        category="Transfer",
        description="Transfer ke BCA: Legacy unlinked",
        raw_text="transfer out: Mandiri -> BCA",
        date=today
    )
    tx_in = Transaction(
        user_id=test_user.id,
        type="transfer_in",
        amount=300000,
        account="BCA",
        category="Transfer",
        description="Transfer dari Mandiri: Legacy unlinked",
        raw_text="transfer in: Mandiri -> BCA",
        date=today
    )
    db_session.add(tx_out)
    db_session.add(tx_in)
    db_session.commit()
    db_session.refresh(tx_out)
    db_session.refresh(tx_in)

    # Delete tx_out
    del_res = client.delete(f"/api/v1/transactions/{tx_out.id}")
    assert del_res.status_code == 200
    assert db_session.query(Transaction).filter(Transaction.id.in_([tx_out.id, tx_in.id])).count() == 0


def test_paycheck_split_updates_cycle_start_date(client, db_session, test_user):
    """Eksekusi /paycheck memperbarui cfg.cycle_start_date ke tanggal transaksi bersangkutan."""
    cfg = PaycheckConfig(
        user_id=test_user.id,
        source_account="BRI 1",
        cycle_days=14,
        cycle_start_date=date(2026, 1, 1),
        pocket_account="Mandiri"
    )
    db_session.add(cfg)
    db_session.commit()

    target_date = "2026-04-25"
    payload = {
        "total_amount": 1500000,
        "date": target_date,
        "note": "Gajian Siklus Baru"
    }
    res = client.post("/api/v1/transactions/paycheck", json=payload)
    assert res.status_code == 200

    db_session.refresh(cfg)
    assert cfg.cycle_start_date == date(2026, 4, 25), f"Expected 2026-04-25, got {cfg.cycle_start_date}"


def test_bot_handle_batal_paired_transfer(db_session, test_user):
    """handle_batal bot Telegram membatalkan mutasi transfer berpasangan secara atomik."""
    today = date(2026, 4, 20)
    tx_out = Transaction(
        user_id=test_user.id,
        type="transfer_out",
        amount=150000,
        account="Mandiri",
        category="Transfer",
        description="Transfer ke Cash: Tarik tunai ATM",
        raw_text="bot transfer: tarik tunai 150k [pair_id:999]",
        date=today
    )
    tx_in = Transaction(
        user_id=test_user.id,
        type="transfer_in",
        amount=150000,
        account="Cash",
        category="Transfer",
        description="Transfer dari Mandiri: Tarik tunai ATM",
        raw_text="bot transfer: tarik tunai 150k",
        date=today
    )
    db_session.add(tx_out)
    db_session.add(tx_in)
    db_session.flush()
    # Correct the pair_id tag
    tx_out.raw_text = f"bot transfer: tarik tunai 150k [pair_id:{tx_in.id}]"
    tx_in.raw_text = f"bot transfer: tarik tunai 150k [pair_id:{tx_out.id}]"
    db_session.commit()

    # Call handle_batal (mocking send_message)
    messages_sent = []
    def mock_send_message(chat_id, text, **kwargs):
        messages_sent.append(text)

    import app.bot.bot as bot_module
    orig_send = bot_module.send_message
    bot_module.send_message = mock_send_message

    try:
        handle_batal(chat_id=test_user.telegram_chat_id, db=db_session, user=test_user)
        # Verify both transactions deleted
        assert db_session.query(Transaction).filter(Transaction.id.in_([tx_out.id, tx_in.id])).count() == 0
        assert len(messages_sent) == 1
        assert "Transfer Berpasangan Berhasil Dibatalkan" in messages_sent[0]
    finally:
        bot_module.send_message = orig_send
