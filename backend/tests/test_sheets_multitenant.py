import pytest
from datetime import date, datetime
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from gspread.exceptions import APIError, SpreadsheetNotFound

from app.db.session import Base
from app.models.user import User
from app.models.account import Account
from app.models.pocket import Pocket
from app.models.transaction import Transaction
from app.models.paycheck import LegacyPaycheckCycle, PaycheckConfig
from app.core.helpers import extract_spreadsheet_id
from app.db.user_schema import ensure_user_spreadsheet_schema
from app.services.sheets_sync import REPORT_TITLE, WIB, sync_all_cycles, sync_cycle_snapshot
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


def test_snapshot_keeps_personal_tab_and_writes_typed_cycle_rows(db_session, test_user):
    start = date(2026, 2, 25)
    test_user.google_spreadsheet_id = "test-sheet"
    db_session.add(PaycheckConfig(
        user_id=test_user.id, cycle_type="monthly_date", paycheck_day=25,
        cycle_days=14, pocket_account="Bank Uji",
    ))
    account = Account(user_id=test_user.id, name="Bank Uji", type="operasional", initial_balance=0)
    db_session.add(account)
    db_session.flush()
    pocket = Pocket(user_id=test_user.id, account_id=account.id, name="Makan", slug="makan",
                    role="operasional", target_amount=500_000, allocation_amount=125_000)
    db_session.add(pocket)
    db_session.flush()
    expense = Transaction(user_id=test_user.id, type="expense", amount=50_000, account="Bank Uji",
                          category="Makan", description="=1+1", date=date(2026, 3, 24), pocket_id=pocket.id)
    db_session.add_all([
        expense,
        Transaction(user_id=test_user.id, type="income", amount=800_000, account="Bank Uji",
                    category="Gaji", description="Gaji", date=start),
        Transaction(user_id=test_user.id, type="income", amount=100_000, account="Bank Uji",
                    category="Saldo Awal", description="Saldo awal", date=start),
        Transaction(user_id=test_user.id, type="transfer_out", amount=200_000, account="Bank Uji",
                    category="Transfer", description="Pindah saldo", date=start),
        Transaction(user_id=test_user.id, type="expense", amount=90_000, account="Bank Uji",
                    category="Makan", description="Di luar siklus", date=date(2026, 3, 25)),
    ])
    db_session.commit()
    personal = MagicMock(title="Sheet1", id=1)
    report = MagicMock(id=2, row_count=100, col_count=10)
    google = MagicMock()
    doc = google.open_by_key.return_value
    doc.worksheets.return_value = [personal]
    date_serial = (expense.date - date(1899, 12, 30)).days

    with patch("app.services.sheets_sync.get_google_sheets_client", return_value=google):
        result = sync_cycle_snapshot(db_session, test_user.id, start)
        requests = doc.batch_update.call_args.args[0]["requests"]
        created = requests[0]["addSheet"]["properties"]
        assert created["title"] == result["sheet_title"]
        assert created["gridProperties"] == {"rowCount": 100, "columnCount": 8, "frozenRowCount": 3}
        assert result["spreadsheet_url"].endswith(f"#gid={created['sheetId']}")
        assert personal.mock_calls == []
        assert result["transaction_count"] == 4
        assert result["pocket_spent"] == 50_000
        assert result["pocket_count"] == 1
        write = next(req["updateCells"] for req in requests if "updateCells" in req)
        cells = [row["values"] for row in write["rows"]]
        data = [[next(iter(cell.get("userEnteredValue", {}).values()), None) for cell in row] for row in cells]
        assert ["Pemasukan", 800_000] in data
        assert ["Saldo awal tercatat", 100_000] in data
        assert ["Anggaran belanja", 700_000] in data
        assert ["Bank Uji", "Makan", "Operasional", 500_000, 125_000, 50_000, 75_000, None] in data
        assert ["Pemasukan", "Gaji", 800_000, 1] in data
        assert ["Pengeluaran", "Makan", 50_000, 1] in data
        assert ["Pemasukan", "Saldo Awal", 100_000, 1] not in data
        assert ["Pengeluaran", "Transfer", 200_000, 1] not in data
        accent_bands = [req["repeatCell"]["cell"]["userEnteredFormat"]["backgroundColor"]
                        for req in requests if "repeatCell" in req
                        and "backgroundColor" in req["repeatCell"]["cell"]["userEnteredFormat"]]
        assert len({tuple(color.values()) for color in accent_bands}) == 7
        transaction = [date_serial, "=1+1", "Makan", "Bank Uji", "Pengeluaran", -50_000, "Makan", expense.id]
        assert cells[data.index(transaction)][1] == {"userEnteredValue": {"stringValue": "=1+1"}}
        assert all("Di luar siklus" not in row for row in data)

        report.title = result["sheet_title"]
        report.get.return_value = [[], ["", "TILLFOLD — LAPORAN SIKLUS 28 HARI"]]
        doc.worksheets.return_value = [personal, report]
        sync_cycle_snapshot(db_session, test_user.id, start)
        refresh = doc.batch_update.call_args.args[0]["requests"]
        assert not any("addSheet" in req for req in refresh)
        assert refresh[1]["unmergeCells"]["range"]["sheetId"] == report.id
        assert next(req["updateCells"] for req in refresh if "updateCells" in req)["range"]["endRowIndex"] == 100
        assert personal.mock_calls == []

        report.id = 3
        report.get.return_value = [["Catatan pribadi"]]
        result = sync_cycle_snapshot(db_session, test_user.id, start)
        assert result["sheet_title"] == f"{report.title} · Tillfold"
        assert "addSheet" in doc.batch_update.call_args.args[0]["requests"][0]


def test_sync_all_cycles_skips_unchanged_tabs_and_freezes_closed_pockets(db_session, test_user):
    test_user.google_spreadsheet_id = "cycle-history-sheet"
    bank = Account(user_id=test_user.id, name="Bank Uji", type="operasional", initial_balance=0)
    db_session.add(bank)
    db_session.flush()
    pocket = Pocket(user_id=test_user.id, account_id=bank.id, name="Liburan", slug="liburan",
                    role="tabungan", target_amount=500_000, allocation_amount=125_000)
    old_start, old_end = date(2026, 2, 1), date(2026, 2, 28)
    current_start, current_end = date(2026, 3, 1), date(2026, 3, 31)
    old_tx = Transaction(user_id=test_user.id, type="income", amount=1_000_000, account=bank.name,
                         category="Gaji", description="Bulan lalu", date=old_start)
    db_session.add_all([
        pocket, old_tx,
        Transaction(user_id=test_user.id, type="income", amount=2_000_000, account=bank.name,
                    category="Gaji", description="Bulan ini", date=current_start),
        LegacyPaycheckCycle(user_id=test_user.id, start_date=old_start, end_date=old_end),
        LegacyPaycheckCycle(user_id=test_user.id, start_date=current_start, end_date=current_end),
    ])
    db_session.commit()

    google = MagicMock()
    doc = google.open_by_key.return_value
    sheets = []
    writes = {}
    doc.worksheets.side_effect = lambda: list(sheets)

    def apply_batch(body):
        requests = body["requests"]
        if "addSheet" in requests[0]:
            props = requests[0]["addSheet"]["properties"]
            sheet = MagicMock(title=props["title"], id=props["sheetId"], row_count=100, col_count=8)
            sheet.get.return_value = [[REPORT_TITLE]]
            sheets.append(sheet)
        update = next(req["updateCells"] for req in requests if "updateCells" in req)
        writes[update["range"]["sheetId"]] = [
            [next(iter(cell.get("userEnteredValue", {}).values()), None) for cell in row["values"]]
            for row in update["rows"]
        ]

    doc.batch_update.side_effect = apply_batch
    close_day = datetime(2026, 3, 1, 1, tzinfo=WIB)
    with patch("app.services.sheets_sync.get_google_sheets_client", return_value=google):
        closed = sync_all_cycles(db_session, test_user.id, closed_only=True, now=close_day)
        assert closed["cycles_updated"] == 1
        closed_sheet = sheets[0]
        assert ["Bank Uji", "Operasional", 1_000_000, "Aktif"] in writes[closed_sheet.id]
        assert ["Kantong · saat siklus ditutup"] in writes[closed_sheet.id]
        assert sync_all_cycles(db_session, test_user.id, closed_only=True, now=close_day)["cycles_checked"] == 0
        assert sync_all_cycles(db_session, test_user.id, now=close_day)["cycles_updated"] == 1
        assert len(sheets) == 2
        repeat = sync_all_cycles(db_session, test_user.id, now=close_day.replace(hour=3))
        assert (repeat["cycles_updated"], repeat["cycles_skipped"]) == (0, 2)
        assert doc.batch_update.call_count == 2

        old_tx.category = "Honor"
        db_session.commit()
        edited = sync_all_cycles(db_session, test_user.id, now=close_day)
        assert (edited["cycles_updated"], edited["cycles_skipped"]) == (1, 1)
        assert ["Pemasukan", "Honor", 1_000_000, 1] in writes[closed_sheet.id]

        pocket.target_amount = 600_000
        db_session.commit()
        changed = sync_all_cycles(db_session, test_user.id, now=close_day)
        assert changed["cycles_updated"] == 1
        assert ["Pemasukan", "Honor", 1_000_000, 1] in writes[closed_sheet.id]
        assert ["Bank Uji", "Liburan", "Tabungan", 500_000, 125_000, 0, 125_000, None] in writes[closed_sheet.id]
        assert ["Bank Uji", "Liburan", "Tabungan", 600_000, 125_000, 0, 125_000, None] in writes[sheets[1].id]


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
