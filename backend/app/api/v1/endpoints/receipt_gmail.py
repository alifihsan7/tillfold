import base64
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.receipt_radar import ReceiptGmailConnection, ReceiptGmailConsent, ReceiptRadarDraft
from app.models.user import User
from app.services.receipt_gmail import (
    GMAIL_SCOPE, GmailError, encrypt_refresh_token, gmail_available, gmail_get, redirect_uri,
    request_token, revoke_refresh_token,
)
from app.services.receipt_radar import utc_datetime

router = APIRouter()
CONSENT_SECONDS = 600


def _cookie() -> tuple[str, bool]:
    secure = urlsplit(settings.APP_BASE_URL).scheme == "https"
    return "__Host-tillfold-gmail" if secure else "tillfold-gmail", secure


def _owner(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id, User.is_active.is_(True)).populate_existing().with_for_update().one_or_none()


def _telegram_linked(user: User) -> bool:
    return bool(user.telegram_chat_id and user.telegram_mode == "shared")


def _result(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"


@router.get("")
def get_gmail_status(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _result(response)
    connection = db.get(ReceiptGmailConnection, user.id)
    return {
        "available": gmail_available(), "telegram_linked": _telegram_linked(user),
        "email": connection.email if connection else None,
        "status": connection.status if connection else "disconnected",
        "last_checked_at": utc_datetime(connection.last_checked_at).isoformat()
        if connection and connection.last_checked_at else None,
    }


@router.post("/connect")
def begin_gmail_consent(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _result(response)
    if not gmail_available():
        raise HTTPException(503, "Koneksi Gmail belum tersedia.")
    owner = _owner(db, user.id)
    if not owner or not _telegram_linked(owner):
        raise HTTPException(409, "Hubungkan Telegram sebelum mengaktifkan Receipt Radar.")

    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    digest = sha256(state.encode()).hexdigest()
    challenge = base64.urlsafe_b64encode(sha256(verifier.encode()).digest()).decode().rstrip("=")
    consent = db.get(ReceiptGmailConsent, owner.id) or ReceiptGmailConsent(user_id=owner.id)
    consent.state_digest = digest
    consent.verifier = verifier
    consent.session_version = owner.session_version
    consent.consumed_at = None
    consent.expires_at = datetime.now(timezone.utc) + timedelta(seconds=CONSENT_SECONDS)
    db.add(consent)
    db.commit()

    name, secure = _cookie()
    response.set_cookie(name, state, max_age=CONSENT_SECONDS, httponly=True, secure=secure, samesite="lax", path="/")
    query = urlencode({
        "client_id": settings.RECEIPT_GMAIL_CLIENT_ID, "redirect_uri": redirect_uri(),
        "response_type": "code", "scope": GMAIL_SCOPE, "access_type": "offline", "prompt": "select_account consent",
        "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
    })
    return {"url": f"https://accounts.google.com/o/oauth2/v2/auth?{query}"}


def _finish(status: str) -> RedirectResponse:
    response = RedirectResponse(f"/?receipt_gmail={status}#/profile", status_code=303)
    _result(response)
    name, secure = _cookie()
    response.delete_cookie(name, path="/", secure=secure, httponly=True, samesite="lax")
    return response


@router.get("/callback", include_in_schema=False)
def finish_gmail_consent(request: Request, state: str = "", code: str = "", error: str = "", db: Session = Depends(get_db)):
    name, _ = _cookie()
    if not gmail_available() or not state or len(state) > 128 or not hmac.compare_digest(
        state.encode(), request.cookies.get(name, "").encode(),
    ):
        return _finish("failed")

    digest = sha256(state.encode()).hexdigest()
    user_id = db.query(ReceiptGmailConsent.user_id).filter(ReceiptGmailConsent.state_digest == digest).scalar()
    owner = _owner(db, user_id) if user_id else None
    consent = db.get(ReceiptGmailConsent, user_id, populate_existing=True) if owner else None
    now = datetime.now(timezone.utc)
    if (not consent or consent.state_digest != digest or consent.consumed_at
            or utc_datetime(consent.expires_at) <= now or consent.session_version != owner.session_version
            or not _telegram_linked(owner)):
        return _finish("failed")
    if error or not code or len(code) > 4096:
        db.delete(consent)
        db.commit()
        return _finish("cancelled")

    verifier, session_version = consent.verifier, consent.session_version
    consent.consumed_at = now
    db.commit()
    try:
        token = request_token(grant_type="authorization_code", code=code, redirect_uri=redirect_uri(), code_verifier=verifier)
        refresh_token = token.get("refresh_token")
        if not isinstance(refresh_token, str) or not refresh_token or len(refresh_token) > 2_000:
            raise GmailError
        address = gmail_get(token["access_token"], "profile", fields="emailAddress").get("emailAddress")
        if not isinstance(address, str) or "@" not in address or len(address) > 254:
            raise GmailError
        address = address.strip().lower()
    except GmailError:
        return _finish("failed")

    owner = _owner(db, user_id)
    consent = db.get(ReceiptGmailConsent, user_id, populate_existing=True) if owner else None
    if (not owner or not _telegram_linked(owner) or owner.session_version != session_version
            or not consent or consent.state_digest != digest):
        return _finish("failed")
    current = db.get(ReceiptGmailConnection, user_id)
    if current and current.email != address:
        return _finish("switch")
    if db.query(ReceiptGmailConnection.user_id).filter(
        ReceiptGmailConnection.email == address, ReceiptGmailConnection.user_id != user_id,
    ).first():
        return _finish("in_use")

    connection = current or ReceiptGmailConnection(user_id=user_id, email=address,
                                                 connected_at=now, checked_through=now)
    connection.refresh_token = encrypt_refresh_token(refresh_token)
    connection.generation = secrets.token_hex(16)
    connection.next_check_at = now
    connection.status = "connected"
    db.add(connection)
    db.delete(consent)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _finish("in_use")
    return _finish("connected")


@router.delete("")
def disconnect_gmail(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _result(response)
    owner = _owner(db, user.id)
    if not owner:
        raise HTTPException(404, "Akun tidak tersedia.")
    consent = db.get(ReceiptGmailConsent, owner.id)
    if consent:
        db.delete(consent)
    connection = db.get(ReceiptGmailConnection, owner.id)
    if not connection:
        db.commit()
        return {"revoked": True}
    revoked = revoke_refresh_token(connection.refresh_token)
    db.delete(connection)
    db.query(ReceiptRadarDraft).filter(
        ReceiptRadarDraft.user_id == owner.id, ReceiptRadarDraft.source == "gmail", ReceiptRadarDraft.status == "pending",
    ).update({ReceiptRadarDraft.status: "discarded", ReceiptRadarDraft.payload: {}}, synchronize_session=False)
    db.commit()
    return {"revoked": revoked}
