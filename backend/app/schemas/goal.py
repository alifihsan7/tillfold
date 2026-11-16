from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

class GoalBase(BaseModel):
    name: str
    target_amount: int
    manual_current_amount: Optional[int] = 0
    linked_account: Optional[str] = None
    target_date: Optional[date] = None
    category: Optional[str] = "Tabungan"
    icon: Optional[str] = "🎯"
    color: Optional[str] = "emerald"
    is_active: Optional[bool] = True
    notes: Optional[str] = None

class GoalCreate(GoalBase):
    pass

class GoalUpdate(BaseModel):
    name: Optional[str] = None
    target_amount: Optional[int] = None
    manual_current_amount: Optional[int] = None
    linked_account: Optional[str] = None
    target_date: Optional[date] = None
    category: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

class GoalResponse(GoalBase):
    id: int
    current_amount: int
    percentage: float
    remaining_amount: int
    estimated_cycles: Optional[int] = None
    estimated_months: Optional[float] = None
    estimated_finish_date: Optional[date] = None
    is_behind_schedule: bool = False
    required_per_cycle: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
