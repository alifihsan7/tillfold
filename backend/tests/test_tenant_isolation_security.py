import pytest
from datetime import date
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.user import User
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.paycheck import PaycheckConfig, PaycheckBucket
from app.models.subscription import Subscription
from app.models.goal import Goal
from app.models.category import Category
from app.core.config import settings

from app.bot.bot import (
    process_update,
    handle_start,
    handle_rekap,
    handle_saldo,
    handle_pacing,
    handle_obsidian,
    handle_transaksi,
    handle_subs,
    handle_goals,
    handle_transfer,
    handle_batal,
    handle_gajian,
    handle_sheets,
    handle_text_message,
    handle_media_message,
    get_user_cycle_info,
    get_safe_to_spend_snippet,
    get_acc_balance,
)
from app.services.sheets_sync import sync_cycle_snapshot
from app.api.v1.endpoints.auth import delete_my_account

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
def user_one(db_session):
    u = User(
        id=1,
        username="alif",
        full_name="Alif Ihsan",
        hashed_password="hash",
        telegram_chat_id=111111,
        telegram_mode="custom",
        telegram_bot_token="111111:OWNER_BOT_TOKEN",
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u

@pytest.fixture
def user_two(db_session):
    u = User(
        id=2,
        username="tenant2",
        full_name="Tenant Dua",
        hashed_password="hash",
        telegram_chat_id=222222,
        telegram_mode="custom",
        telegram_bot_token="222222:OTHER_BOT_TOKEN",
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


# ============================================================================
# SEC-TENANT-01: Telegram BYOB Webhook Authorization Guard
# ============================================================================

def test_byob_webhook_unauthorized_sender_rejected(user_one):
    """
    Update arriving at a BYOB bot (user_override=user_one) from an unauthorized
    chat_id must be rejected immediately, logging a warning and not executing.
    """
    update = {
        "update_id": 100,
        "message": {
            "message_id": 1,
            "from": {"id": 999999, "username": "attacker"},
            "chat": {"id": 999999},
            "text": "makan padang 50k",
        }
    }

    with patch("app.bot.bot.SessionLocal", return_value=TestingSessionLocal()), \
         patch("app.bot.bot.send_message") as mock_send, \
         patch("app.bot.bot.logger.warning") as mock_warn:

        process_update(update, bot_token=user_one.telegram_bot_token, user_override=user_one)

        mock_send.assert_not_called()

    # Verify no transactions were created in DB
    db = TestingSessionLocal()
    assert db.query(Transaction).count() == 0
    db.close()

def test_retired_custom_bot_rejects_even_its_owner(user_one):
    """
    Custom bot credentials are retired even for the former owner.
    """
    update = {
        "update_id": 101,
        "message": {
            "message_id": 2,
            "from": {"id": 111111, "username": "alif"},
            "chat": {"id": 111111},
            "text": "/saldo",
        }
    }

    with patch("app.bot.bot.SessionLocal", return_value=TestingSessionLocal()), \
         patch("app.bot.bot.send_message") as mock_send:

        process_update(update, bot_token=user_one.telegram_bot_token, user_override=user_one)

        mock_send.assert_not_called()


# ============================================================================
# SEC-TENANT-02: Elimination of Permissive Fallback (user_id = user.id if user else 1)
# ============================================================================

def test_handlers_reject_none_user(db_session):
    """
    All bot handlers must reject execution when user is None rather than falling back to user 1.
    """
    handlers = [
        lambda send_mock: handle_start(chat_id=123, user=None),
        lambda send_mock: handle_rekap(chat_id=123, db=db_session, user=None),
        lambda send_mock: handle_saldo(chat_id=123, db=db_session, user=None),
        lambda send_mock: handle_pacing(chat_id=123, db=db_session, user=None),
        lambda send_mock: handle_obsidian(chat_id=123, db=db_session, user=None),
        lambda send_mock: handle_transaksi(chat_id=123, db=db_session, user=None),
        lambda send_mock: handle_subs(chat_id=123, db=db_session, user=None),
        lambda send_mock: handle_goals(chat_id=123, db=db_session, user=None),
        lambda send_mock: handle_transfer(chat_id=123, text="tf 50k mandiri ke bri 1", db=db_session, user=None),
        lambda send_mock: handle_batal(chat_id=123, db=db_session, user=None),
        lambda send_mock: handle_gajian(chat_id=123, text="/gajian 1000000", db=db_session, user=None),
        lambda send_mock: handle_sheets(chat_id=123, db=db_session, user=None),
        lambda send_mock: handle_text_message(chat_id=123, text="nasi goreng 20k", message_id=1, db=db_session, user=None),
        lambda send_mock: handle_media_message(chat_id=123, message={"photo": [{"file_id": "xyz"}]}, message_id=1, db=db_session, user=None),
    ]

    for h in handlers:
        with patch("app.bot.bot.send_message") as mock_send:
            h(mock_send)
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == 123
            assert "Pengguna tidak ditemukan" in call_args[0][1]

    # Database must remain untouched
    assert db_session.query(Transaction).count() == 0


def test_helper_functions_require_explicit_user_id(db_session, user_one):
    """
    Helper functions in bot.py must not silently default user_id to 1.
    """
    import inspect
    sig_cycle = inspect.signature(get_user_cycle_info)
    assert sig_cycle.parameters["user_id"].default is inspect.Parameter.empty

    sig_safe = inspect.signature(get_safe_to_spend_snippet)
    assert sig_safe.parameters["user_id"].default is inspect.Parameter.empty

    sig_bal = inspect.signature(get_acc_balance)
    assert sig_bal.parameters["user_id"].default is inspect.Parameter.empty


# ============================================================================
# SEC-TENANT-05 / SEC-TENANT-06: Multi-Tenant Isolation in sheets_sync.py
# ============================================================================

def test_sync_cycle_snapshot_tenant_isolation(db_session, user_one, user_two):
    """
    sync_cycle_snapshot must only query and aggregate data belonging to the requested user_id.
    """
    # Setup User 1 data
    cfg1 = PaycheckConfig(id=1, user_id=1, pocket_account="Mandiri", cycle_days=14, cycle_start_date=date.today())
    tx1_inc = Transaction(user_id=1, type="income", amount=1500000, account="Mandiri", category="Gajian", description="Gajian Masuk", date=date.today())
    tx1_exp = Transaction(user_id=1, type="expense", amount=250000, account="Mandiri", category="Makan", description="Makan Siang", date=date.today())
    bucket1 = PaycheckBucket(config_id=1, account="Mandiri", percentage=50, purpose="Saku", category="Gajian")
    acc1 = Account(user_id=1, name="Mandiri", type="operasional", tag="Saku Mandiri", initial_balance=0)

    # Setup User 2 data (must NOT leak into User 1's snapshot)
    cfg2 = PaycheckConfig(id=2, user_id=2, pocket_account="Bank Jago", cycle_days=30, cycle_start_date=date.today())
    tx2_inc = Transaction(user_id=2, type="income", amount=8000000, account="Bank Jago", category="Gajian", description="Gajian Lain", date=date.today())
    tx2_exp = Transaction(user_id=2, type="expense", amount=3500000, account="Bank Jago", category="Belanja", description="Belanja Elektronik", date=date.today())
    bucket2 = PaycheckBucket(config_id=2, account="Bank Jago", percentage=60, purpose="Saku Jago", category="Gajian")
    acc2 = Account(user_id=2, name="Bank Jago", type="operasional", tag="Saku Jago", initial_balance=0)

    db_session.add_all([cfg1, tx1_inc, tx1_exp, bucket1, acc1, cfg2, tx2_inc, tx2_exp, bucket2, acc2])
    db_session.commit()

    user_one.google_spreadsheet_id = "test_sheet_id_one"
    user_two.google_spreadsheet_id = "test_sheet_id_two"
    db_session.commit()

    # Mock Google Sheets API to avoid external network dependency
    mock_ws = MagicMock()
    mock_ws.id = 12345
    mock_ws.row_count = 100
    mock_ws.title = "Sheet1"

    mock_doc = MagicMock()
    mock_doc.worksheets.return_value = [mock_ws]
    mock_client = MagicMock()
    mock_client.open_by_key.return_value = mock_doc

    with patch("app.services.sheets_sync.get_google_sheets_client", return_value=mock_client):

        res = sync_cycle_snapshot(db_session, user_id=1, cycle_start_date=date.today())

        assert res["success"] is True
        mock_client.open_by_key.assert_called_with("test_sheet_id_one")
        # User 1 has exactly 2 transactions; User 2's transactions must not be counted
        assert res["transaction_count"] == 2
        # User 1 spent 250,000; User 2's 3,500,000 must NOT be included
        assert res["pocket_spent"] == 250000
        # Net balance for User 1: 1,500,000 - 250,000 = 1,250,000
        assert res["total_balance"] == 1250000

        # User 2 sync also opens user 2's sheet
        res2 = sync_cycle_snapshot(db_session, user_id=2, cycle_start_date=date.today())
        assert res2["success"] is True
        mock_client.open_by_key.assert_called_with("test_sheet_id_two")
        assert res2["transaction_count"] == 2
        assert res2["pocket_spent"] == 3500000


# ============================================================================
# SEC-TENANT-06: deleteWebhook execution on delete_my_account
# ============================================================================

def test_delete_my_account_ignores_retired_custom_bot(db_session, user_one):
    """
    Account deletion does not contact retired custom bots.
    """
    assert user_one.telegram_bot_token is not None

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"ok": True}

        res = delete_my_account(current_user=user_one, db=db_session)
        assert res["success"] is True

        mock_post.assert_not_called()

    # User must be deleted
    assert db_session.query(User).filter(User.id == user_one.id).first() is None


def test_delete_my_account_skips_webhook_if_no_bot_token(db_session):
    """
    When deleting an account without a custom bot token, deleteWebhook should not be called.
    """
    user_no_token = User(
        id=3,
        username="user3",
        full_name="User Tiga",
        hashed_password="hash",
        telegram_chat_id=333333,
        telegram_mode="shared",
        telegram_bot_token=None,
        is_active=True,
    )
    db_session.add(user_no_token)
    db_session.commit()

    with patch("requests.post") as mock_post:
        res = delete_my_account(current_user=user_no_token, db=db_session)
        assert res["success"] is True
        mock_post.assert_not_called()

    assert db_session.query(User).filter(User.id == 3).first() is None
