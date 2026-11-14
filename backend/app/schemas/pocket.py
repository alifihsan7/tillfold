from typing import Optional, List, Any, Set
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator

VALID_POCKET_ROLES: Set[str] = {
    "operasional",
    "tagihan",
    "darurat",
    "tabungan",
    "investasi",
}


class PocketBase(BaseModel):
    name: str = Field(..., max_length=100)
    slug: Optional[str] = Field(default=None, max_length=50)
    account_id: Optional[int] = None
    role: str = Field(default="operasional", max_length=30)
    balance: int = Field(default=0, ge=0)
    target_amount: int = Field(default=0, ge=0)
    is_active: bool = True

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: Optional[str]) -> str:
        if not v:
            return "operasional"
        normalized = str(v).strip().lower()
        if normalized not in VALID_POCKET_ROLES:
            raise ValueError(f"Role kantong tidak valid. Pilihan: {', '.join(sorted(VALID_POCKET_ROLES))}")
        return normalized


class PocketCreate(BaseModel):
    account_id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=100)
    balance: Optional[int] = Field(default=None, ge=0)
    target_amount: int = Field(default=0, ge=0)
    role: str = Field(default="operasional", max_length=30)
    slug: Optional[str] = Field(default=None, max_length=50)
    is_active: bool = True

    @model_validator(mode="before")
    @classmethod
    def sync_create_amounts(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "balance" in data and data["balance"] is not None:
                if "target_amount" not in data or data["target_amount"] == 0:
                    data["target_amount"] = data["balance"]
            elif "target_amount" in data and ("balance" not in data or data["balance"] is None):
                data["balance"] = data["target_amount"]
        return data

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: Optional[str]) -> str:
        if not v:
            return "operasional"
        normalized = str(v).strip().lower()
        if normalized not in VALID_POCKET_ROLES:
            raise ValueError(f"Role kantong tidak valid. Pilihan: {', '.join(sorted(VALID_POCKET_ROLES))}")
        return normalized


class PocketTargetUpdate(BaseModel):
    id: Optional[int] = None
    slug: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    account_id: Optional[int] = None
    balance: Optional[int] = Field(None, ge=0)
    target_amount: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def sync_target_amount(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "target_amount" not in data or data["target_amount"] is None:
                if "balance" in data and data["balance"] is not None:
                    data["target_amount"] = data["balance"]
            elif "balance" not in data or data["balance"] is None:
                if "target_amount" in data and data["target_amount"] is not None:
                    data["balance"] = data["target_amount"]
        return data

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = str(v).strip().lower()
        if normalized not in VALID_POCKET_ROLES:
            raise ValueError(f"Role kantong tidak valid. Pilihan: {', '.join(sorted(VALID_POCKET_ROLES))}")
        return normalized


class PocketUpdate(BaseModel):
    name: Optional[str] = None
    balance: Optional[int] = Field(None, ge=0)
    target_amount: Optional[int] = Field(None, ge=0)
    role: Optional[str] = None
    account_id: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = str(v).strip().lower()
        if normalized not in VALID_POCKET_ROLES:
            raise ValueError(f"Role kantong tidak valid. Pilihan: {', '.join(sorted(VALID_POCKET_ROLES))}")
        return normalized


class PocketsBatchUpdate(BaseModel):
    pockets: Optional[List[PocketTargetUpdate]] = None


class PocketMutationItemResponse(BaseModel):
    id: int
    pocket_id: int
    pocket_name: Optional[str] = None
    counterpart_pocket_id: Optional[int] = None
    counterpart_pocket_name: Optional[str] = None
    transaction_id: Optional[int] = None
    mutation_type: str  # 'allocation_in', 'allocation_out', 'expense', 'income'
    amount: int
    balance_after: int
    description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PocketItemResponse(BaseModel):
    id: int
    user_id: int
    account_id: Optional[int] = None
    account_name: Optional[str] = None
    subscription_id: Optional[int] = None
    subscription_name: Optional[str] = None
    subscription_status: Optional[str] = None
    subscription_billing_cycle: Optional[str] = None
    name: str
    slug: str
    role: str = "operasional"
    balance: int = 0
    current_balance: int = 0
    target_amount: int = 0
    spent_amount: int = 0
    remaining_amount: int = 0
    percentage_spent: float = 0.0
    percentage: float = 0.0
    is_active: bool = True
    recent_mutations: List[PocketMutationItemResponse] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PocketSubscriptionLink(BaseModel):
    subscription_id: Optional[int] = Field(..., gt=0)


class PocketTransferRequest(BaseModel):
    account_id: Optional[int] = None
    from_pocket_id: Optional[int] = None
    from_pocket_slug: Optional[str] = None
    to_pocket_id: Optional[int] = None
    to_pocket_slug: Optional[str] = None
    amount: int = Field(..., gt=0, le=9_000_000_000_000_000)
    note: Optional[str] = Field(None, max_length=255)


class PocketTransferResponse(BaseModel):
    status: str = "success"
    account_id: Optional[int] = None
    from_pocket_id: int
    from_pocket_name: str
    from_pocket_balance: int
    to_pocket_id: int
    to_pocket_name: str
    to_pocket_balance: int
    amount: int
    note: Optional[str] = None
    created_at: datetime
    pockets: List[PocketItemResponse] = Field(default_factory=list)


class PocketSummaryResponse(BaseModel):
    account_id: Optional[int] = None
    account_name: Optional[str] = None
    total_balance: int = 0
    total_pocket_balance: int = 0
    total_jago_balance: int = 0
    total_target_amount: int = 0
    total_spent_amount: int = 0
    total_remaining_amount: int = 0
    cycle_start: Optional[date] = None
    cycle_end: Optional[date] = None
    pockets: List[PocketItemResponse] = Field(default_factory=list)
    items: List[PocketItemResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def sync_pocket_balances(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Harmonize total_balance, total_pocket_balance, total_jago_balance
            bal = data.get("total_pocket_balance")
            if bal is None:
                bal = data.get("total_balance")
            if bal is None:
                bal = data.get("total_jago_balance", 0)
            data["total_pocket_balance"] = bal
            data["total_balance"] = bal
            data["total_jago_balance"] = bal
        return data


# Backward compatibility aliases
JagoPocketBase = PocketBase
JagoPocketCreate = PocketCreate
JagoPocketTargetUpdate = PocketTargetUpdate
JagoPocketUpdate = PocketUpdate
JagoPocketsBatchUpdate = PocketsBatchUpdate
JagoPocketItemResponse = PocketItemResponse
JagoPocketsSummaryResponse = PocketSummaryResponse
PocketResponse = PocketItemResponse
