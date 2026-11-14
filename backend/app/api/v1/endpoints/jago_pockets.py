"""
Backward compatibility shim for legacy jago_pockets endpoint module.
All pocket logic and routes have been generalized into app.api.v1.endpoints.pockets.
"""
from app.api.v1.endpoints.pockets import (
    router,
    DEFAULT_POCKET_SPECS,
    get_current_cycle_bounds,
    get_target_pocket_account_names,
    ensure_default_pockets,
    get_pocket_account_balance,
    get_jago_account_balance,
    classify_pocket_transaction,
    classify_jago_transaction,
    classify_pocket_transaction_for_account,
    compute_pockets_summary,
    compute_jago_pockets_summary,
    normalize_update_payload,
)

__all__ = [
    "router",
    "DEFAULT_POCKET_SPECS",
    "get_current_cycle_bounds",
    "get_target_pocket_account_names",
    "ensure_default_pockets",
    "get_pocket_account_balance",
    "get_jago_account_balance",
    "classify_pocket_transaction",
    "classify_jago_transaction",
    "classify_pocket_transaction_for_account",
    "compute_pockets_summary",
    "compute_jago_pockets_summary",
    "normalize_update_payload",
]
