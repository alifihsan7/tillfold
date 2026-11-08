from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal
from datetime import date as dt_date, datetime
from uuid import UUID

class PaycheckConfigOut(BaseModel):
    id: int
    source_account: str
    use_gate: bool
    gate_name: str
    cycle_type: str = "biweekly"
    cycle_days: int = 14
    paycheck_day: Optional[int] = 25
    cycle_start_date: Optional[dt_date] = None
    pocket_account: str = "Mandiri"
    is_active: bool

    class Config:
        from_attributes = True

class PaycheckConfigUpdate(BaseModel):
    source_account: str
    use_gate: bool
    gate_name: str
    cycle_type: str = "biweekly"
    cycle_days: int = 14
    paycheck_day: Optional[int] = 25
    cycle_start_date: Optional[dt_date] = None
    pocket_account: str = "Mandiri"

class PaycheckBucketBase(BaseModel):
    account: str
    percentage: float = Field(ge=0, le=100, allow_inf_nan=False)
    fixed_amount: Optional[int] = None
    via_gate: bool = False
    via_secondary: Optional[str] = None
    purpose: str
    sort_order: int = 0

class PaycheckBucketOut(PaycheckBucketBase):
    id: int

    class Config:
        from_attributes = True

class PaycheckStep(BaseModel):
    id: str
    phase: int
    app: str
    title: str
    badge: Optional[str] = None
    description: str
    source_account: str
    target_account: str
    amount: int
    is_done: bool = False
    is_auto: bool = False
    creates_income: bool = True
    transaction_id: Optional[int] = None

class PaycheckSessionOut(BaseModel):
    id: int
    total_amount: int
    date: dt_date
    status: str
    note: Optional[str] = None
    steps: List[PaycheckStep]
    completed_steps: int
    total_steps: int
    progress_percentage: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PaycheckStartRequest(BaseModel):
    total_amount: int = 1500000
    date: Optional[dt_date] = None
    note: Optional[str] = "Alokasi Gajian Siklus"
    allocations: Optional[Dict[str, int]] = None  # Custom adjusted amounts: {"Mandiri": 825000, ...}
    cycle_type: Optional[Literal["weekly", "biweekly", "monthly", "custom"]] = None
    cycle_days: Optional[int] = Field(default=None, ge=1, le=365)
    save_cycle_default: bool = False


class PaycheckRecordRequest(BaseModel):
    request_key: UUID
    total_amount: int = Field(gt=0, le=9_000_000_000_000_000)
    account: str
    date: dt_date
    start_cycle: bool = True
    cycle_type: Optional[Literal["weekly", "biweekly", "monthly", "custom"]] = None
    cycle_days: Optional[int] = Field(default=None, ge=1, le=365)
    save_cycle_default: bool = False


class ReceiptAllocation(BaseModel):
    account_id: int = Field(gt=0)
    amount: int = Field(ge=0, le=9_000_000_000_000_000)
    transfer_id: Optional[int] = None


class ReceiptAllocationsUpdate(BaseModel):
    allocations: List[ReceiptAllocation] = Field(max_length=100)
    expected_allocations: List[ReceiptAllocation] = Field(max_length=100)
