"""Safe defaults before test modules import main and its schema initialization."""
import os
import tempfile
from pathlib import Path
import pytest

_test_root = tempfile.TemporaryDirectory(prefix="tillfold-unit-")
os.environ.update({
    "TILLFOLD_TESTING": "1",
    "DATABASE_URL": f"sqlite:///{Path(_test_root.name) / 'bootstrap.sqlite3'}",
    "JWT_SECRET_KEY": "isolated-unit-test-jwt-not-production",
    "BOT_TOKEN_ENCRYPTION_KEY": "isolated-unit-test-encryption-not-production",
    "TELEGRAM_BOT_TOKEN": "", "BOT_TOKEN": "",
    "GOOGLE_CLIENT_ID": "", "GOOGLE_SHEETS_SPREADSHEET_ID": "",
    "GOOGLE_SERVICE_ACCOUNT_FILE": str(Path(_test_root.name) / "no-credentials.json"),
    "AI_ROUTER_URL": "http://127.0.0.1:9/disabled", "AI_ROUTER_KEY": "",
    "ENVIRONMENT": "production",
})


def pytest_addoption(parser):
    parser.addoption("--run-live", action="store_true", default=False,
                     help="Run explicitly configured tests for a dedicated live integration account")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-live"):
        skip = pytest.mark.skip(reason="Live integration requires --run-live and explicit dedicated-account settings")
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip)
