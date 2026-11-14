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
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from main import app

# In-memory SQLite for deterministic, isolated backend tests
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
        username="zephyr_dev",
        hashed_password="dummy_secure_hash",
        telegram_chat_id=111111,
        full_name="Zephyr Developer",
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
        username="other_dev",
        hashed_password="dummy_secure_hash",
        telegram_chat_id=222222,
        full_name="Other Developer",
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


def test_pockets_default_seeding(client, db_session, test_user):
    """Verifies idempotent default seeding of the 5 canonical pockets."""
    response = client.get("/api/v1/pockets")
    assert response.status_code == 200
    data = response.json()

    assert "pockets" in data
    assert len(data["pockets"]) == 5

    slugs = {p["slug"]: p for p in data["pockets"]}
    assert "gym" in slugs
    assert "claude" in slugs
    assert "kuota" in slugs
    assert "visa" in slugs
    assert "utama" in slugs

    # Assert default target allocations
    assert slugs["gym"]["target_amount"] == 225_000
    assert slugs["gym"]["name"] == "GYM"
    assert slugs["claude"]["target_amount"] == 75_000
    assert slugs["claude"]["name"] == "Subscription Claude"
    assert slugs["kuota"]["target_amount"] == 50_000
    assert slugs["visa"]["target_amount"] == 50_000
    # Kantong Utama defaults to 0 (or dynamic remaining from Jago balance)
    assert slugs["utama"]["spent_amount"] == 0

    # Ensure idempotence on second GET
    response_second = client.get("/api/v1/pockets")
    assert response_second.status_code == 200
    assert len(response_second.json()["pockets"]) == 5


def test_pockets_do_not_guess_subscription_links(db_session, test_user):
    """Matching names do not overwrite manual targets without an explicit link."""
    # Seed active subscriptions before first pocket access
    sub_gym = Subscription(
        user_id=test_user.id,
        name="FitHub Gym Membership",
        amount=350_000,
        category="Gym & Fitness",
        account="Bank Jago",
        is_active=True,
    )
    sub_claude = Subscription(
        user_id=test_user.id,
        name="Anthropic Claude Pro",
        amount=315_000,
        category="Langganan AI",
        account="Bank Jago",
        is_active=True,
    )
    db_session.add_all([sub_gym, sub_claude])
    db_session.commit()

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

    response = c.get("/api/v1/pockets")
    assert response.status_code == 200
    data = response.json()
    slugs = {p["slug"]: p for p in data["pockets"]}

    assert slugs["gym"]["target_amount"] == 225_000
    assert slugs["claude"]["target_amount"] == 75_000
    assert slugs["gym"]["subscription_id"] is None
    assert slugs["kuota"]["target_amount"] == 50_000  # Default fallback
    assert slugs["visa"]["target_amount"] == 50_000   # Default fallback

    app.dependency_overrides.clear()


def test_pockets_auto_deduction_and_balance(client, db_session, test_user):
    """
    Verifies auto-deduction logic:
    - GYM deduction via keyword or category
    - Claude deduction via keyword/AI
    - Kuota deduction
    - VISA deduction
    - Kantong Utama fallback
    - Non-Jago transactions are ignored
    - Total Jago bank balance calculation
    """
    today = date.today()

    # Configure cycle
    cfg = PaycheckConfig(
        user_id=test_user.id,
        source_account="Mandiri",
        pocket_account="Bank Jago",
        cycle_type="monthly",
        cycle_days=30,
        cycle_start_date=today,
        is_active=True,
    )
    db_session.add(cfg)

    # 1. Bank Jago initial income
    tx_income = Transaction(
        user_id=test_user.id,
        type="income",
        amount=1_000_000,
        account="Bank Jago",
        category="Gajian",
        description="Transfer Alokasi Jago",
        date=today,
    )

    # 2. Expense for GYM
    tx_gym = Transaction(
        user_id=test_user.id,
        type="expense",
        amount=225_000,
        account="Bank Jago",
        category="Gym & Fitness",
        description="FitHub Membership Renewal",
        date=today,
    )

    # 3. Expense for Claude
    tx_claude = Transaction(
        user_id=test_user.id,
        type="expense",
        amount=75_000,
        account="Bank Jago",
        category="Langganan",
        description="Subscription Claude Pro AI",
        date=today,
    )

    # 4. Expense for Kuota
    tx_kuota = Transaction(
        user_id=test_user.id,
        type="expense",
        amount=45_000,
        account="Bank Jago",
        category="Tagihan",
        description="Paket Data Telkomsel 20GB",
        date=today,
    )

    # 5. Expense for VISA
    tx_visa = Transaction(
        user_id=test_user.id,
        type="expense",
        amount=30_000,
        account="Bank Jago",
        category="Belanja Online",
        description="Online Debit VISA Merchant",
        date=today,
    )

    # 6. Expense for Kantong Utama (fallback)
    tx_utama = Transaction(
        user_id=test_user.id,
        type="expense",
        amount=50_000,
        account="Bank Jago",
        category="Makanan & Minuman",
        description="Kopi Kenangan Senopati",
        date=today,
    )

    # 7. Expense on another account (Mandiri) - MUST NOT DEDUCT JAGO POCKETS
    tx_mandiri = Transaction(
        user_id=test_user.id,
        type="expense",
        amount=200_000,
        account="Mandiri",
        category="Gym & Fitness",
        description="Another Gym Mandiri",
        date=today,
    )

    db_session.add_all([tx_income, tx_gym, tx_claude, tx_kuota, tx_visa, tx_utama, tx_mandiri])
    db_session.commit()

    response = client.get("/api/v1/pockets")
    assert response.status_code == 200
    data = response.json()

    # Total pocket balance: 1,000,000 income - (225k + 75k + 45k + 30k + 50k = 425k expenses) = 575,000
    assert data["total_balance"] == 575_000
    assert data["total_pocket_balance"] == 575_000
    assert data["total_jago_balance"] == 575_000

    slugs = {p["slug"]: p for p in data["pockets"]}

    # GYM
    assert slugs["gym"]["target_amount"] == 225_000
    assert slugs["gym"]["spent_amount"] == 225_000
    assert slugs["gym"]["remaining_amount"] == 0
    assert slugs["gym"]["percentage_spent"] == 100.0

    # Claude
    assert slugs["claude"]["target_amount"] == 75_000
    assert slugs["claude"]["spent_amount"] == 75_000
    assert slugs["claude"]["remaining_amount"] == 0
    assert slugs["claude"]["percentage_spent"] == 100.0

    # Kuota
    assert slugs["kuota"]["target_amount"] == 50_000
    assert slugs["kuota"]["spent_amount"] == 45_000
    assert slugs["kuota"]["remaining_amount"] == 5_000
    assert slugs["kuota"]["percentage_spent"] == 90.0

    # VISA
    assert slugs["visa"]["target_amount"] == 50_000
    assert slugs["visa"]["spent_amount"] == 30_000
    assert slugs["visa"]["remaining_amount"] == 20_000
    assert slugs["visa"]["percentage_spent"] == 60.0

    # Kantong Utama: target is dynamic sisa penampung:
    # other targets sum = 225k + 75k + 50k + 50k = 400k.
    # Add back the 425,000 in expenses before allocating the 575,000 ledger balance.
    assert slugs["utama"]["target_amount"] == 600_000
    assert slugs["utama"]["spent_amount"] == 50_000
    assert slugs["utama"]["remaining_amount"] == 550_000
    assert slugs["utama"]["percentage_spent"] == 8.3
    assert data["total_remaining_amount"] == data["total_jago_balance"]


def test_pockets_put_updates(client, db_session, test_user):
    """Verifies updating target allocations via PUT /api/v1/pockets."""
    # Seed pockets first
    client.get("/api/v1/pockets")

    # 1. Update using list payload
    payload_list = [
        {"slug": "gym", "target_amount": 250_000},
        {"slug": "claude", "target_amount": 80_000},
    ]
    res1 = client.put("/api/v1/pockets", json=payload_list)
    assert res1.status_code == 200
    slugs1 = {p["slug"]: p for p in res1.json()["pockets"]}
    assert slugs1["gym"]["target_amount"] == 250_000
    assert slugs1["claude"]["target_amount"] == 80_000

    # 2. Update using dict wrapper {"pockets": [...]}
    payload_dict = {
        "pockets": [
            {"slug": "kuota", "target_amount": 60_000},
            {"slug": "visa", "target_amount": 75_000},
        ]
    }
    res2 = client.put("/api/v1/pockets", json=payload_dict)
    assert res2.status_code == 200
    slugs2 = {p["slug"]: p for p in res2.json()["pockets"]}
    assert slugs2["kuota"]["target_amount"] == 60_000
    assert slugs2["visa"]["target_amount"] == 75_000

    # 3. Update using slug-key mapping {"gym": 260000}
    payload_kv = {"gym": 260_000}
    res3 = client.put("/api/v1/pockets", json=payload_kv)
    assert res3.status_code == 200
    slugs3 = {p["slug"]: p for p in res3.json()["pockets"]}
    assert slugs3["gym"]["target_amount"] == 260_000


def test_pockets_single_pocket_endpoints(client, db_session, test_user):
    """Verifies GET /{slug} and PUT /{slug} endpoints."""
    # Ensure seeded
    client.get("/api/v1/pockets")

    # Get single pocket
    get_res = client.get("/api/v1/pockets/gym")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["slug"] == "gym"
    assert data["name"] == "GYM"

    # Put single pocket
    put_res = client.put("/api/v1/pockets/gym", json={"target_amount": 280_000})
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["slug"] == "gym"
    assert updated["target_amount"] == 280_000

    # 404 for non-existent slug
    notFound = client.get("/api/v1/pockets/non_existent_pocket")
    assert notFound.status_code == 404


def test_pockets_tenant_isolation(client, db_session, test_user, other_user):
    """Ensures strict multi-tenant isolation: user data never leaks across users."""
    today = date.today()

    # Create transaction for other user on Bank Jago
    tx_other = Transaction(
        user_id=other_user.id,
        type="expense",
        amount=999_999,
        account="Bank Jago",
        category="Gym & Fitness",
        description="Other User Gym Expense",
        date=today,
    )
    db_session.add(tx_other)
    db_session.commit()

    # Current user requests pockets
    res = client.get("/api/v1/pockets")
    assert res.status_code == 200
    data = res.json()
    slugs = {p["slug"]: p for p in data["pockets"]}

    # Current user's gym spent amount MUST be 0
    assert slugs["gym"]["spent_amount"] == 0
    assert slugs["gym"]["user_id"] == test_user.id


def test_pockets_total_pocket_balance_alias(client, db_session, test_user):
    """Verifies that total_pocket_balance is present and matches total_jago_balance."""
    response = client.get("/api/v1/pockets")
    assert response.status_code == 200
    data = response.json()
    assert "total_pocket_balance" in data
    assert "total_jago_balance" in data
    assert data["total_pocket_balance"] == data["total_jago_balance"]


def test_pockets_dynamic_account_resolution(client, db_session, test_user):
    """Verifies that pocket balance & expenses resolve dynamically for accounts named 'Kantong' or non-utama."""
    today = date.today()
    # Create custom account with 'kantong' in name
    kantong_acc = Account(
        user_id=test_user.id,
        name="Kantong Tagihan",
        type="operasional",
        tag="Subs & Tagihan",
        initial_balance=0,
    )
    db_session.add(kantong_acc)
    db_session.commit()

    # Funding income transaction
    tx_inc = Transaction(
        user_id=test_user.id,
        type="income",
        amount=300_000,
        account="Kantong Tagihan",
        category="Gajian",
        description="Alokasi Gajian Kantong Tagihan",
        date=today,
    )
    # Expense on this custom pocket account
    tx_exp = Transaction(
        user_id=test_user.id,
        type="expense",
        amount=50_000,
        account="Kantong Tagihan",
        category="Tagihan",
        description="Paket Kuota Bulanan",
        date=today,
    )
    db_session.add_all([tx_inc, tx_exp])
    db_session.commit()

    response = client.get("/api/v1/pockets")
    assert response.status_code == 200
    data = response.json()
    slugs = {p["slug"]: p for p in data["pockets"]}
    assert slugs["kuota"]["spent_amount"] == 50_000
    assert data["total_pocket_balance"] == 250_000
    assert data["total_jago_balance"] == 250_000


def test_pocket_envelopes_bot_generalization(db_session, test_user):
    """Verifies bot pocket envelope calculations and dynamic pocket matching."""
    from app.bot.bot import (
        get_pocket_envelopes,
        get_mandiri_envelopes,
        is_matching_pocket_account,
        get_pocket_account_variants,
    )

    # 1. Verification of get_pocket_envelopes & backward compat alias
    env_pocket = get_pocket_envelopes(30)
    env_mandiri = get_mandiri_envelopes(30)
    assert env_pocket == env_mandiri
    assert env_pocket["Makanan & Minuman"] == 450_000
    assert env_pocket["Jajan / Ngopi"] == 100_000

    # 2. Matching with custom bank/pocket accounts
    assert is_matching_pocket_account("BCA", "BCA") is True
    assert is_matching_pocket_account("bca", "BCA") is True
    assert is_matching_pocket_account("BRI", "BCA") is False

    # 3. Inter-compatibility for operational/mandiri/saku defaults
    assert is_matching_pocket_account("Mandiri", "Rekening Utama") is True
    assert is_matching_pocket_account("saku", "operasional") is True

    # 4. Variants generation
    variants_custom = get_pocket_account_variants("BCA")
    assert "bca" in variants_custom

    variants_mandiri = get_pocket_account_variants("Mandiri")
    assert "mandiri" in variants_mandiri
    assert "rekening utama" in variants_mandiri


def test_pockets_deprecated_jago_pockets_alias_backward_compatibility(client, test_user):
    """
    Verifies that legacy /api/v1/jago-pockets route remains operational as a
    deprecated alias during transitional migration while returning universal data.
    """
    res_universal = client.get("/api/v1/pockets")
    assert res_universal.status_code == 200

    res_deprecated = client.get("/api/v1/jago-pockets")
    assert res_deprecated.status_code == 200

    data_u = res_universal.json()
    data_d = res_deprecated.json()

    assert data_u["total_balance"] == data_d["total_balance"]
    assert data_u["total_pocket_balance"] == data_d["total_pocket_balance"]
    assert len(data_u["pockets"]) == len(data_d["pockets"])
