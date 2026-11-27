import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

CACHE_DIR = Path("/home/alifihsan/.hermes/cache")
PENDING_FILE = CACHE_DIR / "receipt_radar_pending.json"


def _ensure_dir():
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error("Failed to create cache dir: %s", e)


def list_pending_receipts() -> Dict[str, Any]:
    _ensure_dir()
    if PENDING_FILE.exists():
        try:
            return json.loads(PENDING_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("Failed to read pending receipts: %s", e)
    return {}


@contextmanager
def _locked_store():
    _ensure_dir()
    with PENDING_FILE.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _write_pending(pending: Dict[str, Any]) -> None:
    path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=PENDING_FILE.parent, encoding="utf-8", delete=False) as temp:
            path = Path(temp.name)
            json.dump(pending, temp, indent=2, default=str)
        os.replace(path, PENDING_FILE)
    finally:
        if path:
            path.unlink(missing_ok=True)


def save_pending_receipt(ref_number: str, data: Dict[str, Any]) -> bool:
    try:
        with _locked_store():
            pending = list_pending_receipts()
            pending[ref_number] = data
            _write_pending(pending)
        return True
    except Exception as e:
        logger.error("Failed to save pending receipt %s: %s", ref_number, e)
        return False


def get_pending_receipt(ref_number: str) -> Optional[Dict[str, Any]]:
    return list_pending_receipts().get(ref_number)


def delete_pending_receipt(ref_number: str) -> bool:
    try:
        with _locked_store():
            pending = list_pending_receipts()
            if ref_number not in pending:
                return False
            del pending[ref_number]
            _write_pending(pending)
        return True
    except Exception as e:
        logger.error("Failed to delete pending receipt %s: %s", ref_number, e)
        return False
