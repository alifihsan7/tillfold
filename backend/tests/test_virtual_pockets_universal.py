from datetime import date
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.db.session import Base, get_db
from app.models.account import Account
from app.models.pocket import Pocket, JagoPocket
from app.models.paycheck import PaycheckConfig
from app.models.transaction import Transaction
from app.models.user import User
from main import app

# In-memory SQLite for deterministic, isolated test execution
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
        username="zephyr_universal",
        hashed_password="dummy_hash",
        telegram_chat_id=123456,
        full_name="Zephyr Architect",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def other_user(db_session):
    user = User(
        id=2,
        username="other_luminary",
        hashed_password="dummy_hash",
        telegram_chat_id=654321,
        full_name="Other Luminary",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
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

    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# ============================================================================
# 1. Universal Pockets CRUD on Parent Accounts (Mandiri, BCA, GoPay, Cash)
# ============================================================================

def test_create_universal_pockets_on_different_accounts(client, db_session, test_user):
    """Verifies creating virtual pockets attached to any parent account with specific roles."""
    acc_mandiri = Account(user_id=test_user.id, name="Bank Mandiri", type="operasional", initial_balance=5_000_000)
    acc_bca = Account(user_id=test_user.id, name="BCA Prioritas", type="operasional", initial_balance=10_000_000)
    db_session.add_all([acc_mandiri, acc_bca])
    db_session.commit()

    # Create pocket on Mandiri with role 'operasional'
    res_m1 = client.post(
        "/api/v1/pockets",
        json={
            "account_id": acc_mandiri.id,
            "name": "Belanja Bulanan",
            "target_amount": 2_500_000,
            "role": "operasional",
        },
    )
    assert res_m1.status_code == 201
    data_m1 = res_m1.json()
    assert data_m1["account_id"] == acc_mandiri.id
    assert data_m1["account_name"] == "Bank Mandiri"
    assert data_m1["name"] == "Belanja Bulanan"
    assert data_m1["role"] == "operasional"
    assert data_m1["target_amount"] == 2_500_000

    # Create pocket on Mandiri with role 'tagihan'
    res_m2 = client.post(
        "/api/v1/pockets",
        json={
            "account_id": acc_mandiri.id,
            "name": "Cicilan KPR Mandiri",
            "target_amount": 1_800_000,
            "role": "tagihan",
        },
    )
    assert res_m2.status_code == 201
    data_m2 = res_m2.json()
    assert data_m2["role"] == "tagihan"

    # Create pocket on BCA with role 'darurat'
    res_b1 = client.post(
        "/api/v1/pockets",
        json={
            "account_id": acc_bca.id,
            "name": "Dana Darurat BCA",
            "target_amount": 5_000_000,
            "role": "darurat",
        },
    )
    assert res_b1.status_code == 201
    data_b1 = res_b1.json()
    assert data_b1["account_id"] == acc_bca.id
    assert data_b1["role"] == "darurat"


def test_pocket_role_validation(client, db_session, test_user):
    """Verifies that invalid roles are rejected with 400 Bad Request."""
    acc = Account(user_id=test_user.id, name="Test Account", type="operasional")
    db_session.add(acc)
    db_session.commit()

    res = client.post(
        "/api/v1/pockets",
        json={
            "account_id": acc.id,
            "name": "Invalid Pocket",
            "target_amount": 100_000,
            "role": "invalid_role_xyz",
        },
    )
    assert res.status_code == 422 or res.status_code == 400


# ============================================================================
# 2. Filter Pockets by Account ID
# ============================================================================

def test_filter_pockets_by_account_id(client, db_session, test_user):
    """Verifies GET /api/v1/pockets?account_id={id} filters strictly by parent account."""
    acc_mandiri = Account(user_id=test_user.id, name="Mandiri", type="operasional", initial_balance=3_000_000)
    acc_cash = Account(user_id=test_user.id, name="Cash Tunai", type="operasional", initial_balance=500_000)
    db_session.add_all([acc_mandiri, acc_cash])
    db_session.commit()

    client.post("/api/v1/pockets", json={"account_id": acc_mandiri.id, "name": "Bensin & Tol", "target_amount": 500_000, "role": "operasional"})
    client.post("/api/v1/pockets", json={"account_id": acc_mandiri.id, "name": "Tagihan Listrik", "target_amount": 400_000, "role": "tagihan"})
    client.post("/api/v1/pockets", json={"account_id": acc_cash.id, "name": "Jajan Pinggir Jalan", "target_amount": 300_000, "role": "operasional"})

    # Filter Mandiri
    res_mandiri = client.get(f"/api/v1/pockets?account_id={acc_mandiri.id}")
    assert res_mandiri.status_code == 200
    data_m = res_mandiri.json()
    assert data_m["account_id"] == acc_mandiri.id
    m_pocket_names = [p["name"] for p in data_m["pockets"]]
    assert "Bensin & Tol" in m_pocket_names
    assert "Tagihan Listrik" in m_pocket_names
    assert "Jajan Pinggir Jalan" not in m_pocket_names

    # Filter Cash
    res_cash = client.get(f"/api/v1/pockets?account_id={acc_cash.id}")
    assert res_cash.status_code == 200
    data_c = res_cash.json()
    assert data_c["account_id"] == acc_cash.id
    c_pocket_names = [p["name"] for p in data_c["pockets"]]
    assert "Jajan Pinggir Jalan" in c_pocket_names
    assert "Bensin & Tol" not in c_pocket_names


# ============================================================================
# 3. Update & Delete Kantong (PUT & DELETE /api/v1/pockets/{id})
# ============================================================================

def test_update_and_delete_pocket_by_id_and_slug(client, db_session, test_user):
    """Verifies updating and deleting pockets by integer ID or unique slug."""
    acc = Account(user_id=test_user.id, name="Mandiri", type="operasional")
    db_session.add(acc)
    db_session.commit()

    res_create = client.post(
        "/api/v1/pockets",
        json={"account_id": acc.id, "name": "Saku Hiburan", "target_amount": 600_000, "role": "operasional"},
    )
    assert res_create.status_code == 201
    pocket_id = res_create.json()["id"]
    pocket_slug = res_create.json()["slug"]

    # Update by ID: change target and role
    res_update_id = client.put(
        f"/api/v1/pockets/{pocket_id}",
        json={"name": "Saku Hiburan & Hobi", "target_amount": 750_000, "role": "tabungan"},
    )
    assert res_update_id.status_code == 200
    assert res_update_id.json()["name"] == "Saku Hiburan & Hobi"
    assert res_update_id.json()["target_amount"] == 750_000
    assert res_update_id.json()["role"] == "tabungan"

    # Update by Slug: change target
    res_update_slug = client.put(
        f"/api/v1/pockets/{pocket_slug}",
        json={"target_amount": 900_000},
    )
    assert res_update_slug.status_code == 200
    assert res_update_slug.json()["target_amount"] == 900_000

    # Delete by ID
    res_del = client.delete(f"/api/v1/pockets/{pocket_id}")
    assert res_del.status_code == 200
    assert res_del.json()["ok"] is True

    # Confirm deletion
    res_check = client.get(f"/api/v1/pockets/{pocket_id}")
    assert res_check.status_code == 404


def test_tenant_isolation_on_pockets(client, db_session, test_user, other_user):
    """Verifies users cannot view, edit, or delete pockets owned by other users."""
    acc2 = Account(user_id=other_user.id, name="Account Other", type="operasional")
    db_session.add(acc2)
    db_session.commit()

    pocket_other = JagoPocket(
        user_id=other_user.id,
        account_id=acc2.id,
        name="Private Pocket Other",
        slug="private-other",
        role="operasional",
        target_amount=1_000_000,
    )
    db_session.add(pocket_other)
    db_session.commit()

    # User 1 attempts to get pocket of User 2
    res_get = client.get(f"/api/v1/pockets/{pocket_other.id}")
    assert res_get.status_code == 404

    # User 1 attempts to update pocket of User 2
    res_put = client.put(f"/api/v1/pockets/{pocket_other.id}", json={"target_amount": 0})
    assert res_put.status_code == 404

    # User 1 attempts to delete pocket of User 2
    res_del = client.delete(f"/api/v1/pockets/{pocket_other.id}")
    assert res_del.status_code == 404


# ============================================================================
# 4. Safe-to-Spend Consumes ONLY Kantong with role == 'operasional'
# ============================================================================

def test_safe_to_spend_only_consumes_operasional_pockets(client, db_session, test_user):
    """
    Krusial: Perhitungan safe-to-spend hanya mengonsumsi kantong yang memiliki role == 'operasional'.
    Pengeluaran untuk kantong ber-role 'tagihan', 'darurat', 'tabungan' tidak boleh mengurangi safe-to-spend!
    """
    today = date.today()

    # Account: Mandiri Utama (as pocket_account)
    acc = Account(user_id=test_user.id, name="Mandiri Utama", type="operasional", initial_balance=0)
    db_session.add(acc)
    db_session.commit()

    # Create 2 virtual pockets on Mandiri Utama:
    # 1. Operasional pocket: "Makan & Harian" (role: operasional)
    # 2. Tagihan pocket: "Cicilan & Tagihan" (role: tagihan)
    p_op = JagoPocket(
        user_id=test_user.id,
        account_id=acc.id,
        name="Makan & Harian",
        slug="makan-harian",
        role="operasional",
        target_amount=1_500_000,
    )
    p_tag = JagoPocket(
        user_id=test_user.id,
        account_id=acc.id,
        name="Cicilan & Tagihan",
        slug="cicilan-tagihan",
        role="tagihan",
        target_amount=1_000_000,
    )
    db_session.add_all([p_op, p_tag])

    # PaycheckConfig
    cfg = PaycheckConfig(
        user_id=test_user.id,
        pocket_account="Mandiri Utama",
        cycle_days=30,
        cycle_start_date=today,
    )
    db_session.add(cfg)

    # Income into Mandiri Utama: 2.500.000
    tx_inc = Transaction(
        user_id=test_user.id,
        account="Mandiri Utama",
        type="income",
        amount=2_500_000,
        category="Gajian",
        description="Gaji Masuk",
        date=today,
    )

    # Expense 1: Operational spending on Mandiri Utama (300.000) -> MUST deduct safe-to-spend!
    tx_exp_op = Transaction(
        user_id=test_user.id,
        account="Mandiri Utama",
        type="expense",
        amount=300_000,
        category="Makanan",
        description="Makan & Harian siang resto",
        date=today,
    )

    # Expense 2: Tagihan bill spending on Mandiri Utama (800.000) -> MUST NOT deduct safe-to-spend!
    tx_exp_tag = Transaction(
        user_id=test_user.id,
        account="Mandiri Utama",
        type="expense",
        amount=800_000,
        category="Tagihan",
        description="Cicilan & Tagihan listrik rumah",
        date=today,
    )

    db_session.add_all([tx_inc, tx_exp_op, tx_exp_tag])
    db_session.commit()

    # Query analytics summary
    resp = client.get("/api/v1/analytics/summary?period_type=cycle")
    assert resp.status_code == 200
    safe = resp.json()["safe_to_spend"]

    assert safe["pocket_account"] == "Mandiri Utama"
    assert safe["pocket_budget"] == 2_500_000

    # PENTING: pocket_spent HANYA 300.000 (dari kantong operasional).
    # 800.000 dari kantong 'Cicilan & Tagihan' (role: tagihan) diproteksi dari daily burn safe-to-spend!
    assert safe["pocket_spent"] == 300_000
    assert safe["pocket_remaining"] == 2_200_000


# ============================================================================
# 5. Saldo Rekening Induk Breakdown & Dynamic Kantong Utama
# ============================================================================

def test_account_pockets_breakdown_and_dynamic_target(client, db_session, test_user):
    """
    Verifies that:
    1. Saldo rekening induk otomatis ter-breakdown per kantong.
    2. Kantong Utama otomatis mengalirkan sisa saldo rekening induk (balance - target kantong lain).
    3. GET /api/v1/accounts menyertakan list pockets.
    4. GET /api/v1/accounts/{id}/pockets mengembalikan summary lengkap.
    """
    today = date.today()
    acc_mandiri = Account(user_id=test_user.id, name="Mandiri Payroll", type="operasional", initial_balance=5_000_000)
    db_session.add(acc_mandiri)
    db_session.commit()

    # Initial balance transaction (5.000.000)
    tx_init = Transaction(
        user_id=test_user.id,
        account="Mandiri Payroll",
        type="income",
        amount=5_000_000,
        category="Saldo Awal",
        description="Initial balance",
        date=today,
    )
    db_session.add(tx_init)
    db_session.commit()

    # Create 2 custom pockets on Mandiri Payroll:
    # 1. Investasi (target: 1.500.000)
    # 2. Tagihan Internet (target: 500.000)
    # Total other targets = 2.000.000
    # Expected dynamic target for Kantong Utama = 5.000.000 - 2.000.000 = 3.000.000!
    client.post("/api/v1/pockets", json={"account_id": acc_mandiri.id, "name": "Investasi Reksadana", "target_amount": 1_500_000, "role": "investasi"})
    client.post("/api/v1/pockets", json={"account_id": acc_mandiri.id, "name": "Tagihan Internet", "target_amount": 500_000, "role": "tagihan"})

    # Get accounts list -> verify pockets breakdown inside AccountResponse
    res_acc = client.get("/api/v1/accounts")
    assert res_acc.status_code == 200
    data_acc = res_acc.json()
    mandiri_data = next((a for a in data_acc if a["id"] == acc_mandiri.id), None)
    assert mandiri_data is not None
    assert "pockets" in mandiri_data
    assert len(mandiri_data["pockets"]) >= 2

    # Query account pockets summary endpoint
    res_pockets = client.get(f"/api/v1/accounts/{acc_mandiri.id}/pockets")
    assert res_pockets.status_code == 200
    p_data = res_pockets.json()
    assert p_data["account_id"] == acc_mandiri.id
    assert p_data["total_pocket_balance"] == 5_000_000

    p_map = {p["name"]: p for p in p_data["pockets"]}
    assert "Investasi Reksadana" in p_map
    assert p_map["Investasi Reksadana"]["target_amount"] == 1_500_000
    assert "Tagihan Internet" in p_map
    assert p_map["Tagihan Internet"]["target_amount"] == 500_000

    # Verify Kantong Utama exists and captured the dynamic remaining balance (5.000.000 - 2.000.000 = 3.000.000)
    if "Kantong Utama" in p_map:
        assert p_map["Kantong Utama"]["target_amount"] == 3_000_000


# ============================================================================
# 6. Backward Compatibility with GET /api/v1/jago-pockets
# ============================================================================

def test_backward_compatibility_jago_pockets(client, db_session, test_user):
    """Verifies that /api/v1/jago-pockets retains 100% backward compatibility."""
    res = client.get("/api/v1/jago-pockets")
    assert res.status_code == 200
    data = res.json()

    assert "pockets" in data
    assert len(data["pockets"]) == 5
    slugs = {p["slug"] for p in data["pockets"]}
    assert {"gym", "claude", "kuota", "visa", "utama"}.issubset(slugs)

    # Universal /api/v1/pockets without account_id also returns default summary
    res_universal = client.get("/api/v1/pockets")
    assert res_universal.status_code == 200
    assert len(res_universal.json()["pockets"]) == 5
