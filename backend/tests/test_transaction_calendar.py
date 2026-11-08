from datetime import date

import pytest

from app.api.deps import get_current_user
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from test_ledger_workflow import ledger


def add(db, kind, amount, day, account="Bank", user_id=1):
    db.add(Transaction(user_id=user_id, type=kind, amount=amount, date=day,
                       account=account, category="Calendar", description="Calendar test"))


def month(client, year=2026, month=11, **params):
    response = client.get("/transactions/calendar", params={"year": year, "month": month, **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_daily_totals_cover_all_rows_and_separate_transfers_adjustments(ledger):
    client, db = ledger
    day = date(2026, 11, 8)
    for _ in range(150):
        add(db, "expense", 10, day)
    for kind, amount, account in [("income", 5000, "Bank"), ("transfer_out", 200, "Bank"),
                                  ("transfer_in", 200, "Cash"), ("adjustment_in", 40, "Bank"),
                                  ("adjustment_out", 20, "Bank")]:
        add(db, kind, amount, day, account)
    add(db, "expense", 70, date(2026, 10, 31))
    add(db, "income", 10000, date(2026, 12, 1))
    db.commit()
    report = month(client)
    assert len(report["days"]) == 30
    selected = report["days"][7]
    assert selected["date"] == "2026-11-08"
    assert (selected["income"], selected["expense"], selected["net"], selected["count"]) == (5000, 1500, 3500, 155)
    assert (selected["transfer_in"], selected["transfer_out"], selected["transfer_count"]) == (200, 200, 2)
    assert (selected["adjustment_in"], selected["adjustment_out"], selected["adjustment_count"]) == (40, 20, 2)
    assert report["totals"]["income"] == 5000
    assert report["totals"]["expense"] == 1500
    assert report["totals"]["net"] == 3500
    detail = client.get("/transactions/history", params={"start_date": str(day), "end_date": str(day)}).json()
    assert detail["total"] == selected["count"]
    assert len(detail["items"]) == 25
    assert detail["income"] == selected["income"]
    assert detail["expense"] == selected["expense"]
    assert sum(item["count"] for item in report["days"]) == report["totals"]["count"] == 155


def test_calendar_filters_account_and_includes_archived_history(ledger):
    client, db = ledger
    bank = db.query(Account).filter_by(name="Bank").one()
    bank.is_archived = True
    add(db, "income", 1000, date(2026, 11, 1))
    add(db, "expense", 300, date(2026, 11, 2), "Cash")
    add(db, "transfer_in", 200, date(2026, 11, 3), "Cash")
    db.commit()
    bank_report = month(client, account="Bank")
    assert bank_report["totals"]["income"] == 1000
    assert bank_report["totals"]["expense"] == 0
    cash = month(client, account="Cash")
    assert cash["totals"]["income"] == 0
    assert cash["totals"]["expense"] == 300
    assert cash["totals"]["transfer_in"] == 200
    assert cash["totals"]["net"] == -300
    assert month(client, account="Missing")["totals"]["count"] == 0


def test_calendar_and_year_metadata_are_isolated_per_user(ledger):
    client, db = ledger
    db.add(User(id=2, username="calendar-peer", full_name="Peer", hashed_password="unused", is_active=True))
    db.flush()
    add(db, "income", 9999, date(1995, 1, 1), user_id=2)
    add(db, "income", 9999, date(2026, 11, 8), user_id=2)
    add(db, "expense", 100, date(2010, 2, 1))
    add(db, "expense", 200, date(2026, 11, 8))
    db.commit()
    report = month(client)
    assert report["totals"]["income"] == 0
    assert report["totals"]["expense"] == 200
    assert report["available_years"] == [2010, 2026]
    assert month(client, 1995, 1)["totals"]["count"] == 0


@pytest.mark.parametrize("year, month_value, days", [(2024, 2, 29), (2025, 2, 28), (2000, 2, 29), (2100, 2, 28), (1, 1, 31), (9999, 12, 31)])
def test_calendar_handles_leap_years_and_date_boundaries(ledger, year, month_value, days):
    client, db = ledger
    report = month(client, year, month_value)
    assert len(report["days"]) == days
    assert report["days"][0]["date"] == f"{year:04d}-{month_value:02d}-01"
    assert report["days"][-1]["date"] == f"{year:04d}-{month_value:02d}-{days:02d}"
    assert all(day["count"] == 0 and day["income"] == 0 and day["expense"] == 0 for day in report["days"])
    assert report["totals"]["count"] == 0


@pytest.mark.parametrize("params", [{"year": 0, "month": 1}, {"year": 10000, "month": 1}, {"year": 2026, "month": 0}, {"year": 2026, "month": 13}, {"year": 2026}, {"month": 11}])
def test_invalid_calendar_period_is_rejected(ledger, params):
    assert ledger[0].get("/transactions/calendar", params=params).status_code == 422


def test_calendar_requires_authentication(ledger):
    client, db = ledger
    del client.app.dependency_overrides[get_current_user]
    assert client.get("/transactions/calendar", params={"year": 2026, "month": 11}).status_code == 401
