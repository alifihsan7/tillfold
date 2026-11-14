import json
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


def save_pending_receipt(ref_number: str, data: Dict[str, Any]) -> bool:
    _ensure_dir()
    pending = list_pending_receipts()
    pending[ref_number] = data
    try:
        PENDING_FILE.write_text(json.dumps(pending, indent=2, default=str), encoding="utf-8")
        return True
    except Exception as e:
        logger.error("Failed to save pending receipt %s: %s", ref_number, e)
        return False


def get_pending_receipt(ref_number: str) -> Optional[Dict[str, Any]]:
    pending = list_pending_receipts()
    return pending.get(ref_number)


def delete_pending_receipt(ref_number: str) -> bool:
    _ensure_dir()
    pending = list_pending_receipts()
    if ref_number in pending:
        del pending[ref_number]
        try:
            PENDING_FILE.write_text(json.dumps(pending, indent=2), encoding="utf-8")
            return True
        except Exception as e:
            logger.error("Failed to delete pending receipt %s: %s", ref_number, e)
    return False
