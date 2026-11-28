import pytest
from datetime import date, datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.models.user import User
from app.models.account import Account
from app.models.category import Category
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

def test_receipt_radar_category_picker_records_selected_category(db_session, monkeypatch, tmp_path):
    from app.bot import bot
    from app.core import receipt_store

    user = db_session.get(User, 1)
    user.telegram_chat_id = 12345
    db_session.add(User(id=2, username="other", hashed_password="pw", is_active=True, full_name="Other"))
    db_session.add_all([
        Category(id=100 + i, user_id=1, type="expense", name=f"Pilihan {i:02}")
        for i in range(9)
    ])
    db_session.add_all([
        Category(id=200, user_id=1, type="income", name="Pemasukan milik sendiri"),
        Category(id=201, user_id=2, type="expense", name="Kategori akun lain"),
    ])
    db_session.commit()
    monkeypatch.setattr(receipt_store, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(receipt_store, "PENDING_FILE", tmp_path / "receipt.json")
    monkeypatch.setattr(bot, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(bot, "get_safe_to_spend_snippet", lambda db, user_id: "")
    messages = []
    monkeypatch.setattr(bot.requests, "post", lambda url, **kwargs: messages.append((url, kwargs["json"])))
    ref = "R" * 40
    assert save_pending_receipt(ref, {
        "user_id": 1, "nominal": 75_000, "merchant": "Kedai Uji", "category": "Makan",
    })

    def press(data):
        bot.handle_callback_query({
            "id": "test", "data": data, "from": {"id": 12345},
            "message": {"chat": {"id": 12345}, "message_id": 10},
        })

    def buttons():
        edits = [body for url, body in messages if url.endswith("/editMessageText")]
        return {item["text"]: item["callback_data"] for row in edits[-1]["reply_markup"]["inline_keyboard"] for item in row}

    press(f"rcpt_rec:{ref}:Mandiri")
    assert db_session.query(Transaction).count() == 0
    first = buttons()
    assert all(not label.startswith("Pakai saran") for label in first)
    assert "Belum ada saran yang cocok." in messages[-1][1]["text"]
    old_callback = next(data for label, data in first.items() if label == "Pilihan 00")
    press(old_callback.rsplit(":", 1)[0] + ":0")
    assert db_session.query(Transaction).count() == 0
    assert "Kategori akun lain" not in first
    assert "Pemasukan milik sendiri" not in first
    assert all(len(label.encode()) <= 64 for label in first.values())

    press(first["Berikutnya"])
    second = buttons()
    assert "Sebelumnya" in second
    press(second["Pilihan 08"])
    tx = db_session.query(Transaction).one()
    assert (tx.user_id, tx.amount, tx.account, tx.category) == (1, 75_000, "Mandiri", "Pilihan 08")
    assert "Pilihan 08" in messages[-1][1]["text"]
    assert get_pending_receipt(ref) is None
    press(second["Pilihan 08"])
    assert db_session.query(Transaction).count() == 1

    next_ref = "next-receipt"
    assert save_pending_receipt(next_ref, {
        "user_id": 1, "nominal": 25_000, "merchant": "Kedai Uji", "category": "Makan",
    })
    press(f"rcpt_rec:{next_ref}:Mandiri")
    suggested = buttons()["Pakai saran · Pilihan 08"]
    assert suggested.endswith(":108")
    press(suggested)
    saved = db_session.query(Transaction).filter(Transaction.amount == 25_000).one()
    assert saved.category == "Pilihan 08"


def test_receipt_suggestion_uses_own_category_and_consistent_merchant_history(db_session):
    from app.bot.bot import suggest_receipt_category

    db_session.add(User(id=2, username="other", hashed_password="pw", is_active=True, full_name="Other"))
    db_session.add_all([
        Category(id=301, user_id=1, type="expense", name="Makan"),
        Category(id=302, user_id=1, type="expense", name="Makan Kampus"),
        Category(id=303, user_id=1, type="income", name="Transportasi"),
        Category(id=304, user_id=2, type="expense", name="Transportasi"),
    ])
    db_session.flush()
    assert suggest_receipt_category(db_session, 1, "Warmindo Fajar", "Lainnya").id == 301
    assert suggest_receipt_category(db_session, 1, "Vendor Uji", "Transportasi") is None

    def prior(merchant, category, user_id=1):
        return Transaction(user_id=user_id, type="expense", description=merchant,
                           category=category, account="Mandiri", amount=15000, date=date(2026, 11, 8))

    db_session.add_all([
        prior("Warmindo Fajar (Struk MANDIRI)", "Makan Kampus"),
        prior("Warmindo Fajar", "Kategori yang sudah dihapus"),
        prior("Warmindo Fajar", "Makan", user_id=2),
        prior("GoPay Customer (Struk MANDIRI)", "Makan Kampus"),
    ])
    db_session.flush()
    assert suggest_receipt_category(db_session, 1, "WARmindo Fajar", "Makanan & Minuman").id == 302
    assert suggest_receipt_category(db_session, 1, "GoPay Customer", "Lainnya") is None

    db_session.add(prior("Warmindo Fajar", "Makan"))
    db_session.flush()
    assert suggest_receipt_category(db_session, 1, "Warmindo Fajar", "Makanan & Minuman") is None


def test_receipt_radar_callback_rcpt_xfer_atomic_and_idempotent(db_session, monkeypatch, tmp_path):
    import app.bot.bot as bot
    from app.core import receipt_store

    monkeypatch.setattr(receipt_store, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(receipt_store, "PENDING_FILE", tmp_path / "receipt.json")

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



@pytest.mark.parametrize("continue_recording", [False, True])
def test_receipt_possible_duplicate_can_be_dropped_or_recorded(db_session, monkeypatch, tmp_path, continue_recording):
    from app.bot import bot
    from app.core import receipt_store

    user = db_session.get(User, 1)
    user.telegram_chat_id = 12345
    occurred = datetime(2026, 11, 27, 12, 30, tzinfo=bot.WIB)
    account = "Mandiri"
    category = Category(user_id=1, name="Ngopi", type="expense")
    db_session.add(category)
    db_session.add(Transaction(
        user_id=1, type="expense", amount=25000, account=account, category="Ngopi",
        description="Kopi yang dicatat lewat chat", date=occurred.date(), created_at=occurred.astimezone(timezone.utc),
    ))
    db_session.commit()

    monkeypatch.setattr(receipt_store, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(receipt_store, "PENDING_FILE", tmp_path / "receipt.json")
    monkeypatch.setattr(bot, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(bot, "get_safe_to_spend_snippet", lambda db, user_id: "")
    messages = []
    monkeypatch.setattr(bot.requests, "post", lambda url, **kwargs: messages.append(kwargs["json"]) if url.endswith("editMessageText") else None)

    ref = "REF-POSSIBLE-DUPLICATE"
    receipt = {
        "user_id": 1, "nominal": 25000, "merchant": "GoPay Customer",
        "category": "Ngopi", "date": occurred.isoformat(),
    }
    assert save_pending_receipt(ref, receipt)

    def press(data, private=True):
        bot.handle_callback_query({
            "id": "duplicate-check", "data": data, "from": {"id": 12345},
            "message": {"chat": {"id": 12345 if private else -100, "type": "private" if private else "supergroup"}, "message_id": 21},
        })

    def buttons():
        return {button["text"]: button["callback_data"]
                for row in messages[-1]["reply_markup"]["inline_keyboard"] for button in row}

    press(f"rcpt_rec:{ref}:{account}", private=False)
    assert "Struk mungkin sudah dicatat" in messages[-1]["text"]
    assert "Kopi yang dicatat lewat chat" not in messages[-1]["text"]
    press(f"rcpt_rec:{ref}:{account}")
    assert "Kopi yang dicatat lewat chat" in messages[-1]["text"]
    assert db_session.query(Transaction).count() == 1

    if continue_recording:
        press(buttons()["Tetap catat"])
        assert db_session.query(Transaction).count() == 1
        press(buttons()["Pakai saran · Ngopi"])
        assert db_session.query(Transaction).count() == 2
        assert save_pending_receipt(ref, receipt)
        press(f"rcpt_rec:{ref}:{account}")
        assert messages[-1]["text"] == "Struk ini sudah tercatat."
        assert db_session.query(Transaction).count() == 2
    else:
        press(buttons()["Abaikan struk"])
        assert db_session.query(Transaction).count() == 1
    assert get_pending_receipt(ref) is None


def test_receipt_duplicate_candidates_match_account_date_amount_and_ownership(db_session):
    from app.bot import bot

    occurred = datetime(2026, 11, 27, 1, 0, tzinfo=bot.WIB)
    utc = occurred.astimezone(timezone.utc)
    db_session.add(User(id=2, username="another", hashed_password="pw", is_active=True, full_name="Other"))
    values = {"user_id": 1, "type": "expense", "amount": 50000, "account": "Mandiri", "category": "Makan",
              "description": "Kedai Uji", "date": occurred.date(), "created_at": utc - timedelta(hours=3)}
    matches = Transaction(**values)
    different_merchant = Transaction(**{**values, "description": "Kedai lain"})
    db_session.add_all([matches, different_merchant])
    for overrides in ({"user_id": 2}, {"type": "income"}, {"amount": 55000},
                      {"account": "BRI 1"}, {"date": occurred.date() - timedelta(days=1)}):
        db_session.add(Transaction(**{**values, **overrides, "created_at": utc}))
    db_session.commit()

    find = bot.find_similar_receipt_expenses
    assert find(db_session, 1, "Mandiri", 50000, "Kedai Uji", "2026-11-27") == [matches]
    assert find(db_session, 1, "Mandiri", 50000, "GoPay Customer", occurred.isoformat()) == []
    assert find(db_session, 1, "Mandiri", 50000, "Kedai Uji", None) == []


def test_receipt_store_writes_preserve_other_updates(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    from app.core import receipt_store

    monkeypatch.setattr(receipt_store, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(receipt_store, "PENDING_FILE", tmp_path / "receipt.json")
    refs = [f"receipt-{index}" for index in range(30)]
    with ThreadPoolExecutor(max_workers=6) as executor:
        assert all(executor.map(lambda ref: save_pending_receipt(ref, {"ref": ref}), refs))
        assert all(executor.map(delete_pending_receipt, refs[::2]))
    assert receipt_store.list_pending_receipts() == {ref: {"ref": ref} for ref in refs[1::2]}


def test_account_forwarding_verification_receipt_and_bot_approval(db_session, monkeypatch):
    from email.message import EmailMessage
    from unittest.mock import Mock

    from app.bot import bot
    from app.core.config import settings
    from app.models.receipt_radar import ReceiptRadarDraft

    users = [
        db_session.get(User, 1),
        User(id=2, username="recipient", hashed_password="pw", full_name="Recipient", is_active=True),
    ]
    users[0].telegram_chat_id = 54321
    db_session.add(users[1])
    db_session.commit()

    monkeypatch.setattr(settings, "RECEIPT_RADAR_DOMAIN", "receipts.test.example")
    monkeypatch.setattr(settings, "RECEIPT_RADAR_INGRESS_TOKEN", "test-only-ingress-secret-not-production")
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "test-only-bot")
    monkeypatch.setattr(bot, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(bot, "get_safe_to_spend_snippet", lambda db, user_id: "")
    telegram = []
    fail_next_delivery = False

    def fake_post(url, *, json, timeout):
        nonlocal fail_next_delivery
        if fail_next_delivery and url.endswith("/sendMessage"):
            fail_next_delivery = False
            raise bot.requests.Timeout()
        telegram.append((url.rsplit("/", 1)[-1], json))
        return Mock(ok=True, json=lambda: {"ok": True, "result": {"message_id": 77}})

    monkeypatch.setattr(bot.requests, "post", fake_post)
    active_username = "alif"
    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: db_session)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: db_session.query(User).filter(User.username == active_username).one())
    api = TestClient(app)
    path = "/api/v1/receipt-radar"
    assert api.get(path).json()["address"] is None
    first_response = api.post(path)
    assert first_response.status_code == 200
    assert first_response.headers["cache-control"] == "no-store"
    first = first_response.json()["address"]
    assert first.endswith("@receipts.test.example")
    assert api.post(path).json()["address"] == first
    active_username = "recipient"
    assert api.post(path).status_code == 409
    users[1].telegram_chat_id = 12345
    db_session.commit()
    second = api.post(path).json()["address"]
    assert first != second

    gateway = {"Authorization": f"Bearer {settings.RECEIPT_RADAR_INGRESS_TOKEN}",
               "X-Receipt-Recipient": first, "Content-Type": "message/rfc822"}
    verification = EmailMessage()
    verification["Subject"] = "Gmail Forwarding Confirmation"
    verification.set_content("Confirmation code: 123456789. Open https://mail.google.com/mail/vf-test-token")
    assert api.post(path + "/inbound", headers={"X-Receipt-Recipient": first}, content=verification.as_bytes()).status_code == 401
    received = api.post(path + "/inbound", headers={**gateway, "X-Receipt-Sender": "forwarding-noreply@google.com"},
                        content=verification.as_bytes())
    assert received.json() == {"ok": True, "status": "verification"}
    assert api.get(path).json()["verification_code"] is None
    active_username = "alif"
    assert api.get(path).json()["verification_code"] == "123456789"
    assert api.get(path).json()["verification_url"] == "https://mail.google.com/mail/vf-test-token"

    original = EmailMessage()
    original["From"] = "noreply.livin@bankmandiri.co.id"
    original["Subject"] = "Livin Mandiri"
    original.set_content(MANDIRI_SAMPLE_HTML, subtype="html")
    forwarded = EmailMessage()
    forwarded["Subject"] = "Fwd: Bukti pembayaran"
    forwarded["To"] = second
    forwarded.set_content("Terusan.")
    forwarded.add_attachment(original)
    assert api.post(path + "/inbound", headers=gateway, content=b"x" * (512 * 1024 + 1)).status_code == 413
    fail_next_delivery = True
    assert api.post(path + "/inbound", headers=gateway, content=forwarded.as_bytes()).status_code == 502
    assert db_session.query(ReceiptRadarDraft).count() == 1
    response = api.post(path + "/inbound", headers=gateway, content=forwarded.as_bytes())
    assert response.json() == {"ok": True, "status": "pending"}
    assert api.post(path + "/inbound", headers=gateway, content=forwarded.as_bytes()).json()["status"] == "duplicate"
    assert db_session.query(Transaction).count() == 0
    assert db_session.query(ReceiptRadarDraft).count() == 1
    assert len(telegram) == 1 and telegram[0][1]["chat_id"] == 54321
    assert telegram[0][1]["parse_mode"] == "HTML"
    assert "RECEIPT RADAR: MANDIRI" in telegram[0][1]["text"]
    assert "Merchant/Penerima" in telegram[0][1]["text"] and "No. Referensi" in telegram[0][1]["text"]
    accounts = {button["text"]: button["callback_data"]
                for row in telegram[0][1]["reply_markup"]["inline_keyboard"] for button in row}

    def press(button, sender):
        bot.handle_callback_query({
            "id": "approval", "data": button, "from": {"id": sender},
            "message": {"message_id": 77, "chat": {"id": sender, "type": "private"}},
        })

    press(accounts["✅ Catat di Mandiri"], 12345)
    assert db_session.query(Transaction).count() == 0
    press(accounts["✅ Catat di Mandiri"], 54321)
    categories = {button["text"]: button["callback_data"]
                  for row in telegram[-1][1]["reply_markup"]["inline_keyboard"] for button in row}
    assert "Pakai saran · Makan" in categories
    press(categories["Pakai saran · Makan"], 54321)
    press(categories["Pakai saran · Makan"], 54321)
    saved = db_session.query(Transaction).one()
    assert (saved.user_id, saved.account, saved.amount) == (1, "Mandiri", 10_000)
    assert db_session.query(ReceiptRadarDraft).one().status == "recorded"

    reference = "2611081122524341667"
    assert f"[receipt_radar:ref_{reference}]" in saved.raw_text
    duplicate = ReceiptRadarDraft(
        id="fw_duplicate_chat", user_id=1, fingerprint="other-proof", status="pending",
        payload={"bank": "mandiri", "merchant": "Merchant", "nominal": 10_000, "source_ref": reference},
    )
    db_session.add(duplicate)
    db_session.commit()
    press("rcpt_pick:fw_duplicate_chat:1", 54321)
    assert "Struk ini sudah tercatat." in telegram[-1][1]["text"]
    assert "Rekening: Mandiri" in telegram[-1][1]["text"]
    assert "Tanggal transaksi:" in telegram[-1][1]["text"]
    assert db_session.query(Transaction).count() == 1

    assert api.delete(path).json()["address"] is None
    assert api.post(path + "/inbound", headers=gateway, content=forwarded.as_bytes()).status_code == 404
    assert api.post(path).json()["address"] != first
    active_username = "recipient"
    assert api.get(path).json()["address"] == second
    assert api.post(path + "/inbound", headers={**gateway, "X-Receipt-Recipient": second},
                    content=forwarded.as_bytes()).json()["status"] == "pending"
    assert telegram[-1][1]["chat_id"] == 12345
    assert db_session.query(Transaction).count() == 1


def test_gmail_once_consent_polls_only_new_mail_and_disconnects(db_session, monkeypatch):
    import base64
    import json
    from email.message import EmailMessage
    from urllib.parse import parse_qs, urlsplit
    from unittest.mock import Mock

    from cryptography.fernet import Fernet

    from app.api.v1.endpoints import receipt_gmail as endpoint
    from app.core.config import settings
    from app.models.receipt_radar import ReceiptGmailConnection, ReceiptRadarDraft
    from app.services import receipt_gmail
    from app.services import receipt_radar as radar

    monkeypatch.setattr(settings, "RECEIPT_GMAIL_CLIENT_ID", "local-gmail-client")
    monkeypatch.setattr(settings, "RECEIPT_GMAIL_CLIENT_SECRET", "local-gmail-secret")
    key = Fernet.generate_key()
    monkeypatch.setattr(settings, "RECEIPT_GMAIL_ENCRYPTION_KEY", key.decode())
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "local-bot-token")
    monkeypatch.setattr(settings, "APP_BASE_URL", "http://localhost:8080")
    monkeypatch.setattr(receipt_gmail, "SessionLocal", TestingSessionLocal)
    user = db_session.get(User, 1)
    user.telegram_chat_id = 54321
    db_session.add(User(id=2, username="gmail-peer", full_name="Peer", hashed_password="unused",
                        is_active=True, telegram_chat_id=54322))
    db_session.commit()

    owner_id = 1
    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: db_session)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: db_session.get(User, owner_id))
    exchange = Mock(return_value={"access_token": "token", "refresh_token": "refresh-token"})
    monkeypatch.setattr(endpoint, "request_token", exchange)
    monkeypatch.setattr(endpoint, "gmail_get", lambda *_args, **_kwargs: {"emailAddress": "radar@example.test"})
    client = TestClient(app)
    path = "/api/v1/receipt-radar/gmail"
    started = client.post(path + "/connect")
    params = parse_qs(urlsplit(started.json()["url"]).query)
    assert params["scope"] == [receipt_gmail.GMAIL_SCOPE]
    assert params["access_type"] == ["offline"]
    assert params["code_challenge_method"] == ["S256"]
    state = params["state"][0]
    without_cookie = TestClient(app)
    bad = without_cookie.get(path + "/callback", params={"state": state, "code": "once"}, follow_redirects=False)
    assert "failed" in bad.headers["location"]
    exchange.assert_not_called()
    success = client.get(path + "/callback", params={"state": state, "code": "once"}, follow_redirects=False)
    assert success.headers["location"] == "/?receipt_gmail=connected#/profile"
    assert success.headers["referrer-policy"] == "no-referrer"
    assert exchange.call_args.kwargs["code_verifier"]
    replay = client.get(path + "/callback", params={"state": state, "code": "once"}, follow_redirects=False)
    assert "failed" in replay.headers["location"] and exchange.call_count == 1
    connection = db_session.get(ReceiptGmailConnection, 1)
    assert connection.refresh_token != "refresh-token"
    assert Fernet(key).decrypt(connection.refresh_token.encode()) == b"refresh-token"
    assert client.get(path).json()["email"] == "radar@example.test"

    owner_id = 2
    other = client.post(path + "/connect")
    other_state = parse_qs(urlsplit(other.json()["url"]).query)["state"][0]
    result = client.get(path + "/callback", params={"state": other_state, "code": "peer"}, follow_redirects=False)
    assert "in_use" in result.headers["location"]
    assert client.get(path).json()["email"] is None
    owner_id = 1

    now = datetime.now(timezone.utc)
    connection.checked_through = now - timedelta(minutes=2)
    connection.next_check_at = connection.checked_through
    db_session.commit()
    raw_message = EmailMessage()
    raw_message["From"] = "noreply.livin@bankmandiri.co.id"
    raw_message["Subject"] = "Livin Mandiri"
    raw_message.set_content(MANDIRI_SAMPLE_HTML, subtype="html")
    inline_forward = EmailMessage()
    inline_forward["From"] = "owner@example.test"
    inline_forward["Subject"] = "Fwd: Pembayaran Berhasil"
    inline_forward.set_content(
        '<p>From: <a href="mailto:noreply.livin@bankmandiri.co.id">Bank Mandiri</a></p>' + MANDIRI_SAMPLE_HTML,
        subtype="html",
    )
    raw = base64.urlsafe_b64encode(inline_forward.as_bytes()).decode().rstrip("=")

    monkeypatch.setattr(receipt_gmail, "request_token", Mock(return_value={"access_token": "poll-token"}))

    def gmail_get(token, gmail_path, **params):
        assert token == "poll-token"
        if gmail_path == "messages":
            assert "from:noreply.livin@bankmandiri.co.id" in params["q"]
            assert "subject:fwd" in params["q"] and "subject:pembayaran" in params["q"]
            return {"messages": [{"id": "old"}, {"id": "gone"}, {"id": "new"}]}
        if gmail_path.endswith("gone"):
            raise receipt_gmail.GmailMessageSkipped
        received = now - timedelta(minutes=3 if gmail_path.endswith("old") else 1)
        return {"raw": raw, "internalDate": str(int(received.timestamp() * 1000))}

    monkeypatch.setattr(receipt_gmail, "gmail_get", gmail_get)
    telegram = Mock(return_value=Mock(ok=True, json=lambda: {"ok": True}))
    monkeypatch.setattr(radar.requests, "post", telegram)
    receipt_gmail.poll_gmail_receipts()
    db_session.expire_all()
    item = db_session.query(ReceiptRadarDraft).one()
    assert item.user_id == 1 and item.source == "gmail" and item.notified_at
    assert item.payload["nominal"] == 10000
    assert telegram.call_args.kwargs["json"]["chat_id"] == 54321
    assert db_session.query(Transaction).count() == 0
    assert client.get(path).json()["last_checked_at"]
    assert "refresh-token" not in json.dumps(client.get(path).json())

    revoke = Mock(return_value=True)
    monkeypatch.setattr(endpoint, "revoke_refresh_token", revoke)
    assert client.delete(path).json() == {"revoked": True}
    assert client.get(path).json()["status"] == "disconnected"
    assert db_session.get(ReceiptGmailConnection, 1) is None
    assert db_session.query(ReceiptRadarDraft).one().status == "discarded"
    receipt_gmail.poll_gmail_receipts()
    assert telegram.call_count == 1
    revoke.assert_called_once()


def test_empty_gmail_listing_accepts_no_content(monkeypatch):
    from unittest.mock import MagicMock, Mock

    from app.services import receipt_gmail

    response = MagicMock(status_code=204, ok=True)
    response.__enter__.return_value = response
    get = Mock(return_value=response)
    monkeypatch.setattr(receipt_gmail.requests, "get", get)
    assert receipt_gmail.gmail_get("test-token", "messages", fields="messages(id),nextPageToken") == {}
    response.iter_content.assert_not_called()



def test_forwarded_receipt_requires_original_sender_match():
    from email.message import EmailMessage
    from app.services.receipt_gmail import SENDERS
    from app.services.receipt_radar import has_receipt_sender

    mail = EmailMessage()
    mail["From"] = "forwarder@example.test"
    mail["Subject"] = "Fwd: Pembayaran Berhasil"
    mail.set_content("From: noreply.livin@bankmandiri.co.id.example.test")
    assert not has_receipt_sender(mail, SENDERS)

    original = EmailMessage()
    original["From"] = "Bank BRI <BankBRI@bri.co.id>"
    original.set_content("Receipt")
    mail.add_attachment(original)
    assert has_receipt_sender(mail, SENDERS)



def test_receipt_card_uses_legacy_layout_and_masks_source_account():
    from app.services.receipt_radar import draft_text, normalize_receipt

    _, payload = normalize_receipt({
        "bank": "mandiri", "merchant": "Toko <Uji> & Co", "nominal": 25_000,
        "source_account": "Tabungan 1234567890", "ref_number": "REF123",
        "datetime": datetime(2026, 11, 28, 3, 20, tzinfo=timezone.utc),
    })
    text = draft_text(payload)
    assert "<b>RECEIPT RADAR: MANDIRI</b>" in text
    assert "<code>Toko &lt;Uji&gt; &amp; Co</code>" in text
    assert "Rekening •••• 7890" in text
    assert "1234567890" not in text
    assert "28 Nov 2026 10:20 WIB" in text
    assert "REF123" in text


@pytest.mark.parametrize(("subject", "status"), [
    ("Your Google Play payment is pending", ""),
    ("Pesanan Google Play Anda tertunda", ""),
    ("Google Play Order Receipt", "Payment is pending."),
    ("Tanda terima pesanan Google Play", "Status pembayaran: masih tertunda"),
    ("Google Play Order Receipt", "Complete your payment."),
    ("Google Play Order Receipt", "Payment was declined."),
])
def test_google_play_pending_or_failed_orders_are_not_receipts(subject, status):
    assert parse_google_play_receipt(GOOGLE_PLAY_SAMPLE_TEXT + "\n" + status, subject) is None


def test_google_play_order_needs_confirmation_even_with_total_and_payment_method():
    data = GOOGLE_PLAY_SAMPLE_TEXT.replace("Thank you for your order.", "")
    assert parse_google_play_receipt(data, "Google Play order notice") is None


def test_personal_radar_skips_pending_and_retries_unsent_card(db_session, monkeypatch, tmp_path):
    from email.message import EmailMessage
    from unittest.mock import Mock

    from app.bot import bot
    from app.core import receipt_store
    from app.models.account import Account
    from app.services import personal_receipt_radar as radar

    owner = db_session.get(User, 1)
    owner.telegram_chat_id = 54321
    db_session.add(User(id=2, username="peer-radar", full_name="Peer", hashed_password="unused",
                        is_active=True, telegram_chat_id=54322))
    db_session.add(Account(id=40, user_id=2, name="Peer bank", type="operasional"))
    db_session.add(Account(id=41, user_id=1, name="Archived bank", type="operasional", is_archived=True))
    db_session.commit()
    owner_id = owner.id
    monkeypatch.setattr(radar, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(receipt_store, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(receipt_store, "PENDING_FILE", tmp_path / "pending.json")
    send = Mock(side_effect=[False, True])
    monkeypatch.setattr(radar, "_send_card", send)
    cfg = radar.PersonalRadarConfig("user@example.test", "local-test", "local", tmp_path / "uid", 54321, -100, 1)
    mail = EmailMessage()
    mail["From"] = "googleplay-noreply@google.com"
    mail["Subject"] = "Google Play payment pending"
    mail.set_content(GOOGLE_PLAY_SAMPLE_TEXT + "\nYour payment is pending.")
    assert radar.handle_mail(cfg, mail.as_bytes())
    send.assert_not_called()
    assert not receipt_store.list_pending_receipts()

    mail.replace_header("Subject", "Google Play Order Receipt")
    mail.set_content(GOOGLE_PLAY_SAMPLE_TEXT)
    raw = mail.as_bytes()
    assert not radar.handle_mail(cfg, raw)
    pending = receipt_store.list_pending_receipts()
    assert len(pending) == 1 and not next(iter(pending.values())).get("notified")
    assert radar.handle_mail(cfg, raw)
    assert radar.handle_mail(cfg, raw)
    assert send.call_count == 2
    pending = receipt_store.list_pending_receipts()
    draft = next(iter(pending.values()))
    assert draft["user_id"] == owner_id and draft["telegram_user_id"] == 54321 and draft["notified"]
    text, markup = send.call_args.args[1:]
    assert "RECEIPT RADAR: GOOGLE PLAY" in text
    buttons = [button for row in markup["inline_keyboard"] for button in row]
    assert buttons[0]["text"] == "✅ Catat di BRI 1"
    assert all("Peer bank" not in button["text"] and "Archived bank" not in button["text"] for button in buttons)
    assert all(len(button["callback_data"].encode()) <= 64 for button in buttons)
    assert db_session.query(Transaction).count() == 0

    monkeypatch.setattr(bot, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(bot, "get_safe_to_spend_snippet", lambda *args, **kwargs: "")
    updates = []
    monkeypatch.setattr(bot.requests, "post", lambda url, **kwargs: updates.append(kwargs["json"]) if url.endswith("/editMessageText") else None)

    def press(value, sender):
        bot.handle_callback_query({
            "id": "personal-radar", "from": {"id": sender}, "data": value,
            "message": {"message_id": 45, "chat": {"id": -100, "type": "supergroup"}},
        })

    button = buttons[0]["callback_data"]
    press(button, 54322)
    assert not updates
    press(button, 54321)
    category = next(btn["callback_data"] for row in updates[-1]["reply_markup"]["inline_keyboard"] for btn in row
                    if btn["text"] == "Pakai saran · Tagihan")
    press(category, 54321)
    saved = db_session.query(Transaction).one()
    assert saved.user_id == 1 and saved.account == "BRI 1" and saved.amount == 26_900
    assert "[receipt_radar:ref_GPA.1234-5678-9012-34567]" in saved.raw_text


def test_personal_radar_checkpoint_stops_at_unsent_receipt(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    from app.services import personal_receipt_radar as radar

    client = MagicMock()
    client.__enter__.return_value = client
    client.select.return_value = ("OK", [])
    client.uid.side_effect = [
        ("OK", [b"11 12 13"]),
        ("OK", [(b"11", b"first")]),
        ("OK", [(b"12", b"second")]),
    ]
    monkeypatch.setattr(radar.imaplib, "IMAP4_SSL", lambda *args, **kwargs: client)
    def handle(_cfg, raw):
        return raw == b"first"
    monkeypatch.setattr(radar, "handle_mail", handle)
    cfg = radar.PersonalRadarConfig("user@example.test", "local", "local", tmp_path / "uid", 123, -100, 12)
    cfg.checkpoint.write_text("10")
    radar.check_mail(cfg)
    assert cfg.checkpoint.read_text() == "11"
    assert client.uid.call_count == 3
    assert client.select.call_args.kwargs["readonly"] is True
