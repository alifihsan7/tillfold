"""Session revocation, proof of identity and registration boundaries."""
import time
from datetime import datetime, timezone, timedelta

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import main
from app.api.v1.endpoints import auth
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import Base, get_db
from app.db.user_schema import ensure_user_session_schema
from app.models.user import User

OLD = "OriginalPassword2026!"
NEW = "NewPassword2026!"
HASH = hash_password(OLD)

@pytest.fixture
def identity():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    for limiter in [auth.auth_limiter, auth.login_limiter, auth.register_limiter]:
        limiter.requests.clear()
    with Session(engine, expire_on_commit=False) as db:
        user = User(username="session_owner", email="owner@example.com", full_name="Owner", hashed_password=HASH, is_active=True)
        db.add(user); db.commit()
        app = FastAPI(); app.include_router(auth.router, prefix="/auth")
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, db, user
    engine.dispose()


def bearer(token):
    return {"Authorization": "Bearer " + token}


def legacy_token(user, **extra):
    return jwt.encode({"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(days=1), **extra}, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def test_password_change_revokes_all_old_sessions_and_accepts_fresh_login(identity):
    c, db, user = identity
    first = create_access_token(user.id)
    second = legacy_token(user)  # Existing users stay signed in until they change their password.
    assert c.get("/auth/me", headers=bearer(second)).status_code == 200
    response = c.put("/auth/me", headers=bearer(first), json={"password": NEW, "current_password": OLD})
    assert response.status_code == 200
    assert "session_version" not in response.json()
    for token in [first, second]:
        assert c.get("/auth/me", headers=bearer(token)).status_code == 401
        assert c.put("/auth/me", headers=bearer(token), json={"full_name": "Stale write"}).status_code == 401
    assert c.post("/auth/login", json={"username_or_email": user.username, "password": OLD}).status_code == 401
    login = c.post("/auth/login", json={"username_or_email": user.username, "password": NEW})
    assert login.status_code == 200
    assert c.get("/auth/me", headers=bearer(login.json()["access_token"])).status_code == 200
    db.refresh(user); assert user.session_version == 1


@pytest.mark.parametrize("proof", [None, "wrong-password"])
def test_password_change_requires_proof_and_never_partially_edits_profile(identity, proof):
    c, db, user = identity
    headers = bearer(create_access_token(user.id))
    response = c.put("/auth/me", headers=headers, json={"password": NEW, "current_password": proof, "full_name": "Must not persist"})
    assert response.status_code == 403
    db.expire_all(); assert user.full_name == "Owner"
    assert user.session_version == 0 and verify_password(OLD, user.hashed_password)
    assert c.get("/auth/me", headers=headers).status_code == 200


@pytest.mark.parametrize("provider", ["google", "telegram"])
def test_recent_bound_federated_sign_in_can_set_password(identity, provider):
    c, db, user = identity
    if provider == "google": user.google_id = "verified-google"
    else: user.telegram_chat_id = 777001
    db.commit()
    token = create_access_token(user.id, auth_method=provider, auth_time=int(time.time()))
    assert c.put("/auth/me", headers=bearer(token), json={"password": NEW}).status_code == 200
    assert c.get("/auth/me", headers=bearer(token)).status_code == 401


@pytest.mark.parametrize("provider,bound,age", [("google", True, 301), ("telegram", True, 301), ("google", False, 0), ("telegram", False, 0), ("password", True, 0)])
def test_stale_or_unbound_sign_in_cannot_replace_password_without_proof(identity, provider, bound, age):
    c, db, user = identity
    if bound:
        user.google_id = "verified-google"; user.telegram_chat_id = 777001; db.commit()
    token = legacy_token(user, amr=provider, iat=int(time.time()), auth_time=int(time.time()) - age, ver=0)
    assert c.put("/auth/me", headers=bearer(token), json={"password": NEW}).status_code == 403
    db.refresh(user); assert verify_password(OLD, user.hashed_password)


@pytest.mark.parametrize("username", ["", "   ", "ab", "a" * 51, "owner@example.com", "name space", "../name"])
def test_registration_rejects_invalid_usernames(identity, username):
    c, db, user = identity
    response = c.post("/auth/register", json={"username": username, "full_name": "Test", "password": NEW})
    assert response.status_code == 422
    assert db.query(User).count() == 1


@pytest.mark.parametrize("email", ["not-an-email", "x@@example.com", "x@localhost", "x@-example.com", "a..b@example.com", "x@example.com\nBcc:other@example.com", "x" * 65 + "@example.com"])
def test_registration_and_profile_reject_malformed_email(identity, email):
    c, db, user = identity
    assert c.post("/auth/register", json={"username": "valid_user", "full_name": "Test", "password": NEW, "email": email}).status_code == 422
    assert c.put("/auth/me", headers=bearer(create_access_token(user.id)), json={"email": email}).status_code == 422
    assert db.query(User).count() == 1


def test_registration_normalizes_valid_identity_and_profile_can_remove_email(identity):
    c, db, user = identity
    response = c.post("/auth/register", json={"username": " New-User ", "full_name": " New User ", "password": NEW, "email": " New.User+Budget@Example.COM "})
    assert response.status_code == 201
    assert response.json()["user"]["username"] == "new-user"
    assert response.json()["user"]["email"] == "new.user+budget@example.com"
    headers = bearer(create_access_token(user.id))
    assert c.put("/auth/me", headers=headers, json={"email": None}).json()["email"] is None
    assert c.put("/auth/me", headers=headers, json={"full_name": " "}).status_code == 422


def test_session_migration_is_repeatable_and_preserves_legacy_data():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)"))
        connection.execute(text("INSERT INTO users VALUES (1, 'legacy')"))
    ensure_user_session_schema(engine); ensure_user_session_schema(engine)
    with engine.connect() as connection:
        assert tuple(connection.execute(text("SELECT username,session_version FROM users")).one()) == ("legacy", 0)
    engine.dispose()


def test_new_federated_session_cannot_refresh_missing_identity_proof(identity):
    c, db, user = identity
    user.google_id = "verified-google"; db.commit()
    token = create_access_token(user.id, auth_method="google")
    assert c.put("/auth/me", headers=bearer(token), json={"password": NEW}).status_code == 403


@pytest.mark.parametrize("provider", ["google", "telegram"])
@pytest.mark.parametrize("proof_age", [0, 3600])
def test_provider_login_preserves_the_age_of_identity_proof(identity, monkeypatch, provider, proof_age):
    c, db, user = identity
    issued = int(time.time()) - proof_age
    if provider == "google":
        user.google_id = "bound-google"
        monkeypatch.setattr(auth.settings, "GOOGLE_CLIENT_ID", "test-client")
        monkeypatch.setattr(auth.id_token, "verify_oauth2_token", lambda *args: {"sub": user.google_id, "email": user.email, "email_verified": True, "iat": issued})
        path, data = "/auth/google", {"credential": "provider-verified"}
    else:
        user.telegram_chat_id = 777001
        monkeypatch.setattr(auth.settings, "TELEGRAM_BOT_TOKEN", "test-bot")
        monkeypatch.setattr(auth, "verify_telegram_init_data", lambda *args: {"auth_date": str(issued), "user": {"id": 777001}})
        path, data = "/auth/telegram-webapp", {"init_data": "provider-verified"}
    db.commit()
    login = c.post(path, json=data)
    assert login.status_code == 200
    token = login.json()["access_token"]
    claims = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert claims["auth_time"] == issued
    assert c.put("/auth/me", headers=bearer(token), json={"password": NEW}).status_code == (200 if proof_age == 0 else 403)


def test_local_reminder_uses_current_session_version_without_password_change_privilege(identity):
    from app.core.security import create_local_job_token
    c, db, user = identity
    user.session_version = 3; db.commit()
    token = create_local_job_token(db, user.id)
    assert c.get("/auth/me", headers=bearer(token)).status_code == 200
    assert c.put("/auth/me", headers=bearer(token), json={"password": NEW}).status_code == 403
    user.is_active = False; db.commit()
    with pytest.raises(ValueError):
        create_local_job_token(db, user.id)
