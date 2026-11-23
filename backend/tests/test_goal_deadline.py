from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.goals import WIB, compute_goal_metrics
from app.db.session import Base
from app.models.goal import Goal
from app.models.account import Account
from app.models.paycheck import PaycheckConfig, PaycheckBucket
from app.models.user import User
from datetime import datetime


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(id=1, username="goal", full_name="Uji", hashed_password="x", is_active=True))
        session.add(PaycheckConfig(user_id=1, source_account="BCA", pocket_account="BCA", cycle_type="biweekly",
                                   cycle_days=14, is_active=True, use_gate=False))
        session.flush()
        session.add(Account(user_id=1, name="BCA", type="tabungan"))
        cfg = session.query(PaycheckConfig).filter_by(user_id=1).one()
        session.add(PaycheckBucket(config_id=cfg.id, account="BCA", percentage=100,
                                   fixed_amount=100_000, purpose="Tabungan"))
        session.commit()
        yield session
    engine.dispose()


def goal(target, current, days_to_deadline):
    today = datetime.now(WIB).date()
    deadline = today + timedelta(days=days_to_deadline) if days_to_deadline is not None else None
    return Goal(id=1, user_id=1, name="Uji", target_amount=target, manual_current_amount=current, target_date=deadline)


def test_estimate_past_deadline_is_flagged_with_required_saving(db):
    # Without an allocation, show the requirement without inventing a forecast.
    m = compute_goal_metrics(goal(6_000_000, 100_000, 56), 1, db)
    assert m["estimated_cycles"] is None
    assert m["is_behind_schedule"] is False
    assert m["required_per_cycle"] == 1_475_000


def test_goal_on_track_is_not_flagged(db):
    m = compute_goal_metrics(goal(1_000_000, 900_000, 56), 1, db)
    assert m["is_behind_schedule"] is False
    assert m["required_per_cycle"] == 25_000


def test_missed_deadline_needs_the_whole_remainder(db):
    m = compute_goal_metrics(goal(1_000_000, 400_000, -3), 1, db)
    assert m["is_behind_schedule"] is True
    assert m["required_per_cycle"] == 600_000


def test_reached_or_undated_goal_is_never_flagged(db):
    assert compute_goal_metrics(goal(1_000_000, 1_200_000, -3), 1, db)["is_behind_schedule"] is False
    undated = compute_goal_metrics(goal(1_000_000, 0, None), 1, db)
    assert undated["is_behind_schedule"] is False and undated["required_per_cycle"] is None


def test_linked_goal_forecasts_from_configured_allocation(db):
    item = goal(1_000_000, 0, 56)
    item.linked_account = "BCA"
    m = compute_goal_metrics(item, 1, db)
    assert m["estimated_cycles"] == 10
    assert m["is_behind_schedule"] is True
    assert m["required_per_cycle"] == 250_000
