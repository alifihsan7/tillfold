from typing import Optional
import logging
import secrets
import hmac
import hashlib
import json
import time
from urllib.parse import parse_qsl
import requests
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from app.db.session import get_db
from app.models.user import User, TelegramLink
from app.services.telegram_link import create_link
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.subscription import Subscription, SubscriptionPayment
from app.models.goal import Goal
from app.models.category import Category
from app.models.paycheck import PaycheckConfig, PaycheckBucket, PaycheckSession
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserUpdate,
    UserResponse,
    TokenResponse,
    GoogleAuthRequest,
    TelegramWebAppAuthRequest,
)
from app.core.security import hash_password, verify_password, create_access_token
from app.core.config import settings
from app.core.rate_limit import login_limiter, register_limiter, auth_limiter
from app.api.deps import get_strict_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)):
    register_limiter.check(request)
    # Check existing username or email
    clean_username = payload.username.strip().lower()
    existing = db.query(User).filter(
        or_(
            User.username == clean_username,
            (User.email == payload.email) if payload.email else False
        )
    ).first()

    if existing:
        if existing.username == clean_username:
            raise HTTPException(status_code=400, detail="Username sudah digunakan oleh akun lain")
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")

    hashed_pw = hash_password(payload.password)
    user = User(
        username=clean_username,
        email=payload.email.strip() if payload.email else None,
        full_name=payload.full_name.strip(),
        hashed_password=hashed_pw,
        telegram_chat_id=None,
        is_active=True,
        is_onboarded=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.from_orm(user)
    )

@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    login_limiter.check(request)
    login_id = payload.username_or_email.strip().lower()
    user = db.query(User).filter(
        or_(
            User.username == login_id,
            User.email == login_id
        )
    ).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        client_ip = (
            login_limiter._get_real_ip(request)
            if hasattr(login_limiter, "_get_real_ip")
            else (request.client.host if request.client else "unknown")
        )
        logger.warning(f"[AUTH_FAIL] IP={client_ip} username={login_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun ini telah dinonaktifkan",
        )

    token = create_access_token(subject=user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.from_orm(user)
    )

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(user: User = Depends(get_strict_current_user)):
    return UserResponse.from_orm(user)

@router.put("/me", response_model=UserResponse)
def update_profile(
    payload: UserUpdate,
    user: User = Depends(get_strict_current_user),
    db: Session = Depends(get_db)
):
    if payload.full_name:
        user.full_name = payload.full_name.strip()
    if payload.email:
        # Check email uniqueness
        existing = db.query(User).filter(User.email == payload.email, User.id != user.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email sudah digunakan akun lain")
        user.email = payload.email.strip()
    if payload.password:
        user.hashed_password = hash_password(payload.password)

    db.commit()
    db.refresh(user)
    return UserResponse.from_orm(user)

@router.post("/link-telegram")
def link_telegram_chat(
    user: User = Depends(get_strict_current_user),
    db: Session = Depends(get_db)
):
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(503, "Bot Telegram belum dikonfigurasi di server.")
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe", timeout=10,
        )
        data = response.json()
        username = data.get("result", {}).get("username") if data.get("ok") else None
        if not username:
            raise ValueError("Missing bot username")
    except (requests.RequestException, ValueError):
        raise HTTPException(503, "Bot Telegram belum tersedia. Coba lagi nanti.")
    token = create_link(db, user)
    return {"url": f"https://t.me/{username}?start=link_{token}", "expires_in": 600}


@router.post("/link-telegram-custom")
def retired_custom_bot_registration():
    raise HTTPException(410, "Gunakan bot Tillfold melalui pengaturan integrasi Telegram.")


@router.post("/unlink-telegram", response_model=UserResponse)
def unlink_telegram(
    user: User = Depends(get_strict_current_user),
    db: Session = Depends(get_db)
):
    db.query(TelegramLink).filter(TelegramLink.user_id == user.id).delete()
    user.telegram_chat_id = None
    user.telegram_bot_token = None
    user.telegram_bot_username = None
    user.telegram_webhook_secret = None
    user.telegram_mode = "shared"
    db.commit()
    db.refresh(user)
    return UserResponse.from_orm(user)

@router.get("/google/config")
def get_google_auth_config():
    return {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "is_configured": bool(settings.GOOGLE_CLIENT_ID)
    }

@router.post("/google", response_model=TokenResponse)
def google_auth(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Sign-In belum dikonfigurasi di server (GOOGLE_CLIENT_ID belum diatur di .env)",
        )

    try:
        id_info = id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token autentikasi Google tidak valid: {str(e)}",
        )

    google_id = str(id_info.get("sub"))
    email = id_info.get("email")
    full_name = id_info.get("name") or "Pengguna Google"
    avatar = id_info.get("picture")

    if not email:
        raise HTTPException(status_code=400, detail="Akun Google Anda tidak menyediakan alamat email")

    # 1. Cari user berdasarkan google_id
    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        # 2. Cari user berdasarkan email yang cocok
        user = db.query(User).filter(User.email == email).first()
        if user:
            # Tautkan akun Google ke user eksisting
            user.google_id = google_id
            if avatar and not user.avatar_url:
                user.avatar_url = avatar
            db.commit()
            db.refresh(user)
        else:
            # 3. Buat user baru
            base_username = email.split("@")[0].lower()
            clean_username = "".join(c for c in base_username if c.isalnum() or c in ("_", "-")) or "user"
            candidate = clean_username
            counter = 1
            while db.query(User).filter(User.username == candidate).first():
                candidate = f"{clean_username}{counter}"
                counter += 1

            random_pw = hash_password(secrets.token_urlsafe(32))
            user = User(
                username=candidate,
                email=email,
                full_name=full_name,
                hashed_password=random_pw,
                google_id=google_id,
                avatar_url=avatar,
                is_active=True,
                is_onboarded=False, # Baru mendaftar -> picu Onboarding Wizard
            )
            db.add(user)
            db.commit()
            db.refresh(user)

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Akun ini telah dinonaktifkan")

    token = create_access_token(subject=user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=user,
    )

def verify_telegram_init_data(init_data: str, bot_token: str) -> Optional[dict]:
    """
    Validates data received from Telegram WebApp via HMAC-SHA256 signature check.
    """
    try:
        parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in parsed_data:
            return None
        
        received_hash = parsed_data.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        
        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(computed_hash, received_hash):
            return None

        # Check auth_date within 7 days
        auth_date = int(parsed_data.get("auth_date", 0))
        if time.time() - auth_date > 86400 * 7:
            return None
            
        if "user" in parsed_data:
            parsed_data["user"] = json.loads(parsed_data["user"])
            
        return parsed_data
    except Exception as e:
        print(f"Error validating Telegram WebApp initData: {e}")
        return None

@router.post("/telegram-webapp", response_model=TokenResponse)
def telegram_webapp_auth(payload: TelegramWebAppAuthRequest, request: Request, db: Session = Depends(get_db)):
    """
    Authenticate a user directly from Telegram Mini App initData without password.
    """
    if request:
        auth_limiter.check(request)
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram Bot Token belum dikonfigurasi di server",
        )

    validated = verify_telegram_init_data(payload.init_data, settings.TELEGRAM_BOT_TOKEN)

    if not validated or "user" not in validated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Data autentikasi Telegram WebApp tidak valid atau telah kedaluwarsa",
        )

    tg_user = validated["user"]
    tg_id = tg_user.get("id")
    if not tg_id:
        raise HTTPException(status_code=400, detail="Data Telegram tidak memuat ID pengguna")

    # 1. Cari user yang sudah terhubung dengan telegram_chat_id ini
    user = db.query(User).filter(User.telegram_chat_id == int(tg_id)).first()
    
    if not user:
        # Buat user baru secara otomatis untuk pengguna Telegram baru
        tg_username = tg_user.get("username")
        first_name = tg_user.get("first_name") or "Pengguna Telegram"
        
        base_username = (tg_username or f"tg_{tg_id}").lower()
        clean_username = "".join(c for c in base_username if c.isalnum() or c in ("_", "-")) or f"tg_{tg_id}"
        candidate = clean_username
        counter = 1
        while db.query(User).filter(User.username == candidate).first():
            candidate = f"{clean_username}{counter}"
            counter += 1

        random_pw = hash_password(secrets.token_urlsafe(32))
        user = User(
            username=candidate,
            full_name=first_name,
            hashed_password=random_pw,
            telegram_chat_id=int(tg_id),
            is_active=True,
            is_onboarded=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Akun ini telah dinonaktifkan")

    token = create_access_token(subject=user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.from_orm(user),
    )

@router.delete("/me")
def delete_my_account(
    current_user: User = Depends(get_strict_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user.id

    db.query(TelegramLink).filter(TelegramLink.user_id == user_id).delete()

    # Hapus seluruh relasi data pengguna secara permanen
    db.query(SubscriptionPayment).filter(SubscriptionPayment.user_id == user_id).delete()
    db.query(Transaction).filter(Transaction.user_id == user_id).delete()
    db.query(Subscription).filter(Subscription.user_id == user_id).delete()
    db.query(Goal).filter(Goal.user_id == user_id).delete()
    db.query(PaycheckSession).filter(PaycheckSession.user_id == user_id).delete()

    configs = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == user_id).all()
    for cfg in configs:
        db.query(PaycheckBucket).filter(PaycheckBucket.config_id == cfg.id).delete()
        db.delete(cfg)

    db.query(Account).filter(Account.user_id == user_id).delete()
    db.query(Category).filter(Category.user_id == user_id).delete()
    db.delete(current_user)
    db.commit()

    return {"success": True, "message": "Akun dan seluruh data Anda berhasil dihapus secara permanen"}
