from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey, func, Boolean, false
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.user import User

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    name = Column(String(50), nullable=False, index=True)
    type = Column(String(30), nullable=False, default="operasional") # operasional, tagihan, gajian, tabungan, investasi, darurat, ewallet
    tag = Column(String(100), nullable=True) # e.g. "Saku Tambahan", "E-Wallet", dll
    color = Column(String(50), nullable=False, default="amberGold") # amberGold, cyanHub, purpleLock, mintRise, coralFall, blue
    is_archived = Column(Boolean, nullable=False, default=False, server_default=false())
    initial_balance = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    pockets = relationship("JagoPocket", back_populates="account", cascade="all, delete-orphan", lazy="selectin")
