from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, Field

class SubscriptionBase(BaseModel):
    name: str
    amount: int = Field(gt=0)
    category: str = "Layanan Digital"
    account: str = ""
    billing_cycle: str = "monthly"
    billing_day: Optional[int] = Field(1, ge=1, le=31)
    billing_type: str = "fixed_day"
    exact_due_date: Optional[date] = None
    is_active: bool = True
    notes: Optional[str] = None

class SubscriptionCreate(SubscriptionBase):
    pass

class SubscriptionUpdate(BaseModel):
    name: Optional[str] = None
    amount: Optional[int] = Field(None, gt=0)
    category: Optional[str] = None
    account: Optional[str] = None
    billing_cycle: Optional[str] = None
    billing_day: Optional[int] = Field(None, ge=1, le=31)
    billing_type: Optional[str] = None
    exact_due_date: Optional[date] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

class SubscriptionResponse(SubscriptionBase):
    id: int
    created_at: datetime
    days_until_due: Optional[int] = None
    next_billing_date: Optional[str] = None
    payment_period: Optional[str] = None
    payment_due_date: Optional[date] = None
    is_paid: bool = False
    paid_date: Optional[date] = None
    payment_transaction_id: Optional[int] = None
    paid_amount: Optional[int] = None

    class Config:
        from_attributes = True

class SubscriptionsSummary(BaseModel):
    total_monthly_commitment: int
    active_count: int
    upcoming_this_week: int
    items: List[SubscriptionResponse]
