from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.api.v1.endpoints import search
from app.db.session import Base, get_db
from app.models.account import Account
from app.models.goal import Goal
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User


@pytest.fixture
def finder():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        users = [User(id=i, username=f"finder{i}", full_name=f"Finder {i}", hashed_password="unused", is_active=True) for i in (1, 2)]
        db.add_all(users)
        db.flush()
        for user in users:
            db.add(Account(user_id=user.id, name="Needle Bank", type="operasional", is_archived=True, tag="Needle account"))
            db.add(Transaction(user_id=user.id, type="expense", account="Needle Bank", amount=25000,
                               category="Food", description="Needle expense", raw_text="internal-marker", date=date(2010, 1, 1)))
            db.add(Subscription(user_id=user.id, name="Needle internet", amount=50000, account="Needle Bank", is_active=False))
            db.add(Goal(user_id=user.id, name="Needle travel", target_amount=100000, manual_current_amount=5000,
                        category="Tabungan", is_active=False, notes="Vacation"))
        db.commit()
        app = FastAPI()
        app.include_router(search.router, prefix="/search")
        app.dependency_overrides[get_db] = lambda: db
        current = [users[0]]
        app.dependency_overrides[get_current_user] = lambda: current[0]
        with TestClient(app) as client:
            yield client, db, current, users, app
    engine.dispose()


def groups(response):
    assert response.status_code == 200, response.text
    return {group["kind"]: group for group in response.json()["groups"]}


def test_search_spans_all_periods_and_keeps_archived_and_inactive_items(finder):
    client, db, current, users, app = finder
    found = groups(client.get("/search", params={"q": "  nEEdLe  "}))
    assert set(found) == {"transaction", "account", "bill", "goal"}
    assert all(len(group["items"]) == 1 for group in found.values())
    assert found["transaction"]["items"][0]["data"]["date"] == "2010-01-01"
    assert found["account"]["items"][0]["data"]["is_archived"] is True
    assert found["account"]["items"][0]["amount"] == -25000
    assert found["bill"]["items"][0]["data"]["is_active"] is False
    assert found["goal"]["items"][0]["data"]["is_active"] is False
    assert found["goal"]["items"][0]["data"]["current_amount"] == 5000


def test_every_group_is_scoped_to_logged_in_user(finder):
    client, db, current, users, app = finder
    first = groups(client.get("/search", params={"q": "Needle"}))
    current[0] = users[1]
    second = groups(client.get("/search", params={"q": "Needle"}))
    assert all(first[kind]["items"][0]["id"] != second[kind]["items"][0]["id"] for kind in first)
    db.query(Transaction).filter_by(user_id=1).update({"description": "OwnerSecret"})
    db.query(Account).filter_by(user_id=1).update({"tag": "OwnerSecret"})
    db.query(Subscription).filter_by(user_id=1).update({"notes": "OwnerSecret"})
    db.query(Goal).filter_by(user_id=1).update({"notes": "OwnerSecret"})
    db.commit()
    assert groups(client.get("/search", params={"q": "OwnerSecret"})) == {}


@pytest.mark.parametrize("query", ["25000", "25.000", "25,000", "Rp 25.000", "2010-01-01"])
def test_amount_and_date_find_old_transaction(finder, query):
    client, db, current, users, app = finder
    found = groups(client.get("/search", params={"q": query}))
    assert found["transaction"]["items"][0]["amount"] == 25000


def test_wildcards_and_quotes_are_literal_and_internal_markers_are_not_searched(finder):
    client, db, current, users, app = finder
    db.add(Transaction(user_id=1, type="expense", amount=10, account="Needle Bank", category="Test",
                       description="Literal %_ and back\\slash", date=date.today()))
    db.commit()
    for query in ("%_", "back\\slash"):
        found = groups(client.get("/search", params={"q": query}))
        assert list(found) == ["transaction"]
        assert len(found["transaction"]["items"]) == 1
    assert groups(client.get("/search", params={"q": "' OR 1=1 --"})) == {}
    assert groups(client.get("/search", params={"q": "internal-marker"})) == {}


def test_limits_are_per_group_with_visible_more_flag_and_stable_order(finder):
    client, db, current, users, app = finder
    for index in range(8):
        db.add(Transaction(user_id=1, type="expense", amount=10, account="Needle Bank", category="Test",
                           description=f"Needle recent {index}", date=date(2026, 11, 8)))
        db.add(Goal(user_id=1, name=f"Needle active {index}", target_amount=100, is_active=True))
    db.commit()
    found = groups(client.get("/search", params={"q": "Needle", "limit": 3}))
    assert len(found["transaction"]["items"]) == 3
    assert found["transaction"]["has_more"] is True
    assert found["transaction"]["items"][0]["title"] == "Needle recent 7"
    assert found["goal"]["has_more"] is True
    assert all(item["data"]["is_active"] for item in found["goal"]["items"])
    assert found["account"]["has_more"] is False


@pytest.mark.parametrize("params", [{"q": "x"}, {"q": "x" * 121}, {"q": "ok", "limit": 0}, {"q": "ok", "limit": 11}, {}])
def test_search_rejects_invalid_query_and_limit(finder, params):
    assert finder[0].get("/search", params=params).status_code == 422


def test_whitespace_and_no_match_return_empty_without_mutations(finder):
    client, db, current, users, app = finder
    before = {model.__name__: db.query(model).count() for model in (Account, Transaction, Subscription, Goal)}
    assert groups(client.get("/search", params={"q": "   "})) == {}
    assert groups(client.get("/search", params={"q": "No result"})) == {}
    assert {model.__name__: db.query(model).count() for model in (Account, Transaction, Subscription, Goal)} == before


def test_search_requires_authentication(finder):
    client, db, current, users, app = finder
    del app.dependency_overrides[get_current_user]
    assert client.get("/search", params={"q": "Needle"}).status_code == 401
