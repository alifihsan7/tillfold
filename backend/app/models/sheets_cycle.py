from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, JSON, String

from app.db.session import Base


class SheetsCycle(Base):
    __tablename__ = "sheets_cycles"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    cycle_start = Column(Date, primary_key=True)
    cycle_end = Column(Date, nullable=False)
    closed_pockets = Column(JSON(none_as_null=True), nullable=True)
    spreadsheet_id = Column(String(255), nullable=True)
    sheet_id = Column(Integer, nullable=True)
    content_hash = Column(String(64), nullable=True)
    exported_closed = Column(Boolean, nullable=False, default=False)
