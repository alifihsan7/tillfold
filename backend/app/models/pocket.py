from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Index, func
from sqlalchemy.orm import relationship
from app.db.session import Base


class Pocket(Base):
    __tablename__ = "pockets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="RESTRICT"), nullable=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), nullable=False, index=True)
    role = Column(String(30), nullable=False, default="operasional")  # operasional, tagihan, darurat, tabungan, investasi
    balance = Column(BigInteger, nullable=False, default=0)
    target_amount = Column(BigInteger, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    account = relationship("Account", back_populates="pockets")
    mutations = relationship(
        "PocketMutation",
        foreign_keys="PocketMutation.pocket_id",
        back_populates="pocket",
        cascade="all, delete-orphan",
        order_by="desc(PocketMutation.id)",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "slug", name="uq_pockets_user_slug"),
        Index("uq_pocket_subscription", "user_id", "subscription_id", unique=True),
    )


class PocketMutation(Base):
    __tablename__ = "pocket_mutations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    pocket_id = Column(Integer, ForeignKey("pockets.id", ondelete="CASCADE"), nullable=False, index=True)
    counterpart_pocket_id = Column(Integer, ForeignKey("pockets.id", ondelete="SET NULL"), nullable=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
    mutation_type = Column(String(30), nullable=False)  # 'allocation_in', 'allocation_out', 'expense', 'income'
    amount = Column(BigInteger, nullable=False)
    balance_after = Column(BigInteger, nullable=False, default=0)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    pocket = relationship("Pocket", foreign_keys=[pocket_id], back_populates="mutations")
    counterpart_pocket = relationship("Pocket", foreign_keys=[counterpart_pocket_id])
    transaction = relationship("Transaction")


# Backward compatibility alias
JagoPocket = Pocket
