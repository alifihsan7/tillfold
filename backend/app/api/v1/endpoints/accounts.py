from typing import List, Optional
from datetime import datetime, date
import zoneinfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.db.session import get_db
from app.models.account import Account
from app.models.pocket import Pocket
from app.models.transaction import Transaction
from app.core.ledger import POSITIVE_TYPES, NEGATIVE_TYPES
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionPayment
from app.models.paycheck import PaycheckConfig, PaycheckBucket
from app.schemas.account import AccountCreate, AccountResponse, AccountUpdate, PocketBreakdownItem
from app.schemas.pocket import PocketSummaryResponse
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.ledger import signed_amount
from pydantic import BaseModel, Field
from uuid import UUID

router = APIRouter()
WIB = zoneinfo.ZoneInfo(settings.TIMEZONE)


class ReconcileRequest(BaseModel):
    request_key: UUID
    actual_balance: int = Field(ge=-9_000_000_000_000_000, le=9_000_000_000_000_000)
    expected_balance: int = Field(ge=-9_000_000_000_000_000, le=9_000_000_000_000_000)
    latest_transaction_id: int = Field(ge=0)
    note: str = Field(min_length=1, max_length=120)


def reconciliation_snapshot(db: Session, user_id: int, name: str):
    balance, latest = db.query(
        func.coalesce(func.sum(signed_amount()), 0), func.coalesce(func.max(Transaction.id), 0),
    ).filter(Transaction.user_id == user_id, Transaction.account == name).one()
    return {"balance": int(balance), "latest_transaction_id": int(latest)}


@router.get("/{account_id}/reconciliation")
def reconciliation_preview(account_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if account is None:
        raise HTTPException(404, "Rekening tidak ditemukan.")
    return {"account": account.name, **reconciliation_snapshot(db, current_user.id, account.name)}


@router.post("/{account_id}/reconciliation")
def reconcile_account(account_id: int, payload: ReconcileRequest,
                      current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = db.query(Account).filter(
        Account.id == account_id, Account.user_id == current_user.id,
    ).with_for_update().first()
    if account is None:
        raise HTTPException(404, "Rekening tidak ditemukan.")
    if account.is_archived:
        raise HTTPException(409, "Aktifkan kembali rekening sebelum mencatat penyesuaian saldo.")
    marker = f"reconciliation:{payload.request_key}"
    existing = db.query(Transaction).filter(
        Transaction.user_id == current_user.id, Transaction.account == account.name,
        Transaction.raw_text == marker, Transaction.type.in_(["adjustment_in", "adjustment_out"]),
    ).first()
    if existing:
        return {"transaction_id": existing.id, "difference": existing.amount if existing.type == "adjustment_in" else -existing.amount}
    snapshot = reconciliation_snapshot(db, current_user.id, account.name)
    if snapshot["balance"] != payload.expected_balance or snapshot["latest_transaction_id"] != payload.latest_transaction_id:
        raise HTTPException(409, "Saldo berubah. Muat ulang saldo lalu periksa selisihnya lagi.")
    difference = payload.actual_balance - snapshot["balance"]
    if not difference:
        return {"transaction_id": None, "difference": 0}
    if abs(difference) > 9_000_000_000_000_000:
        raise HTTPException(400, "Selisih saldo terlalu besar.")
    note = payload.note.strip()
    if not note:
        raise HTTPException(400, "Isi catatan penyesuaian.")
    tx = Transaction(
        user_id=current_user.id, account=account.name,
        type="adjustment_in" if difference > 0 else "adjustment_out",
        amount=abs(difference), category="Penyesuaian saldo",
        description=f"Saldo {snapshot['balance']} → {payload.actual_balance}. {note}",
        raw_text=marker, date=datetime.now(WIB).date(),
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return {"transaction_id": tx.id, "difference": difference}

DEFAULT_ACCOUNTS = [
    {"name": "Rekening Utama", "type": "operasional", "tag": "Saku Operasional", "color": "amberGold", "initial_balance": 0},
    {"name": "Rekening Tagihan", "type": "tagihan", "tag": "Subs & Tagihan", "color": "purpleLock", "initial_balance": 0},
    {"name": "Investasi", "type": "investasi", "tag": "Portofolio Aset", "color": "teal", "initial_balance": 0},
    {"name": "Dana Darurat", "type": "darurat", "tag": "Cadangan Likuid", "color": "cyanHub", "initial_balance": 0},
    {"name": "Cash", "type": "operasional", "tag": "Uang Tunai Fisik", "color": "amberGold", "initial_balance": 0},
]

def ensure_default_accounts(db: Session, user_id: int):
    has_account = db.query(Account).filter(Account.user_id == user_id).first()
    if not has_account:
        for d in DEFAULT_ACCOUNTS:
            acc = Account(
                user_id=user_id,
                name=d["name"],
                type=d["type"],
                tag=d["tag"],
                color=d["color"],
                initial_balance=d["initial_balance"],
            )
            db.add(acc)
        db.commit()

@router.get("", response_model=List[AccountResponse])
def get_accounts(
    type: Optional[str] = Query(None, description="Filter akun berdasarkan tipe/role finansial"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ensure_default_accounts(db, current_user.id)
    
    # Hitung saldo riil all-time per akun dari ledger transaksi milik user ini
    acc_rows = db.query(
        Transaction.account,
        func.sum(
            case(
                (Transaction.type.in_(POSITIVE_TYPES), Transaction.amount),
                (Transaction.type.in_(NEGATIVE_TYPES), -Transaction.amount),
                else_=0
            )
        ).label("balance")
    ).filter(Transaction.user_id == current_user.id).group_by(Transaction.account).all()

    balance_map = {r.account: int(r.balance or 0) for r in acc_rows}

    query = db.query(Account).filter(Account.user_id == current_user.id)
    if type and type.strip().lower() != "all":
        query = query.filter(func.lower(Account.type) == type.strip().lower())
    accounts = query.order_by(Account.id.asc()).all()

    all_user_pockets = db.query(Pocket).filter(
        Pocket.user_id == current_user.id,
        Pocket.is_active == True,
    ).all()

    pocket_by_account: dict[int, list[Pocket]] = {}
    for p in all_user_pockets:
        if p.account_id:
            pocket_by_account.setdefault(p.account_id, []).append(p)

    results = []
    for acc in accounts:
        curr_bal = balance_map.get(acc.name, 0)
        acc_pockets = pocket_by_account.get(acc.id, [])
        if not acc_pockets and any(k in acc.name.lower() for k in ["jago", "pocket"]):
            acc_pockets = [p for p in all_user_pockets if p.account_id is None]

        sum_other_targets = sum(int(p.target_amount) for p in acc_pockets if not p.slug.startswith("utama"))
        pockets_breakdown = []
        for p in acc_pockets:
            target = int(p.target_amount)
            if p.slug.startswith("utama") and target == 0:
                target = max(0, curr_bal - sum_other_targets)
            pocket_bal = target
            pockets_breakdown.append(PocketBreakdownItem(
                id=p.id,
                name=p.name,
                slug=p.slug,
                role=p.role,
                balance=pocket_bal,
                current_balance=pocket_bal,
                target_amount=target,
                spent_amount=0,
                remaining_amount=pocket_bal,
                percentage_spent=0.0,
                is_active=p.is_active,
            ))

        results.append(AccountResponse(
            id=acc.id,
            is_archived=acc.is_archived,
            name=acc.name,
            type=acc.type,
            tag=acc.tag,
            color=acc.color,
            initial_balance=acc.initial_balance,
            current_balance=curr_bal,
            created_at=acc.created_at,
            pockets=pockets_breakdown,
        ))
    return results


@router.get("/{account_id}/pockets", response_model=PocketSummaryResponse)
def get_account_pockets(
    account_id: int,
    cycle_start: Optional[date] = None,
    cycle_end: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full pocket breakdown and metrics for a specific parent account."""
    from app.api.v1.endpoints.pockets import compute_pockets_summary
    return compute_pockets_summary(
        db=db,
        user_id=current_user.id,
        account_id=account_id,
        cycle_start=cycle_start,
        cycle_end=cycle_end,
    )

@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    account_in: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    name_clean = account_in.name.strip()
    if not name_clean:
        raise HTTPException(status_code=400, detail="Nama rekening tidak boleh kosong")

    existing = db.query(Account).filter(
        Account.user_id == current_user.id,
        func.lower(Account.name) == name_clean.lower()
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Rekening '{name_clean}' sudah terdaftar")

    acc_type = (account_in.type or "operasional").strip().lower()
    new_acc = Account(
        user_id=current_user.id,
        name=name_clean,
        type=acc_type,
        tag=account_in.tag or f"Akun {name_clean}",
        color=account_in.color or "amberGold",
        initial_balance=account_in.initial_balance
    )
    db.add(new_acc)
    db.commit()
    db.refresh(new_acc)

    # Jika ada saldo awal > 0, catat otomatis sebagai transaksi 'income' (Saldo Awal)
    if account_in.initial_balance > 0:
        now_wib = datetime.now(WIB)
        init_tx = Transaction(
            user_id=current_user.id,
            type="income",
            amount=account_in.initial_balance,
            account=new_acc.name,
            category="Saldo Awal",
            description=f"Saldo Awal Akun {new_acc.name}",
            date=now_wib.date(),
            raw_text=f"init_account: {new_acc.name} {account_in.initial_balance}"
        )
        db.add(init_tx)
        db.commit()

    return AccountResponse(
        id=new_acc.id,
        name=new_acc.name,
        type=new_acc.type,
        tag=new_acc.tag,
        color=new_acc.color,
        initial_balance=new_acc.initial_balance,
        current_balance=account_in.initial_balance,
        created_at=new_acc.created_at
    )

@router.put("/{account_id}", response_model=AccountResponse)
def update_account(
    account_id: int,
    account_in: AccountUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    acc = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Rekening tidak ditemukan")

    old_name = acc.name
    new_name = account_in.name.strip() if account_in.name is not None else old_name
    if not new_name:
        raise HTTPException(status_code=400, detail="Nama rekening tidak boleh kosong")

    # Cek duplikasi jika nama berubah
    if new_name != old_name:
        if new_name.lower() != old_name.lower():
            existing = db.query(Account).filter(
                Account.user_id == current_user.id,
                Account.id != account_id,
                func.lower(Account.name) == new_name.lower()
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail=f"Rekening '{new_name}' sudah terdaftar")
        
        # Cascade update nama akun pada transaksi terkait
        db.query(Transaction).filter(
            Transaction.user_id == current_user.id,
            Transaction.account == old_name
        ).update({Transaction.account: new_name}, synchronize_session=False)
        db.query(Subscription).filter(
            Subscription.user_id == current_user.id, Subscription.account == old_name,
        ).update({Subscription.account: new_name}, synchronize_session=False)
        db.query(SubscriptionPayment).filter(
            SubscriptionPayment.user_id == current_user.id, SubscriptionPayment.account == old_name,
        ).update({SubscriptionPayment.account: new_name}, synchronize_session=False)

        # Update PaycheckConfig jika menggunakan akun lama
        cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == current_user.id).first()
        if cfg:
            if cfg.main_income_account == old_name:
                cfg.main_income_account = new_name
            if cfg.pocket_account == old_name:
                cfg.pocket_account = new_name
            db.query(PaycheckBucket).filter(
                PaycheckBucket.config_id == cfg.id,
                PaycheckBucket.account == old_name
            ).update({PaycheckBucket.account: new_name}, synchronize_session=False)
        
        acc.name = new_name

    if account_in.type is not None:
        acc.type = account_in.type.strip().lower()
    if account_in.tag is not None:
        acc.tag = account_in.tag
    if account_in.color is not None:
        acc.color = account_in.color

    db.commit()
    db.refresh(acc)

    # Hitung saldo riil
    bal = db.query(
        func.sum(
            case(
                (Transaction.type.in_(POSITIVE_TYPES), Transaction.amount),
                (Transaction.type.in_(NEGATIVE_TYPES), -Transaction.amount),
                else_=0
            )
        )
    ).filter(Transaction.user_id == current_user.id, Transaction.account == acc.name).scalar() or 0

    return AccountResponse(
        id=acc.id,
        name=acc.name,
        type=acc.type,
        tag=acc.tag,
        color=acc.color,
        initial_balance=acc.initial_balance,
        is_archived=acc.is_archived,
        current_balance=int(bal),
        created_at=acc.created_at
    )

class AccountArchiveRequest(BaseModel):
    is_archived: bool


@router.put("/{account_id}/archive")
def set_account_archive(account_id: int, payload: AccountArchiveRequest,
                        current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Serialize archive changes per user so concurrent requests cannot archive the last two accounts.
    db.query(User).filter(User.id == current_user.id).with_for_update().one()
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).with_for_update().first()
    if not account:
        raise HTTPException(404, "Rekening tidak ditemukan.")
    if payload.is_archived and not account.is_archived:
        active = db.query(Account).filter(Account.user_id == current_user.id, Account.is_archived == False,
                                           Account.id != account_id).order_by(Account.id).all()
        if not active:
            raise HTTPException(409, "Sisakan minimal satu rekening aktif.")
        cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == current_user.id).first()
        if cfg:
            if cfg.source_account == account.name:
                cfg.source_account = next((row.name for row in active if row.type == "gajian"), active[0].name)
            if cfg.pocket_account == account.name:
                cfg.pocket_account = next((row.name for row in active if row.type == "operasional"), active[0].name)
    account.is_archived = payload.is_archived
    db.commit()
    return {"id": account.id, "is_archived": account.is_archived}


@router.delete("/{account_id}")
def delete_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db.query(User).filter(User.id == current_user.id).with_for_update().one()
    acc = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Rekening tidak ditemukan")

    total_accs = db.query(Account).filter(Account.user_id == current_user.id).count()
    if total_accs <= 1 or (not acc.is_archived and db.query(Account).filter(Account.user_id == current_user.id, Account.is_archived == False).count() <= 1):
        raise HTTPException(status_code=400, detail="Minimal harus ada 1 rekening aktif")

    acc_name = acc.name
    if db.query(Transaction.id).filter(
        Transaction.user_id == current_user.id, Transaction.account == acc_name,
        Transaction.type.in_(["transfer_in", "transfer_out"]),
    ).first():
        raise HTTPException(409, "Rekening masih memiliki riwayat transfer. Hapus transfer terkait terlebih dahulu agar saldo rekening lain tetap konsisten.")
    db.query(SubscriptionPayment).filter(
        SubscriptionPayment.user_id == current_user.id,
        SubscriptionPayment.transaction_id.in_(db.query(Transaction.id).filter(
            Transaction.user_id == current_user.id, Transaction.account == acc_name,
        )),
    ).delete(synchronize_session=False)
    # Hapus seluruh transaksi yang terkait rekening ini
    db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
        Transaction.account == acc_name
    ).delete()

    # Perbarui konfigurasi gajian jika mengacu pada akun ini
    cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == current_user.id).first()
    if cfg:
        db.query(PaycheckBucket).filter(
            PaycheckBucket.config_id == cfg.id,
            PaycheckBucket.account == acc_name
        ).delete()
        other_acc = db.query(Account).filter(Account.user_id == current_user.id, Account.id != acc.id).first()
        if other_acc:
            if cfg.pocket_account == acc_name:
                cfg.pocket_account = other_acc.name
            if cfg.source_account == acc_name:
                cfg.source_account = other_acc.name

    db.delete(acc)
    db.commit()
    return {"success": True, "message": f"Rekening '{acc_name}' berhasil dihapus"}
