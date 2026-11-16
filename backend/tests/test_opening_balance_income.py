from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.api.v1.endpoints.analytics import router as analytics_router
from app.api.v1.endpoints.transactions import router as transactions_router
from app.db.session import Base, get_db
from app.models.transaction import Transaction
from app.models.user import User


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(id=1, username="opening-test", full_name="Test User", hashed_password="x", is_active=True)
        db.add(user)
        db.flush()
        rows = [
            ("income", "Saldo Awal", 7_000_000, date(2026, 11, 9)),
            ("income", "Gaji", 4_000_000, date(2026, 11, 9)),
            ("expense", "Makan", 1_000_000, date(2026, 11, 10)),
        ]
        db.add_all(Transaction(user_id=1, type=kind, category=cat, amount=amount, date=day,
                               account="BCA", description="uji")
                   for kind, cat, amount, day in rows)
        db.commit()
        app = FastAPI()
        app.include_router(analytics_router, prefix="/analytics")
        app.include_router(transactions_router, prefix="/transactions")
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: user
        with TestClient(app) as test_client:
            yield test_client
    engine.dispose()


PERIOD = {"period_type": "custom", "start": "2026-11-09", "end": "2026-11-22"}


def test_summary_reports_opening_balance_apart_from_income(client):
    result = client.get("/analytics/summary", params=PERIOD).json()
    assert result["income"] == 4_000_000
    assert result["opening_balance"] == 7_000_000
    assert result["net"] == 3_000_000
    assert result["savings_rate"] == 75.0
    assert [c["category"] for c in result["income_categories"]] == ["Gaji"]
    day = next(d for d in result["daily_trend"] if d["date"] == "2026-11-09")
    assert day["income"] == 4_000_000
    # The opening balance still counts toward what the account holds.
    assert result["total_balance"] == 10_000_000


def test_history_totals_report_opening_balance_apart_from_income(client):
    result = client.get("/transactions/history").json()
    assert result["total"] == 3
    assert result["income"] == 4_000_000
    assert result["opening_balance"] == 7_000_000
    assert result["net"] == 3_000_000
