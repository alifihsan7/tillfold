from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, ForeignKey
from sqlalchemy.sql import func
from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=True, index=True)
    full_name = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    telegram_chat_id = Column(BigInteger, unique=True, nullable=True, index=True)
    telegram_bot_token = Column(String(500), nullable=True)
    telegram_bot_username = Column(String(100), nullable=True)
    telegram_webhook_secret = Column(String(64), unique=True, nullable=True, index=True)
    telegram_mode = Column(String(20), default="shared", nullable=False)
    google_id = Column(String(100), unique=True, nullable=True, index=True)
    google_spreadsheet_id = Column(String(255), nullable=True)
    avatar_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_onboarded = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    @property
    def decrypted_bot_token(self) -> Optional[str]:
        from app.core.security import decrypt_token
        return decrypt_token(self.telegram_bot_token)


class TelegramLink(Base):
    __tablename__ = "telegram_links"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    token_hash = Column(String(64), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)


class TelegramProcessedMessage(Base):
    __tablename__ = "telegram_processed_messages"

    chat_id = Column(BigInteger, primary_key=True)
    message_id = Column(BigInteger, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
