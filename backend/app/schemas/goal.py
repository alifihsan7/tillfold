from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime

class GoalBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    target_amount: int = Field(gt=0, le=9_000_000_000_000_000)
    manual_current_amount: Optional[int] = Field(default=0, ge=0, le=9_000_000_000_000_000)
    linked_account: Optional[str] = None
    target_date: Optional[date] = None
    category: Optional[str] = "Tabungan"
    icon: Optional[str] = "🎯"
    color: Optional[str] = "emerald"
    is_active: Optional[bool] = True
    notes: Optional[str] = None

class GoalCreate(GoalBase):
    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("Nama target wajib diisi.")
        return value.strip()


class GoalUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    target_amount: Optional[int] = Field(default=None, gt=0, le=9_000_000_000_000_000)
    manual_current_amount: Optional[int] = Field(default=None, ge=0, le=9_000_000_000_000_000)
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
