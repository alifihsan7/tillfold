import hmac
import re
import secrets
from datetime import datetime, timezone
from email.errors import MessageError

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.receipt_radar import ReceiptRadarAddress, ReceiptRadarDraft
from app.models.user import User
from app.services.receipt_radar import (
    MAX_EMAIL_BYTES, VERIFICATION_TTL, ReceiptDeliveryError, ReceiptLimitReached, deliver_receipt,
    forwarding_verification, normalize_receipt, parse_email, parse_forwarded_receipt, stage_receipt, utc_datetime,
)

router = APIRouter()


def _domain() -> str:
    return settings.RECEIPT_RADAR_DOMAIN.strip().lower()


def _available() -> bool:
    return bool(_domain() and len(settings.RECEIPT_RADAR_INGRESS_TOKEN) >= 32 and settings.TELEGRAM_BOT_TOKEN)


def _has_telegram(user: User) -> bool:
    return bool(user.telegram_chat_id and user.telegram_mode == "shared")


def _status(user: User, address: ReceiptRadarAddress | None) -> dict:
    available = _available()
    result = {"available": available, "telegram_linked": _has_telegram(user), "address": None,
              "verification_code": None, "verification_url": None}
    if available and address:
        result["address"] = f"receipt-{address.alias}@{_domain()}"
        if address.verification_at and datetime.now(timezone.utc) - utc_datetime(address.verification_at) < VERIFICATION_TTL:
            result["verification_code"] = address.verification_code
            result["verification_url"] = address.verification_url
    return result


@router.get("")
def get_forwarding_status(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return _status(user, db.get(ReceiptRadarAddress, user.id))


@router.post("")
def enable_forwarding(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    if not _available():
        raise HTTPException(503, "Alamat penerima Receipt Radar belum dikonfigurasi.")
    owner = db.query(User).filter(User.id == user.id, User.is_active.is_(True)).with_for_update().one_or_none()
    if not owner or not _has_telegram(owner):
        raise HTTPException(409, "Hubungkan Telegram sebelum mengaktifkan Receipt Radar.")
    address = db.get(ReceiptRadarAddress, owner.id)
    if address is None:
        address = ReceiptRadarAddress(user_id=owner.id, alias=secrets.token_hex(16))
        db.add(address)
        db.commit()
    return _status(owner, address)


@router.delete("")
def disable_forwarding(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    db.query(User.id).filter(User.id == user.id).with_for_update().one()
    address = db.get(ReceiptRadarAddress, user.id)
    if address:
        db.delete(address)
    db.query(ReceiptRadarDraft).filter(
        ReceiptRadarDraft.user_id == user.id, ReceiptRadarDraft.status == "pending", ReceiptRadarDraft.source == "forwarding",
    ).update({ReceiptRadarDraft.status: "discarded", ReceiptRadarDraft.payload: {}}, synchronize_session=False)
    db.commit()
    return _status(user, None)


async def _read_inbound(request: Request, authorization: str = Header(default="")) -> bytes:
    secret = settings.RECEIPT_RADAR_INGRESS_TOKEN
    if not _available() or not hmac.compare_digest(authorization.encode(), f"Bearer {secret}".encode()):
        raise HTTPException(401, "Ingress tidak diotorisasi.")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_EMAIL_BYTES:
            raise HTTPException(413, "Email terlalu besar.")
        body.extend(chunk)
    return bytes(body)


@router.post("/inbound", include_in_schema=False)
def inbound_email(
    raw: bytes = Depends(_read_inbound), recipient: str = Header(alias="X-Receipt-Recipient"),
    sender: str = Header(default="", alias="X-Receipt-Sender"), db: Session = Depends(get_db),
):
    local, _, domain = recipient.strip().lower().rpartition("@")
    if domain != _domain() or not re.fullmatch(r"receipt-[a-f0-9]{32}", local):
        raise HTTPException(404, "Alamat Receipt Radar tidak tersedia.")
    alias = local.removeprefix("receipt-")
    address = db.query(ReceiptRadarAddress).filter(ReceiptRadarAddress.alias == alias).first()
    if not address:
        raise HTTPException(404, "Alamat Receipt Radar tidak tersedia.")

    try:
        message = parse_email(raw)
        code, link = forwarding_verification(message, sender)
        parsed = None if code or link else normalize_receipt(parse_forwarded_receipt(message) or {})
    except (MessageError, LookupError, TypeError, ValueError, OverflowError):
        raise HTTPException(422, "Format email struk tidak terbaca.") from None
    if not (code or link or parsed):
        raise HTTPException(422, "Email ini belum didukung Receipt Radar.")

    # Serialize mail, account changes and Telegram approvals for the same owner.
    user = db.query(User).filter(User.id == address.user_id, User.is_active.is_(True)).with_for_update().one_or_none()
    if not user or not db.query(ReceiptRadarAddress.user_id).filter(
        ReceiptRadarAddress.user_id == user.id, ReceiptRadarAddress.alias == alias,
    ).first():
        raise HTTPException(404, "Alamat Receipt Radar tidak tersedia.")
    if code or link:
        db.refresh(address)
        address.verification_code = code
        address.verification_url = link
        address.verification_at = datetime.now(timezone.utc)
        db.commit()
        return {"ok": True, "status": "verification"}
    if not _has_telegram(user):
        raise HTTPException(409, "Hubungkan kembali Telegram di Tillfold.")

    owner_id = user.id
    try:
        draft_id = stage_receipt(db, owner_id, parsed).id
    except ReceiptLimitReached:
        raise HTTPException(429, "Batas harian Receipt Radar tercapai.") from None
    db.commit()

    user = db.query(User).filter(User.id == owner_id, User.is_active.is_(True)).with_for_update().one_or_none()
    if not user or not _has_telegram(user):
        raise HTTPException(409, "Hubungkan kembali Telegram di Tillfold.")
    draft = db.get(ReceiptRadarDraft, draft_id, populate_existing=True)
    if draft is None:
        return {"ok": True, "status": "duplicate"}
    try:
        sent = deliver_receipt(db, user, draft)
    except ReceiptDeliveryError:
        raise HTTPException(502, "Kartu struk belum terkirim ke Telegram.") from None
    db.commit()
    return {"ok": True, "status": "pending" if sent else "duplicate"}
