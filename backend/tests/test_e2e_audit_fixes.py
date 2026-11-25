"""Reproductions of the November 24 browser/security audit, with isolated state."""
from datetime import date
from copy import deepcopy
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import main  # Registers every model against the test bootstrap database.
from app.api.deps import get_current_user, get_strict_current_user
from app.api.v1.endpoints import auth, accounts, onboarding, analytics, pockets
from app.core.rate_limit import auth_limiter, login_limiter, register_limiter
from app.core.security import hash_password
from app.db.session import Base, get_db
from app.models.account import Account
from app.models.pocket import Pocket
from app.models.transaction import Transaction
from app.models.user import User

PASSWORD = "AuditPassword2026!"
HASH = hash_password(PASSWORD)


@pytest.fixture
def isolated():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    for limiter in [auth_limiter, login_limiter, register_limiter]:
        limiter.requests.clear()
    with Session(engine, expire_on_commit=False) as db:
        user = User(username="owner", email="owner@example.com", full_name="Owner", hashed_password=HASH,
                    is_active=True, is_onboarded=False)
        db.add(user); db.commit()
        app = FastAPI()
        for name, router in [("auth", auth.router), ("accounts", accounts.router), ("onboarding", onboarding.router),
                             ("analytics", analytics.router), ("pockets", pockets.router)]:
            app.include_router(router, prefix="/" + name)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_strict_current_user] = lambda: user
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, db, user
    engine.dispose()
    for limiter in [auth_limiter, login_limiter, register_limiter]:
        limiter.requests.clear()


def google(client, **overrides):
    claims = {"sub": "google-owner", "email": "owner@example.com", "email_verified": True, "name": "Owner"}
    password = overrides.pop("password", None)
    claims.update(overrides)
    with patch.object(auth.settings, "GOOGLE_CLIENT_ID", "isolated-test-client"), \
         patch.object(auth.id_token, "verify_oauth2_token", return_value=claims):
        return client.post("/auth/google", json={"credential": "verified-provider-test-token", "current_password": password})


@pytest.mark.parametrize("claims", [{"email_verified": False}, {"email_verified": None}, {"sub": None}, {"sub": ""}])
def test_google_rejects_unverified_email_or_missing_subject(isolated, claims):
    c, db, user = isolated
    assert google(c, **claims).status_code == 401
    db.refresh(user); assert user.google_id is None


def test_google_email_match_does_not_grant_access_or_link_account(isolated):
    c, db, user = isolated
    r = google(c)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "google_link_required"
    db.refresh(user); assert user.google_id is None
    assert db.query(User).count() == 1


def test_google_link_requires_correct_existing_password(isolated):
    c, db, user = isolated
    assert google(c, password="incorrect-password").status_code == 401
    db.refresh(user); assert user.google_id is None
    r = google(c, password=PASSWORD)
    assert r.status_code == 200
    assert r.json()["user"]["id"] == user.id
    db.refresh(user); assert user.google_id == "google-owner"
    assert google(c).status_code == 200  # Returning identity uses its bound subject, not an email merge.


def test_google_never_overwrites_another_binding(isolated):
    c, db, user = isolated
    user.google_id = "previous-google"; db.commit()
    assert google(c, password=PASSWORD).status_code == 409
    db.refresh(user); assert user.google_id == "previous-google"


def test_new_verified_google_identity_still_can_register(isolated):
    c, db, user = isolated
    r = google(c, sub="new-google", email="new@example.com")
    assert r.status_code == 200
    assert r.json()["user"]["id"] != user.id
    assert not r.json()["user"]["is_onboarded"]


def test_legacy_email_case_matches_but_never_auto_links(isolated):
    c, db, user = isolated
    user.email = "Owner@Example.COM"; db.commit()
    assert google(c).status_code == 409
    assert c.post("/auth/login", json={"username_or_email": "OWNER@EXAMPLE.COM", "password": PASSWORD}).status_code == 200


def test_ambiguous_legacy_emails_require_username_and_are_not_merged(isolated):
    c, db, user = isolated
    db.add(User(username="second", email="Owner@Example.com", full_name="Second", hashed_password=HASH)); db.commit()
    assert google(c, password=PASSWORD).status_code == 409
    assert c.post("/auth/login", json={"username_or_email": "owner@example.com", "password": PASSWORD}).status_code == 401
    assert c.post("/auth/login", json={"username_or_email": "owner", "password": PASSWORD}).status_code == 200
    assert all(u.google_id is None for u in db.query(User))


def test_email_create_and_profile_update_normalize_and_reject_case_duplicates(isolated):
    c, db, user = isolated
    r = c.post("/auth/register", json={"username": "mixed", "full_name": "Mixed", "email": " Mixed@Example.COM ", "password": PASSWORD})
    assert r.status_code == 201
    assert r.json()["user"]["email"] == "mixed@example.com"
    assert c.post("/auth/register", json={"username": "duplicate", "full_name": "Duplicate", "email": "MIXED@example.com", "password": PASSWORD}).status_code == 400
    assert c.put("/auth/me", json={"email": "MIXED@EXAMPLE.COM"}).status_code == 400
    assert c.put("/auth/me", json={"email": " OWN.NEW@Example.COM "}).json()["email"] == "own.new@example.com"


def payload():
    return {"initial_accounts": [{"name": "Bank", "initial_balance": 1000000},
                                 {"name": "Cash", "initial_balance": 200000},
                                 {"name": "Savings", "type": "tabungan", "initial_balance": 500000}],
            "source_account": "Bank", "pocket_account": "Bank", "use_gate": False,
            "cycle_start_date": "2026-11-24", "cycle_type": "biweekly", "cycle_days": 14,
            "buckets": [{"account": "Bank", "percentage": 100, "purpose": "Operational"}]}


def test_account_prefetch_does_not_seed_an_unfinished_onboarding(isolated):
    c, db, user = isolated
    assert c.get("/accounts").json() == []
    assert db.query(Account).count() == 0
    assert c.post("/onboarding/complete", json=payload()).status_code == 200
    assert db.query(Account).count() == 3
    assert sum(tx.amount for tx in db.query(Transaction)) == 1700000
    r = c.get("/analytics/summary", params={"period_type": "custom", "start": "2026-11-01", "end": "2026-12-31"})
    assert r.status_code == 200
    assert (r.json()["total_balance"], r.json()["income"], r.json()["opening_balance"]) == (1700000, 0, 1700000)


def test_onboarding_applies_opening_to_empty_existing_account_exactly_once(isolated):
    c, db, user = isolated
    db.add(Account(user_id=user.id, name="Bank", initial_balance=0)); db.commit()
    for _ in range(2):
        assert c.post("/onboarding/complete", json=payload()).status_code == 200
    assert db.query(Account).count() == 3
    assert db.query(Transaction).count() == 3
    assert db.query(Account).filter_by(name="Bank").one().initial_balance == 1000000


def test_onboarding_never_guesses_or_overwrites_existing_financial_history(isolated):
    c, db, user = isolated
    db.add(Account(user_id=user.id, name="Bank", initial_balance=0))
    db.add(Transaction(user_id=user.id, type="expense", amount=50000, account="Bank", category="Food", description="Existing", date=date(2026,11,24))); db.commit()
    assert c.post("/onboarding/complete", json=payload()).status_code == 409
    assert db.query(Account).count() == 1
    assert db.query(Transaction).count() == 1
    db.refresh(user); assert not user.is_onboarded


INVALID = [
    {"initial_accounts": [{"name": "Bank", "initial_balance": -1}]},
    {"initial_accounts": [{"name": "Bank", "initial_balance": 9000000000000001}]},
    {"initial_accounts": [{"name": " "}]}, {"initial_accounts": []},
    {"initial_accounts": [{"name": "Bank"}, {"name": "bank"}]},
    {"source_account": "Foreign"}, {"pocket_account": "Foreign"},
    {"cycle_days": 0}, {"cycle_days": 366}, {"cycle_type": "nonsense"},
    {"paycheck_day": 0}, {"paycheck_day": 32}, {"buckets": []},
    {"buckets": [{"account": "Foreign", "percentage":100,"purpose":"Invalid"}]},
    {"buckets": [{"account": "Bank", "percentage":150,"purpose":"Invalid"}]},
    {"buckets": [{"account": "Bank", "percentage":99,"purpose":"Invalid"}]},
    {"buckets": [{"account": "Bank", "percentage":50,"purpose":"A"},{"account":"Bank","percentage":50,"purpose":"B"}]},
    {"buckets": [{"account": "Bank", "percentage":100,"purpose":"Invalid","via_secondary":"Foreign"}]},
]
@pytest.mark.parametrize("change", INVALID)
def test_invalid_onboarding_never_writes_partial_financial_data(isolated, change):
    c, db, user = isolated
    body = payload(); body.update(deepcopy(change))
    assert c.post("/onboarding/complete", json=body).status_code == 422
    assert db.query(Account).count() == 0
    assert db.query(Transaction).count() == 0
    db.refresh(user); assert not user.is_onboarded


@pytest.mark.parametrize("slug", ["bills", "utama-protected", "utama"])
@pytest.mark.parametrize("legacy_pockets", [False, True])
def test_general_expenses_never_fall_back_to_only_protected_pocket(isolated, slug, legacy_pockets):
    c, db, user = isolated
    bank = Account(user_id=user.id, name="Bank"); db.add(bank); db.flush()
    pocket = Pocket(user_id=user.id, account_id=bank.id, name="Reserved bills", slug=slug, role="tagihan",
                    target_amount=300000, allocation_amount=200000, allocation_start_date=date(2026,11,24))
    db.add(pocket); db.flush()
    if legacy_pockets:
        db.add(Pocket(user_id=user.id, account_id=bank.id, name="Gym", slug="gym", role="tagihan", target_amount=0, allocation_amount=0))
    for kind, amount, category, pocket_id in [("income",1000000,"Salary",None), ("expense",150000,"Food",None), ("expense",50000,"Other",pocket.id)]:
        db.add(Transaction(user_id=user.id,type=kind,amount=amount,account="Bank",category=category,description="Audit",date=date(2026,11,24),pocket_id=pocket_id))
    db.commit()
    r=c.get(f"/accounts/{bank.id}/pockets",params={"cycle_start":"2026-11-24","cycle_end":"2026-12-07"})
    assert r.status_code == 200
    item=next(p for p in r.json()["pockets"] if p["id"]==pocket.id)
    assert item["spent_amount"] == 50000
    assert item["balance"] == 150000


def test_google_password_proof_is_rate_limited(isolated):
    c, db, user = isolated
    for _ in range(10):
        assert google(c, password="incorrect-password").status_code == 401
    assert google(c, password=PASSWORD).status_code == 429
    db.refresh(user)
    assert user.google_id is None


def test_password_validation_rejects_short_and_oversized_utf8_without_server_error(isolated):
    c, db, user = isolated
    for password in ["abc123", "🔐" * 19]:
        response = c.post("/auth/register", json={"username": "invalid", "full_name": "Invalid", "password": password})
        assert response.status_code == 422
        assert c.put("/auth/me", json={"password": password}).status_code == 422
    assert db.query(User).count() == 1
    assert c.post("/auth/login", json={"username_or_email": "owner", "password": PASSWORD}).status_code == 200


def test_pocket_summary_exposes_free_cash_without_confusing_computed_funding(isolated):
    c, db, user = isolated
    bank = Account(user_id=user.id, name="Bank"); db.add(bank); db.flush()
    free = Pocket(user_id=user.id, account_id=bank.id, name="Kas bebas", slug="utama-17", role="operasional", allocation_amount=None, target_amount=0)
    reserved = Pocket(user_id=user.id, account_id=bank.id, name="Tagihan", slug="utama-reserved", role="tagihan", allocation_amount=200000, target_amount=300000)
    db.add_all([free, reserved, Transaction(user_id=user.id, type="income", amount=2000000, account="Bank", category="Salary", description="Audit", date=date(2026,11,25))]); db.commit()
    response = c.get(f"/accounts/{bank.id}/pockets", params={"cycle_start":"2026-11-25", "cycle_end":"2026-12-08"})
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["pockets"]}
    assert items[free.id]["uses_unallocated_cash"] is True
    assert items[free.id]["allocation_amount"] == 1800000  # Computed period funding is not a classification flag.
    assert items[reserved.id]["uses_unallocated_cash"] is False
    assert sum(item["balance"] for item in items.values()) == 2000000
    db.refresh(free); assert free.allocation_amount is None
