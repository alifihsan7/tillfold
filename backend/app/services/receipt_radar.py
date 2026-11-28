import re
import secrets
from datetime import datetime, timedelta, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr
from hashlib import sha256
from html import unescape
from urllib.parse import urlsplit

import requests
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.receipt_parser import html_to_text, parse_brimo_receipt, parse_google_play_receipt, parse_mandiri_receipt
from app.models.account import Account
from app.models.receipt_radar import ReceiptRadarDraft
from app.models.user import User

MAX_EMAIL_BYTES = 512 * 1024
RECEIPT_PREFIX = "fw_"
VERIFICATION_TTL = timedelta(days=1)
DRAFT_TTL = timedelta(days=14)
ACCOUNT_PAGE_SIZE = 8


def parse_email(raw: bytes) -> EmailMessage:
    return BytesParser(policy=policy.default).parsebytes(raw)


def _body(message: EmailMessage) -> str:
    part = message.get_body(preferencelist=("html", "plain"))
    if part is None:
        return ""
    content = part.get_content(errors="replace")
    return content if isinstance(content, str) else ""


def forwarding_verification(message: EmailMessage, envelope_sender: str) -> tuple[str | None, str | None]:
    if envelope_sender.strip().lower() != "forwarding-noreply@google.com":
        return None, None
    content = _body(message)
    text = html_to_text(content)
    match = re.search(r"(?:confirmation code|verification code|kode konfirmasi|kode verifikasi)\s*[:：]?\s*(\d{5,12})\b", text, re.I)
    link = None
    for candidate in re.findall(r'https://mail\.google\.com/mail/vf-[^\s<>"\']{1,970}', unescape(content)):
        parsed = urlsplit(candidate)
        if parsed.netloc == "mail.google.com" and parsed.path.startswith("/mail/vf-"):
            link = candidate
            break
    return match.group(1) if match else None, link


def has_receipt_sender(message: EmailMessage, senders: tuple[str, ...]) -> bool:
    if parseaddr(str(message.get("From", "")))[1].lower() in senders:
        return True
    subject = str(message.get("Subject", ""))
    if not re.match(r"\s*(?:fwd|fw|terusan|tr)\s*:", subject, re.I):
        return False
    for part in message.iter_attachments():
        if part.get_content_type() == "message/rfc822" and isinstance(part.get_payload(), list):
            for original in part.get_payload()[:1]:
                if isinstance(original, EmailMessage) and parseaddr(str(original.get("From", "")))[1].lower() in senders:
                    return True
    inline = unescape(_body(message)).lower()
    return any(re.search(rf"(?<![\w.+-]){re.escape(sender)}(?![\w.-])", inline) for sender in senders)


def parse_forwarded_receipt(message: EmailMessage) -> dict | None:
    # Structured forwards may carry the original as a message/rfc822 attachment.
    candidates = [message]
    for part in message.iter_attachments():
        if part.get_content_type() == "message/rfc822":
            candidates.extend(part.get_payload()[:1])
    for candidate in candidates:
        if not isinstance(candidate, EmailMessage):
            continue
        subject = str(candidate.get("Subject") or message.get("Subject") or "")
        content = _body(candidate)
        descriptor = f"{candidate.get('From', '')} {subject} {content}".lower()
        if "bankmandiri.co.id" in descriptor or "bank mandiri" in descriptor or re.search(r"\blivin\b", descriptor):
            parser = parse_mandiri_receipt
        elif "bri.co.id" in descriptor or "brimo" in descriptor:
            parser = parse_brimo_receipt
        elif "googleplay-noreply@google.com" in descriptor or "google play" in descriptor:
            parser = parse_google_play_receipt
        else:
            continue
        receipt = parser(content, subject)
        if receipt:
            return receipt
    return None


def normalize_receipt(receipt: dict) -> tuple[str, dict] | None:
    nominal = receipt.get("nominal")
    if receipt.get("is_transfer") or type(nominal) is not int or not 0 < nominal <= 9_000_000_000_000_000:
        return None
    bank = str(receipt.get("bank") or "").strip().lower()
    merchant = str(receipt.get("merchant") or "Transaksi").strip()[:200]
    occurred = receipt.get("datetime")
    source_ref = str(receipt.get("ref_number") or "").strip()[:160]
    if source_ref:
        reference = source_ref
    elif isinstance(occurred, datetime):
        reference = f"{occurred.isoformat()}:{nominal}:{merchant.casefold()}"
    else:
        return None
    digest = sha256(f"{bank}:{reference}".encode()).hexdigest()
    return digest, {
        "bank": bank, "merchant": merchant, "nominal": nominal,
        "date": occurred.isoformat() if isinstance(occurred, datetime) else None,
        "category": str(receipt.get("inferred_category") or "")[:100],
        "source_ref": source_ref,
    }


def account_keyboard(db: Session, user_id: int, reference: str, page: int) -> dict:
    accounts = db.query(Account.id, Account.name).filter(
        Account.user_id == user_id, Account.is_archived.is_(False),
    ).order_by(func.lower(Account.name), Account.id).offset(page * ACCOUNT_PAGE_SIZE).limit(ACCOUNT_PAGE_SIZE + 1).all()
    rows = [[{"text": name, "callback_data": f"rcpt_pick:{reference}:{account_id}"}]
            for account_id, name in accounts[:ACCOUNT_PAGE_SIZE]]
    navigation = []
    if page > 0:
        navigation.append({"text": "Sebelumnya", "callback_data": f"rcpt_accounts:{reference}:{page - 1}"})
    if len(accounts) > ACCOUNT_PAGE_SIZE:
        navigation.append({"text": "Berikutnya", "callback_data": f"rcpt_accounts:{reference}:{page + 1}"})
    if not accounts and not page:
        navigation.append({"text": "Muat ulang rekening", "callback_data": f"rcpt_accounts:{reference}:0"})
    if navigation:
        rows.append(navigation)
    rows.append([{"text": "Abaikan struk", "callback_data": f"rcpt_drop:{reference}:0:0"}])
    return {"inline_keyboard": rows}


def draft_text(payload: dict) -> str:
    amount = f"Rp {payload['nominal']:,}".replace(",", ".")
    return (
        f"🧾 Struk email · {payload['bank'].upper()}\n\n"
        f"{payload['merchant']} · {amount}\n\n"
        "Pilih rekening untuk mulai. Struk belum dicatat."
    )


def resolve_draft(draft: ReceiptRadarDraft, status: str) -> None:
    draft.status = status
    draft.payload = {}


def utc_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class ReceiptDeliveryError(Exception):
    pass


class ReceiptLimitReached(Exception):
    pass


def stage_receipt(db: Session, user_id: int, parsed: tuple[str, dict], *, source: str = "forwarding") -> ReceiptRadarDraft:
    """Call with the owner row locked to serialize aliases and mailbox polling."""
    now = datetime.now(timezone.utc)
    fingerprint, payload = parsed
    db.query(ReceiptRadarDraft).filter(
        ReceiptRadarDraft.user_id == user_id, ReceiptRadarDraft.status == "pending",
        ReceiptRadarDraft.created_at <= now - DRAFT_TTL,
    ).update({ReceiptRadarDraft.status: "expired", ReceiptRadarDraft.payload: {}}, synchronize_session=False)
    draft = db.query(ReceiptRadarDraft).filter(
        ReceiptRadarDraft.user_id == user_id, ReceiptRadarDraft.fingerprint == fingerprint,
    ).first()
    if draft is not None:
        return draft
    recent = db.query(ReceiptRadarDraft.id).filter(
        ReceiptRadarDraft.user_id == user_id, ReceiptRadarDraft.created_at >= now - timedelta(days=1),
    ).count()
    if recent >= 30:
        raise ReceiptLimitReached
    draft = ReceiptRadarDraft(id=f"{RECEIPT_PREFIX}{secrets.token_hex(12)}", user_id=user_id,
                              fingerprint=fingerprint, payload=payload, created_at=now, source=source)
    db.add(draft)
    return draft


def deliver_receipt(db: Session, user: User, draft: ReceiptRadarDraft) -> bool:
    """Deliver once per draft after it survives a commit. Caller holds the owner lock."""
    if draft.status != "pending" or draft.notified_at:
        return False
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": user.telegram_chat_id, "text": draft_text(draft.payload),
                  "reply_markup": account_keyboard(db, user.id, draft.id, 0)},
            timeout=8,
        )
        if not response.ok or not response.json().get("ok"):
            raise ReceiptDeliveryError
    except (requests.RequestException, ValueError, AttributeError):
        raise ReceiptDeliveryError from None
    draft.notified_at = datetime.now(timezone.utc)
    return True
