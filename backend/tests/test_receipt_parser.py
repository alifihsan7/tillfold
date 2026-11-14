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
from app.core.receipt_parser import (
    parse_mandiri_receipt,
    parse_brimo_receipt,
    parse_google_play_receipt,
    infer_category,
    html_to_text,
)
from app.core.receipt_store import (
    save_pending_receipt,
    get_pending_receipt,
    delete_pending_receipt,
)
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

GOOGLE_PLAY_SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div>Google Play</div>
    <div>Terima kasih atas pesanan Anda.</div>
    <div>Nomor pesanan: GPA.3311-6234-1706-42627</div>
    <div>Tanggal pemesanan: Nov 13, 2026 7:58:44 PM GMT+7</div>
    <div>Item</div>
    <div>Claude Pro Subscription (Claude by Anthropic)</div>
    <div>Rp 387.390/bulan</div>
    <div>Pajak: Rp 38.390</div>
    <div>Total: Rp 387.390</div>
    <div>Metode pembayaran: GoPay: •••• 3744</div>
</body>
</html>
"""

GOOGLE_PLAY_SAMPLE_TEXT = """
Google Play
Thank you for your order.
Order number: GPA.1234-5678-9012-34567
Order date: Nov 10, 2026 2:15:30 PM GMT+7
Item
Google One (100 GB)
Total: Rp 26.900/month
Payment method: Bank Jago: •••• 1234
"""

MANDIRI_INTERNAL_BIFAST_HTML = """
<!DOCTYPE html>
<html>
<body>
    <h2>Livin' by Mandiri</h2>
    <p>Transfer dengan BI Fast Berhasil</p>
    <div>Penerima</div>
    <div>ALIF IHSAN</div>
    <div>Bank Tujuan</div>
    <div>Bank Jago</div>
    <div>No. Rekening Tujuan</div>
    <div>1029384756</div>
    <div>Tanggal</div>
    <div>10 Nov 2026</div>
    <div>Jam</div>
    <div>14:20:00 WIB</div>
    <div>Nominal Transfer</div>
    <div>Rp 500.000,00</div>
    <div>Biaya Transfer</div>
    <div>Rp 2.500,00</div>
    <div>Total Transaksi</div>
    <div>Rp 502.500,00</div>
    <div>No. Referensi BI Fast</div>
    <div>20261110BMRIIDJA010O1234567890</div>
    <div>Sumber Dana</div>
    <div>ALIF IHSAN ****7292</div>
</body>
</html>
"""

BRIMO_INTERNAL_TRANSFER_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div>Bank BRI - Transaksi Berhasil</div>
    <div>Pemindahan Dana Sesama Rekening BRI</div>
    <div>Tanggal</div>
    <div>09 November 2026 , 14:00:00 WIB</div>
    <div>Nomor Referensi</div>
    <div>247999888111</div>
    <div>Sumber Dana</div>
    <div>ALIF IHSAN</div>
    <div>5722 **** **** 1532</div>
    <div>Nama Tujuan</div>
    <div>ALIF IHSAN</div>
    <div>Nomor Tujuan</div>
    <div>5722 0100 9999 6532</div>
    <div>Bank Tujuan</div>
    <div>BANK BRI</div>
    <div>Nominal</div>
    <div>Rp 200.000</div>
    <div>Biaya Admin</div>
    <div>Rp 0</div>
    <div>Total</div>
    <div>Rp 200.000</div>
</body>
</html>
"""

BRIMO_BIFAST_INTERNAL_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div>Bank BRI - Transaksi Berhasil</div>
    <div>Pemindahan Dana Bank Lain Dalam Negeri</div>
    <div>Tanggal</div>
    <div>10 November 2026 , 15:30:00 WIB</div>
    <div>Nomor Referensi</div>
    <div>248111222333</div>
    <div>Sumber Dana</div>
    <div>ALIF IHSAN</div>
    <div>5722 **** **** 1532</div>
    <div>Nama Tujuan</div>
    <div>ALIF IHSAN</div>
    <div>Nomor Tujuan</div>
    <div>1029384756</div>
    <div>Bank Tujuan</div>
    <div>BANK JAGO</div>
    <div>Nominal</div>
    <div>Rp 50.000</div>
    <div>Biaya Admin</div>
    <div>Rp 2.500</div>
    <div>Total</div>
    <div>Rp 52.500</div>
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
    assert res["nominal"] == 160011
    assert res["admin_fee"] == 2500
    assert res["merchant"] == "ALDYTO RAFIF ABHINAYA"
    assert res["ref_number"] == "20261031BMRIIDJA010O0220930922"
    assert res["datetime"] == datetime(2026, 10, 31, 21, 28, 14)
    assert res["is_transfer"] is True
    assert res["is_internal_transfer"] is False
    assert res["destination_name"] == "ALDYTO RAFIF ABHINAYA"
    assert res["destination_account_candidate"] is None

def test_parse_mandiri_bifast_internal_transfer():
    res = parse_mandiri_receipt(MANDIRI_INTERNAL_BIFAST_HTML, raw_subject="Transfer dengan BI Fast Berhasil")
    assert res is not None
    assert res["bank"] == "mandiri"
    assert res["nominal"] == 500000
    assert res["admin_fee"] == 2500
    assert res["destination_name"] == "ALIF IHSAN"
    assert res["destination_bank"] == "Bank Jago"
    assert res["is_transfer"] is True
    assert res["is_internal_transfer"] is True
    assert res["destination_account_candidate"] == "Bank Jago"
    assert res["ref_number"] == "20261110BMRIIDJA010O1234567890"

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
    assert res["admin_fee"] == 0
    assert res["merchant"] == "FLIPTECH LENTERA INS"
    assert res["ref_number"] == "247834695002"
    assert res["datetime"] == datetime(2026, 11, 8, 10, 32, 51)
    assert res["default_account"] == "BRI 1"
    assert res["is_ambiguous_account"] is True
    assert res["is_transfer"] is True
    assert res["is_internal_transfer"] is False
    assert res["destination_name"] == "FLIPTECH LENTERA INS"
    assert res["destination_account_candidate"] is None

def test_parse_brimo_receipt_internal_transfer_sesama_bri():
    res = parse_brimo_receipt(BRIMO_INTERNAL_TRANSFER_HTML, raw_subject="Pemindahan Dana Sesama Rekening BRI")
    assert res is not None
    assert res["bank"] == "bri"
    assert res["nominal"] == 200000
    assert res["admin_fee"] == 0
    assert res["destination_name"] == "ALIF IHSAN"
    assert res["destination_bank"] == "BANK BRI"
    assert res["is_transfer"] is True
    assert res["is_internal_transfer"] is True
    assert res["destination_account_candidate"] == "BRI 2"
    assert res["ref_number"] == "247999888111"

def test_parse_brimo_receipt_internal_transfer_bifast():
    res = parse_brimo_receipt(BRIMO_BIFAST_INTERNAL_HTML, raw_subject="Pemindahan Dana Bank Lain Dalam Negeri")
    assert res is not None
    assert res["bank"] == "bri"
    assert res["nominal"] == 50000
    assert res["admin_fee"] == 2500
    assert res["destination_name"] == "ALIF IHSAN"
    assert res["destination_bank"] == "BANK JAGO"
    assert res["is_transfer"] is True
    assert res["is_internal_transfer"] is True
    assert res["destination_account_candidate"] == "Bank Jago"
    assert res["ref_number"] == "248111222333"

def test_parse_google_play_receipt_html():
    res = parse_google_play_receipt(GOOGLE_PLAY_SAMPLE_HTML, raw_subject="Google Play Order Receipt")
    assert res is not None
    assert res["bank"] == "google_play"
    assert res["ref_number"] == "GPA.3311-6234-1706-42627"
    assert res["nominal"] == 387390
    assert res["merchant"] == "Claude Pro Subscription (Claude by Anthropic)"
    assert res["datetime"] == datetime(2026, 11, 13, 19, 58, 44)
    assert res["payment_method"] == "GoPay: •••• 3744"
    assert res["is_transfer"] is False
    assert res["inferred_category"] == "Langganan & Servis"
    assert res["default_account"] == "BRI 1"
    assert "GPA.3311-6234-1706-42627" in res["raw_text"]

def test_parse_google_play_receipt_text():
    res = parse_google_play_receipt(GOOGLE_PLAY_SAMPLE_TEXT, raw_subject="Tanda terima pesanan Google Play Anda")
    assert res is not None
    assert res["bank"] == "google_play"
    assert res["ref_number"] == "GPA.1234-5678-9012-34567"
    assert res["nominal"] == 26900
    assert "Google One" in res["merchant"]
    assert res["payment_method"] == "Bank Jago: •••• 1234"
    assert res["is_transfer"] is False

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
    assert parse_google_play_receipt(spam_html, raw_subject="Promo") is None

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
    import app.bot.bot as bot

    calls = []
    def fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json})
        class DummyResp:
            status_code = 200
            def json(self):
                return {"ok": True}
        return DummyResp()

    monkeypatch.setattr(bot.requests, "post", fake_post)

    # 1. Unauthorized user (not in database)
    unauth_cb = {
        "id": "cb_unauth_1",
        "data": "rcpt_rec:REF123:Mandiri",
        "message": {"message_id": 999, "chat": {"id": -1004483626622}},
        "from": {"id": 999999999}
    }
    bot.handle_callback_query(unauth_cb)
    assert len(calls) == 2  # first acknowledge, second reject alert
    reject_call = [c for c in calls if "text" in (c.get("json") or {})][0]
    assert reject_call["json"]["callback_query_id"] == "cb_unauth_1"
    assert "Akses ditolak" in reject_call["json"]["text"]
    assert reject_call["json"]["show_alert"] is True

def test_receipt_radar_callback_rcpt_xfer_atomic_and_idempotent(db_session, monkeypatch):
    import app.bot.bot as bot

    # 1. Setup user & accounts in db_session
    u = db_session.query(User).filter(User.id == 1).first()
    u.telegram_chat_id = 1357550611
    jago = db_session.query(Account).filter(Account.user_id == 1, Account.name == "Bank Jago").first()
    if not jago:
        db_session.add(Account(id=6, user_id=1, name="Bank Jago", type="operasional"))
    db_session.commit()

    # Monkeypatch SessionLocal in bot module to use db_session
    monkeypatch.setattr(bot, "SessionLocal", lambda: db_session)

    telegram_calls = []
    def fake_post(url, json=None, timeout=None):
        telegram_calls.append({"url": url, "json": json})
        class DummyResp:
            status_code = 200
            def json(self):
                return {"ok": True}
        return DummyResp()

    monkeypatch.setattr(bot.requests, "post", fake_post)

    ref_test = "GPA.TEST-XFER-9999-11111"
    pending_data = {
        "bank": "mandiri",
        "nominal": 75000,
        "merchant": "Bank Jago",
        "ref_number": ref_test,
        "date": "2026-11-10T14:20:00",
        "category": "Transfer",
        "source_account": "Mandiri",
        "default_account": "Mandiri",
        "is_transfer": True,
        "is_internal_transfer": True,
        "destination_bank": "Bank Jago",
        "destination_name": "ALIF IHSAN",
        "destination_account_candidate": "Bank Jago",
        "admin_fee": 2500,
        "payment_method": None,
    }
    save_pending_receipt(ref_test, pending_data)
    assert get_pending_receipt(ref_test) is not None

    cb = {
        "id": "cb_xfer_1",
        "data": f"rcpt_xfer:{ref_test}:Mandiri:Bank Jago:2500",
        "message": {"message_id": 1001, "chat": {"id": -1004483626622}},
        "from": {"id": 1357550611}
    }

    bot.handle_callback_query(cb)

    # Verify transactions created in database
    tx_out = db_session.query(Transaction).filter(
        Transaction.user_id == 1,
        Transaction.type == "transfer_out",
        Transaction.raw_text.like(f"%[receipt_radar:ref_{ref_test}]%")
    ).first()
    tx_in = db_session.query(Transaction).filter(
        Transaction.user_id == 1,
        Transaction.type == "transfer_in",
        Transaction.raw_text.like(f"%[receipt_radar:ref_{ref_test}]%")
    ).first()
    tx_fee = db_session.query(Transaction).filter(
        Transaction.user_id == 1,
        Transaction.type == "expense",
        Transaction.category == "Biaya Admin",
        Transaction.raw_text.like(f"%[receipt_radar:ref_{ref_test}_admin]%")
    ).first()

    assert tx_out is not None
    assert tx_out.account == "Mandiri"
    assert tx_out.amount == 75000
    assert f"[pair_id:{tx_in.id}]" in tx_out.raw_text

    assert tx_in is not None
    assert tx_in.account == "Bank Jago"
    assert tx_in.amount == 75000
    assert f"[pair_id:{tx_out.id}]" in tx_in.raw_text

    assert tx_fee is not None
    assert tx_fee.account == "Mandiri"
    assert tx_fee.amount == 2500

    # Verify pending receipt was cleared from store
    assert get_pending_receipt(ref_test) is None

    # Verify edit message call was sent to Telegram
    edit_calls = [c for c in telegram_calls if "editMessageText" in c["url"]]
    assert len(edit_calls) == 1
    assert "TRANSFER ANTAR-REKENING BERHASIL DICATAT" in edit_calls[0]["json"]["text"]

    # Test Idempotency: Trigger callback again with same ref_test
    save_pending_receipt(ref_test, pending_data)
    cb2 = {
        "id": "cb_xfer_2",
        "data": f"rcpt_xfer:{ref_test}:Mandiri:Bank Jago:2500",
        "message": {"message_id": 1001, "chat": {"id": -1004483626622}},
        "from": {"id": 1357550611}
    }
    bot.handle_callback_query(cb2)

    total_tx_out = db_session.query(Transaction).filter(
        Transaction.user_id == 1,
        Transaction.type == "transfer_out",
        Transaction.raw_text.like(f"%[receipt_radar:ref_{ref_test}]%")
    ).count()
    assert total_tx_out == 1

    edit_calls_2 = [c for c in telegram_calls if "editMessageText" in c["url"]]
    assert len(edit_calls_2) == 2
    assert "SUDAH TERCATAT SEBELUMNYA" in edit_calls_2[-1]["json"]["text"]

