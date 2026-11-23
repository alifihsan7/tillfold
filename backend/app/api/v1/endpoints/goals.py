from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import List, Optional
import math
import json
from datetime import date, datetime, timedelta
import zoneinfo

from app.db.session import get_db
from app.models.goal import Goal
from app.models.transaction import Transaction
from app.core.ledger import POSITIVE_TYPES, NEGATIVE_TYPES
from app.models.user import User
from app.models.paycheck import PaycheckConfig, PaycheckBucket, PaycheckReceipt
from app.models.account import Account
from app.api.deps import get_current_user
from app.schemas.goal import GoalCreate, GoalUpdate, GoalResponse

router = APIRouter()
WIB = zoneinfo.ZoneInfo("Asia/Jakarta")

def goal_cycle_allocation(db: Session, user_id: int, account_name: str | None) -> int | None:
    """Only forecast from an explicitly configured or recorded allocation."""
    if not account_name:
        return None
    account = db.query(Account).filter(Account.user_id == user_id, Account.name == account_name).first()
    if not account:
        return None
    cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == user_id).first()
    if cfg:
        bucket = db.query(PaycheckBucket).filter(
            PaycheckBucket.config_id == cfg.id, PaycheckBucket.account == account_name,
        ).first()
        if bucket and bucket.fixed_amount and bucket.fixed_amount > 0:
            return bucket.fixed_amount
    receipt = db.query(PaycheckReceipt).join(Transaction, Transaction.id == PaycheckReceipt.transaction_id).filter(
        PaycheckReceipt.user_id == user_id, Transaction.user_id == user_id,
    ).order_by(Transaction.date.desc(), Transaction.id.desc()).first()
    if receipt:
        return next((item["amount"] for item in json.loads(receipt.allocations_json)
                     if item["account_id"] == account.id and item["amount"] > 0), None)
    return None


def require_goal_account(db: Session, user_id: int, name: str | None):
    if name and not db.query(Account.id).filter(
        Account.user_id == user_id, Account.name == name.strip(), Account.is_archived.is_(False),
    ).first():
        raise HTTPException(400, "Pilih rekening aktif yang terdaftar untuk target.")


def get_account_balance(account_name: str, user_id: int, db: Session) -> int:
    val = db.query(
        func.coalesce(
            func.sum(
                case(
                    (Transaction.type.in_(POSITIVE_TYPES), Transaction.amount),
                    (Transaction.type.in_(NEGATIVE_TYPES), -Transaction.amount),
                    else_=0
                )
            ),
            0
        )
    ).filter(Transaction.user_id == user_id, func.lower(Transaction.account) == account_name.strip().lower()).scalar()
    return int(val or 0)

def compute_goal_metrics(goal: Goal, user_id: int, db: Session) -> dict:
    if goal.linked_account and goal.linked_account.strip():
        current_amount = get_account_balance(goal.linked_account, user_id, db)
    else:
        current_amount = int(goal.manual_current_amount or 0)

    target_amt = int(goal.target_amount) if goal.target_amount > 0 else 1
    pct = round((current_amount / target_amt * 100), 1)
    remaining = max(0, target_amt - current_amount)

    today = datetime.now(WIB).date()
    est_cycles = None
    est_months = None
    est_finish_date = None

    cycle_days = 14
    if remaining == 0:
        est_cycles = 0
        est_months = 0.0
        est_finish_date = today
    else:
        cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == user_id).first()
        cycle_days = cfg.cycle_days if (cfg and cfg.cycle_days and cfg.cycle_days > 0) else 14
        alloc = goal_cycle_allocation(db, user_id, goal.linked_account)
        if alloc:
            est_cycles = math.ceil(remaining / alloc)
            days = est_cycles * cycle_days
            try:
                est_finish_date = today + timedelta(days=days)
            except (OverflowError, ValueError):
                est_finish_date = None
            est_months = round(days / 30.417, 1)

    # Deadline check: flag goals whose estimate lands after the target date and
    # say how much each cycle must set aside to finish on time.
    is_behind_schedule = False
    required_per_cycle = None
    if remaining > 0 and goal.target_date:
        if goal.target_date <= today:
            is_behind_schedule = True
            required_per_cycle = remaining
        else:
            cycles_left = max(1, math.ceil((goal.target_date - today).days / cycle_days))
            required_per_cycle = math.ceil(remaining / cycles_left)
            is_behind_schedule = est_finish_date is not None and est_finish_date > goal.target_date

    return {
        "id": goal.id,
        "name": goal.name,
        "target_amount": goal.target_amount,
        "manual_current_amount": goal.manual_current_amount,
        "linked_account": goal.linked_account,
        "target_date": goal.target_date,
        "category": goal.category,
        "icon": goal.icon,
        "color": goal.color,
        "is_active": goal.is_active,
        "notes": goal.notes,
        "created_at": goal.created_at,
        "updated_at": goal.updated_at,
        "current_amount": current_amount,
        "percentage": pct,
        "remaining_amount": remaining,
        "estimated_cycles": est_cycles,
        "estimated_months": est_months,
        "estimated_finish_date": est_finish_date,
        "is_behind_schedule": is_behind_schedule,
        "required_per_cycle": required_per_cycle,
    }

@router.get("", response_model=List[GoalResponse])
def get_goals(
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Goal).filter(Goal.user_id == current_user.id)
    if active_only:
        query = query.filter(Goal.is_active == True)
    goals = query.order_by(Goal.id.asc()).all()
    return [compute_goal_metrics(g, current_user.id, db) for g in goals]

@router.post("", response_model=GoalResponse)
def create_goal(
    payload: GoalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    require_goal_account(db, current_user.id, payload.linked_account)
    goal = Goal(
        user_id=current_user.id,
        name=payload.name.strip(),
        target_amount=payload.target_amount,
        manual_current_amount=payload.manual_current_amount or 0,
        linked_account=payload.linked_account.strip() if payload.linked_account else None,
        target_date=payload.target_date,
        category=payload.category or "Tabungan",
        icon=payload.icon or "🎯",
        color=payload.color or "emerald",
        is_active=payload.is_active if payload.is_active is not None else True,
        notes=payload.notes
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return compute_goal_metrics(goal, current_user.id, db)

@router.put("/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: int,
    payload: GoalUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal tidak ditemukan")

    data = payload.model_dump(exclude_unset=True)
    if "linked_account" in data:
        require_goal_account(db, current_user.id, data["linked_account"])
    if any(data.get(field) is None for field in ("name", "target_amount", "manual_current_amount", "is_active") if field in data):
        raise HTTPException(422, "Nama, nominal, saldo manual, dan status target tidak boleh kosong.")
    for k, v in data.items():
        if k == "name" and v:
            setattr(goal, k, v.strip())
        elif k == "linked_account":
            setattr(goal, k, v.strip() if v else None)
        else:
            setattr(goal, k, v)

    db.commit()
    db.refresh(goal)
    return compute_goal_metrics(goal, current_user.id, db)

@router.delete("/{goal_id}")
def delete_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal tidak ditemukan")

    db.delete(goal)
    db.commit()
    return {"ok": True, "message": f"Goal '{goal.name}' berhasil dihapus"}
