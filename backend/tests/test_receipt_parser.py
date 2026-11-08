import pytest
from datetime import datetime, date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.models.user import User
from app.models.account import Account
from app.models.transaction import Transaction
from app.core.receipt_parser import parse_mandiri_receipt, parse_brimo_receipt, infer_category, html_to_text
from app.services.receipt_service import record_receipt_mutation
from app.api.deps import get_current_user
from main import app

# In-memory SQLite for testing receipt service
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    # Seed user & accounts
    u = User(id=1, username="alif", hashed_password="pw", is_active=True, full_name="Alif")
    db.add(u)
    db.add(Account(id=1, user_id=1, name="Mandiri", type="operasional"))
    db.add(Account(id=4, user_id=1, name="BRI 1", type="darurat"))
    db.add(Account(id=5, user_id=1, name="BRI 2", type="tabungan"))
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

MANDIRI_SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><style>body { font-size: 14px; }</style><title>Livin' by Mandiri</title></head>
<body>
<h2>Pembayaran Berhasil</h2>
<p>Halo ALIF IHSAN,</p>
<p>Berikut adalah detail transaksi Anda dengan QR:</p>
<table>
    <tr><td>Penerima</td></tr>
    <tr><td>Warmindo Fajar 99</td></tr>
    <tr><td>Bandung (Kab) - ID</td></tr>
    <tr><td>Tanggal</td></tr>
    <tr><td>8 Nov 2026</td></tr>
    <tr><td>Jam</td></tr>
    <tr><td>13:38:27 WIB</td></tr>
    <tr><td>Nominal Transaksi</td></tr>
    <tr><td>Rp 10.000,00</td></tr>
    <tr><td>No. Referensi</td></tr>
    <tr><td>2611081122524341667</td></tr>
    <tr><td>Sumber Dana</td></tr>
    <tr><td>ALIF IHSAN</td></tr>
    <tr><td>****7292</td></tr>
</table>
</body>
</html>
"""

MANDIRI_BIFAST_HTML = """
<!DOCTYPE html>
<html>
<body>
    <h2>Livin' by Mandiri</h2>
    <p>Transfer dengan BI Fast Berhasil</p>
    <div>Penerima</div>
    <div>ALDYTO RAFIF ABHINAYA</div>
    <div>Tanggal</div>
    <div>31 Okt 2026</div>
    <div>Jam</div>
    <div>21:28:14 WIB</div>
    <div>Nominal Transfer</div>
    <div>Rp 160.011,00</div>
    <div>Biaya Transfer</div>
    <div>Rp 2.500,00</div>
    <div>Total Transaksi</div>
    <div>Rp 162.511,00</div>
    <div>No. Referensi BI Fast</div>
    <div>20261031BMRIIDJA010O0220930922</div>
    <div>Sumber Dana</div>
    <div>ALIF IHSAN ****7292</div>
</body>
</html>
"""

BRIMO_QRIS_HTML = """
<!DOCTYPE html>
<html>
<head><style>.box { color: red; }</style></head>
<body>
    <div>BRImo Transaction Details</div>
    <div>Total Transaksi</div>
    <div>18.000</div>
    <div>Tujuan</div>
    <div>Golden Crispy Chicken, DY</div>
    <div>Nomor Referensi</div>
    <div>247437017542</div>
    <div>Tanggal Transaksi</div>
    <div>07 Nov 2026, 17:53:33 WIB</div>
    <div>Rekening Sumber Dana</div>
    <div>5722 **** **** 532</div>
    <div>Nominal</div>
    <div>Rp18.000</div>
</body>
</html>
"""

BRIMO_TRANSFER_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div>Bank BRI - Transaksi Berhasil</div>
    <div>Tanggal</div>
    <div>08 November 2026 , 10:32:51 WIB</div>
    <div>Nomor Referensi</div>
    <div>247834695002</div>
    <div>Sumber Dana</div>
    <div>ALIF IHSAN</div>
    <div>5722 **** **** 532</div>
    <div>Nama Tujuan</div>
    <div>FLIPTECH LENTERA INS</div>
    <div>Nominal</div>
    <div>Rp1.300.332</div>
    <div>Total</div>
    <div>Rp1.300.332</div>
</body>
</html>
"""

BRIMO_ACCOUNT_1532_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div>Bank Rakyat Indonesia (BRImo)</div>
    <div>Total Transaksi: Rp 75.000</div>
    <div>Merchant: Kopi Kenangan</div>
    <div>No. Referensi: 987654321</div>
    <div>Rekening Sumber: 5722 0100 1234 1532</div>
</body>
</html>
"""

BRIMO_ACCOUNT_6532_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div>Bank Rakyat Indonesia (BRImo)</div>
    <div>Total Transaksi: Rp 500.000</div>
    <div>Merchant: Deposito BRI</div>
    <div>No. Referensi: 1122334455</div>
    <div>Rekening Sumber: 5722 0100 1234 6532</div>
</body>
</html>
"""

def test_parse_mandiri_receipt_qris():
    res = parse_mandiri_receipt(MANDIRI_SAMPLE_HTML, raw_subject="Pembayaran Berhasil!")
    assert res is not None
    assert res["bank"] == "mandiri"
    assert res["nominal"] == 10000
    assert res["merchant"] == "Warmindo Fajar 99"
    assert res["ref_number"] == "2611081122524341667"
    assert res["default_account"] == "Mandiri"
    assert res["inferred_category"] == "Makanan & Minuman"
    assert res["datetime"] == datetime(2026, 11, 8, 13, 38, 27)

def test_parse_mandiri_bifast_total_amount():
    res = parse_mandiri_receipt(MANDIRI_BIFAST_HTML, raw_subject="Transfer dengan BI Fast Berhasil")
    assert res is not None
    assert res["bank"] == "mandiri"
    assert res["nominal"] == 162511
    assert res["merchant"] == "ALDYTO RAFIF ABHINAYA"
    assert res["ref_number"] == "20261031BMRIIDJA010O0220930922"
    assert res["datetime"] == datetime(2026, 10, 31, 21, 28, 14)

def test_parse_brimo_receipt_qris():
    res = parse_brimo_receipt(BRIMO_QRIS_HTML, raw_subject="Pembelian QRIS Berhasil")
    assert res is not None
    assert res["bank"] == "bri"
    assert res["nominal"] == 18000
    assert "Golden Crispy" in res["merchant"]
    assert res["ref_number"] == "247437017542"
    assert res["datetime"] == datetime(2026, 11, 7, 17, 53, 33)
    assert res["default_account"] == "BRI 1"
    assert res["is_ambiguous_account"] is True
    assert res["inferred_category"] == "Makanan & Minuman"

def test_parse_brimo_receipt_transfer():
    res = parse_brimo_receipt(BRIMO_TRANSFER_HTML, raw_subject="Pemindahan Dana Sesama Rekening BRI")
    assert res is not None
    assert res["bank"] == "bri"
    assert res["nominal"] == 1300332
    assert res["merchant"] == "FLIPTECH LENTERA INS"
    assert res["ref_number"] == "247834695002"
    assert res["datetime"] == datetime(2026, 11, 8, 10, 32, 51)
    assert res["default_account"] == "BRI 1"
    assert res["is_ambiguous_account"] is True

def test_brimo_account_detection_1532_darurat():
    res = parse_brimo_receipt(BRIMO_ACCOUNT_1532_HTML, raw_subject="Notifikasi Transaksi")
    assert res is not None
    assert res["default_account"] == "BRI 1"
    assert res["is_ambiguous_account"] is False

def test_brimo_account_detection_6532_tabungan():
    res = parse_brimo_receipt(BRIMO_ACCOUNT_6532_HTML, raw_subject="Notifikasi Transaksi")
    assert res is not None
    assert res["default_account"] == "BRI 2"
    assert res["is_ambiguous_account"] is False

def test_non_bank_email_rejection():
    spam_html = "<html><body><h1>Promo Diskon 50%</h1><p>Beli sekarang di Shopee</p></body></html>"
    assert parse_mandiri_receipt(spam_html, raw_subject="Promo") is None
    assert parse_brimo_receipt(spam_html, raw_subject="Promo") is None

def test_infer_category():
    assert infer_category("Warmindo Fajar 99") == "Makanan & Minuman"
    assert infer_category("Golden Crispy Chicken") == "Makanan & Minuman"
    assert infer_category("Janji Jiwa Kopi") == "Jajan / Ngopi"
    assert infer_category("SPBU Pertamina") == "Transportasi"
    assert infer_category("Indomaret Point") == "Kebutuhan Harian"
    assert infer_category("Unknown Vendor XYZ") == "Lainnya"

def test_record_receipt_mutation_idempotent(db_session):
    # 1. First recording
    res1 = record_receipt_mutation(
        db=db_session,
        user_id=1,
        ref_number="REF-TEST-999",
        merchant="Warmindo Fajar 99",
        amount=10000,
        account_name="Mandiri",
        category="Makanan & Minuman",
        tx_date=date(2026, 11, 8),
        raw_summary="Mandiri Livin QR"
    )
    assert res1["ok"] is True
    assert res1["already_recorded"] is False
    assert res1["amount"] == 10000
    assert res1["account"] == "Mandiri"

    # Verify DB transaction
    tx = db_session.query(Transaction).filter(Transaction.id == res1["transaction_id"]).first()
    assert tx is not None
    assert tx.description == "Warmindo Fajar 99 - Ref: REF-TEST-999"
    assert "[receipt_radar:ref_REF-TEST-999]" in tx.raw_text

    # 2. Second attempt with same ref_number must be idempotent (no duplicate)
    res2 = record_receipt_mutation(
        db=db_session,
        user_id=1,
        ref_number="REF-TEST-999",
        merchant="Warmindo Fajar 99",
        amount=10000,
        account_name="Mandiri",
        category="Makanan & Minuman",
        tx_date=date(2026, 11, 8),
        raw_summary="Duplicate attempt"
    )
    assert res2["ok"] is True
    assert res2["already_recorded"] is True
    assert res2["transaction_id"] == tx.id

    # Count in DB must still be 1
    total_tx = db_session.query(Transaction).filter(
        Transaction.user_id == 1,
        Transaction.raw_text.like("%[receipt_radar:ref_REF-TEST-999]%")
    ).count()
    assert total_tx == 1

def test_record_receipt_api_endpoint(db_session):
    u = db_session.query(User).filter(User.id == 1).first()

    def override_get_db():
        yield db_session

    def override_get_current_user():
        return u

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(app)
    try:
        payload = {
            "ref_number": "REF-API-12345",
            "merchant": "Golden Crispy Chicken",
            "amount": 18000,
            "account": "BRI 1",
            "category": "Makanan & Minuman",
            "date": "2026-11-07",
            "raw_summary": "BRImo QRIS receipt"
        }
        resp = client.post("/api/v1/transactions/receipts/record", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["already_recorded"] is False
        assert data["amount"] == 18000
        assert data["account"] == "BRI 1"

        # Repeat to test idempotency through API
        resp2 = client.post("/api/v1/transactions/receipts/record", json=payload)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["ok"] is True
        assert data2["already_recorded"] is True
    finally:
        app.dependency_overrides.clear()

def test_record_receipt_mutation_s2s_exception_resilience(db_session, monkeypatch):
    import app.services.receipt_service as rs
    def broken_s2s(db, user_id):
        raise RuntimeError("Simulated cycle calculation failure")
    monkeypatch.setattr(rs, "get_safe_to_spend_snippet", broken_s2s)

    res = rs.record_receipt_mutation(
        db=db_session,
        user_id=1,
        ref_number="REF-RESILIENCE-001",
        merchant="Aegis Guard Cafe",
        amount=25000,
        account_name="Mandiri",
        category="Makanan & Minuman",
        tx_date=date(2026, 11, 8),
        raw_summary="Testing s2s resilience"
    )
    assert res["ok"] is True
    assert res["s2s"] == ""
    assert res["transaction_id"] > 0

    # Repeat for idempotency check with broken s2s
    res2 = rs.record_receipt_mutation(
        db=db_session,
        user_id=1,
        ref_number="REF-RESILIENCE-001",
        merchant="Aegis Guard Cafe",
        amount=25000,
        account_name="Mandiri",
        category="Makanan & Minuman",
        tx_date=date(2026, 11, 8),
        raw_summary="Testing s2s resilience dup"
    )
    assert res2["ok"] is True
    assert res2["already_recorded"] is True
    assert res2["s2s"] == ""

def test_safe_to_spend_snippet_legacy_markdown_syntax(db_session):
    from app.bot.bot import get_safe_to_spend_snippet
    snippet = get_safe_to_spend_snippet(db_session, user_id=1)
    assert "*Safe-to-Spend:*" in snippet
    assert "**Safe-to-Spend:**" not in snippet

def test_receipt_radar_callback_authorization_rejected(monkeypatch):
    import sys
    hermes_scripts = "/home/alifihsan/.hermes/scripts"
    if hermes_scripts not in sys.path:
        sys.path.insert(0, hermes_scripts)
    import tillfold_receipt_radar as radar

    calls = []
    def fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json})
        class DummyResp:
            status_code = 200
            def json(self):
                return {"ok": True}
        return DummyResp()

    monkeypatch.setattr(radar.requests, "post", fake_post)

    # 1. Unauthorized user
    unauth_cb = {
        "id": "cb_unauth_1",
        "data": "rcpt_rec:REF123:Mandiri",
        "message": {"message_id": 999, "chat": {"id": radar.CHAT_ID}},
        "from": {"id": 999999999}
    }
    radar.handle_callback_query(unauth_cb)
    assert len(calls) == 1
    assert calls[0]["json"]["callback_query_id"] == "cb_unauth_1"
    assert "Akses ditolak" in calls[0]["json"]["text"]
    assert calls[0]["json"]["show_alert"] is True

    # 2. Unauthorized chat
    calls.clear()
    unauth_chat_cb = {
        "id": "cb_unauth_2",
        "data": "rcpt_rec:REF123:Mandiri",
        "message": {"message_id": 999, "chat": {"id": -1001234567890}},
        "from": {"id": radar.ALLOWED_USER_ID}
    }
    radar.handle_callback_query(unauth_chat_cb)
    assert len(calls) == 1
    assert calls[0]["json"]["callback_query_id"] == "cb_unauth_2"
    assert "Akses ditolak" in calls[0]["json"]["text"]

