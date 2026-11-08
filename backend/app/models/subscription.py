from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, Date, ForeignKey, UniqueConstraint, func
from app.db.session import Base
from app.models.user import User

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    name = Column(String(100), nullable=False)
    amount = Column(BigInteger, nullable=False)
    category = Column(String(50), nullable=False, default="Layanan Digital")
    account = Column(String(50), nullable=False, default="Jago")
    billing_cycle = Column(String(20), nullable=False, default="monthly") # 'monthly', 'yearly'
    billing_day = Column(Integer, nullable=False, default=1)              # 1-31
    billing_type = Column(String(20), nullable=False, default="fixed_day") # 'fixed_day', 'exact_date'
    exact_due_date = Column(Date, nullable=True)  # One-time expiry or annual billing anchor
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SubscriptionPayment(Base):
    __tablename__ = "subscription_payments"
    __table_args__ = (UniqueConstraint("subscription_id", "period_key"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, unique=True)
    subscription_name = Column(String(100), nullable=False)
    period_key = Column(String(30), nullable=False)
    due_date = Column(Date, nullable=False)
    paid_date = Column(Date, nullable=False)
    amount = Column(BigInteger, nullable=False)
    account = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
