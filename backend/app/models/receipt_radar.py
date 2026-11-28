from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func

from app.db.session import Base


class ReceiptRadarAddress(Base):
    __tablename__ = "receipt_radar_addresses"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    alias = Column(String(32), nullable=False, unique=True)
    verification_code = Column(String(12))
    verification_url = Column(String(1024))
    verification_at = Column(DateTime(timezone=True))


class ReceiptRadarDraft(Base):
    __tablename__ = "receipt_radar_drafts"
    __table_args__ = (UniqueConstraint("user_id", "fingerprint", name="uq_receipt_radar_draft_owner"),)

    id = Column(String(32), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    fingerprint = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    source = Column(String(16), nullable=False, default="forwarding")
    notified_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ReceiptGmailConnection(Base):
    __tablename__ = "receipt_gmail_connections"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    email = Column(String(254), nullable=False, unique=True)
    refresh_token = Column(String(4096), nullable=False)
    generation = Column(String(32), nullable=False)
    connected_at = Column(DateTime(timezone=True), nullable=False)
    checked_through = Column(DateTime(timezone=True), nullable=False)
    next_check_at = Column(DateTime(timezone=True), nullable=False, index=True)
    last_checked_at = Column(DateTime(timezone=True))
    status = Column(String(16), nullable=False, default="connected")


class ReceiptGmailConsent(Base):
    __tablename__ = "receipt_gmail_consent"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    state_digest = Column(String(64), nullable=False, unique=True)
    verifier = Column(String(96), nullable=False)
    session_version = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True))
