import base64
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.errors import MessageError

import requests
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.receipt_radar import ReceiptGmailConnection, ReceiptRadarDraft
from app.models.user import User
from app.services.receipt_radar import (
    MAX_EMAIL_BYTES, ReceiptDeliveryError, ReceiptLimitReached, deliver_receipt,
    has_receipt_sender, normalize_receipt, parse_email, parse_forwarded_receipt, stage_receipt,
    utc_datetime,
)

logger = logging.getLogger(__name__)
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
TOKEN_URL = "https://oauth2.googleapis.com/token"
CONSENT_CALLBACK = "/api/v1/receipt-radar/gmail/callback"
SENDERS = (
    "noreply.livin@bankmandiri.co.id",
    "bankbri@bri.co.id",
    "googleplay-noreply@google.com",
)
POLL_INTERVAL = timedelta(minutes=2)
FORWARDED_SUBJECTS = (
    "livin", "mandiri", "brimo", "bri", '"google play"', "transaksi",
    "pembayaran", "receipt", "qris",
)


def receipt_search(after: int, before: int) -> str:
    direct = " ".join(f"from:{sender}" for sender in SENDERS)
    forward_prefixes = "{subject:fwd subject:fw subject:terusan subject:tr}"
    receipt_subjects = "{" + " ".join(f"subject:{subject}" for subject in FORWARDED_SUBJECTS) + "}"
    return f"after:{after} before:{before} {{{direct} ({forward_prefixes} {receipt_subjects})}}"


class GmailError(Exception):
    pass


class GmailReauthorization(GmailError):
    pass


class GmailMessageSkipped(GmailError):
    pass


class GmailAccessLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        return not (isinstance(args, tuple) and len(args) >= 3 and CONSENT_CALLBACK in str(args[2]))


def _fernet() -> Fernet:
    return Fernet(settings.RECEIPT_GMAIL_ENCRYPTION_KEY.encode())


def gmail_available() -> bool:
    if not (settings.RECEIPT_GMAIL_CLIENT_ID and settings.RECEIPT_GMAIL_CLIENT_SECRET and settings.TELEGRAM_BOT_TOKEN):
        return False
    try:
        _fernet()
    except ValueError:
        return False
    return True


def encrypt_refresh_token(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def _decrypt_refresh_token(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        raise GmailReauthorization from None


def redirect_uri() -> str:
    return settings.APP_BASE_URL.rstrip("/") + CONSENT_CALLBACK


def _json(response: requests.Response) -> dict:
    data = response.json()
    if not isinstance(data, dict):
        raise GmailError
    return data


def request_token(**fields: str) -> dict:
    try:
        response = requests.post(
            TOKEN_URL, data={"client_id": settings.RECEIPT_GMAIL_CLIENT_ID,
                             "client_secret": settings.RECEIPT_GMAIL_CLIENT_SECRET, **fields},
            timeout=10,
        )
        data = _json(response)
        if data.get("error") == "invalid_grant":
            raise GmailReauthorization
        if not response.ok or not isinstance(data.get("access_token"), str):
            raise GmailError
        if "scope" in data and GMAIL_SCOPE not in str(data["scope"]).split():
            raise GmailReauthorization
        return data
    except (requests.RequestException, ValueError):
        raise GmailError from None


def gmail_get(token: str, path: str, *, max_bytes: int = 128 * 1024, **params: str | int) -> dict:
    try:
        with requests.get(f"{GMAIL_API}/{path}", params=params, headers={"Authorization": f"Bearer {token}"},
                          timeout=10, stream=True) as response:
            # Gmail can return no body when every selected list field is empty.
            if path == "messages" and response.status_code == 204:
                return {}
            if response.status_code == 401:
                raise GmailReauthorization
            if response.status_code == 404:
                raise GmailMessageSkipped
            if not response.ok:
                raise GmailError
            chunks = bytearray()
            for chunk in response.iter_content(chunk_size=16384):
                if len(chunks) + len(chunk) > max_bytes:
                    raise GmailMessageSkipped
                chunks.extend(chunk)
    except requests.RequestException:
        raise GmailError from None
    try:
        data = json.loads(chunks)
    except ValueError:
        raise GmailError from None
    if not isinstance(data, dict):
        raise GmailError
    return data


def revoke_refresh_token(encrypted_token: str) -> bool:
    try:
        token = _decrypt_refresh_token(encrypted_token)
        response = requests.post("https://oauth2.googleapis.com/revoke", data={"token": token}, timeout=8)
        return response.ok or (response.status_code == 400 and _json(response).get("error") == "invalid_token")
    except (GmailError, requests.RequestException, ValueError):
        return False


@dataclass(frozen=True)
class Mailbox:
    user_id: int
    generation: str
    refresh_token: str
    checked_through: datetime


def _active_owner(db: Session, mailbox: Mailbox) -> User | None:
    owner = db.query(User).filter(
        User.id == mailbox.user_id, User.is_active.is_(True),
        User.telegram_mode == "shared", User.telegram_chat_id.is_not(None),
    ).with_for_update().first()
    if owner and db.query(ReceiptGmailConnection.user_id).filter(
        ReceiptGmailConnection.user_id == owner.id, ReceiptGmailConnection.generation == mailbox.generation,
        ReceiptGmailConnection.status == "connected",
    ).first():
        return owner
    return None


def _pending_card(mailbox: Mailbox, parsed: tuple[str, dict]) -> bool:
    with SessionLocal() as db:
        if not _active_owner(db, mailbox):
            return False
        draft_id = stage_receipt(db, mailbox.user_id, parsed, source="gmail").id
        db.commit()

        owner = _active_owner(db, mailbox)
        if not owner:
            return False
        draft = db.get(ReceiptRadarDraft, draft_id)
        if draft:
            deliver_receipt(db, owner, draft)
        db.commit()
        return True


def _scan_mailbox(mailbox: Mailbox, until: datetime) -> None:
    token = request_token(grant_type="refresh_token",
                          refresh_token=_decrypt_refresh_token(mailbox.refresh_token))["access_token"]
    after = int(mailbox.checked_through.timestamp()) - 1
    before = int(until.timestamp()) + 1
    seen_pages = set()
    params = {"q": receipt_search(after, before), "maxResults": 50, "fields": "messages(id),nextPageToken"}
    while True:
        page = gmail_get(token, "messages", **params)
        for entry in page.get("messages", []):
            message_id = entry.get("id", "")
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", message_id):
                continue
            try:
                result = gmail_get(token, f"messages/{message_id}",
                                   max_bytes=(MAX_EMAIL_BYTES * 4 // 3) + 2048,
                                   format="raw", fields="id,raw,internalDate")
            except GmailMessageSkipped:
                continue
            try:
                internal_date = datetime.fromtimestamp(int(result["internalDate"]) / 1000, timezone.utc)
                if not mailbox.checked_through < internal_date <= until:
                    continue
                raw = result["raw"]
                content = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
                if len(content) > MAX_EMAIL_BYTES:
                    continue
                message = parse_email(content)
                if not has_receipt_sender(message, SENDERS):
                    continue
                parsed = normalize_receipt(parse_forwarded_receipt(message) or {})
            except (KeyError, MessageError, LookupError, TypeError, ValueError, OverflowError):
                continue
            if parsed and not _pending_card(mailbox, parsed):
                return
        cursor = page.get("nextPageToken")
        if not cursor:
            return
        if cursor in seen_pages:
            raise GmailError
        seen_pages.add(cursor)
        params["pageToken"] = cursor


def poll_gmail_receipts() -> None:
    if not gmail_available():
        return
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        waiting = db.query(ReceiptGmailConnection.user_id).join(User, User.id == ReceiptGmailConnection.user_id).filter(
            ReceiptGmailConnection.status == "connected", ReceiptGmailConnection.next_check_at <= now,
            User.is_active.is_(True), User.telegram_mode == "shared", User.telegram_chat_id.is_not(None),
        ).order_by(ReceiptGmailConnection.next_check_at).limit(10).all()
    for (user_id,) in waiting:
        with SessionLocal() as db:
            connection = db.query(ReceiptGmailConnection).filter(
                ReceiptGmailConnection.user_id == user_id, ReceiptGmailConnection.next_check_at <= now,
                ReceiptGmailConnection.status == "connected",
            ).with_for_update(skip_locked=True).first()
            if not connection:
                continue
            mailbox = Mailbox(connection.user_id, connection.generation, connection.refresh_token,
                              utc_datetime(connection.checked_through))
            # A lease allows another worker to take over if this process dies.
            connection.next_check_at = now + timedelta(minutes=10)
            db.commit()

        until = datetime.now(timezone.utc)
        status = "connected"
        finished = False
        try:
            _scan_mailbox(mailbox, until)
            finished = True
        except GmailReauthorization:
            status = "reconnect"
        except (GmailError, ReceiptDeliveryError, ReceiptLimitReached):
            logger.warning("Receipt Gmail sync will retry")
        with SessionLocal() as db:
            connection = db.query(ReceiptGmailConnection).filter(
                ReceiptGmailConnection.user_id == user_id, ReceiptGmailConnection.generation == mailbox.generation,
            ).with_for_update().first()
            if connection:
                connection.status = status
                connection.next_check_at = datetime.now(timezone.utc) + POLL_INTERVAL
                if finished:
                    connection.checked_through = until
                    connection.last_checked_at = until
                db.commit()
