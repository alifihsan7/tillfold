from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.account import Account
from app.models.paycheck import PaycheckConfig
from app.models.transaction import Transaction
from app.models.user import User
from app.services.analytics import compute_safe_to_spend_metrics

START, END, TODAY = date(2026, 11, 9), date(2026, 11, 22), date(2026, 11, 15)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(id=1, username="budget", full_name="Uji", hashed_password="x", is_active=True))
        session.add_all([
            Account(user_id=1, name="BCA", type="operasional", color="slate", initial_balance=0),
            Account(user_id=1, name="Jago", type="tabungan", color="slate", initial_balance=0),
        ])
        session.add(PaycheckConfig(user_id=1, source_account="BCA", pocket_account="BCA", cycle_type="biweekly",
                                   cycle_days=14, cycle_start_date=START, is_active=True, use_gate=False))
        session.commit()
        yield session
    engine.dispose()


def add(db, kind, amount, account="BCA", category="Gaji", day=date(2026, 11, 9), raw=None):
    db.add(Transaction(user_id=1, type=kind, amount=amount, account=account, category=category,
                       description="uji", date=day, raw_text=raw))
    db.commit()


def metrics(db):
    return compute_safe_to_spend_metrics(db, 1, START, END, "cycle", TODAY)


def test_transfer_out_of_pocket_account_reduces_budget(db):
    add(db, "income", 10_250_000)
    add(db, "expense", 4_458_000, category="Makan", day=date(2026, 11, 12))
    add(db, "transfer_out", 500_000, category="Transfer", day=date(2026, 11, 10))
    add(db, "transfer_in", 500_000, account="Jago", category="Transfer", day=date(2026, 11, 10))
    m = metrics(db)
    assert m.pocket_budget == 9_750_000
    # Remaining budget now matches the money left in the account.
    assert m.pocket_remaining == 10_250_000 - 4_458_000 - 500_000


def test_plain_transfer_in_does_not_inflate_budget(db):
    add(db, "income", 3_000_000)
    add(db, "transfer_in", 1_000_000, category="Transfer", day=date(2026, 11, 10))
    assert metrics(db).pocket_budget == 3_000_000


def test_paycheck_receipt_transfers_still_count(db):
    add(db, "transfer_in", 4_000_000, category="Transfer", raw="split [paycheck_receipt:7]")
    add(db, "transfer_out", 1_000_000, category="Transfer", raw="split [paycheck_receipt:7]")
    assert metrics(db).pocket_budget == 3_000_000


def test_transfers_out_exceeding_income_floor_at_zero(db):
    add(db, "income", 1_000_000)
    add(db, "transfer_out", 2_000_000, category="Transfer")
    assert metrics(db).pocket_budget == 0
