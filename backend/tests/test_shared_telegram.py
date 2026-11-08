from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_strict_current_user
from app.api.v1.endpoints import auth, bot_webhook
from app.bot import bot
from app.db.session import Base, get_db
from app.models.user import TelegramLink, User
from app.services.telegram_link import consume_link, create_link


@pytest.fixture
def shared_bot(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        users = [User(username=name, full_name=name, hashed_password="unused", is_active=True)
                 for name in ("first", "second")]
        db.add_all(users)
        db.commit()
        app = FastAPI()
        app.include_router(auth.router, prefix="/auth")
        app.include_router(bot_webhook.router, prefix="/bot")
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_strict_current_user] = lambda: users[0]
        monkeypatch.setattr(bot, "SessionLocal", lambda: Session(engine, expire_on_commit=False))
        monkeypatch.setattr(auth.settings, "TELEGRAM_BOT_TOKEN", "test-token")
        response = Mock()
        response.json.return_value = {"ok": True, "result": {"username": "TillfoldTestBot"}}
        monkeypatch.setattr(auth.requests, "get", Mock(return_value=response))
        send = Mock()
        monkeypatch.setattr(bot, "send_message", send)
        with TestClient(app) as client:
            yield client, db, users, send
    engine.dispose()


def message(chat_id, text, kind="private", sender=None):
    return {"message": {"message_id": 1, "chat": {"id": chat_id, "type": kind},
                        "from": {"id": sender or chat_id}, "text": text}}


def test_link_requires_telegram_start_and_is_single_use(shared_bot):
    client, db, users, send = shared_bot
    response = client.post("/auth/link-telegram", json={"telegram_chat_id": 999})
    assert response.status_code == 200
    link = response.json()
    assert link["expires_in"] == 600
    assert link["url"].startswith("https://t.me/TillfoldTestBot?start=link_")
    token = link["url"].split("start=link_")[1]
    assert len("link_" + token) <= 64
    assert db.get(TelegramLink, users[0].id).token_hash != token
    assert users[0].telegram_chat_id is None

    bot.process_update(message(111, "/start link_" + token))
    db.refresh(users[0])
    assert users[0].telegram_chat_id == 111
    assert db.get(TelegramLink, users[0].id) is None
    assert not consume_link(db, token, 222)
    assert "terhubung" in send.call_args.args[1]


def test_link_expiry_regeneration_and_unlink_revoke_pending_token(shared_bot):
    client, db, users, send = shared_bot
    old = create_link(db, users[0])
    token = create_link(db, users[0])
    assert not consume_link(db, old, 111)
    db.get(TelegramLink, users[0].id).expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    assert not consume_link(db, token, 111)
    token = create_link(db, users[0])
    assert consume_link(db, token, 111)
    pending = create_link(db, users[0])
    assert client.post("/auth/unlink-telegram").status_code == 200
    assert not consume_link(db, pending, 111)
    bot.process_update(message(111, "/saldo"))
    assert "Hubungkan Telegram" in send.call_args.args[1]


def test_shared_bot_routes_two_users_and_rejects_identity_collision(shared_bot, monkeypatch):
    client, db, users, send = shared_bot
    assert consume_link(db, create_link(db, users[0]), 111)
    assert not consume_link(db, create_link(db, users[1]), 111)
    assert consume_link(db, create_link(db, users[1]), 222)
    handler = Mock()
    monkeypatch.setattr(bot, "handle_saldo", handler)
    for chat_id, user in zip((111, 222), users):
        bot.process_update(message(chat_id, "/saldo"))
        assert handler.call_args.kwargs["user"].id == user.id
    assert handler.call_count == 2


def test_shared_bot_rejects_groups_spoofed_senders_and_inactive_users(shared_bot, monkeypatch):
    client, db, users, send = shared_bot
    token = create_link(db, users[0])
    bot.process_update(message(111, "/start link_" + token, kind="group"))
    bot.process_update(message(111, "/start link_" + token, sender=222))
    assert users[0].telegram_chat_id is None
    assert send.call_count == 0
    assert consume_link(db, token, 111)
    users[0].is_active = False
    db.commit()
    handler = Mock()
    monkeypatch.setattr(bot, "handle_saldo", handler)
    bot.process_update(message(111, "/saldo"))
    handler.assert_not_called()


def test_legacy_custom_bot_cannot_be_registered_or_dispatch(shared_bot, monkeypatch):
    client, db, users, send = shared_bot
    assert client.post("/auth/link-telegram-custom", json={"bot_token": "unused"}).status_code == 410
    assert client.post("/bot/webhook/old-secret", json=message(111, "/saldo")).status_code == 410
    assert send.call_count == 0
    users[0].telegram_mode = "custom"
    users[0].telegram_chat_id = 111
    users[0].telegram_bot_token = "legacy-token"
    db.commit()
    handler = Mock()
    monkeypatch.setattr(bot, "handle_saldo", handler)
    bot.process_update(message(111, "/saldo"))
    handler.assert_not_called()
    assert consume_link(db, create_link(db, users[0]), 111)
    db.refresh(users[0])
    assert users[0].telegram_mode == "shared"
    assert users[0].telegram_bot_token is None


def test_bot_unavailable_does_not_issue_link(shared_bot, monkeypatch):
    client, db, users, send = shared_bot
    monkeypatch.setattr(auth.settings, "TELEGRAM_BOT_TOKEN", "")
    assert client.post("/auth/link-telegram").status_code == 503
    assert db.get(TelegramLink, users[0].id) is None


def test_unlinked_admin_id_does_not_fall_back_to_first_account(shared_bot, monkeypatch):
    client, db, users, send = shared_bot
    monkeypatch.setattr(bot.settings, "ALLOWED_USER_ID", 111)
    handler = Mock()
    monkeypatch.setattr(bot, "handle_saldo", handler)
    bot.process_update(message(111, "/saldo"))
    handler.assert_not_called()
    assert "Hubungkan Telegram" in send.call_args.args[1]


def test_mini_app_rejects_legacy_custom_bot_token(shared_bot, monkeypatch):
    client, db, users, send = shared_bot
    users[0].telegram_bot_token = "legacy-token"
    users[0].telegram_chat_id = 111
    db.commit()
    verify = Mock(return_value=None)
    monkeypatch.setattr(auth, "verify_telegram_init_data", verify)
    response = client.post("/auth/telegram-webapp", json={"init_data": 'user={"id":111}'})
    assert response.status_code == 401
    verify.assert_called_once_with('user={"id":111}', "test-token")
