"""
Backward compatibility shim for legacy jago_pocket schema imports.
All domain schemas have been generalized into app.schemas.pocket.
"""
from app.schemas.pocket import (
    VALID_POCKET_ROLES,
    PocketBase,
    PocketCreate,
    PocketTargetUpdate,
    PocketUpdate,
    PocketsBatchUpdate,
    PocketMutationItemResponse,
    PocketItemResponse,
    PocketSubscriptionLink,
    PocketTransferRequest,
    PocketTransferResponse,
    PocketSummaryResponse,
    PocketResponse,
    JagoPocketBase,
    JagoPocketCreate,
    JagoPocketTargetUpdate,
    JagoPocketUpdate,
    JagoPocketsBatchUpdate,
    JagoPocketItemResponse,
    JagoPocketsSummaryResponse,
)

__all__ = [
    "VALID_POCKET_ROLES",
    "PocketBase",
    "PocketCreate",
    "PocketTargetUpdate",
    "PocketUpdate",
    "PocketsBatchUpdate",
    "PocketMutationItemResponse",
    "PocketItemResponse",
    "PocketSubscriptionLink",
    "PocketTransferRequest",
    "PocketTransferResponse",
    "PocketSummaryResponse",
    "PocketResponse",
    "JagoPocketBase",
    "JagoPocketCreate",
    "JagoPocketTargetUpdate",
    "JagoPocketUpdate",
    "JagoPocketsBatchUpdate",
    "JagoPocketItemResponse",
    "JagoPocketsSummaryResponse",
]
