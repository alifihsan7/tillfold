from datetime import datetime
import zoneinfo
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import Base, get_db
from app.models.account import Account
from app.models.pocket import Pocket, PocketMutation
from app.models.internal_loan import InternalLoan
from app.models.paycheck import PaycheckConfig
from app.models.transaction import Transaction
from app.models.user import User
from main import app

WIB = zoneinfo.ZoneInfo(settings.TIMEZONE)

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
        username="zephyr_loans",
        hashed_password="dummy_secure_hash",
        telegram_chat_id=123123,
        full_name="Zephyr Software Architect",
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
        username="other_dev_loans",
        hashed_password="dummy_secure_hash",
        telegram_chat_id=999999,
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
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def seed_account_with_balance(db, user_id, name, type="operasional", balance=0):
    acc = Account(user_id=user_id, name=name, type=type, initial_balance=balance)
    db.add(acc)
    db.commit()
    db.refresh(acc)
    if balance > 0:
        tx = Transaction(
            user_id=user_id,
            type="income",
            amount=balance,
            account=name,
            category="Penyesuaian Saldo",
            description="Saldo Awal",
            date=datetime.now(WIB).date(),
        )
        db.add(tx)
        db.commit()
    return acc


def test_create_internal_loan_success_atomic_ledger(client, db_session, test_user):
    # Setup accounts
    bri = seed_account_with_balance(db_session, test_user.id, "BRI 2", type="darurat", balance=1_000_000)
    mandiri = seed_account_with_balance(db_session, test_user.id, "Mandiri", type="operasional", balance=200_000)

    payload = {
        "source_account_id": bri.id,
        "target_account_id": mandiri.id,
        "amount": 400_000,
        "note": "Kas darurat untuk operasional",
    }
    response = client.post("/api/v1/internal-loans", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()

    assert data["amount"] == 400_000
    assert data["remaining_amount"] == 400_000
    assert data["status"] == "active"
    assert data["source_account_id"] == bri.id
    assert data["source_account_name"] == "BRI 2"
    assert data["target_account_id"] == mandiri.id
    assert data["target_account_name"] == "Mandiri"
    assert data["note"] == "Kas darurat untuk operasional"
    assert data["settled_at"] is None

    loan_id = data["id"]

    # Verify ledger transactions
    tx_out = db_session.query(Transaction).filter(
        Transaction.user_id == test_user.id,
        Transaction.type == "transfer_out",
        Transaction.account == "BRI 2",
    ).first()
    assert tx_out is not None
    assert tx_out.amount == 400_000
    assert f"[internal_loan_id:{loan_id}]" in tx_out.raw_text

    tx_in = db_session.query(Transaction).filter(
        Transaction.user_id == test_user.id,
        Transaction.type == "transfer_in",
        Transaction.account == "Mandiri",
    ).first()
    assert tx_in is not None
    assert tx_in.amount == 400_000
    assert f"[internal_loan_id:{loan_id}]" in tx_in.raw_text

    # Cross-link verification
    assert f"[pair_id:{tx_in.id}]" in tx_out.raw_text
    assert f"[pair_id:{tx_out.id}]" in tx_in.raw_text

    # Net worth balance verification
    acc_res = client.get("/api/v1/accounts").json()
    balances = {a["name"]: a["current_balance"] for a in acc_res}
    assert balances["BRI 2"] == 600_000
    assert balances["Mandiri"] == 600_000
    assert sum(balances.values()) == 1_200_000  # Conserved net worth


def test_create_internal_loan_validation_errors(client, db_session, test_user):
    bri = seed_account_with_balance(db_session, test_user.id, "BRI 2", type="darurat", balance=100_000)
    mandiri = seed_account_with_balance(db_session, test_user.id, "Mandiri", type="operasional", balance=50_000)

    # 1. Zero or negative amount
    res = client.post("/api/v1/internal-loans", json={
        "source_account_id": bri.id,
        "target_account_id": mandiri.id,
        "amount": 0,
    })
    assert res.status_code == 422 or res.status_code == 400

    # 2. Same account without pockets
    res = client.post("/api/v1/internal-loans", json={
        "source_account_id": bri.id,
        "target_account_id": bri.id,
        "amount": 50_000,
    })
    assert res.status_code == 400
    assert "sama" in res.json()["detail"].lower()

    # 3. Insufficient source balance (has 100k, requested 500k)
    res = client.post("/api/v1/internal-loans", json={
        "source_account_id": bri.id,
        "target_account_id": mandiri.id,
        "amount": 500_000,
    })
    assert res.status_code == 400
    assert "tidak mencukupi" in res.json()["detail"].lower()

    # 4. Non-existent account
    res = client.post("/api/v1/internal-loans", json={
        "source_account_id": 9999,
        "target_account_id": mandiri.id,
        "amount": 10_000,
    })
    assert res.status_code == 404

    # 5. Archived account
    bri.is_archived = True
    db_session.commit()
    res = client.post("/api/v1/internal-loans", json={
        "source_account_id": bri.id,
        "target_account_id": mandiri.id,
        "amount": 10_000,
    })
    assert res.status_code == 400
    assert "diarsipkan" in res.json()["detail"].lower()


def test_create_internal_loan_with_pockets(client, db_session, test_user):
    acc = seed_account_with_balance(db_session, test_user.id, "Bank Jago", type="operasional", balance=1_000_000)

    # Create two pockets on same account
    p_tagihan = Pocket(user_id=test_user.id, account_id=acc.id, name="Tagihan Listrik", slug="tagihan-listrik", role="tagihan", balance=400_000, target_amount=400_000)
    p_operasional = Pocket(user_id=test_user.id, account_id=acc.id, name="Kantong Utama", slug="utama", role="operasional", balance=600_000, target_amount=600_000)
    db_session.add_all([p_tagihan, p_operasional])
    db_session.commit()

    # Borrow from tagihan pocket to operasional pocket within same account
    res = client.post("/api/v1/internal-loans", json={
        "source_account_id": acc.id,
        "source_pocket_id": p_tagihan.id,
        "target_account_id": acc.id,
        "target_pocket_id": p_operasional.id,
        "amount": 150_000,
        "note": "Pinjam dana tagihan untuk operasional",
    })
    assert res.status_code == 201, res.text
    data = response_loan = res.json()
    assert data["source_pocket_name"] == "Tagihan Listrik"
    assert data["target_pocket_name"] == "Kantong Utama"

    # Check pocket balance reduction
    db_session.refresh(p_tagihan)
    assert p_tagihan.balance == 250_000

    # Check pocket mutations recorded
    muts = db_session.query(PocketMutation).filter(PocketMutation.user_id == test_user.id).all()
    assert len(muts) >= 2


def test_settle_partial_and_full_internal_loan(client, db_session, test_user):
    # Setup accounts
    bri = seed_account_with_balance(db_session, test_user.id, "BRI 2", type="darurat", balance=1_000_000)
    mandiri = seed_account_with_balance(db_session, test_user.id, "Mandiri", type="operasional", balance=100_000)

    # Create loan of 600,000 from BRI 2 to Mandiri
    create_res = client.post("/api/v1/internal-loans", json={
        "source_account_id": bri.id,
        "target_account_id": mandiri.id,
        "amount": 600_000,
        "note": "Dana talangan proyek",
    })
    assert create_res.status_code == 201
    loan_id = create_res.json()["id"]

    # Now Mandiri has 100k + 600k = 700k; BRI 2 has 400k.
    # 1. Partial settlement of 200,000
    settle1 = client.post(f"/api/v1/internal-loans/{loan_id}/settle", json={
        "amount": 200_000,
        "note": "Cicilan 1 gajian parsial",
    })
    assert settle1.status_code == 200, settle1.text
    s1_data = settle1.json()
    assert s1_data["remaining_amount"] == 400_000
    assert s1_data["status"] == "active"
    assert s1_data["settled_at"] is None

    # Check balances after partial settlement:
    # Mandiri: 700k - 200k = 500k; BRI 2: 400k + 200k = 600k
    acc_res = client.get("/api/v1/accounts").json()
    balances = {a["name"]: a["current_balance"] for a in acc_res}
    assert balances["Mandiri"] == 500_000
    assert balances["BRI 2"] == 600_000

    # 2. Full settlement (empty amount payload = settle remaining 400,000)
    settle2 = client.post(f"/api/v1/internal-loans/{loan_id}/settle", json={})
    assert settle2.status_code == 200, settle2.text
    s2_data = settle2.json()
    assert s2_data["remaining_amount"] == 0
    assert s2_data["status"] == "settled"
    assert s2_data["settled_at"] is not None

    # Final balances: Mandiri: 100k; BRI 2: 1,000k (fully restored)
    acc_res_final = client.get("/api/v1/accounts").json()
    balances_final = {a["name"]: a["current_balance"] for a in acc_res_final}
    assert balances_final["Mandiri"] == 100_000
    assert balances_final["BRI 2"] == 1_000_000


def test_settle_insufficient_debtor_balance(client, db_session, test_user):
    bri = seed_account_with_balance(db_session, test_user.id, "BRI 2", type="darurat", balance=500_000)
    mandiri = seed_account_with_balance(db_session, test_user.id, "Mandiri", type="operasional", balance=0)

    # Loan of 300,000 from BRI 2 -> Mandiri
    create_res = client.post("/api/v1/internal-loans", json={
        "source_account_id": bri.id,
        "target_account_id": mandiri.id,
        "amount": 300_000,
    })
    assert create_res.status_code == 201
    loan_id = create_res.json()["id"]

    # Now spend Mandiri down to 50,000
    tx_spend = Transaction(
        user_id=test_user.id,
        type="expense",
        amount=250_000,
        account="Mandiri",
        category="Belanja",
        description="Belanja darurat",
        date=datetime.now(WIB).date(),
    )
    db_session.add(tx_spend)
    db_session.commit()

    # Attempt to settle 100,000 when Mandiri only has 50,000
    res = client.post(f"/api/v1/internal-loans/{loan_id}/settle", json={"amount": 100_000})
    assert res.status_code == 400
    assert "tidak mencukupi" in res.json()["detail"].lower()


def test_settle_inactive_or_cancelled_loan_rejected(client, db_session, test_user):
    bri = seed_account_with_balance(db_session, test_user.id, "BRI 2", type="darurat", balance=500_000)
    mandiri = seed_account_with_balance(db_session, test_user.id, "Mandiri", type="operasional", balance=500_000)

    create_res = client.post("/api/v1/internal-loans", json={
        "source_account_id": bri.id,
        "target_account_id": mandiri.id,
        "amount": 100_000,
    })
    loan_id = create_res.json()["id"]

    # Settle full
    client.post(f"/api/v1/internal-loans/{loan_id}/settle", json={})

    # Re-settle should be rejected
    res = client.post(f"/api/v1/internal-loans/{loan_id}/settle", json={})
    assert res.status_code == 400
    assert "status" in res.json()["detail"].lower()


def test_list_internal_loans_filter_and_summary(client, db_session, test_user):
    bri = seed_account_with_balance(db_session, test_user.id, "BRI 2", type="darurat", balance=2_000_000)
    mandiri = seed_account_with_balance(db_session, test_user.id, "Mandiri", type="operasional", balance=2_000_000)

    # Loan 1: active (300k)
    l1 = client.post("/api/v1/internal-loans", json={"source_account_id": bri.id, "target_account_id": mandiri.id, "amount": 300_000}).json()
    # Loan 2: will settle (200k)
    l2 = client.post("/api/v1/internal-loans", json={"source_account_id": bri.id, "target_account_id": mandiri.id, "amount": 200_000}).json()
    client.post(f"/api/v1/internal-loans/{l2['id']}/settle", json={})
    # Loan 3: will cancel (150k)
    l3 = client.post("/api/v1/internal-loans", json={"source_account_id": bri.id, "target_account_id": mandiri.id, "amount": 150_000}).json()
    client.delete(f"/api/v1/internal-loans/{l3['id']}")

    # 1. List active
    res_active = client.get("/api/v1/internal-loans?status=active").json()
    assert res_active["total"] == 1
    assert res_active["total_active_loan_amount"] == 300_000
    assert res_active["items"][0]["id"] == l1["id"]

    # 2. List settled
    res_settled = client.get("/api/v1/internal-loans?status=settled").json()
    assert res_settled["total"] == 1
    assert res_settled["total_active_loan_amount"] == 300_000
    assert res_settled["items"][0]["id"] == l2["id"]

    # 3. List cancelled
    res_cancelled = client.get("/api/v1/internal-loans?status=cancelled").json()
    assert res_cancelled["total"] == 1
    assert res_cancelled["total_active_loan_amount"] == 300_000
    assert res_cancelled["items"][0]["id"] == l3["id"]

    # 4. List all
    res_all = client.get("/api/v1/internal-loans?status=all").json()
    assert res_all["total"] == 3
    assert res_all["total_active_loan_amount"] == 300_000


def test_cancel_internal_loan(client, db_session, test_user):
    bri = seed_account_with_balance(db_session, test_user.id, "BRI 2", type="darurat", balance=500_000)
    mandiri = seed_account_with_balance(db_session, test_user.id, "Mandiri", type="operasional", balance=100_000)

    loan = client.post("/api/v1/internal-loans", json={
        "source_account_id": bri.id,
        "target_account_id": mandiri.id,
        "amount": 250_000,
        "note": "Salah input",
    }).json()

    cancel_res = client.delete(f"/api/v1/internal-loans/{loan['id']}")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    # Cannot cancel twice
    res2 = client.delete(f"/api/v1/internal-loans/{loan['id']}")
    assert res2.status_code == 400

    # Total active amount excludes cancelled
    summary = client.get("/api/v1/internal-loans").json()
    assert summary["total_active_loan_amount"] == 0


def test_tenant_isolation_internal_loans(client, db_session, test_user, other_user):
    u1_bri = seed_account_with_balance(db_session, test_user.id, "BRI U1", type="darurat", balance=500_000)
    u1_mandiri = seed_account_with_balance(db_session, test_user.id, "Mandiri U1", type="operasional", balance=100_000)

    u2_bca = seed_account_with_balance(db_session, other_user.id, "BCA U2", type="operasional", balance=500_000)
    u2_cimb = seed_account_with_balance(db_session, other_user.id, "CIMB U2", type="darurat", balance=500_000)

    # U1 creates loan
    create_res = client.post("/api/v1/internal-loans", json={
        "source_account_id": u1_bri.id,
        "target_account_id": u1_mandiri.id,
        "amount": 100_000,
    })
    assert create_res.status_code == 201
    l1 = create_res.json()

    # Switch session context to other_user
    app.dependency_overrides[get_current_user] = lambda: other_user

    # Other user attempts to fetch U1's loan
    res = client.get(f"/api/v1/internal-loans/{l1['id']}")
    assert res.status_code == 404

    # Other user attempts to settle U1's loan
    res = client.post(f"/api/v1/internal-loans/{l1['id']}/settle", json={})
    assert res.status_code == 404

    # Other user attempts to cancel U1's loan
    res = client.delete(f"/api/v1/internal-loans/{l1['id']}")
    assert res.status_code == 404

    # Other user list does not include U1's loan
    other_list = client.get("/api/v1/internal-loans").json()
    assert other_list["total"] == 0
    assert other_list["total_active_loan_amount"] == 0


def test_paycheck_and_analytics_integration(client, db_session, test_user):
    bri = seed_account_with_balance(db_session, test_user.id, "BRI 2", type="darurat", balance=1_000_000)
    mandiri = seed_account_with_balance(db_session, test_user.id, "Mandiri", type="operasional", balance=1_000_000)

    # Create active loan: 450,000
    loan = client.post("/api/v1/internal-loans", json={
        "source_account_id": bri.id,
        "target_account_id": mandiri.id,
        "amount": 450_000,
    }).json()

    # 1. Paycheck config endpoint includes total_active_loan_amount and active_internal_loans
    cfg_res = client.get("/api/v1/paycheck/config")
    assert cfg_res.status_code == 200
    cfg_data = cfg_res.json()
    assert cfg_data["total_active_loan_amount"] == 450_000
    assert len(cfg_data["active_internal_loans"]) == 1
    assert cfg_data["active_internal_loans"][0]["id"] == loan["id"]

    # 2. Analytics summary endpoint includes total_active_loan_amount
    summary_res = client.get("/api/v1/analytics/summary", params={"period_type": "month"})
    assert summary_res.status_code == 200
    summary_data = summary_res.json()
    assert summary_data["total_active_loan_amount"] == 450_000

    # 3. Auto-settle endpoint during paycheck
    auto_res = client.post("/api/v1/paycheck/auto-settle-loans", params={"account_id": mandiri.id})
    assert auto_res.status_code == 200
    auto_data = auto_res.json()
    assert auto_data["status"] == "success"
    assert auto_data["settled_count"] == 1
    assert auto_data["settled_loans"][0]["status"] == "settled"

    # Verify loan status after auto-settle
    loan_after = client.get(f"/api/v1/internal-loans/{loan['id']}").json()
    assert loan_after["status"] == "settled"
    assert loan_after["remaining_amount"] == 0
