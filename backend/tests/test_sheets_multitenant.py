import pytest
from datetime import date
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from gspread.exceptions import APIError, SpreadsheetNotFound

from app.db.session import Base
from app.models.user import User
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.paycheck import PaycheckConfig
from app.core.helpers import extract_spreadsheet_id
from app.db.user_schema import ensure_user_spreadsheet_schema
from app.services.sheets_sync import sync_cycle_snapshot
from app.bot.bot import handle_set_sheet, handle_sheets
from app.api.deps import get_db, get_strict_current_user, get_current_user
from main import app

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
    ensure_user_spreadsheet_schema(engine)
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
    u = User(
        id=42,
        username="universal_user",
        full_name="Universal User",
        email="universal@example.com",
        hashed_password="hashed_pw",
        telegram_chat_id=888888,
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


# ============================================================================
# 1. Regex URL Parser Unit Tests
# ============================================================================

def test_extract_spreadsheet_id_full_url():
    url = "https://docs.google.com/spreadsheets/d/1yq0SQLZ9QVUTeRksKNJtDKTyDGxUKn5fkUVnBxplhn4/edit?usp=sharing"
    assert extract_spreadsheet_id(url) == "1yq0SQLZ9QVUTeRksKNJtDKTyDGxUKn5fkUVnBxplhn4"

    url_hash = "https://docs.google.com/spreadsheets/d/1yq0SQLZ9QVUTeRksKNJtDKTyDGxUKn5fkUVnBxplhn4/edit#gid=12345"
    assert extract_spreadsheet_id(url_hash) == "1yq0SQLZ9QVUTeRksKNJtDKTyDGxUKn5fkUVnBxplhn4"

    url_bare = "https://docs.google.com/spreadsheets/d/1yq0SQLZ9QVUTeRksKNJtDKTyDGxUKn5fkUVnBxplhn4"
    assert extract_spreadsheet_id(url_bare) == "1yq0SQLZ9QVUTeRksKNJtDKTyDGxUKn5fkUVnBxplhn4"


def test_extract_spreadsheet_id_raw_or_trimmed():
    raw_id = "1yq0SQLZ9QVUTeRksKNJtDKTyDGxUKn5fkUVnBxplhn4"
    assert extract_spreadsheet_id(raw_id) == raw_id
    assert extract_spreadsheet_id(f"  {raw_id}  \n") == raw_id
    assert extract_spreadsheet_id("") == ""
    assert extract_spreadsheet_id(None) == ""


# ============================================================================
# 2. Schema Auto-Migration Idempotency
# ============================================================================

def test_ensure_user_spreadsheet_schema_idempotent():
    ensure_user_spreadsheet_schema(engine)
    ensure_user_spreadsheet_schema(engine)


# ============================================================================
# 3. Service Level Sync & Tenant Isolation
# ============================================================================

def test_sync_cycle_snapshot_without_sheet_raises_friendly_error(db_session, test_user):
    test_user.google_spreadsheet_id = None
    db_session.commit()

    with pytest.raises(ValueError) as excinfo:
        sync_cycle_snapshot(db_session, user_id=test_user.id, cycle_start_date=date.today())

    assert "Google Spreadsheet belum ditautkan" in str(excinfo.value)
    assert "/set_sheet" in str(excinfo.value)


def test_sync_cycle_snapshot_multi_tenant_isolation(db_session):
    u1 = User(id=101, username="tenant_a", full_name="Tenant A", hashed_password="pw", is_active=True, google_spreadsheet_id="sheet_aaa")
    u2 = User(id=102, username="tenant_b", full_name="Tenant B", hashed_password="pw", is_active=True, google_spreadsheet_id="sheet_bbb")
    db_session.add_all([u1, u2])
    db_session.commit()

    mock_ws = MagicMock()
    mock_ws.id = 1
    mock_ws.row_count = 100
    mock_ws.title = "Sheet1"

    mock_doc = MagicMock()
    mock_doc.worksheets.return_value = [mock_ws]
    mock_client = MagicMock()
    mock_client.open_by_key.return_value = mock_doc

    with patch("app.services.sheets_sync.get_google_sheets_client", return_value=mock_client):
        res1 = sync_cycle_snapshot(db_session, user_id=u1.id, cycle_start_date=date.today())
        assert res1["success"] is True
        mock_client.open_by_key.assert_called_with("sheet_aaa")

        res2 = sync_cycle_snapshot(db_session, user_id=u2.id, cycle_start_date=date.today())
        assert res2["success"] is True
        mock_client.open_by_key.assert_called_with("sheet_bbb")


def test_snapshot_keeps_personal_tab_and_writes_cycle_transactions_as_values(db_session, test_user):
    start = date(2026, 2, 25)
    test_user.google_spreadsheet_id = "test-sheet"
    db_session.add(PaycheckConfig(
        user_id=test_user.id, cycle_type="monthly_date", paycheck_day=25,
        cycle_days=14, pocket_account="Bank Uji",
    ))
    db_session.add_all([
        Transaction(user_id=test_user.id, type="expense", amount=50_000, account="Bank Uji",
                    category="Makan", description="=1+1", date=date(2026, 3, 24)),
        Transaction(user_id=test_user.id, type="expense", amount=90_000, account="Bank Uji",
                    category="Makan", description="Di luar siklus", date=date(2026, 3, 25)),
    ])
    db_session.commit()
    personal = MagicMock(title="Sheet1")
    report = MagicMock(id=2, row_count=100)
    google = MagicMock()
    doc = google.open_by_key.return_value
    doc.worksheets.return_value = [personal]
    doc.add_worksheet.return_value = report

    with patch("app.services.sheets_sync.get_google_sheets_client", return_value=google):
        result = sync_cycle_snapshot(db_session, test_user.id, start)
        doc.add_worksheet.assert_called_once_with(title=result["sheet_title"], rows=100, cols=10)
        assert personal.mock_calls == []
        assert result["transaction_count"] == 1
        assert result["pocket_spent"] == 50_000
        upload = report.update.call_args.kwargs
        assert upload["value_input_option"] == "RAW"
        assert ["", "2026-03-24", "=1+1", "Makan", "Bank Uji", "EXPENSE", -50_000] in upload["values"]

        report.title = result["sheet_title"]
        doc.worksheets.return_value = [personal, report]
        sync_cycle_snapshot(db_session, test_user.id, start)
        assert doc.add_worksheet.call_count == 1
        report.unmerge_cells.assert_called_once_with("A1:G100")
        report.batch_clear.assert_called_once_with(["A1:G100"])
        assert personal.mock_calls == []


# ============================================================================
# 4. Telegram Bot Command Tests
# ============================================================================

def test_bot_set_sheet_no_arg_returns_instructions(db_session, test_user):
    with patch("app.bot.bot.send_message") as mock_send:
        handle_set_sheet(chat_id=test_user.telegram_chat_id, text="/set_sheet", db=db_session, user=test_user)
        mock_send.assert_called_once()
        sent_text = mock_send.call_args[0][1]
        assert "/set_sheet <link_spreadsheet>" in sent_text
        assert "tillfold@tillfold.iam.gserviceaccount.com" in sent_text


def test_bot_set_sheet_valid_url_persists_id(db_session, test_user):
    url = "https://docs.google.com/spreadsheets/d/abc123xyz789_unique/edit#gid=0"
    with patch("app.bot.bot.send_message") as mock_send:
        handle_set_sheet(chat_id=test_user.telegram_chat_id, text=f"/set_sheet {url}", db=db_session, user=test_user)
        mock_send.assert_called_once()
        sent_text = mock_send.call_args[0][1]
        assert "Google Spreadsheet Berhasil Ditautkan!" in sent_text
        assert "abc123xyz789_unique" in sent_text

    db_session.refresh(test_user)
    assert test_user.google_spreadsheet_id == "abc123xyz789_unique"


def test_bot_sheets_without_sheet_prompts_setup(db_session, test_user):
    test_user.google_spreadsheet_id = None
    db_session.commit()

    with patch("app.bot.bot.send_message") as mock_send:
        handle_sheets(chat_id=test_user.telegram_chat_id, db=db_session, user=test_user)
        mock_send.assert_called_once()
        sent_text = mock_send.call_args[0][1]
        assert "Google Spreadsheet belum ditautkan" in sent_text
        assert "/set_sheet" in sent_text


# ============================================================================
# 5. REST API Tests
# ============================================================================

def test_api_auth_me_update_google_sheet(db_session, test_user):
    def override_get_db():
        yield db_session

    def override_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_strict_current_user] = override_current_user
    app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(app)

    # 1. Update with full URL in google_sheet_url
    resp = client.put("/api/v1/auth/me", json={
        "google_sheet_url": "https://docs.google.com/spreadsheets/d/api_sheet_test_id/edit"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["google_spreadsheet_id"] == "api_sheet_test_id"

    # 2. Get /api/v1/auth/me reflects the ID
    get_resp = client.get("/api/v1/auth/me")
    assert get_resp.status_code == 200
    assert get_resp.json()["google_spreadsheet_id"] == "api_sheet_test_id"

    unrelated = client.put("/api/v1/auth/me", json={"full_name": "Nama Baru"})
    assert unrelated.json()["google_spreadsheet_id"] == "api_sheet_test_id"
    disconnected = client.put("/api/v1/auth/me", json={"google_spreadsheet_id": None})
    assert disconnected.status_code == 200
    assert disconnected.json()["google_spreadsheet_id"] is None
    assert client.get("/api/v1/auth/me").json()["google_spreadsheet_id"] is None

    app.dependency_overrides.clear()


def test_api_sync_sheets_universal_for_non_admin_user(db_session, test_user):
    test_user.google_spreadsheet_id = "universal_sheet_id"
    db_session.commit()

    def override_get_db():
        yield db_session

    def override_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(app)

    mock_ws = MagicMock()
    mock_ws.id = 12
    mock_ws.row_count = 100
    mock_ws.title = "Sheet1"

    mock_doc = MagicMock()
    mock_doc.worksheets.return_value = [mock_ws]
    mock_client = MagicMock()
    mock_client.open_by_key.return_value = mock_doc

    with patch("app.services.sheets_sync.get_google_sheets_client", return_value=mock_client):
        resp = client.post("/api/v1/analytics/sync-sheets")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_client.open_by_key.assert_called_with("universal_sheet_id")

    app.dependency_overrides.clear()


@pytest.mark.parametrize(("failure", "status", "message"), [
    (PermissionError(), 403, "akses Editor"),
    (SpreadsheetNotFound(), 404, "Periksa tautannya"),
    (FileNotFoundError("private-credentials.json"), 503, "server Tillfold belum siap"),
])
def test_api_sync_sheets_gives_actionable_error(db_session, test_user, monkeypatch, failure, status, message):
    test_user.google_spreadsheet_id = "test-sheet"
    db_session.commit()
    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: db_session)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: test_user)
    with patch("app.services.sheets_sync.get_google_sheets_client") as get_client:
        if isinstance(failure, FileNotFoundError):
            get_client.side_effect = failure
        else:
            get_client.return_value.open_by_key.side_effect = failure
        response = TestClient(app).post("/api/v1/analytics/sync-sheets")
    assert response.status_code == status
    assert message in response.json()["detail"]
    assert "private-credentials.json" not in response.text


def test_api_sync_sheets_distinguishes_disabled_google_api(db_session, test_user, monkeypatch):
    test_user.google_spreadsheet_id = "test-sheet"
    db_session.commit()
    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: db_session)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: test_user)
    google_response = MagicMock(status_code=403)
    google_response.json.return_value = {"error": {
        "code": 403, "message": "provider project details",
        "details": [{"reason": "SERVICE_DISABLED"}],
    }}
    failure = PermissionError()
    failure.__cause__ = APIError(google_response)
    with patch("app.services.sheets_sync.get_google_sheets_client") as get_client:
        get_client.return_value.open_by_key.side_effect = failure
        response = TestClient(app).post("/api/v1/analytics/sync-sheets")
    assert response.status_code == 503
    assert "Google Sheets API belum aktif" in response.json()["detail"]
    assert "provider project details" not in response.text
