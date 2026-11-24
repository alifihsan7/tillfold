from typing import Optional, List, Literal
from datetime import datetime, date
from pydantic import BaseModel, Field, field_validator, model_validator

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: str

def clean_email(value):
    if value is None:
        return None
    return str(value).strip().lower() or None


def validate_password(value):
    if value is not None and len(value.encode("utf-8")) > 72:
        raise ValueError("Password maksimal 72 byte.")
    return value


class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: str
    password: str = Field(..., min_length=8, description="Password minimal 8 karakter")

    _email = field_validator("email", mode="before")(clean_email)
    _password = field_validator("password")(validate_password)

class UserLogin(BaseModel):
    username_or_email: str
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8)
    google_spreadsheet_id: Optional[str] = None
    google_sheet_url: Optional[str] = None

    _email = field_validator("email", mode="before")(clean_email)
    _password = field_validator("password")(validate_password)

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
    current_password: Optional[str] = None

class TelegramWebAppAuthRequest(BaseModel):
    init_data: str

class OnboardingAccountItem(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    type: Literal["operasional", "tagihan", "gajian", "tabungan", "investasi", "darurat", "ewallet"] = "operasional"
    tag: Optional[str] = Field(default=None, max_length=100)
    color: str = Field(default="amberGold", max_length=50)
    initial_balance: int = Field(default=0, ge=0, le=9_000_000_000_000_000)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class OnboardingBucketItem(BaseModel):
    account: str = Field(min_length=1, max_length=50)
    percentage: float = Field(ge=0, le=100, allow_inf_nan=False)
    via_gate: bool = False
    via_secondary: Optional[str] = Field(default=None, max_length=50)
    purpose: str = Field(min_length=1, max_length=100)


class OnboardingRequest(BaseModel):
    initial_accounts: List[OnboardingAccountItem] = Field(min_length=1, max_length=100)
    cycle_type: Literal["weekly", "biweekly", "monthly", "monthly_date", "custom"] = "biweekly"
    cycle_days: int = Field(default=14, ge=1, le=365)
    paycheck_day: Optional[int] = Field(default=25, ge=1, le=31)
    cycle_start_date: Optional[date] = None
    source_account: str = Field(default="BCA", min_length=1, max_length=50)
    use_gate: bool = True
    gate_name: Optional[str] = Field(default="Perantara transfer", max_length=50)
    pocket_account: str = Field(default="BCA", min_length=1, max_length=50)
    buckets: List[OnboardingBucketItem] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def valid_allocation(self):
        names = [account.name for account in self.initial_accounts]
        if len({name.casefold() for name in names}) != len(names):
            raise ValueError("Nama rekening tidak boleh duplikat.")
        if self.source_account not in names or self.pocket_account not in names:
            raise ValueError("Pilih rekening sumber dan rekening belanja dari daftar rekening awal.")
        bucket_names = [bucket.account for bucket in self.buckets]
        if len(set(bucket_names)) != len(bucket_names):
            raise ValueError("Alokasi rekening tidak boleh duplikat.")
        if any(name not in names for name in bucket_names):
            raise ValueError("Rekening alokasi tidak tersedia.")
        if any(bucket.via_secondary and bucket.via_secondary not in names for bucket in self.buckets):
            raise ValueError("Rekening perantara alokasi tidak tersedia.")
        if abs(sum(bucket.percentage for bucket in self.buckets) - 100) > 0.001:
            raise ValueError("Total alokasi harus 100%.")
        if self.use_gate and not (self.gate_name or "").strip():
            raise ValueError("Nama rekening perantara wajib diisi.")
        return self
