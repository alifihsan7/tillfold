from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class InternalLoanCreate(BaseModel):
    source_account_id: int = Field(..., description="ID rekening pemberi pinjaman/talangan")
    source_pocket_id: Optional[int] = Field(None, description="ID kantong sumber (opsional)")
    target_account_id: int = Field(..., description="ID rekening peminjam")
    target_pocket_id: Optional[int] = Field(None, description="ID kantong tujuan (opsional)")
    amount: int = Field(..., gt=0, le=9_000_000_000_000_000, description="Nominal pinjaman")
    note: Optional[str] = Field(None, max_length=255, description="Keterangan pinjaman")


class InternalLoanSettleRequest(BaseModel):
    amount: Optional[int] = Field(None, gt=0, le=9_000_000_000_000_000, description="Nominal pelunasan (kosong/None = lunas penuh)")
    note: Optional[str] = Field(None, max_length=255, description="Keterangan pelunasan")


class InternalLoanResponse(BaseModel):
    id: int
    user_id: int
    source_account_id: int
    source_account_name: Optional[str] = None
    source_pocket_id: Optional[int] = None
    source_pocket_name: Optional[str] = None
    target_account_id: int
    target_account_name: Optional[str] = None
    target_pocket_id: Optional[int] = None
    target_pocket_name: Optional[str] = None
    amount: int
    remaining_amount: int
    status: str
    note: Optional[str] = None
    created_at: datetime
    settled_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InternalLoanListResponse(BaseModel):
    items: List[InternalLoanResponse]
    total: int
    total_active_loan_amount: int

    model_config = ConfigDict(from_attributes=True)


class InternalLoanSummaryResponse(BaseModel):
    total_active_loan_amount: int
    active_count: int
    items: List[InternalLoanResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
