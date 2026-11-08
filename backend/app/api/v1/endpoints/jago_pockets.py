import calendar
import re
import zoneinfo
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.account import Account
from app.models.jago_pocket import JagoPocket, Pocket
from app.models.paycheck import PaycheckConfig
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.core.ledger import POSITIVE_TYPES, NEGATIVE_TYPES
from app.models.user import User
from app.schemas.jago_pocket import (
    JagoPocketCreate,
    JagoPocketItemResponse,
    JagoPocketsBatchUpdate,
    JagoPocketsSummaryResponse,
    JagoPocketTargetUpdate,
    JagoPocketUpdate,
    VALID_POCKET_ROLES,
    PocketSubscriptionLink,
)

router = APIRouter()
WIB = zoneinfo.ZoneInfo(settings.TIMEZONE)

DEFAULT_POCKET_SPECS = [
    {
        "slug": "gym",
        "name": "GYM",
        "default_target": 225_000,
        "role": "tagihan",
    },
    {
        "slug": "claude",
        "name": "Subscription Claude",
        "default_target": 75_000,
        "role": "tagihan",
    },
    {
        "slug": "kuota",
        "name": "Kuota",
        "default_target": 50_000,
        "role": "tagihan",
    },
    {
        "slug": "visa",
        "name": "VISA",
        "default_target": 50_000,
        "role": "operasional",
    },
    {
        "slug": "utama",
        "name": "Kantong Utama",
        "default_target": 0,
        "role": "operasional",
    },
]


def get_current_cycle_bounds(db: Session, user_id: int, ref_date: Optional[date] = None) -> tuple[date, date]:
    """Deterministically determine the active financial cycle date range for user."""
    if ref_date is None:
        ref_date = datetime.now(WIB).date()

    from app.services.paycheck_cycles import recorded_cycle_ends

    cycle_ends = recorded_cycle_ends(db, user_id)
    cycle_start = max((day for day, end in cycle_ends.items() if day <= ref_date <= end), default=None)
    if cycle_start:
        return cycle_start, cycle_ends[cycle_start]

    cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == user_id).first()
    cycle_days = cfg.cycle_days if cfg and cfg.cycle_days and cfg.cycle_days > 0 else 30
    cycle_type = cfg.cycle_type if cfg and cfg.cycle_type else "monthly_date"
    anchor_start = cfg.cycle_start_date if cfg and cfg.cycle_start_date else None
    paycheck_day = cfg.paycheck_day if cfg and cfg.paycheck_day else (anchor_start.day if anchor_start else 25)

    if cycle_type == "monthly_date":
        from app.api.v1.endpoints.analytics import get_monthly_date_bounds

        return get_monthly_date_bounds(ref_date, paycheck_day)
    elif anchor_start:
        cycle_start = anchor_start
        cycle_end = cycle_start + timedelta(days=cycle_days - 1)
        while ref_date > cycle_end:
            cycle_start = cycle_end + timedelta(days=1)
            cycle_end = cycle_start + timedelta(days=cycle_days - 1)
        return cycle_start, cycle_end
    else:
        start_date = ref_date.replace(day=1)
        _, last_day = calendar.monthrange(ref_date.year, ref_date.month)
        end_date = ref_date.replace(day=last_day)
        return start_date, end_date




def get_target_pocket_account_names(db: Session, user_id: int) -> List[str]:
    """
    Dynamically resolves account names representing sub-pockets / billing pockets for user:
    - Accounts with type 'pocket'
    - Accounts whose name or tag contains 'kantong', 'jago', 'pocket', 'subs', 'tagihan'
    - Fallback to non-utama operational accounts
    - Always includes ['bank jago', 'jago'] for full backward compatibility.
    """
    matched: set[str] = set()
    user_accs = db.query(Account).filter(Account.user_id == user_id).all()

    for acc in user_accs:
        name_l = (acc.name or "").strip().lower()
        tag_l = (acc.tag or "").strip().lower()
        type_l = (acc.type or "").strip().lower()

        if (
            type_l in ["pocket", "tagihan"]
            or any(k in name_l for k in ["kantong", "jago", "pocket"])
            or any(k in tag_l for k in ["kantong", "jago", "pocket", "subs", "tagihan"])
        ):
            matched.add(name_l)

    if not matched and user_accs:
        cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == user_id).first()
        primary_spent_acc = (cfg.pocket_account.strip().lower() if cfg and cfg.pocket_account else "")
        primary_src_acc = (cfg.source_account.strip().lower() if cfg and cfg.source_account else "")

        for acc in user_accs:
            name_l = (acc.name or "").strip().lower()
            type_l = (acc.type or "").strip().lower()
            if type_l == "operasional":
                if (
                    name_l != primary_spent_acc
                    and name_l != primary_src_acc
                    and not any(u in name_l for u in ["utama", "main", "primary", "gaji", "income"])
                ):
                    matched.add(name_l)

    # Always ensure backward-compatible tokens
    matched.add("bank jago")
    matched.add("jago")
    return list(matched)


def ensure_default_pockets(db: Session, user_id: int, account_id: Optional[int] = None) -> List[JagoPocket]:
    """
    Idempotently seeds default pockets for user and links legacy pockets to parent account.
    - If account_id is None, seeds the 5 canonical Bank Jago pockets if none exist.
    - If account_id is provided, seeds canonical pockets if it's Jago, or 1 Kantong Utama for other accounts.
    - Automatically migrates existing pockets with account_id=None to user's active Jago/operational account.
    """
    # 1. Fallback migration: link orphan pockets with account_id=None
    orphans = db.query(JagoPocket).filter(JagoPocket.user_id == user_id, JagoPocket.account_id == None).all()
    if orphans:
        jago_acc = db.query(Account).filter(
            Account.user_id == user_id,
            func.lower(Account.name).like("%jago%")
        ).first()
        if not jago_acc:
            jago_acc = db.query(Account).filter(Account.user_id == user_id, Account.type == "operasional").first()
        if jago_acc:
            for p in orphans:
                p.account_id = jago_acc.id
            db.commit()

    # 2. If specific account requested
    if account_id is not None:
        target_acc = db.query(Account).filter(Account.id == account_id, Account.user_id == user_id).first()
        if not target_acc:
            return []

        existing = db.query(JagoPocket).filter(
            JagoPocket.user_id == user_id,
            JagoPocket.account_id == account_id,
        ).all()
        if existing:
            return existing

        is_jago = any(k in target_acc.name.lower() for k in ["jago", "pocket"])
        added = False
        if is_jago:
            for spec in DEFAULT_POCKET_SPECS:
                initial_target = spec["default_target"]
                new_pocket = JagoPocket(
                    user_id=user_id,
                    account_id=target_acc.id,
                    name=spec["name"],
                    slug=spec["slug"],
                    role=spec.get("role", "operasional"),
                    target_amount=initial_target,
                    is_active=True,
                )
                db.add(new_pocket)
                added = True
        else:
            # Seed default Kantong Utama for non-Jago accounts
            slug = f"utama-{target_acc.id}"
            new_pocket = JagoPocket(
                user_id=user_id,
                account_id=target_acc.id,
                name="Kantong Utama",
                slug=slug,
                role="operasional",
                target_amount=0,
                is_active=True,
            )
            db.add(new_pocket)
            added = True

        if added:
            db.commit()
        return db.query(JagoPocket).filter(JagoPocket.user_id == user_id, JagoPocket.account_id == account_id).all()

    # 3. Default / backward compatibility mode (no account_id specified)
    existing = db.query(JagoPocket).filter(JagoPocket.user_id == user_id).all()
    existing_map = {p.slug: p for p in existing}

    target_acc = db.query(Account).filter(
        Account.user_id == user_id,
        func.lower(Account.name).like("%jago%")
    ).first()
    if not target_acc:
        target_acc = db.query(Account).filter(Account.user_id == user_id, Account.type == "operasional").first()
    default_acc_id = target_acc.id if target_acc else None

    added = False
    for spec in DEFAULT_POCKET_SPECS:
        slug = spec["slug"]
        if slug not in existing_map:
            initial_target = spec["default_target"]

            new_pocket = JagoPocket(
                user_id=user_id,
                account_id=default_acc_id,
                name=spec["name"],
                slug=slug,
                role=spec.get("role", "operasional"),
                target_amount=initial_target,
                is_active=True,
            )
            db.add(new_pocket)
            existing_map[slug] = new_pocket
            added = True

    if added:
        db.commit()

    return list(existing_map.values())


def _get_ledger_balance(db: Session, user_id: int, account_names: List[str]) -> Optional[int]:
    tx_balance = db.query(
        func.sum(
            case(
                (Transaction.type.in_(POSITIVE_TYPES), Transaction.amount),
                (Transaction.type.in_(NEGATIVE_TYPES), -Transaction.amount),
                else_=0,
            ),
        )
    ).filter(
        Transaction.user_id == user_id,
        func.lower(Transaction.account).in_(account_names),
    ).scalar()
    return int(tx_balance) if tx_balance is not None else None


def get_jago_account_balance(db: Session, user_id: int) -> int:
    """Calculates all-time ledger balance for pocket / Bank Jago accounts."""
    pocket_names = get_target_pocket_account_names(db, user_id)
    balance = _get_ledger_balance(db, user_id, pocket_names)
    if balance is not None:
        return balance
    pocket_acc = db.query(Account).filter(
        Account.user_id == user_id,
        func.lower(Account.name).in_(pocket_names),
    ).first()
    return max(0, int(pocket_acc.initial_balance)) if pocket_acc else 0


get_pocket_account_balance = get_jago_account_balance


def classify_jago_transaction(tx: Transaction) -> str:
    """
    Auto-deduction classifier mapping Bank Jago expense transactions into pocket slugs:
    1. GYM: 'Gym & Fitness' category or keyword 'gym' / 'fitness'
    2. Subscription Claude: 'Claude' / 'AI' category or keywords
    3. Kuota: 'Kuota' / 'Pulsa' category or keywords
    4. VISA: 'VISA' / 'Online debit' category or keywords
    5. Kantong Utama: default fallback for general operational expenses
    """
    desc = (tx.description or "").lower()
    cat = (tx.category or "").lower()
    combined = f"{cat} {desc}"

    # 1. GYM: 'Gym & Fitness' or keyword 'gym' / 'fitness'
    if (
        "gym" in cat
        or "fitness" in cat
        or re.search(r"\b(?:gym|fitness|fithub|fit hub|megafit|workout|membership gym)\b", combined)
    ):
        return "gym"

    # 2. Subscription Claude: 'Claude' / 'AI'
    if (
        "claude" in combined
        or "anthropic" in combined
        or re.search(r"\b(?:claude|anthropic)\b", combined)
        or (re.search(r"\bai\b", combined) and any(w in combined for w in ["subs", "langganan", "chatgpt", "openai", "copilot", "perplexity", "midjourney", "token", "api", "software", "digital", "claude"]))
        or ("ai" in cat.split())
    ):
        return "claude"

    # 3. Kuota: Kuota / Pulsa
    if (
        any(k in cat for k in ["kuota", "pulsa", "paket data", "internet", "telekomunikasi"])
        or any(k in desc for k in ["kuota", "pulsa", "paket data", "paket internet", "by.u", "byu", "telkomsel", "indosat", "tri", "three", "xl axiata", "smartfren"])
    ):
        return "kuota"

    # 4. VISA: VISA / Online debit
    if (
        "visa" in combined
        or "online debit" in combined
        or "debit online" in combined
        or re.search(r"\b(?:visa|vcc|online debit|debit online|card debit)\b", combined)
    ):
        return "visa"

    # 5. Default fallback: Kantong Utama
    return "utama"


classify_pocket_transaction = classify_jago_transaction


def classify_pocket_transaction_for_account(tx: Transaction, pockets: List[JagoPocket], payment_pockets=None) -> str:
    """Classifies an expense transaction to the most appropriate pocket slug for a parent account."""
    if not pockets:
        return "utama"
    if payment_pockets and tx.id in payment_pockets:
        return payment_pockets[tx.id]

    p_slugs = {p.slug: p for p in pockets}
    if "gym" in p_slugs or "claude" in p_slugs:
        return classify_jago_transaction(tx)

    desc = (tx.description or "").lower()
    cat = (tx.category or "").lower()
    combined = f"{cat} {desc}"

    # 1. Match by pocket name or slug keyword
    for p in pockets:
        p_name_clean = (p.name or "").strip().lower()
        if p_name_clean and p_name_clean != "kantong utama" and p_name_clean in combined:
            return p.slug
        p_slug_clean = (p.slug or "").strip().lower()
        if p_slug_clean and not p_slug_clean.startswith("utama") and p_slug_clean in combined:
            return p.slug

    # 2. Match by role (e.g. tagihan category)
    if any(k in combined for k in ["tagihan", "subs", "langganan", "cicilan", "listrik", "air", "wifi", "internet"]):
        tagihan_p = next((p for p in pockets if p.role == "tagihan"), None)
        if tagihan_p:
            return tagihan_p.slug

    # 3. Fallback to Utama or first operasional pocket
    main_pocket = next((p for p in pockets if p.slug.startswith("utama")), None)
    fallback_p = main_pocket or next((p for p in pockets if p.role == "operasional"), pockets[0])
    return fallback_p.slug


def compute_pockets_summary(
    db: Session,
    user_id: int,
    account_id: Optional[int] = None,
    cycle_start: Optional[date] = None,
    cycle_end: Optional[date] = None,
) -> JagoPocketsSummaryResponse:
    """Computes comprehensive summary, auto-deduction metrics, and balance for pockets of an account."""
    ensure_default_pockets(db, user_id, account_id=account_id)

    if not cycle_start or not cycle_end:
        calc_start, calc_end = get_current_cycle_bounds(db, user_id)
        cycle_start = cycle_start or calc_start
        cycle_end = cycle_end or calc_end

    acc: Optional[Account] = None
    target_account_names: List[str] = []
    ordered_pockets: List[JagoPocket] = []

    if account_id is not None:
        acc = db.query(Account).filter(
            Account.id == account_id,
            Account.user_id == user_id,
        ).first()
        if not acc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rekening dengan id {account_id} tidak ditemukan",
            )
        target_account_names = [acc.name.lower()]
        ordered_pockets = db.query(JagoPocket).filter(
            JagoPocket.user_id == user_id,
            JagoPocket.account_id == acc.id,
            JagoPocket.is_active == True,
        ).order_by(JagoPocket.id.asc()).all()
    else:
        # Backward compatibility mode
        target_account_names = get_target_pocket_account_names(db, user_id)
        acc = db.query(Account).filter(
            Account.user_id == user_id,
            func.lower(Account.name).in_(target_account_names),
        ).first()
        if not acc:
            acc = db.query(Account).filter(Account.user_id == user_id).first()

        slug_order = ["gym", "claude", "kuota", "visa", "utama"]
        all_pockets = db.query(JagoPocket).filter(
            JagoPocket.user_id == user_id,
            JagoPocket.is_active == True,
        ).all()
        pocket_map = {p.slug: p for p in all_pockets}
        for s in slug_order:
            if s in pocket_map:
                ordered_pockets.append(pocket_map[s])
        for p in all_pockets:
            if p.slug not in slug_order and p not in ordered_pockets:
                ordered_pockets.append(p)

    total_balance = _get_ledger_balance(db, user_id, target_account_names)
    if total_balance is None:
        total_balance = max(0, int(acc.initial_balance)) if acc else 0

    expenses = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.type == "expense",
        func.lower(Transaction.account).in_(target_account_names),
        Transaction.date >= cycle_start,
        Transaction.date <= cycle_end,
    ).all()

    spent_by_slug: dict[str, int] = defaultdict(int)
    from app.services.subscription_payments import payment_pocket_slugs
    payment_pockets = payment_pocket_slugs(db, user_id, ordered_pockets)
    for tx in expenses:
        slug = classify_pocket_transaction_for_account(tx, ordered_pockets, payment_pockets)
        spent_by_slug[slug] += int(tx.amount)

    linked_ids = [p.subscription_id for p in ordered_pockets if p.subscription_id]
    linked_subscriptions = {sub.id: sub for sub in db.query(Subscription).filter(
        Subscription.user_id == user_id, Subscription.id.in_(linked_ids),
    ).all()} if linked_ids else {}
    account_names = {account.id: account.name.strip().casefold() for account in db.query(Account).filter(Account.user_id == user_id).all()}
    targets = {}
    link_states = {}
    for pocket in ordered_pockets:
        target = int(pocket.target_amount)
        if pocket.subscription_id:
            sub = linked_subscriptions.get(pocket.subscription_id)
            state = "missing" if not sub else "inactive" if not sub.is_active else "active"
            if sub and sub.account.strip().casefold() != account_names.get(pocket.account_id):
                state = "account_mismatch"
            target = int(sub.amount) if state == "active" else 0
            link_states[pocket.id] = state
        targets[pocket.id] = target
    sum_other_targets = sum(targets[p.id] for p in ordered_pockets if not p.slug.startswith("utama"))
    # The ledger already subtracts expenses. Add back the ones deducted from pocket targets below.
    allocated_spending = sum(spent_by_slug.get(p.slug, 0) for p in ordered_pockets)

    items: List[JagoPocketItemResponse] = []
    total_target = 0
    total_spent = 0

    for p in ordered_pockets:
        target = targets[p.id]
        if p.slug.startswith("utama") and target == 0 and not p.subscription_id:
            target = max(0, total_balance + allocated_spending - sum_other_targets)

        spent = spent_by_slug.get(p.slug, 0)
        remaining = target - spent
        pct = round((spent / target * 100), 1) if target > 0 else 0.0

        p_acc = db.query(Account).filter(Account.id == p.account_id).first() if p.account_id else acc

        item = JagoPocketItemResponse(
            id=p.id,
            user_id=p.user_id,
            account_id=p.account_id or (acc.id if acc else None),
            account_name=p_acc.name if p_acc else None,
            subscription_id=p.subscription_id,
            subscription_name=linked_subscriptions[p.subscription_id].name if p.subscription_id in linked_subscriptions else None,
            subscription_status=link_states.get(p.id),
            subscription_billing_cycle=linked_subscriptions[p.subscription_id].billing_cycle if p.subscription_id in linked_subscriptions else None,
            name=p.name,
            slug=p.slug,
            role=p.role,
            target_amount=target,
            spent_amount=spent,
            remaining_amount=remaining,
            percentage_spent=pct,
            percentage=pct,
            is_active=p.is_active,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        items.append(item)
        total_target += target
        total_spent += spent

    total_remaining = total_target - total_spent

    return JagoPocketsSummaryResponse(
        account_id=acc.id if acc else None,
        account_name=acc.name if acc else None,
        total_jago_balance=total_balance,
        total_pocket_balance=total_balance,
        total_target_amount=total_target,
        total_spent_amount=total_spent,
        total_remaining_amount=total_remaining,
        cycle_start=cycle_start,
        cycle_end=cycle_end,
        pockets=items,
        items=items,
    )


def compute_jago_pockets_summary(
    db: Session,
    user_id: int,
    cycle_start: Optional[date] = None,
    cycle_end: Optional[date] = None,
) -> JagoPocketsSummaryResponse:
    """Backward compatible helper for Jago pockets summary."""
    return compute_pockets_summary(
        db=db,
        user_id=user_id,
        account_id=None,
        cycle_start=cycle_start,
        cycle_end=cycle_end,
    )


def normalize_update_payload(payload: Any) -> List[Dict[str, Any]]:
    """Normalizes heterogeneous batch update payloads into list of update dicts."""
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    elif isinstance(payload, dict):
        if "pockets" in payload and isinstance(payload["pockets"], list):
            return [p for p in payload["pockets"] if isinstance(p, dict)]
        if "slug" in payload or "id" in payload:
            return [payload]
        results = []
        for k, v in payload.items():
            if isinstance(v, (int, float)):
                results.append({"slug": str(k), "target_amount": int(v)})
            elif isinstance(v, dict):
                entry = dict(v)
                entry.setdefault("slug", str(k))
                results.append(entry)
        return results
    return []


@router.get("", response_model=JagoPocketsSummaryResponse)
def get_pockets(
    account_id: Optional[int] = Query(None, description="Filter pockets berdasarkan Rekening Induk (account_id)"),
    cycle_start: Optional[date] = None,
    cycle_end: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get summary of virtual pockets with real-time auto-deductions,
    target allocations, remaining balances, and total ledger balance.
    Can be filtered by account_id for universal multi-account pockets.
    """
    return compute_pockets_summary(
        db=db,
        user_id=current_user.id,
        account_id=account_id,
        cycle_start=cycle_start,
        cycle_end=cycle_end,
    )


@router.post("", response_model=JagoPocketItemResponse, status_code=status.HTTP_201_CREATED)
def create_pocket(
    payload: JagoPocketCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new universal virtual pocket associated with a parent account.
    Accepts account_id, name, target_amount, role (operasional, tagihan, darurat, tabungan, investasi).
    """
    name_clean = payload.name.strip()
    if not name_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nama kantong tidak boleh kosong",
        )

    # Resolve parent account
    acc = None
    if payload.account_id is not None:
        acc = db.query(Account).filter(
            Account.id == payload.account_id,
            Account.user_id == current_user.id,
            Account.is_archived == False,
        ).first()
        if not acc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rekening dengan id {payload.account_id} tidak ditemukan",
            )
    else:
        # Default fallback to operational or first account
        acc = db.query(Account).filter(
            Account.user_id == current_user.id,
            Account.is_archived == False,
            Account.type == "operasional",
        ).first()
        if not acc:
            acc = db.query(Account).filter(Account.user_id == current_user.id, Account.is_archived == False).first()

    # Generate or sanitize slug
    slug = payload.slug.strip().lower() if payload.slug else None
    if not slug:
        base_slug = re.sub(r"[^a-z0-9]+", "-", name_clean.lower()).strip("-") or "pocket"
        slug = base_slug
        idx = 1
        while db.query(JagoPocket).filter(JagoPocket.user_id == current_user.id, JagoPocket.slug == slug).first():
            if acc and idx == 1:
                slug = f"{base_slug}-{acc.id}"
            else:
                slug = f"{base_slug}-{idx}"
            idx += 1
    else:
        existing = db.query(JagoPocket).filter(
            JagoPocket.user_id == current_user.id,
            JagoPocket.slug == slug,
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Kantong dengan slug '{slug}' sudah terdaftar",
            )

    new_pocket = JagoPocket(
        user_id=current_user.id,
        account_id=acc.id if acc else None,
        name=name_clean,
        slug=slug,
        role=payload.role,
        target_amount=payload.target_amount,
        is_active=payload.is_active,
    )
    db.add(new_pocket)
    db.commit()
    db.refresh(new_pocket)

    return JagoPocketItemResponse(
        id=new_pocket.id,
        user_id=new_pocket.user_id,
        account_id=new_pocket.account_id,
        account_name=acc.name if acc else None,
        name=new_pocket.name,
        slug=new_pocket.slug,
        role=new_pocket.role,
        target_amount=new_pocket.target_amount,
        spent_amount=0,
        remaining_amount=new_pocket.target_amount,
        percentage_spent=0.0,
        percentage=0.0,
        is_active=new_pocket.is_active,
        created_at=new_pocket.created_at,
        updated_at=new_pocket.updated_at,
    )


@router.put("", response_model=JagoPocketsSummaryResponse)
def update_pockets_batch(
    payload: Any = Body(...),
    account_id: Optional[int] = Query(None, description="Optional account_id filter for summary"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update target allocations manually for pockets in batch.
    Accepts batch list, wrapper object `{"pockets": [...]}`, or slug-target dictionary.
    """
    ensure_default_pockets(db, current_user.id, account_id=account_id)
    updates = normalize_update_payload(payload)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format payload update tidak valid",
        )

    for item in updates:
        slug = item.get("slug")
        pocket_id = item.get("id")
        name = item.get("name")
        role = item.get("role")
        target_amount = item.get("target_amount")
        is_active = item.get("is_active")
        item_acc_id = item.get("account_id")

        pocket = None
        if pocket_id:
            pocket = db.query(JagoPocket).filter(
                JagoPocket.id == pocket_id,
                JagoPocket.user_id == current_user.id,
            ).first()
        elif slug:
            pocket = db.query(JagoPocket).filter(
                func.lower(JagoPocket.slug) == slug.strip().lower(),
                JagoPocket.user_id == current_user.id,
            ).first()
        elif name:
            pocket = db.query(JagoPocket).filter(
                func.lower(JagoPocket.name) == name.strip().lower(),
                JagoPocket.user_id == current_user.id,
            ).first()

        if pocket:
            if target_amount is not None and not pocket.subscription_id:
                pocket.target_amount = max(0, int(target_amount))
            if role is not None and role in VALID_POCKET_ROLES:
                pocket.role = role
            if is_active is not None:
                pocket.is_active = bool(is_active)
            if item_acc_id is not None:
                if pocket.subscription_id and item_acc_id != pocket.account_id:
                    raise HTTPException(status_code=409, detail="Lepaskan hubungan tagihan sebelum memindahkan kantong")
                acc_exists = db.query(Account).filter(Account.id == item_acc_id, Account.user_id == current_user.id, Account.is_archived == False).first()
                if acc_exists:
                    pocket.account_id = item_acc_id

    db.commit()

    return compute_pockets_summary(
        db=db,
        user_id=current_user.id,
        account_id=account_id,
    )


@router.post("/sync-commitments", response_model=JagoPocketsSummaryResponse)
def sync_commitments_from_subscriptions(
    account_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compatibility endpoint: only explicit links affect effective targets."""
    return compute_pockets_summary(db=db, user_id=current_user.id, account_id=account_id)


@router.put("/{pocket_id}/subscription", response_model=JagoPocketsSummaryResponse)
def link_pocket_subscription(
    pocket_id: int,
    payload: PocketSubscriptionLink,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pocket = db.query(JagoPocket).filter(JagoPocket.id == pocket_id, JagoPocket.user_id == current_user.id).first()
    if not pocket:
        raise HTTPException(status_code=404, detail="Kantong tidak ditemukan")
    account = db.query(Account).filter(Account.id == pocket.account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=400, detail="Kantong harus memiliki rekening induk")
    if payload.subscription_id is not None:
        sub = db.query(Subscription).filter(Subscription.id == payload.subscription_id, Subscription.user_id == current_user.id).first()
        if not sub:
            raise HTTPException(status_code=404, detail="Tagihan tidak ditemukan")
        if not sub.is_active:
            raise HTTPException(status_code=400, detail="Pilih tagihan yang masih aktif")
        if sub.account.strip().casefold() != account.name.strip().casefold():
            raise HTTPException(status_code=400, detail="Tagihan harus berasal dari rekening induk yang sama")
        existing = db.query(JagoPocket).filter(JagoPocket.user_id == current_user.id, JagoPocket.subscription_id == sub.id, JagoPocket.id != pocket.id).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Tagihan sudah terhubung ke kantong {existing.name}")
        pocket.subscription_id = sub.id
        pocket.target_amount = int(sub.amount)
    else:
        sub = db.query(Subscription).filter(Subscription.id == pocket.subscription_id, Subscription.user_id == current_user.id).first() if pocket.subscription_id else None
        if sub:
            pocket.target_amount = int(sub.amount) if sub.is_active else 0
        pocket.subscription_id = None
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tagihan sudah terhubung ke kantong lain")
    return compute_pockets_summary(db=db, user_id=current_user.id, account_id=account.id)


@router.get("/{pocket_id_or_slug}", response_model=JagoPocketItemResponse)
def get_single_pocket(
    pocket_id_or_slug: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve details and metrics for an individual virtual pocket by ID or Slug."""
    pocket = None
    if pocket_id_or_slug.isdigit():
        pocket = db.query(JagoPocket).filter(
            JagoPocket.id == int(pocket_id_or_slug),
            JagoPocket.user_id == current_user.id,
        ).first()
    if not pocket:
        pocket = db.query(JagoPocket).filter(
            func.lower(JagoPocket.slug) == pocket_id_or_slug.strip().lower(),
            JagoPocket.user_id == current_user.id,
        ).first()

    if not pocket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kantong '{pocket_id_or_slug}' tidak ditemukan",
        )

    summary = compute_pockets_summary(db=db, user_id=current_user.id, account_id=pocket.account_id)
    pocket_item = next((p for p in summary.pockets if p.id == pocket.id or p.slug == pocket.slug), None)
    if not pocket_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kantong '{pocket_id_or_slug}' tidak ditemukan",
        )
    return pocket_item


@router.put("/{pocket_id_or_slug}", response_model=JagoPocketItemResponse)
def update_single_pocket(
    pocket_id_or_slug: str,
    payload: JagoPocketUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update target amount, name, role, account_id, or status for a single pocket."""
    pocket = None
    if pocket_id_or_slug.isdigit():
        pocket = db.query(JagoPocket).filter(
            JagoPocket.id == int(pocket_id_or_slug),
            JagoPocket.user_id == current_user.id,
        ).first()
    if not pocket:
        pocket = db.query(JagoPocket).filter(
            func.lower(JagoPocket.slug) == pocket_id_or_slug.strip().lower(),
            JagoPocket.user_id == current_user.id,
        ).first()

    if not pocket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kantong '{pocket_id_or_slug}' tidak ditemukan",
        )

    if payload.target_amount is not None and not pocket.subscription_id:
        pocket.target_amount = max(0, int(payload.target_amount))
    if payload.name is not None and payload.name.strip():
        pocket.name = payload.name.strip()
    if payload.role is not None:
        pocket.role = payload.role
    if payload.account_id is not None:
        if pocket.subscription_id and payload.account_id != pocket.account_id:
            raise HTTPException(status_code=409, detail="Lepaskan hubungan tagihan sebelum memindahkan kantong")
        acc = db.query(Account).filter(Account.id == payload.account_id, Account.user_id == current_user.id, Account.is_archived == False).first()
        if not acc:
            raise HTTPException(status_code=404, detail="Rekening tidak ditemukan")
        pocket.account_id = payload.account_id
    if payload.is_active is not None:
        pocket.is_active = bool(payload.is_active)

    db.commit()
    db.refresh(pocket)

    summary = compute_pockets_summary(db=db, user_id=current_user.id, account_id=pocket.account_id)
    pocket_item = next((p for p in summary.pockets if p.id == pocket.id or p.slug == pocket.slug), None)
    return pocket_item


@router.delete("/{pocket_id_or_slug}")
def delete_single_pocket(
    pocket_id_or_slug: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an individual virtual pocket by ID or Slug."""
    pocket = None
    if pocket_id_or_slug.isdigit():
        pocket = db.query(JagoPocket).filter(
            JagoPocket.id == int(pocket_id_or_slug),
            JagoPocket.user_id == current_user.id,
        ).first()
    if not pocket:
        pocket = db.query(JagoPocket).filter(
            func.lower(JagoPocket.slug) == pocket_id_or_slug.strip().lower(),
            JagoPocket.user_id == current_user.id,
        ).first()

    if not pocket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kantong '{pocket_id_or_slug}' tidak ditemukan",
        )

    pocket_name = pocket.name
    pocket_id = pocket.id
    db.delete(pocket)
    db.commit()

    return {
        "ok": True,
        "message": f"Kantong '{pocket_name}' berhasil dihapus",
        "id": pocket_id,
    }
