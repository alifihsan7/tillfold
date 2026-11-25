from datetime import datetime, timedelta, timezone
from typing import Optional, Union
import base64
import hashlib
import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings

def _get_fernet_key() -> bytes:
    key_src = (
        getattr(settings, "BOT_TOKEN_ENCRYPTION_KEY", None)
        or getattr(settings, "JWT_SECRET_KEY", None)
        or "ai7-finance-symmetric-fallback-key-2026"
    )
    digest = hashlib.sha256(key_src.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)

def get_fernet() -> Fernet:
    return Fernet(_get_fernet_key())

def encrypt_token(plain_token: Optional[str]) -> Optional[str]:
    if not plain_token or not isinstance(plain_token, str):
        return plain_token
    # Backward/idempotency check: if token is already validly encrypted under current key, keep as is
    try:
        fernet = get_fernet()
        fernet.decrypt(plain_token.encode("utf-8"))
        return plain_token
    except Exception:
        pass
    fernet = get_fernet()
    return fernet.encrypt(plain_token.encode("utf-8")).decode("utf-8")

def decrypt_token(encrypted_token: Optional[str]) -> Optional[str]:
    if not encrypted_token or not isinstance(encrypted_token, str):
        return encrypted_token
    try:
        fernet = get_fernet()
        decrypted = fernet.decrypt(encrypted_token.encode("utf-8"))
        return decrypted.decode("utf-8")
    except (InvalidToken, Exception):
        # Graceful fallback: return original token if legacy plaintext or invalid
        return encrypted_token

def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def create_access_token(subject: Union[str, int], expires_delta: Optional[timedelta] = None, *, session_version: int = 0, auth_method: str = "password", auth_time: Optional[int] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": str(subject),
        "ver": session_version,
        "amr": auth_method,
        "auth_time": auth_time if auth_time is not None else (int(datetime.now(timezone.utc).timestamp()) if auth_method == "password" else None),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    encoded_jwt = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        decoded = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return decoded
    except (jwt.PyJWTError, Exception):
        return None


def create_local_job_token(db, user_id: int) -> str:
    """Trusted local jobs must follow the account's current session version too."""
    from app.models.user import User
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise ValueError("Akun pengingat tidak tersedia atau dinonaktifkan.")
    return create_access_token(user.id, session_version=user.session_version, auth_method="service")
