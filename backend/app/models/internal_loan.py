from typing import Optional
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.session import Base


class InternalLoan(Base):
    __tablename__ = "internal_loans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    source_pocket_id = Column(Integer, ForeignKey("pockets.id", ondelete="SET NULL"), nullable=True, index=True)
    target_account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    target_pocket_id = Column(Integer, ForeignKey("pockets.id", ondelete="SET NULL"), nullable=True, index=True)
    amount = Column(BigInteger, nullable=False)
    remaining_amount = Column(BigInteger, nullable=False)
    status = Column(String(30), nullable=False, default="active", index=True)  # 'active', 'settled', 'cancelled'
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    settled_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
    source_account = relationship("Account", foreign_keys=[source_account_id])
    source_pocket = relationship("Pocket", foreign_keys=[source_pocket_id])
    target_account = relationship("Account", foreign_keys=[target_account_id])
    target_pocket = relationship("Pocket", foreign_keys=[target_pocket_id])

    @property
    def source_account_name(self) -> Optional[str]:
        return self.source_account.name if self.source_account else None

    @property
    def target_account_name(self) -> Optional[str]:
        return self.target_account.name if self.target_account else None

    @property
    def source_pocket_name(self) -> Optional[str]:
        return self.source_pocket.name if self.source_pocket else None

    @property
    def target_pocket_name(self) -> Optional[str]:
        return self.target_pocket.name if self.target_pocket else None
