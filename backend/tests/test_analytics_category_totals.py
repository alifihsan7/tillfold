from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.api.v1.endpoints.analytics import router
from app.db.session import Base, get_db
from app.models.transaction import Transaction
from app.models.user import User


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(id=1, username="category-test", full_name="Test User", hashed_password="not-a-login", is_active=True)
        other = User(id=2, username="other-test", full_name="Other Test User", hashed_password="not-a-login", is_active=True)
        db.add_all([user, other])
        db.flush()
        rows = [
            (1, "income", "Lainnya", 100, date(2026, 11, 1)),
            (1, "income", "Lainnya", 200, date(2026, 11, 30)),
            (1, "income", "Gaji", 700, date(2026, 11, 2)),
            (1, "expense", "Lainnya", 50, date(2026, 11, 2)),
            (1, "expense", "Makan", 150, date(2026, 11, 3)),
            (1, "transfer_in", "Lainnya", 9000, date(2026, 11, 3)),
            (1, "transfer_out", "Lainnya", 9000, date(2026, 11, 3)),
            (2, "income", "Lainnya", 9999, date(2026, 11, 3)),
            (1, "income", "Lainnya", 9999, date(2026, 10, 31)),
            (1, "income", "Lainnya", 9999, date(2026, 12, 1)),
        ]
        db.add_all(Transaction(user_id=uid, type=kind, category=category, amount=amount,
                               date=day, account="Akun uji", description="Data pengujian")
                   for uid, kind, category, amount, day in rows)
        db.commit()
        app = FastAPI()
        app.include_router(router, prefix="/analytics")
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: user
        with TestClient(app) as test_client:
            yield test_client
    engine.dispose()


def test_income_categories_are_scoped_and_do_not_change_expense_categories(client):
    response = client.get("/analytics/summary", params={
        "period_type": "custom", "start": "2026-11-01", "end": "2026-11-30",
    })
    assert response.status_code == 200, response.text
    result = response.json()
    income = {item["category"]: item for item in result["income_categories"]}
    expenses = {item["category"]: item for item in result["categories"]}
    assert result["income"] == 1000
    assert result["expense"] == 200
    assert income["Lainnya"] == {"category": "Lainnya", "total": 300, "count": 2, "percentage": 30.0}
    assert income["Gaji"]["percentage"] == 70.0
    assert expenses["Lainnya"] == {"category": "Lainnya", "total": 50, "count": 1, "percentage": 25.0}
    assert "Gaji" not in expenses
    assert "Makan" not in income


def test_empty_period_returns_empty_category_lists(client):
    response = client.get("/analytics/summary", params={
        "period_type": "custom", "start": "2030-01-01", "end": "2030-01-31",
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["income_categories"] == []
    assert result["categories"] == []
    assert result["income"] == 0


def test_safe_to_spend_decimal_all_inc_no_typeerror():
    """Verify Decimal aggregate for all_inc does not crash with TypeError against float percentage."""
    from app.models.account import Account
    from app.models.paycheck import PaycheckConfig, PaycheckBucket
    from app.services.analytics import compute_safe_to_spend_metrics

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(id=1, username="test-dec", full_name="Dec User", hashed_password="pw", is_active=True)
        acc_pocket = Account(id=1, user_id=1, name="Mandiri Utama", type="operasional")
        acc_payroll = Account(id=2, user_id=1, name="BCA Payroll", type="gajian")
        cfg = PaycheckConfig(id=1, user_id=1, pocket_account="Mandiri Utama", cycle_days=30, cycle_type="monthly_date")
        bucket = PaycheckBucket(id=1, config_id=1, account="Mandiri Utama", percentage=50.0, purpose="Operasional")
        db.add_all([user, acc_pocket, acc_payroll, cfg, bucket])
        db.commit()

        # Add an income transaction on BCA Payroll (so pocket_entries on Mandiri Utama is 0)
        tx = Transaction(user_id=1, type="income", category="Freelance", amount=10_000_000,
                         date=date(2026, 11, 5), account="BCA Payroll", description="Income")
        db.add(tx)
        db.commit()

        # Mock db.query().filter().scalar() to return Decimal('10000000.00')
        real_query = db.query
        def mock_query(*args, **kwargs):
            q = real_query(*args, **kwargs)
            # If querying func.coalesce for all_inc, return Decimal
            if len(args) == 1 and str(args[0]).startswith("coalesce"):
                mock_scalar = MagicMock(return_value=Decimal("10000000.00"))
                q.scalar = mock_scalar
            return q

        with patch.object(db, "query", side_effect=mock_query):
            res = compute_safe_to_spend_metrics(
                db=db,
                user_id=1,
                start_date=date(2026, 11, 1),
                end_date=date(2026, 11, 30),
                period_type="cycle",
                today_wib=date(2026, 11, 10),
            )
            # 50% of 10,000,000 is 5,000,000
            assert res.pocket_budget == 5_000_000
    engine.dispose()


def test_safe_to_spend_prefers_fixed_amount():
    """Verify PaycheckBucket fixed_amount takes priority over percentage calculation."""
    from app.models.account import Account
    from app.models.paycheck import PaycheckConfig, PaycheckBucket
    from app.services.analytics import compute_safe_to_spend_metrics

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(id=1, username="test-fixed", full_name="Fixed User", hashed_password="pw", is_active=True)
        acc_pocket = Account(id=1, user_id=1, name="Mandiri Utama", type="operasional")
        acc_payroll = Account(id=2, user_id=1, name="BCA Payroll", type="gajian")
        cfg = PaycheckConfig(id=1, user_id=1, pocket_account="Mandiri Utama", cycle_days=30, cycle_type="monthly_date")
        # fixed_amount = 3_500_000, percentage = 50.0
        bucket = PaycheckBucket(id=1, config_id=1, account="Mandiri Utama", percentage=50.0,
                                fixed_amount=3_500_000, purpose="Operasional")
        db.add_all([user, acc_pocket, acc_payroll, cfg, bucket])
        db.commit()

        # Add income of 10_000_000 on BCA Payroll so Mandiri Utama has pocket_entries == 0
        tx = Transaction(user_id=1, type="income", category="Salary", amount=10_000_000,
                         date=date(2026, 11, 5), account="BCA Payroll", description="Income")
        db.add(tx)
        db.commit()

        res = compute_safe_to_spend_metrics(
            db=db,
            user_id=1,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 30),
            period_type="cycle",
            today_wib=date(2026, 11, 10),
        )
        assert res.pocket_budget == 3_500_000
    engine.dispose()


def test_safe_to_spend_decimal_salary():
    """Verify Decimal salary does not crash with TypeError against float percentage."""
    from app.models.account import Account
    from app.models.paycheck import PaycheckConfig, PaycheckBucket
    from app.services.analytics import compute_safe_to_spend_metrics

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(id=1, username="test-salary", full_name="Salary User", hashed_password="pw", is_active=True)
        acc = Account(id=1, user_id=1, name="Mandiri Utama", type="operasional")
        cfg = PaycheckConfig(id=1, user_id=1, pocket_account="Mandiri Utama", cycle_days=30, cycle_type="monthly_date")
        bucket = PaycheckBucket(id=1, config_id=1, account="Mandiri Utama", percentage=40.0, purpose="Operasional")
        db.add_all([user, acc, cfg, bucket])
        db.commit()

        with patch.object(PaycheckConfig, "total_salary", new_callable=lambda: property(lambda self: Decimal("8000000.00"))):
            res = compute_safe_to_spend_metrics(
                db=db,
                user_id=1,
                start_date=date(2026, 11, 1),
                end_date=date(2026, 11, 30),
                period_type="cycle",
                today_wib=date(2026, 11, 10),
            )
            assert res.pocket_budget == 3_200_000
    engine.dispose()


def test_analytics_summary_cycle_endpoint_200(client):
    """Verify GET /analytics/summary?period_type=cycle succeeds with 200 OK."""
    response = client.get("/analytics/summary", params={"period_type": "cycle"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert "safe_to_spend" in data
    assert data["safe_to_spend"] is not None
