from typing import Optional, Set, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

SUPPORTED_ACCOUNT_TYPES: Set[str] = {
    "operasional",
    "tagihan",
    "gajian",
    "tabungan",
    "investasi",
    "darurat",
    "ewallet",
}

PROTECTED_ACCOUNT_TYPES: Set[str] = {
    "tagihan",
    "tabungan",
    "investasi",
    "darurat",
}


class PocketBreakdownItem(BaseModel):
    id: int
    name: str
    slug: str
    role: str = "operasional"
    balance: int = 0
    current_balance: int = 0
    target_amount: int = 0
    spent_amount: int = 0
    remaining_amount: int = 0
    percentage_spent: float = 0.0
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class AccountBase(BaseModel):
    name: str
    type: str = "operasional"
    tag: Optional[str] = None
    color: str = "amberGold"
    initial_balance: int = 0

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: Optional[str]) -> str:
        if not v:
            return "operasional"
        return str(v).strip().lower()


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    tag: Optional[str] = None
    color: Optional[str] = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return str(v).strip().lower()


class AccountResponse(AccountBase):
    is_archived: bool = False
    id: int
    current_balance: int = 0
    created_at: datetime
    pockets: List[PocketBreakdownItem] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
