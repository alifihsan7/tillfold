"""Explicit opt-in integration checks; never discover or impersonate production users."""
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode

import pytest
import requests

pytestmark = pytest.mark.live


def sign_init_data(data, bot_token):
    pairs = {key: json.dumps(value, separators=(",", ":")) if isinstance(value, (dict, list)) else str(value)
             for key, value in data.items()}
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, "\n".join(f"{k}={v}" for k, v in sorted(pairs.items())).encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


def test_live():
    required = ["TILLFOLD_LIVE_BASE_URL", "TILLFOLD_LIVE_USERNAME", "TILLFOLD_LIVE_CHAT_ID", "TILLFOLD_LIVE_BOT_TOKEN"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        pytest.skip("Missing explicit live integration configuration: " + ", ".join(missing))
    username = os.environ["TILLFOLD_LIVE_USERNAME"]
    assert username.startswith(("audit_", "test_", "e2e_")), "Use a dedicated test account, never a personal account"
    base = os.environ["TILLFOLD_LIVE_BASE_URL"].rstrip("/")
    assert base.startswith(("https://", "http://127.0.0.1:", "http://localhost:")), "Set an explicit safe integration URL"
    data = {"auth_date": int(time.time()), "user": {"id": int(os.environ["TILLFOLD_LIVE_CHAT_ID"]), "username": username}}
    valid = requests.post(base + "/api/v1/auth/telegram-webapp", json={"init_data": sign_init_data(data, os.environ["TILLFOLD_LIVE_BOT_TOKEN"])}, timeout=15)
    assert valid.status_code == 200
    assert valid.json()["user"]["username"] == username
    rejected = requests.post(base + "/api/v1/auth/telegram-webapp", json={"init_data": sign_init_data(data, "999999:invalid-integration-token")}, timeout=15)
    assert rejected.status_code == 401
