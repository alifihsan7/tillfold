from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, EmailStr, Field

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: str

class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: str
    password: str = Field(..., min_length=8, description="Password minimal 8 karakter")

class UserLogin(BaseModel):
    username_or_email: str
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    google_spreadsheet_id: Optional[str] = None
    google_sheet_url: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    full_name: str
    telegram_chat_id: Optional[int] = None
    telegram_bot_username: Optional[str] = None
    telegram_mode: Optional[str] = "shared"
    google_spreadsheet_id: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    is_onboarded: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class GoogleAuthRequest(BaseModel):
    credential: str

class TelegramWebAppAuthRequest(BaseModel):
    init_data: str

class OnboardingAccountItem(BaseModel):
    name: str
    type: str = "operasional" # operasional, tabungan, investasi, darurat
    tag: Optional[str] = None
    color: str = "amberGold"
    initial_balance: int = 0

class OnboardingBucketItem(BaseModel):
    account: str
    percentage: float
    via_gate: bool = False
    via_secondary: Optional[str] = None
    purpose: str

class OnboardingRequest(BaseModel):
    initial_accounts: List[OnboardingAccountItem]
    cycle_type: str = "biweekly"
    cycle_days: int = 14
    paycheck_day: Optional[int] = 25
    cycle_start_date: Optional[date] = None
    source_account: str = "BCA"
    use_gate: bool = True
    gate_name: Optional[str] = "Perantara transfer"
    pocket_account: str = "BCA"
    buckets: List[OnboardingBucketItem]
