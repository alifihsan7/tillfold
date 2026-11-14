from typing import Optional
from sqlalchemy import Column, Integer, BigInteger, String, Text, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.user import User

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    type = Column(String(20), nullable=False, index=True)      # 'expense' or 'income'
    amount = Column(BigInteger, nullable=False)
    account = Column(String(50), nullable=False, index=True)   # 'BCA', 'GoPay', 'Cash', etc.
    category = Column(String(100), nullable=False, index=True) # 'Makanan & Minuman', etc.
    description = Column(String(255), nullable=False)
    raw_text = Column(Text, nullable=True)
    date = Column(Date, nullable=False, index=True)
    pocket_id = Column(Integer, ForeignKey("pockets.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    pocket = relationship("Pocket", foreign_keys=[pocket_id])

    @property
    def pocket_name(self) -> Optional[str]:
        return self.pocket.name if self.pocket else None
