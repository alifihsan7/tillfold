from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.internal_loan import (
    InternalLoanCreate,
    InternalLoanResponse,
    InternalLoanListResponse,
    InternalLoanSettleRequest,
)
from app.services.internal_loans import (
    create_internal_loan,
    settle_internal_loan,
    cancel_internal_loan,
    list_internal_loans,
    get_internal_loan_by_id,
)

router = APIRouter()


@router.post("", response_model=InternalLoanResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=InternalLoanResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_loan(
    payload: InternalLoanCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mencatat pinjaman internal baru dan memicu mutasi ledger transfer kas secara atomik.
    """
    return create_internal_loan(db=db, current_user=current_user, payload=payload)


@router.get("", response_model=InternalLoanListResponse)
@router.get("/", response_model=InternalLoanListResponse, include_in_schema=False)
def get_loans(
    status: Optional[str] = Query("all", description="active | settled | cancelled | all"),
    limit: int = Query(50, ge=1, le=500),
    skip: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mengambil daftar pinjaman internal dengan filter status dan ringkasan total outstanding aktif.
    """
    items, total, total_active = list_internal_loans(
        db=db,
        user_id=current_user.id,
        status=status,
        limit=limit,
        skip=skip,
    )
    return InternalLoanListResponse(
        items=[InternalLoanResponse.model_validate(x) for x in items],
        total=total,
        total_active_loan_amount=total_active,
    )


@router.get("/{loan_id}", response_model=InternalLoanResponse)
def get_loan(
    loan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mengambil detail satu pinjaman internal berdasarkan ID.
    """
    loan = get_internal_loan_by_id(db=db, user_id=current_user.id, loan_id=loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Pinjaman internal tidak ditemukan")
    return loan


@router.post("/{loan_id}/settle", response_model=InternalLoanResponse)
def settle_loan(
    loan_id: int,
    payload: Optional[InternalLoanSettleRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Melunasi pinjaman internal (parsial atau penuh) dan memicu mutasi transfer balik di ledger secara atomik.
    """
    request_payload = payload or InternalLoanSettleRequest(amount=None, note=None)
    return settle_internal_loan(
        db=db,
        current_user=current_user,
        loan_id=loan_id,
        payload=request_payload,
    )


@router.delete("/{loan_id}", response_model=InternalLoanResponse)
@router.post("/{loan_id}/cancel", response_model=InternalLoanResponse)
def cancel_loan(
    loan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Membatalkan pinjaman internal bila dibuat karena salah input (tanpa transfer kas balik).
    """
    return cancel_internal_loan(db=db, current_user=current_user, loan_id=loan_id)
