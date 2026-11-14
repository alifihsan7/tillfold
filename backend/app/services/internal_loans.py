import zoneinfo
from datetime import datetime
from typing import List, Optional, Tuple
from fastapi import HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ledger import POSITIVE_TYPES, NEGATIVE_TYPES
from app.models.account import Account
from app.models.pocket import Pocket, PocketMutation
from app.models.transaction import Transaction
from app.models.internal_loan import InternalLoan
from app.models.user import User
from app.schemas.internal_loan import InternalLoanCreate, InternalLoanSettleRequest

WIB = zoneinfo.ZoneInfo(settings.TIMEZONE)


def get_account_balance(db: Session, user_id: int, account_name: str) -> int:
    """Calculates real-time ledger balance for an account."""
    val = db.query(
        func.sum(
            case(
                (Transaction.type.in_(POSITIVE_TYPES), Transaction.amount),
                (Transaction.type.in_(NEGATIVE_TYPES), -Transaction.amount),
                else_=0,
            )
        )
    ).filter(
        Transaction.user_id == user_id,
        func.lower(Transaction.account) == account_name.strip().lower(),
    ).scalar()

    if val is not None:
        return int(val)

    acc = db.query(Account).filter(
        Account.user_id == user_id,
        func.lower(Account.name) == account_name.strip().lower(),
    ).first()
    return int(acc.initial_balance or 0) if acc else 0


def get_pocket_balance(db: Session, user_id: int, pocket: Pocket) -> int:
    """Calculates real-time balance for a pocket."""
    from app.api.v1.endpoints.pockets import compute_pockets_summary
    summary = compute_pockets_summary(db, user_id, account_id=pocket.account_id)
    item = next((p for p in summary.pockets if p.id == pocket.id), None)
    return int(item.balance if item else pocket.balance)


def get_active_internal_loans(db: Session, user_id: int) -> List[InternalLoan]:
    """Retrieves all active internal loans with outstanding balance."""
    return db.query(InternalLoan).filter(
        InternalLoan.user_id == user_id,
        InternalLoan.status == "active",
        InternalLoan.remaining_amount > 0,
    ).order_by(InternalLoan.created_at.desc(), InternalLoan.id.desc()).all()


def get_total_active_loan_amount(db: Session, user_id: int) -> int:
    """Sum of all active remaining loan balances for a user."""
    val = db.query(
        func.coalesce(func.sum(InternalLoan.remaining_amount), 0)
    ).filter(
        InternalLoan.user_id == user_id,
        InternalLoan.status == "active",
    ).scalar()
    return int(val or 0)


def get_internal_loans_summary(db: Session, user_id: int) -> dict:
    """Returns summary dictionary of active loans for analytics and paycheck."""
    loans = get_active_internal_loans(db, user_id)
    total_active = sum(l.remaining_amount for l in loans)
    return {
        "total_active_loan_amount": total_active,
        "active_count": len(loans),
        "loans": loans,
    }


def list_internal_loans(
    db: Session,
    user_id: int,
    status: Optional[str] = "all",
    limit: int = 50,
    skip: int = 0,
) -> Tuple[List[InternalLoan], int, int]:
    """Lists loans with deterministic pagination and total active amount summary."""
    query = db.query(InternalLoan).filter(InternalLoan.user_id == user_id)
    if status and status.strip().lower() != "all":
        query = query.filter(InternalLoan.status == status.strip().lower())

    total_count = query.count()
    items = query.order_by(InternalLoan.created_at.desc(), InternalLoan.id.desc()).offset(skip).limit(limit).all()

    total_active = get_total_active_loan_amount(db, user_id)
    return items, total_count, total_active


def get_internal_loan_by_id(db: Session, user_id: int, loan_id: int) -> Optional[InternalLoan]:
    """Retrieves single internal loan ensuring strict tenant isolation."""
    return db.query(InternalLoan).filter(
        InternalLoan.id == loan_id,
        InternalLoan.user_id == user_id,
    ).first()


def create_internal_loan(
    db: Session,
    current_user: User,
    payload: InternalLoanCreate,
) -> InternalLoan:
    """
    Creates an internal loan and executes an atomic double-entry ledger transfer.
    Net worth of the user remains invariant.
    """
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Nominal pinjaman harus lebih besar dari 0")

    # 1. Validate accounts
    source_acc = db.query(Account).filter(
        Account.id == payload.source_account_id,
        Account.user_id == current_user.id,
    ).first()
    if not source_acc:
        raise HTTPException(status_code=404, detail=f"Rekening sumber dengan id {payload.source_account_id} tidak ditemukan")
    if source_acc.is_archived:
        raise HTTPException(status_code=400, detail=f"Rekening sumber '{source_acc.name}' sedang diarsipkan")

    target_acc = db.query(Account).filter(
        Account.id == payload.target_account_id,
        Account.user_id == current_user.id,
    ).first()
    if not target_acc:
        raise HTTPException(status_code=404, detail=f"Rekening tujuan dengan id {payload.target_account_id} tidak ditemukan")
    if target_acc.is_archived:
        raise HTTPException(status_code=400, detail=f"Rekening tujuan '{target_acc.name}' sedang diarsipkan")

    # 2. Distinctness check
    if payload.source_account_id == payload.target_account_id:
        if not payload.source_pocket_id or not payload.target_pocket_id:
            raise HTTPException(status_code=400, detail="Rekening asal dan tujuan tidak boleh sama kecuali antar sub-kantong berbeda")
        if payload.source_pocket_id == payload.target_pocket_id:
            raise HTTPException(status_code=400, detail="Kantong asal dan tujuan tidak boleh sama")

    # 3. Validate pockets if provided
    source_pocket = None
    if payload.source_pocket_id:
        source_pocket = db.query(Pocket).filter(
            Pocket.id == payload.source_pocket_id,
            Pocket.user_id == current_user.id,
        ).first()
        if not source_pocket or not source_pocket.is_active:
            raise HTTPException(status_code=404, detail=f"Kantong sumber dengan id {payload.source_pocket_id} tidak ditemukan atau tidak aktif")
        if source_pocket.account_id and source_pocket.account_id != source_acc.id:
            raise HTTPException(status_code=400, detail=f"Kantong sumber '{source_pocket.name}' tidak terdaftar pada rekening '{source_acc.name}'")

    target_pocket = None
    if payload.target_pocket_id:
        target_pocket = db.query(Pocket).filter(
            Pocket.id == payload.target_pocket_id,
            Pocket.user_id == current_user.id,
        ).first()
        if not target_pocket or not target_pocket.is_active:
            raise HTTPException(status_code=404, detail=f"Kantong tujuan dengan id {payload.target_pocket_id} tidak ditemukan atau tidak aktif")
        if target_pocket.account_id and target_pocket.account_id != target_acc.id:
            raise HTTPException(status_code=400, detail=f"Kantong tujuan '{target_pocket.name}' tidak terdaftar pada rekening '{target_acc.name}'")

    # 4. Check source balance
    if source_pocket:
        pocket_bal = get_pocket_balance(db, current_user.id, source_pocket)
        if pocket_bal < payload.amount:
            raise HTTPException(
                status_code=400,
                detail=f"Saldo kantong sumber '{source_pocket.name}' tidak mencukupi (Tersedia: Rp{pocket_bal:,}, Dibutuhkan: Rp{payload.amount:,})".replace(",", ".")
            )

    source_acc_bal = get_account_balance(db, current_user.id, source_acc.name)
    if source_acc_bal < payload.amount:
        raise HTTPException(
            status_code=400,
            detail=f"Saldo rekening sumber '{source_acc.name}' tidak mencukupi (Tersedia: Rp{source_acc_bal:,}, Dibutuhkan: Rp{payload.amount:,})".replace(",", ".")
        )

    # 5. Atomic execution: ledger transactions & internal loan record
    now_wib = datetime.now(WIB)
    tx_date = now_wib.date()

    tx_out = Transaction(
        user_id=current_user.id,
        type="transfer_out",
        amount=payload.amount,
        account=source_acc.name,
        category="Transfer",
        description=f"Talangan ke {target_acc.name}: {payload.note or 'Dana Talangan Internal'}",
        raw_text=f"transfer out (internal loan): {source_acc.name} -> {target_acc.name}",
        date=tx_date,
        pocket_id=source_pocket.id if source_pocket else None,
    )
    tx_in = Transaction(
        user_id=current_user.id,
        type="transfer_in",
        amount=payload.amount,
        account=target_acc.name,
        category="Transfer",
        description=f"Talangan dari {source_acc.name}: {payload.note or 'Dana Talangan Internal'}",
        raw_text=f"transfer in (internal loan): {source_acc.name} -> {target_acc.name}",
        date=tx_date,
        pocket_id=target_pocket.id if target_pocket else None,
    )
    db.add(tx_out)
    db.add(tx_in)
    db.flush()

    loan = InternalLoan(
        user_id=current_user.id,
        source_account_id=source_acc.id,
        source_pocket_id=source_pocket.id if source_pocket else None,
        target_account_id=target_acc.id,
        target_pocket_id=target_pocket.id if target_pocket else None,
        amount=payload.amount,
        remaining_amount=payload.amount,
        status="active",
        note=payload.note,
        created_at=now_wib,
        settled_at=None,
    )
    db.add(loan)
    db.flush()

    # Link both ledger entries explicitly
    tx_out.raw_text = f"{tx_out.raw_text} [pair_id:{tx_in.id}] [internal_loan_id:{loan.id}]"
    tx_in.raw_text = f"{tx_in.raw_text} [pair_id:{tx_out.id}] [internal_loan_id:{loan.id}]"

    # Adjust pocket target/balance & log pocket mutations if pockets involved
    if source_pocket:
        source_pocket.balance = max(0, source_pocket.balance - payload.amount)
        if not source_pocket.slug.startswith("utama"):
            source_pocket.target_amount = max(0, source_pocket.target_amount - payload.amount)
        db.add(PocketMutation(
            user_id=current_user.id,
            account_id=source_acc.id,
            pocket_id=source_pocket.id,
            counterpart_pocket_id=target_pocket.id if target_pocket else None,
            transaction_id=tx_out.id,
            mutation_type="allocation_out",
            amount=payload.amount,
            balance_after=source_pocket.balance,
            description=payload.note or f"Talangan ke {target_acc.name}",
        ))

    if target_pocket:
        target_pocket.balance = target_pocket.balance + payload.amount
        if not target_pocket.slug.startswith("utama"):
            target_pocket.target_amount = target_pocket.target_amount + payload.amount
        db.add(PocketMutation(
            user_id=current_user.id,
            account_id=target_acc.id,
            pocket_id=target_pocket.id,
            counterpart_pocket_id=source_pocket.id if source_pocket else None,
            transaction_id=tx_in.id,
            mutation_type="allocation_in",
            amount=payload.amount,
            balance_after=target_pocket.balance,
            description=payload.note or f"Talangan dari {source_acc.name}",
        ))

    db.commit()
    db.refresh(loan)
    return loan


def settle_internal_loan(
    db: Session,
    current_user: User,
    loan_id: int,
    payload: InternalLoanSettleRequest,
) -> InternalLoan:
    """
    Settles an active internal loan (partially or fully).
    Debtor (target) transfers funds back to creditor (source).
    """
    loan = db.query(InternalLoan).filter(
        InternalLoan.id == loan_id,
        InternalLoan.user_id == current_user.id,
    ).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Pinjaman internal tidak ditemukan")
    if loan.status != "active":
        raise HTTPException(status_code=400, detail=f"Pinjaman tidak dapat dilunasi karena berstatus '{loan.status}'")

    if payload.amount is not None:
        if payload.amount <= 0:
            raise HTTPException(status_code=400, detail="Nominal pelunasan harus lebih besar dari 0")
        settle_amount = min(payload.amount, loan.remaining_amount)
    else:
        settle_amount = loan.remaining_amount

    if settle_amount <= 0:
        raise HTTPException(status_code=400, detail="Pinjaman sudah tidak memiliki saldo terutang")

    target_acc = db.query(Account).filter(Account.id == loan.target_account_id, Account.user_id == current_user.id).first()
    source_acc = db.query(Account).filter(Account.id == loan.source_account_id, Account.user_id == current_user.id).first()
    if not target_acc or not source_acc:
        raise HTTPException(status_code=404, detail="Rekening terkait pinjaman tidak ditemukan")

    # Check debtor pocket balance if pocket was used
    target_pocket = None
    if loan.target_pocket_id:
        target_pocket = db.query(Pocket).filter(Pocket.id == loan.target_pocket_id, Pocket.user_id == current_user.id).first()
        if target_pocket:
            pocket_bal = get_pocket_balance(db, current_user.id, target_pocket)
            if pocket_bal < settle_amount:
                raise HTTPException(
                    status_code=400,
                    detail=f"Saldo kantong peminjam '{target_pocket.name}' tidak mencukupi untuk pelunasan (Tersedia: Rp{pocket_bal:,}, Dibutuhkan: Rp{settle_amount:,})".replace(",", ".")
                )

    # Check debtor account balance
    target_bal = get_account_balance(db, current_user.id, target_acc.name)
    if target_bal < settle_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Saldo rekening peminjam '{target_acc.name}' tidak mencukupi untuk pelunasan (Tersedia: Rp{target_bal:,}, Dibutuhkan: Rp{settle_amount:,})".replace(",", ".")
        )

    now_wib = datetime.now(WIB)
    tx_date = now_wib.date()

    desc_note = payload.note or f"Pelunasan pinjaman #{loan.id}"
    tx_out = Transaction(
        user_id=current_user.id,
        type="transfer_out",
        amount=settle_amount,
        account=target_acc.name,
        category="Transfer",
        description=f"Pelunasan Talangan ke {source_acc.name}: {desc_note}",
        raw_text=f"transfer out (pelunasan loan #{loan.id}): {target_acc.name} -> {source_acc.name}",
        date=tx_date,
        pocket_id=loan.target_pocket_id,
    )
    tx_in = Transaction(
        user_id=current_user.id,
        type="transfer_in",
        amount=settle_amount,
        account=source_acc.name,
        category="Transfer",
        description=f"Pelunasan Talangan dari {target_acc.name}: {desc_note}",
        raw_text=f"transfer in (pelunasan loan #{loan.id}): {target_acc.name} -> {source_acc.name}",
        date=tx_date,
        pocket_id=loan.source_pocket_id,
    )
    db.add(tx_out)
    db.add(tx_in)
    db.flush()

    tx_out.raw_text = f"{tx_out.raw_text} [pair_id:{tx_in.id}] [internal_loan_settle_id:{loan.id}]"
    tx_in.raw_text = f"{tx_in.raw_text} [pair_id:{tx_out.id}] [internal_loan_settle_id:{loan.id}]"

    source_pocket = None
    if loan.source_pocket_id:
        source_pocket = db.query(Pocket).filter(Pocket.id == loan.source_pocket_id, Pocket.user_id == current_user.id).first()

    if target_pocket:
        target_pocket.balance = max(0, target_pocket.balance - settle_amount)
        if not target_pocket.slug.startswith("utama"):
            target_pocket.target_amount = max(0, target_pocket.target_amount - settle_amount)
        db.add(PocketMutation(
            user_id=current_user.id,
            account_id=target_acc.id,
            pocket_id=target_pocket.id,
            counterpart_pocket_id=loan.source_pocket_id,
            transaction_id=tx_out.id,
            mutation_type="allocation_out",
            amount=settle_amount,
            balance_after=target_pocket.balance,
            description=payload.note or f"Pelunasan talangan ke {source_acc.name}",
        ))

    if source_pocket:
        source_pocket.balance = source_pocket.balance + settle_amount
        if not source_pocket.slug.startswith("utama"):
            source_pocket.target_amount = source_pocket.target_amount + settle_amount
        db.add(PocketMutation(
            user_id=current_user.id,
            account_id=source_acc.id,
            pocket_id=source_pocket.id,
            counterpart_pocket_id=loan.target_pocket_id,
            transaction_id=tx_in.id,
            mutation_type="allocation_in",
            amount=settle_amount,
            balance_after=source_pocket.balance,
            description=payload.note or f"Pelunasan talangan dari {target_acc.name}",
        ))

    loan.remaining_amount = max(0, loan.remaining_amount - settle_amount)
    if loan.remaining_amount == 0:
        loan.status = "settled"
        loan.settled_at = now_wib

    db.commit()
    db.refresh(loan)
    return loan


def cancel_internal_loan(db: Session, current_user: User, loan_id: int) -> InternalLoan:
    """
    Cancels an active internal loan without reversing past cash transfers
    (used to revoke or invalidate mistaken loan records).
    """
    loan = db.query(InternalLoan).filter(
        InternalLoan.id == loan_id,
        InternalLoan.user_id == current_user.id,
    ).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Pinjaman internal tidak ditemukan")
    if loan.status == "settled":
        raise HTTPException(status_code=400, detail="Pinjaman yang sudah lunas tidak dapat dibatalkan")
    if loan.status == "cancelled":
        raise HTTPException(status_code=400, detail="Pinjaman sudah dibatalkan sebelumnya")

    loan.status = "cancelled"
    db.commit()
    db.refresh(loan)
    return loan


def auto_settle_internal_loans_for_account(
    db: Session,
    current_user: User,
    target_account_id: int,
    available_amount: Optional[int] = None,
    note: Optional[str] = "Auto-settlement gajian",
) -> List[InternalLoan]:
    """
    Auto-settles active internal loans where target_account_id owes money,
    ordered from oldest loan to newest, up to available_amount.
    """
    loans = db.query(InternalLoan).filter(
        InternalLoan.user_id == current_user.id,
        InternalLoan.target_account_id == target_account_id,
        InternalLoan.status == "active",
        InternalLoan.remaining_amount > 0,
    ).order_by(InternalLoan.created_at.asc(), InternalLoan.id.asc()).all()

    settled_loans = []
    budget = available_amount

    for loan in loans:
        if budget is not None and budget <= 0:
            break
        to_pay = loan.remaining_amount if budget is None else min(loan.remaining_amount, budget)
        settled = settle_internal_loan(
            db=db,
            current_user=current_user,
            loan_id=loan.id,
            payload=InternalLoanSettleRequest(amount=to_pay, note=note),
        )
        settled_loans.append(settled)
        if budget is not None:
            budget -= to_pay

    return settled_loans
