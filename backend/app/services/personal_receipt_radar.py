import imaplib
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from email.errors import MessageError
from email.utils import parseaddr
from hashlib import blake2s, sha256
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import or_
from sqlalchemy.orm import Session

import app.models.pocket  # Registers ORM relationships when started outside FastAPI.
from app.core.config import settings
from app.core.receipt_store import get_pending_receipt, mark_receipt_notified, save_pending_receipt
from app.db.session import SessionLocal
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from app.services.receipt_radar import (
    DRAFT_PARSE_MODE, MAX_EMAIL_BYTES, RECEIPT_SENDERS as SENDERS, account_keyboard, draft_text, parse_email, parse_forwarded_receipt,
)

logger = logging.getLogger("receipt-radar")
PERSONAL_RECEIPT_PREFIX = "pr_"
WIB = ZoneInfo(settings.TIMEZONE)


@dataclass(frozen=True)
class PersonalRadarConfig:
    email: str
    app_password: str
    bot_token: str
    checkpoint: Path
    owner_chat_id: int
    group_chat_id: int
    thread_id: int


def _write_checkpoint(path: Path, uid: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as temp:
        target = Path(temp.name)
        temp.write(str(uid))
    try:
        os.replace(target, path)
    finally:
        target.unlink(missing_ok=True)


def _checkpoint(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except FileNotFoundError:
        return None


def _reference(owner_id: int, bank: str, native_reference: str, raw: bytes) -> str:
    identity = native_reference or sha256(raw).hexdigest()
    key = blake2s(f"{owner_id}:{bank}:{identity}".encode(), digest_size=12).hexdigest()
    return PERSONAL_RECEIPT_PREFIX + key


def _payment_source(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return f"Rekening •••• {digits[-4:]}" if len(digits) >= 4 else value[:80]


def _payload(owner: User, reference: str, parsed: dict) -> dict:
    when = parsed.get("datetime") or datetime.now(WIB)
    bank = parsed["bank"]
    source = str(parsed.get("payment_method") or parsed.get("source_account") or "")
    return {
        "user_id": owner.id, "telegram_user_id": owner.telegram_chat_id,
        "bank": bank, "nominal": parsed["nominal"], "merchant": str(parsed.get("merchant") or "Transaksi")[:200],
        "date": when.isoformat(), "category": str(parsed.get("inferred_category") or ""),
        "source_ref": str(parsed.get("ref_number") or ""), "reference": reference,
        "payment_source": _payment_source(source), "preferred_account": parsed.get("default_account"),
        "is_transfer": bool(parsed.get("is_transfer")), "is_internal_transfer": bool(parsed.get("is_internal_transfer")),
        "destination_name": str(parsed.get("destination_name") or "")[:200],
        "destination_bank": str(parsed.get("destination_bank") or "")[:80],
        "destination_account_candidate": parsed.get("destination_account_candidate"),
        "admin_fee": max(0, int(parsed.get("admin_fee") or 0)),
    }


def card(db: Session, user_id: int, payload: dict, page: int = 0) -> tuple[str, dict]:
    reference = payload["reference"]
    preferred = payload.get("preferred_account")
    markup = account_keyboard(db, user_id, reference, page, preferred=preferred)
    text = draft_text(payload)
    if payload.get("is_transfer"):
        destination = payload.get("destination_name") or payload["merchant"]
        if payload.get("destination_bank") and payload["destination_bank"].casefold() != destination.casefold():
            destination += " · " + payload["destination_bank"]
        nominal = f"Rp {payload['nominal']:,}".replace(",", ".")
        fee = f"Rp {payload['admin_fee']:,}".replace(",", ".")
        lines = [
            "🔄 <b>RECEIPT RADAR: TRANSFER</b>", "",
            f"• <b>Tujuan</b>: <code>{escape(destination)}</code>",
            f"• <b>Nominal</b>: <code>{nominal}</code>",
            f"• <b>Biaya Admin</b>: <code>{fee}</code>",
        ]
        if payload.get("source_ref"):
            lines.append(f"• <b>No. Referensi</b>: <code>{escape(payload['source_ref'])}</code>")
        lines.extend(("", "Pilih rekening di bawah untuk mencatat sebagai pengeluaran."))
        text = "\n".join(lines)
        if page == 0 and payload.get("is_internal_transfer"):
            target_name = payload.get("destination_account_candidate")
            accounts = db.query(Account.id, Account.name).filter(
                Account.user_id == user_id, Account.is_archived.is_(False),
                Account.name.in_((preferred, target_name)),
            ).all()
            ids = {account.name: account.id for account in accounts}
            if preferred != target_name and preferred in ids and target_name in ids:
                value = f"rcpt_move:{reference}:{ids[preferred]}:{ids[target_name]}"
                label = f"🔄 Transfer {preferred} → {target_name}"
                markup["inline_keyboard"].insert(0, [{"text": label, "callback_data": value}])
    return text, markup


def _already_recorded(db: Session, user_id: int, references: tuple[str, ...]) -> bool:
    return db.query(Transaction.id).filter(
        Transaction.user_id == user_id,
        or_(*(or_(
            Transaction.raw_text.contains(f"[receipt_radar:ref_{ref}]", autoescape=True),
            Transaction.description.contains(f"(Ref: {ref})", autoescape=True),
        ) for ref in references)),
    ).first() is not None


def _send_card(cfg: PersonalRadarConfig, text: str, markup: dict) -> bool:
    for chat, thread in ((cfg.group_chat_id, cfg.thread_id), (cfg.owner_chat_id, None)):
        payload = {"chat_id": chat, "text": text, "parse_mode": DRAFT_PARSE_MODE, "reply_markup": markup}
        if thread is not None:
            payload["message_thread_id"] = thread
        try:
            response = requests.post(f"https://api.telegram.org/bot{cfg.bot_token}/sendMessage", json=payload, timeout=8)
            if response.ok and response.json().get("ok"):
                return True
        except (requests.RequestException, ValueError, AttributeError):
            pass
    return False


def handle_mail(cfg: PersonalRadarConfig, raw: bytes) -> bool:
    try:
        message = parse_email(raw)
        if parseaddr(str(message.get("From", "")))[1].lower() not in SENDERS:
            return True
        parsed = parse_forwarded_receipt(message)
    except (MessageError, LookupError, TypeError, ValueError):
        logger.info("Ignoring an unreadable receipt email.")
        return True
    amount = parsed.get("nominal") if parsed else None
    if type(amount) is not int or not 0 < amount <= 9_000_000_000_000_000:
        return True

    with SessionLocal() as db:
        owner = db.query(User).filter(
            User.telegram_chat_id == cfg.owner_chat_id, User.is_active.is_(True), User.telegram_mode == "shared",
        ).one_or_none()
        if not owner:
            return False
        original = str(parsed.get("ref_number") or "").strip()
        reference = _reference(owner.id, parsed["bank"], original, raw)
        if _already_recorded(db, owner.id, tuple(key for key in (reference, original) if key)):
            return True
        # Keep approving cards that were sent by the old worker instead of resending them.
        if original and get_pending_receipt(original):
            return True
        previous = get_pending_receipt(reference)
        if previous and previous.get("notified"):
            return True
        payload = previous or _payload(owner, reference, parsed)
        text, markup = card(db, owner.id, payload)
        if previous is None and not save_pending_receipt(reference, payload):
            return False

    if not _send_card(cfg, text, markup):
        logger.warning("Receipt card delivery failed; leaving the IMAP checkpoint unchanged.")
        return False
    return mark_receipt_notified(reference)


def check_mail(cfg: PersonalRadarConfig) -> None:
    checkpoint = _checkpoint(cfg.checkpoint)
    with imaplib.IMAP4_SSL("imap.gmail.com", timeout=12) as mail:
        mail.login(cfg.email, cfg.app_password)
        if mail.select("INBOX", readonly=True)[0] != "OK":
            raise RuntimeError("Inbox unavailable")
        sender_filter = f'(OR (FROM "{SENDERS[0]}") (OR (FROM "{SENDERS[1]}") (FROM "{SENDERS[2]}")))'
        tests = (() if checkpoint is None else (f"UID {checkpoint + 1}:*",)) + (sender_filter,)
        status, data = mail.uid("SEARCH", None, *tests)
        if status != "OK":
            raise RuntimeError("IMAP search failed")
        uids = sorted(int(raw) for raw in (data[0] or b"").split())
        if checkpoint is None:
            if uids:
                _write_checkpoint(cfg.checkpoint, uids[-1])
            return
        for uid in (value for value in uids if value > checkpoint):
            status, entries = mail.uid("FETCH", str(uid), "(BODY.PEEK[])")
            if status != "OK":
                return
            raw = next((item[1] for item in entries if isinstance(item, tuple)), None)
            if raw is None:
                return
            if len(raw) > MAX_EMAIL_BYTES:
                logger.info("Ignoring oversized receipt email.")
            elif not handle_mail(cfg, raw):
                return
            _write_checkpoint(cfg.checkpoint, uid)


def run(cfg: PersonalRadarConfig) -> None:
    logger.info("Tillfold Personal Receipt Radar started.")
    while True:
        try:
            check_mail(cfg)
        except KeyboardInterrupt:
            return
        except Exception as exc:
            logger.warning("Personal Receipt Radar will retry (%s).", type(exc).__name__)
        time.sleep(15)
