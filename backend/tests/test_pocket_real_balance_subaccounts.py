from datetime import date
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.db.session import Base, get_db
from app.models.account import Account
from app.models.pocket import Pocket, PocketMutation
from app.models.paycheck import PaycheckConfig
from app.models.transaction import Transaction
from app.models.user import User
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
        username="zephyr_subaccounts",
        hashed_password="dummy_hash",
        telegram_chat_id=987654,
        full_name="Zephyr Software Architect",
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
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def jago_account(db_session, test_user):
    account = Account(
        user_id=test_user.id,
        name="Bank Jago",
        type="operasional",
        color="purple",
        initial_balance=1_000_000,
        is_archived=False,
    )
    db_session.add(account)
    init_tx = Transaction(
        user_id=test_user.id,
        type="income",
        amount=1_000_000,
        account="Bank Jago",
        category="Saldo Awal",
        description="Saldo Awal Bank Jago",
        date=date.today(),
        raw_text="init_account: Bank Jago 1000000",
    )
    db_session.add(init_tx)
    cfg = PaycheckConfig(
        user_id=test_user.id,
        cycle_start_date=date.today(),
        cycle_days=30,
    )
    db_session.add(cfg)
    db_session.commit()
    db_session.refresh(account)
    return account


def test_pocket_balance_sum_equals_account_current_balance(client, jago_account):
    """
    Kriteria Inti: Total saldo seluruh kantong dalam rekening induk
    harus selalu sama dengan saldo kas rekening induk di ledger (sum(pockets.balance) == account.current_balance).
    Kantong Utama berfungsi sebagai unallocated cash pool.
    """
    res = client.get("/api/v1/pockets")
    assert res.status_code == 200
    data = res.json()

    total_account_balance = data["total_balance"]
    assert total_account_balance == 1_000_000

    pockets = data["pockets"]
    pockets_by_slug = {p["slug"]: p for p in pockets}

    # Canonical default allocations:
    # GYM: 225k, Claude: 75k, Kuota: 50k, VISA: 50k -> Total Sub: 400k
    # Utama: 1,000,000 - 400,000 = 600,000
    assert pockets_by_slug["gym"]["balance"] == 225_000
    assert pockets_by_slug["claude"]["balance"] == 75_000
    assert pockets_by_slug["kuota"]["balance"] == 50_000
    assert pockets_by_slug["visa"]["balance"] == 50_000
    assert pockets_by_slug["utama"]["balance"] == 600_000

    # Invariant: sum(pockets.balance) == total_balance
    total_pocket_balance = sum(p["balance"] for p in pockets)
    assert total_pocket_balance == total_account_balance == 1_000_000


def test_expense_deduction_reduces_pocket_balance_deterministically(client, jago_account, db_session):
    """
    Ketika transaksi pengeluaran terjadi pada rekening dengan alokasi kantong spesifik,
    saldo kantong terkait berkurang secara riil dan total saldo kantong tetap sama dengan saldo rekening.
    """
    # Initialize pockets first
    client.get("/api/v1/pockets")

    # Kuota spending: 50,000
    tx_res = client.post(
        "/api/v1/transactions",
        json={
            "type": "expense",
            "amount": 50_000,
            "account": "Bank Jago",
            "category": "Kuota",
            "description": "Beli paket data 50GB",
            "date": str(date.today()),
        },
    )
    assert tx_res.status_code == 200

    res = client.get("/api/v1/pockets")
    assert res.status_code == 200
    data = res.json()

    assert data["total_balance"] == 950_000
    pockets_by_slug = {p["slug"]: p for p in data["pockets"]}

    # Kuota was 50k - 50k spent = 0 balance
    assert pockets_by_slug["kuota"]["balance"] == 0
    assert pockets_by_slug["kuota"]["spent_amount"] == 50_000
    assert pockets_by_slug["kuota"]["remaining_amount"] == 0

    # Utama remains 600k because Kuota absorbed its own spending
    assert pockets_by_slug["utama"]["balance"] == 600_000

    # Invariant holds: 600k + 225k + 75k + 0 + 50k = 950k
    assert sum(p["balance"] for p in data["pockets"]) == 950_000


def test_pocket_transfer_atomic_success(client, jago_account):
    """
    Memindahkan saldo kas antar-kantong dalam rekening yang sama.
    Contoh: Dari Kantong Utama (600k) ke Kantong GYM (225k) sebesar 100k.
    Hasil: Utama = 500k, GYM = 325k. Saldo total rekening tetap 1,000,000.
    """
    res = client.post(
        "/api/v1/pockets/transfer",
        json={
            "account_id": jago_account.id,
            "from_pocket_slug": "utama",
            "to_pocket_slug": "gym",
            "amount": 100_000,
            "note": "Top up persiapan langganan personal trainer",
        },
    )
    assert res.status_code == 200
    transfer_data = res.json()

    assert transfer_data["status"] == "success"
    assert transfer_data["from_pocket_balance"] == 500_000
    assert transfer_data["to_pocket_balance"] == 325_000
    assert transfer_data["amount"] == 100_000

    # Query latest pockets summary
    summary_res = client.get("/api/v1/pockets")
    summary = summary_res.json()
    pockets = {p["slug"]: p for p in summary["pockets"]}

    assert pockets["utama"]["balance"] == 500_000
    assert pockets["gym"]["balance"] == 325_000
    assert summary["total_balance"] == 1_000_000
    assert sum(p["balance"] for p in summary["pockets"]) == 1_000_000


def test_pocket_transfer_between_subpockets(client, jago_account):
    """
    Memindahkan saldo langsung antar sub-kantong (misal: GYM ke VISA).
    Kantong Utama tidak terpengaruh, total rekening tetap utuh.
    """
    res = client.post(
        "/api/v1/pockets/allocate",
        json={
            "account_id": jago_account.id,
            "from_pocket_slug": "gym",
            "to_pocket_slug": "visa",
            "amount": 25_000,
            "note": "Alokasi sisa gym ke online debit VISA",
        },
    )
    assert res.status_code == 200
    data = res.json()

    assert data["from_pocket_balance"] == 200_000  # 225k - 25k
    assert data["to_pocket_balance"] == 75_000     # 50k + 25k

    summary = client.get("/api/v1/pockets").json()
    pockets = {p["slug"]: p for p in summary["pockets"]}
    assert pockets["gym"]["balance"] == 200_000
    assert pockets["visa"]["balance"] == 75_000
    assert pockets["utama"]["balance"] == 600_000
    assert sum(p["balance"] for p in summary["pockets"]) == 1_000_000


def test_pocket_transfer_insufficient_balance_rejected(client, jago_account):
    """
    Validasi batas saldo: Menolak alokasi bila saldo kantong asal tidak mencukupi.
    """
    res = client.post(
        "/api/v1/pockets/transfer",
        json={
            "account_id": jago_account.id,
            "from_pocket_slug": "kuota",  # balance: 50,000
            "to_pocket_slug": "gym",
            "amount": 200_000,
        },
    )
    assert res.status_code == 400
    assert "tidak mencukupi" in res.json()["detail"].lower()


def test_pocket_transfer_validation_guards(client, jago_account, db_session, test_user):
    """
    Menolak transfer ke kantong yang sama, nominal <= 0, atau antar rekening yang berbeda.
    """
    # 1. Same pocket
    res = client.post(
        "/api/v1/pockets/transfer",
        json={
            "from_pocket_slug": "gym",
            "to_pocket_slug": "gym",
            "amount": 10_000,
        },
    )
    assert res.status_code == 400
    assert "tidak boleh sama" in res.json()["detail"].lower()

    # 2. Non-positive amount
    res = client.post(
        "/api/v1/pockets/transfer",
        json={
            "from_pocket_slug": "utama",
            "to_pocket_slug": "gym",
            "amount": 0,
        },
    )
    assert res.status_code == 422 or res.status_code == 400

    # 3. Cross account rejection
    bca_acc = Account(
        user_id=test_user.id,
        name="Bank BCA",
        type="operasional",
        initial_balance=500_000,
        is_archived=False,
    )
    db_session.add(bca_acc)
    db_session.commit()
    db_session.refresh(bca_acc)

    bca_pocket = Pocket(
        user_id=test_user.id,
        account_id=bca_acc.id,
        name="Kantong BCA Kuliah",
        slug="bca-kuliah",
        balance=100_000,
        target_amount=100_000,
    )
    db_session.add(bca_pocket)
    db_session.commit()

    client.get("/api/v1/pockets")
    jago_gym = db_session.query(Pocket).filter(Pocket.slug == "gym").first()

    res = client.post(
        "/api/v1/pockets/transfer",
        json={
            "from_pocket_id": jago_gym.id,
            "to_pocket_id": bca_pocket.id,
            "amount": 50_000,
        },
    )
    assert res.status_code == 400
    assert "rekening induk yang sama" in res.json()["detail"].lower()


def test_pocket_mutations_audit_trail(client, jago_account):
    """
    Memverifikasi audit trail mutasi alokasi saldo kantong:
    Endpoint /mutations dan /{id}/mutations mengembalikan histori yang akurat.
    """
    # Transfer 50k from Utama to Kuota
    client.post(
        "/api/v1/pockets/transfer",
        json={
            "from_pocket_slug": "utama",
            "to_pocket_slug": "kuota",
            "amount": 50_000,
            "note": "Alokasi pulsa darurat",
        },
    )

    # All mutations
    res = client.get("/api/v1/pockets/mutations")
    assert res.status_code == 200
    mutations = res.json()
    assert len(mutations) >= 2

    out_mut = next(m for m in mutations if m["mutation_type"] == "allocation_out")
    in_mut = next(m for m in mutations if m["mutation_type"] == "allocation_in")

    assert out_mut["amount"] == 50_000
    assert in_mut["amount"] == 50_000
    assert out_mut["counterpart_pocket_name"] == "Kuota"
    assert in_mut["counterpart_pocket_name"] == "Kantong Utama"

    # Single pocket mutations
    res_kuota = client.get("/api/v1/pockets/kuota/mutations")
    assert res_kuota.status_code == 200
    kuota_muts = res_kuota.json()
    assert len(kuota_muts) >= 1
    assert kuota_muts[0]["mutation_type"] == "allocation_in"
    assert kuota_muts[0]["amount"] == 50_000


def test_transaction_creation_with_pocket_id_binding(client, jago_account, db_session):
    """
    Membuat transaksi dengan field `pocket_id` eksplisit mengaitkan transaksi langsung
    ke sub-kantong dan mengembalikan field pocket_id serta pocket_name pada TransactionOut.
    """
    client.get("/api/v1/pockets")
    gym_pocket = db_session.query(Pocket).filter(Pocket.slug == "gym").first()

    tx_res = client.post(
        "/api/v1/transactions",
        json={
            "type": "expense",
            "amount": 75_000,
            "account": "Bank Jago",
            "category": "Gym",
            "description": "Suplemen Whey Protein",
            "pocket_id": gym_pocket.id,
            "date": str(date.today()),
        },
    )
    assert tx_res.status_code == 200
    tx_data = tx_res.json()
    assert tx_data["pocket_id"] == gym_pocket.id
    assert tx_data["pocket_name"] == "GYM"

    # Verify pocket balance reflects deduction
    summary = client.get("/api/v1/pockets").json()
    pockets = {p["slug"]: p for p in summary["pockets"]}
    assert pockets["gym"]["spent_amount"] == 75_000
    assert pockets["gym"]["balance"] == 150_000  # 225k - 75k


def test_accounts_endpoint_returns_real_pocket_balance(client, jago_account):
    """
    Endpoint /api/v1/accounts menyertakan field `balance` dan `current_balance`
    pada setiap breakdown pocket, dengan jumlah total saldo sama persis dengan saldo rekening.
    """
    client.get("/api/v1/pockets")
    res = client.get("/api/v1/accounts")
    assert res.status_code == 200
    accounts = res.json()
    jago = next(a for a in accounts if a["id"] == jago_account.id)

    assert jago["current_balance"] == 1_000_000
    assert len(jago["pockets"]) >= 5

    # Check every pocket item has balance
    total_breakdown_bal = 0
    for p in jago["pockets"]:
        assert "balance" in p
        assert "current_balance" in p
        assert p["balance"] == p["current_balance"]
        total_breakdown_bal += p["balance"]

    assert total_breakdown_bal == jago["current_balance"] == 1_000_000
