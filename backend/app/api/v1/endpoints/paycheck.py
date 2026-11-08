import json
import zoneinfo
from datetime import datetime, date as dt_date, timedelta
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db
from app.core.config import settings
from app.models.paycheck import PaycheckConfig, PaycheckBucket, PaycheckSession, PaycheckCycle, PaycheckReceipt
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from app.api.deps import get_current_user

WIB = zoneinfo.ZoneInfo(settings.TIMEZONE)
from app.schemas.paycheck import (
    PaycheckConfigOut,
    PaycheckConfigUpdate,
    PaycheckBucketBase,
    PaycheckBucketOut,
    PaycheckStep,
    PaycheckSessionOut,
    PaycheckStartRequest,
    PaycheckRecordRequest,
    ReceiptAllocationsUpdate,
)
from app.api.v1.endpoints.transactions import add_transfer_pair
from app.services.paycheck_cycles import preserve_legacy_cycles, receipt_allocations

router = APIRouter()


def receipt_out(db: Session, receipt: PaycheckReceipt):
    tx = db.get(Transaction, receipt.transaction_id)
    accounts = {a.id: a.name for a in db.query(Account).filter(Account.user_id == receipt.user_id)}
    return {
        "id": tx.id, "account": tx.account, "amount": tx.amount, "date": tx.date,
        "cycle_end": receipt.cycle_end,
        "allocations": [
            {**item, "account": accounts.get(item["account_id"])}
            for item in receipt_allocations(db, receipt)
        ],
    }


@router.get("/record/latest")
def latest_paycheck_receipt(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    receipts = db.query(PaycheckReceipt).join(Transaction, Transaction.id == PaycheckReceipt.transaction_id).filter(
        PaycheckReceipt.user_id == current_user.id, Transaction.type == "income",
    ).order_by(PaycheckReceipt.transaction_id.desc())
    account_ids = {account.id for account in db.query(Account.id).filter(Account.user_id == current_user.id)}
    for receipt in receipts:
        allocations = receipt_allocations(db, receipt)
        source = db.get(Transaction, receipt.transaction_id).account
        has_target = db.query(Account.id).filter(Account.user_id == current_user.id, Account.name != source).first() is not None
        if (not allocations and has_target) or any(item["amount"] > 0 and not item["transfer_id"] and item["account_id"] in account_ids
               for item in allocations):
            return receipt_out(db, receipt)
    return None


@router.post("/record", status_code=201)
def record_paycheck(
    payload: PaycheckRecordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    request_key = str(payload.request_key)
    receipts = db.query(PaycheckReceipt).filter(
        PaycheckReceipt.user_id == user_id, PaycheckReceipt.request_key == request_key,
    )
    receipt = receipts.first()
    if receipt:
        return receipt_out(db, receipt)

    accounts = {a.name: a for a in db.query(Account).filter(Account.user_id == user_id)}
    if payload.account not in accounts:
        raise HTTPException(400, "Pilih rekening penerima yang tersedia.")
    if payload.date > datetime.now(WIB).date():
        raise HTTPException(400, "Tanggal gaji masuk belum terjadi.")

    cfg = get_or_seed_config(db, user_id)
    buckets = get_or_seed_buckets(db, cfg.id)
    end_date = None
    if payload.start_cycle:
        days = {"weekly": 7, "biweekly": 14, "monthly": 30, "custom": payload.cycle_days}.get(
            payload.cycle_type, cfg.cycle_days,
        )
        if not days or days < 1:
            raise HTTPException(400, "Isi durasi siklus.")
        try:
            if not payload.cycle_type and cfg.cycle_type == "monthly_date":
                from app.api.v1.endpoints.analytics import get_monthly_date_bounds

                _, end_date = get_monthly_date_bounds(payload.date, payload.date.day)
            else:
                end_date = payload.date + timedelta(days=days - 1)
        except (OverflowError, ValueError):
            raise HTTPException(400, "Tanggal akhir siklus tidak valid.")
        if payload.save_cycle_default and payload.cycle_type:
            if (cfg.cycle_type, cfg.cycle_days) != (payload.cycle_type, days):
                preserve_legacy_cycles(db, cfg, datetime.now(WIB).date())
            cfg.cycle_type = payload.cycle_type
            cfg.cycle_days = days

    amounts = compute_bucket_amounts(payload.total_amount, buckets)
    remaining = payload.total_amount
    allocations = []
    for account, amount in amounts.items():
        if account != payload.account and account in accounts and amount > 0 and remaining > 0:
            amount = min(amount, remaining)
            allocations.append({"account_id": accounts[account].id, "amount": amount, "transfer_id": None})
            remaining -= amount

    label = "Gaji" if payload.start_cycle else "Gaji tambahan"
    tx = Transaction(user_id=user_id, account=payload.account, type="income", amount=payload.total_amount,
                     category=label, description=label, date=payload.date)
    try:
        db.add(tx)
        db.flush()
        receipt = PaycheckReceipt(transaction_id=tx.id, user_id=user_id, request_key=request_key,
                                  cycle_end=end_date, allocations_json=json.dumps(allocations))
        db.add(receipt)
        db.commit()
    except IntegrityError:
        db.rollback()
        receipt = receipts.first()
        if receipt is None:
            raise
    return receipt_out(db, receipt)


@router.put("/record/{receipt_id}/allocations")
def update_receipt_allocations(
    receipt_id: int, payload: ReceiptAllocationsUpdate,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    receipt = db.query(PaycheckReceipt).filter(
        PaycheckReceipt.user_id == current_user.id, PaycheckReceipt.transaction_id == receipt_id,
    ).with_for_update().first()
    if not receipt:
        raise HTTPException(404, "Catatan gaji tidak ditemukan.")
    current = receipt_allocations(db, receipt)
    fingerprint = lambda rows: sorted((row["account_id"], row["amount"], row["transfer_id"] or 0) for row in rows)
    if fingerprint(current) != fingerprint([row.model_dump() for row in payload.expected_allocations]):
        raise HTTPException(409, "Pembagian gaji sudah berubah. Tutup lalu buka kembali untuk memuat data terbaru.")
    tx = db.get(Transaction, receipt_id)
    if not tx or tx.type != "income":
        raise HTTPException(409, "Catatan gaji sudah berubah.")
    requested = [row.model_dump() for row in payload.allocations]
    if len({row["account_id"] for row in requested}) != len(requested):
        raise HTTPException(400, "Setiap rekening hanya boleh muncul sekali.")
    paid = {row["account_id"]: row for row in current if row["transfer_id"]}
    proposed = {row["account_id"]: row for row in requested}
    if any(proposed.get(account_id) != row for account_id, row in paid.items()):
        raise HTTPException(409, "Transfer yang sudah tercatat tidak dapat diubah dari pembagian gaji.")
    owned = {row.id: row.name for row in db.query(Account).filter(Account.user_id == current_user.id)}
    for row in requested:
        if row["account_id"] not in paid:
            if row["transfer_id"] or row["account_id"] not in owned or owned[row["account_id"]] == tx.account:
                raise HTTPException(400, "Pilih rekening tujuan milik Anda yang berbeda dari rekening penerima gaji.")
    if sum(row["amount"] for row in requested) > tx.amount:
        raise HTTPException(400, "Total pembagian melebihi nominal gaji.")
    receipt.allocations_json = json.dumps([row for row in requested if row["amount"] > 0 or row["transfer_id"]])
    db.commit()
    return receipt_out(db, receipt)


@router.post("/record/{receipt_id}/transfer/{account_id}")
def confirm_paycheck_transfer(
    receipt_id: int,
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    receipt = db.query(PaycheckReceipt).filter(
        PaycheckReceipt.user_id == current_user.id, PaycheckReceipt.transaction_id == receipt_id,
    ).with_for_update().first()
    if receipt is None:
        raise HTTPException(404, "Catatan gaji tidak ditemukan.")
    allocations = receipt_allocations(db, receipt)
    item = next((row for row in allocations if row["account_id"] == account_id), None)
    if item is None or item["amount"] <= 0:
        raise HTTPException(404, "Alokasi tidak ditemukan.")
    if item["transfer_id"]:
        return receipt_out(db, receipt)

    tx = db.get(Transaction, receipt_id)
    if tx is None:
        raise HTTPException(404, "Catatan gaji tidak ditemukan.")
    target = db.get(Account, account_id)
    source = db.query(Account.id).filter(Account.user_id == current_user.id, Account.name == tx.account).first()
    if not source or not target or target.user_id != current_user.id or tx.account == target.name or tx.type != "income":
        raise HTTPException(409, "Rekening atau catatan gaji sudah berubah.")
    if sum(row["amount"] for row in allocations if row["transfer_id"]) + item["amount"] > tx.amount:
        raise HTTPException(409, "Total alokasi melebihi nominal gaji.")
    tx_out, tx_in = add_transfer_pair(
        db, current_user.id, tx.account, target.name, item["amount"], datetime.now(WIB).date(), "Pembagian gaji",
    )
    tx_in.raw_text += f" [paycheck_receipt:{receipt_id}]"
    tx_out.raw_text += f" [paycheck_receipt:{receipt_id}]"
    item["transfer_id"] = tx_in.id
    receipt.allocations_json = json.dumps(allocations)
    db.commit()
    return receipt_out(db, receipt)

def get_or_seed_config(db: Session, user_id: int = 1) -> PaycheckConfig:
    cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == user_id).first()
    if not cfg:
        from app.models.account import Account
        user_accs = db.query(Account).filter(Account.user_id == user_id).all()
        source_name = user_accs[0].name if user_accs else "Rekening Utama"
        pocket_acc = next((a for a in user_accs if a.type == "operasional"), None)
        pocket_name = pocket_acc.name if pocket_acc else source_name
        cfg = PaycheckConfig(
            user_id=user_id,
            source_account=source_name,
            use_gate=True,
            gate_name="Perantara transfer",
            cycle_type="monthly_date",
            cycle_days=30,
            pocket_account=pocket_name,
            is_active=True
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg

def get_or_seed_buckets(db: Session, config_id: int = 1) -> List[PaycheckBucket]:
    buckets = db.query(PaycheckBucket).filter(PaycheckBucket.config_id == config_id).order_by(PaycheckBucket.sort_order.asc()).all()
    if not buckets:
        cfg = db.query(PaycheckConfig).filter(PaycheckConfig.id == config_id).first()
        from app.models.account import Account
        user_accs = db.query(Account).filter(Account.user_id == cfg.user_id).all() if cfg else []
        if user_accs:
            n = len(user_accs)
            even_pct = round(100.0 / n, 2)
            default_buckets = []
            for i, acc in enumerate(user_accs):
                pct = round(100.0 - even_pct * (n - 1), 2) if i == n - 1 else even_pct
                purpose_map = {
                    "operasional": "Operasional & Belanja",
                    "tagihan": "Tagihan & Rutin",
                    "gajian": "Pemasukan Utama",
                    "tabungan": "Tabungan",
                    "investasi": "Investasi",
                    "darurat": "Dana Darurat",
                    "ewallet": "Dompet Digital",
                }
                purpose = purpose_map.get((acc.type or "").strip().lower(), "Alokasi Pos")
                default_buckets.append(PaycheckBucket(
                    config_id=config_id,
                    account=acc.name,
                    percentage=pct,
                    via_gate=acc.name != (cfg.source_account if cfg else ""),
                    purpose=purpose,
                    sort_order=i + 1
                ))
        else:
            default_buckets = [
                PaycheckBucket(
                    config_id=config_id,
                    account="Rekening Utama",
                    percentage=100.0,
                    via_gate=False,
                    purpose="Kebutuhan Pokok & Operasional",
                    sort_order=1
                )
            ]
        db.add_all(default_buckets)
        db.commit()
        buckets = db.query(PaycheckBucket).filter(PaycheckBucket.config_id == config_id).order_by(PaycheckBucket.sort_order.asc()).all()
    return buckets

def compute_bucket_amounts(total_amount: int, buckets: List[PaycheckBucket], override: Optional[Dict[str, int]] = None) -> Dict[str, int]:
    result = {}
    if override:
        for b in buckets:
            result[b.account] = int(override.get(b.account, 0))
        return result

    percentages = [Decimal(str(b.percentage)) for b in buckets]
    if any(not pct.is_finite() or pct < 0 or pct > 100 for pct in percentages):
        raise HTTPException(400, "Persentase alokasi harus antara 0 dan 100.")
    total_pct = sum(percentages, Decimal(0))
    if total_pct > 100:
        raise HTTPException(400, "Total pembagian tidak boleh melebihi 100%.")
    if len({b.account for b in buckets}) != len(buckets):
        raise HTTPException(400, "Setiap rekening hanya boleh memiliki satu alokasi.")
    exact = [Decimal(total_amount) * pct / 100 for pct in percentages]
    amounts = [int(amount.to_integral_value(rounding=ROUND_FLOOR)) for amount in exact]
    target = int((Decimal(total_amount) * total_pct / 100).to_integral_value(rounding=ROUND_HALF_UP))
    # Distribute rounding rupiah by fractional share without allocating the unassigned percentage.
    order = sorted(range(len(buckets)), key=lambda i: exact[i] - amounts[i], reverse=True)
    for i in order[:target - sum(amounts)]:
        amounts[i] += 1
    result = {b.account: amount for b, amount in zip(buckets, amounts)}
    return result

def generate_steps(config: PaycheckConfig, buckets: List[PaycheckBucket], amounts: Dict[str, int]) -> List[PaycheckStep]:
    steps: List[PaycheckStep] = []

    # Identify categories
    gate_buckets = [b for b in buckets if b.via_gate and not b.via_secondary]
    secondary_buckets = [b for b in buckets if b.via_secondary]
    direct_buckets = [b for b in buckets if not b.via_gate and b.account != config.source_account]
    hub_bucket = next((b for b in buckets if b.account == config.source_account), None)

    # ------------------ PHASE 1: SUMBER DANA (source_account) ------------------
    # 1. Direct transfers
    for b in direct_buckets:
        amt = amounts.get(b.account, 0)
        if amt > 0:
            steps.append(PaycheckStep(
                id=f"direct_{b.account.lower().replace(' ', '_')}",
                phase=1,
                app=f"M-Banking ({config.source_account})",
                title=f"Transfer {config.source_account} → {b.account}",
                badge="Sesama Bank",
                description=f"{b.purpose} (Rp {amt:,})",
                source_account=config.source_account,
                target_account=b.account,
                amount=amt,
                is_done=False,
                is_auto=False,
                creates_income=True,
            ))

    # 2. Sisa di Rekening Hub
    if hub_bucket:
        hub_amt = amounts.get(hub_bucket.account, 0)
        if hub_amt > 0:
            steps.append(PaycheckStep(
                id=f"stay_{hub_bucket.account.lower().replace(' ', '_')}",
                phase=1,
                app=config.source_account,
                title=f"Sisa Saldo di {config.source_account}",
                badge="Rekening Hub",
                description=f"{hub_bucket.purpose} (Otomatis tetap di rekening penampung)",
                source_account=config.source_account,
                target_account=hub_bucket.account,
                amount=hub_amt,
                is_done=True,
                is_auto=True,
                creates_income=True,
            ))

    # 3. Gate Funding Step (if use_gate is active)
    if config.use_gate and (gate_buckets or secondary_buckets):
        gate_total = sum(amounts.get(b.account, 0) for b in gate_buckets) + sum(amounts.get(b.account, 0) for b in secondary_buckets)
        if gate_total > 0:
            steps.append(PaycheckStep(
                id="gate_funding",
                phase=1,
                app=f"M-Banking ({config.source_account})",
                title=f"Top Up / Transfer {config.source_account} → {config.gate_name}",
                badge="Jembatan Bebas Admin",
                description=f"Kirim total Rp {gate_total:,} ke {config.gate_name} untuk distribusi ke rekening operasional & investasi",
                source_account=config.source_account,
                target_account=config.gate_name,
                amount=gate_total,
                is_done=False,
                is_auto=False,
                creates_income=False, # Bridge funding, not final income
            ))

    # ------------------ PHASE 2: DISTRIBUSI VIA GATE (Flip) ------------------
    if config.use_gate:
        # Accounts that also carry secondary funds (e.g. Jago carries Bibit)
        for b in gate_buckets:
            base_amt = amounts.get(b.account, 0)
            sub_carrying = sum(amounts.get(sec.account, 0) for sec in secondary_buckets if sec.via_secondary == b.account)
            total_sent = base_amt + sub_carrying
            if total_sent > 0:
                is_carrying = sub_carrying > 0
                desc = f"Gabungan pos {b.purpose} (Rp {base_amt:,})" + (f" + modal {', '.join(s.account for s in secondary_buckets if s.via_secondary == b.account)} (Rp {sub_carrying:,})" if is_carrying else "")
                steps.append(PaycheckStep(
                    id=f"gate_to_{b.account.lower().replace(' ', '_')}",
                    phase=2,
                    app=config.gate_name,
                    title=f"{config.gate_name} → {b.account}",
                    badge="Bebas Admin",
                    description=desc,
                    source_account=config.gate_name,
                    target_account=b.account,
                    amount=total_sent,
                    is_done=False,
                    is_auto=False,
                    creates_income=not is_carrying, # If it doesn't carry secondary, it's the direct income. If it carries, final income is recorded on Phase 3
                ))
    else:
        # Direct mode (without gate)
        for b in gate_buckets + secondary_buckets:
            amt = amounts.get(b.account, 0)
            if amt > 0:
                steps.append(PaycheckStep(
                    id=f"direct_to_{b.account.lower().replace(' ', '_')}",
                    phase=1,
                    app=config.source_account,
                    title=f"Transfer {config.source_account} → {b.account}",
                    badge="Direct Transfer",
                    description=f"{b.purpose} (Rp {amt:,})",
                    source_account=config.source_account,
                    target_account=b.account,
                    amount=amt,
                    is_done=False,
                    is_auto=False,
                    creates_income=True,
                ))

    # ------------------ PHASE 3: ALOKASI LANJUTAN (Bank Jago -> Bibit) ------------------
    for b in secondary_buckets:
        amt = amounts.get(b.account, 0)
        if amt > 0:
            steps.append(PaycheckStep(
                id=f"secondary_{b.account.lower().replace(' ', '_')}",
                phase=3,
                app=f"{b.via_secondary} / {b.account}",
                title=f"Top Up {b.via_secondary} → {b.account}",
                badge="Investasi / Sekunder",
                description=f"{b.purpose} (Rp {amt:,})",
                source_account=b.via_secondary or config.source_account,
                target_account=b.account,
                amount=amt,
                is_done=False,
                is_auto=False,
                creates_income=True,
            ))

    # For accounts carrying secondary funds, record their residual balance as final income once reached
    if config.use_gate:
        for b in gate_buckets:
            has_sec = any(sec.via_secondary == b.account for sec in secondary_buckets)
            if has_sec:
                base_amt = amounts.get(b.account, 0)
                if base_amt > 0:
                    steps.append(PaycheckStep(
                        id=f"residual_{b.account.lower().replace(' ', '_')}",
                        phase=3,
                        app=b.account,
                        title=f"Sisa Saldo di {b.account}",
                        badge="Autodebet / Rutin",
                        description=f"{b.purpose} (Tersimpan otomatis untuk autodebet & tagihan)",
                        source_account=b.account,
                        target_account=b.account,
                        amount=base_amt,
                        is_done=False,
                        is_auto=True,
                        creates_income=True,
                    ))

    return steps

def format_session_out(session: PaycheckSession) -> PaycheckSessionOut:
    steps_data = json.loads(session.steps_json)
    steps = [PaycheckStep(**s) for s in steps_data]
    total_steps = len(steps)
    completed_steps = sum(1 for s in steps if s.is_done)
    pct = round((completed_steps / total_steps * 100), 1) if total_steps > 0 else 0.0

    return PaycheckSessionOut(
        id=session.id,
        total_amount=session.total_amount,
        date=session.date,
        status=session.status,
        note=session.note,
        steps=steps,
        completed_steps=completed_steps,
        total_steps=total_steps,
        progress_percentage=pct,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )

@router.get("/config")
def get_paycheck_config_and_buckets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cfg = get_or_seed_config(db, current_user.id)
    buckets = get_or_seed_buckets(db, cfg.id)
    return {
        "config": PaycheckConfigOut.from_orm(cfg),
        "buckets": [PaycheckBucketOut.from_orm(b) for b in buckets],
    }

@router.put("/config", response_model=PaycheckConfigOut)
def update_paycheck_config(
    payload: PaycheckConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cfg = get_or_seed_config(db, current_user.id)
    cfg.source_account = payload.source_account
    cfg.use_gate = payload.use_gate
    cfg.gate_name = payload.gate_name
    if (cfg.cycle_type, cfg.cycle_days, cfg.paycheck_day) != (payload.cycle_type, payload.cycle_days, payload.paycheck_day or cfg.paycheck_day):
        preserve_legacy_cycles(db, cfg, datetime.now(WIB).date())
    cfg.cycle_type = payload.cycle_type
    cfg.cycle_days = payload.cycle_days
    if payload.paycheck_day:
        cfg.paycheck_day = payload.paycheck_day
    if payload.cycle_start_date:
        cfg.cycle_start_date = payload.cycle_start_date
    cfg.pocket_account = payload.pocket_account
    db.commit()
    db.refresh(cfg)
    return PaycheckConfigOut.from_orm(cfg)

@router.put("/buckets", response_model=List[PaycheckBucketOut])
def update_paycheck_buckets(
    payload: List[PaycheckBucketBase],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    names = [bucket.account for bucket in payload]
    if len(set(names)) != len(names):
        raise HTTPException(400, "Setiap rekening hanya boleh memiliki satu alokasi.")
    if sum(Decimal(str(bucket.percentage)) for bucket in payload) > 100:
        raise HTTPException(400, "Total pembagian tidak boleh melebihi 100%.")
    owned = {name for (name,) in db.query(Account.name).filter(Account.user_id == current_user.id)}
    if any(name not in owned for name in names):
        raise HTTPException(400, "Pilih rekening alokasi yang tersedia.")
    cfg = get_or_seed_config(db, current_user.id)
    # Clear existing and replace
    db.query(PaycheckBucket).filter(PaycheckBucket.config_id == cfg.id).delete()
    new_buckets = []
    for idx, b in enumerate(payload):
        bucket = PaycheckBucket(
            config_id=cfg.id,
            account=b.account,
            percentage=b.percentage,
            fixed_amount=b.fixed_amount,
            via_gate=b.via_gate,
            via_secondary=b.via_secondary,
            purpose=b.purpose,
            sort_order=idx + 1
        )
        db.add(bucket)
        new_buckets.append(bucket)
    db.commit()
    return [PaycheckBucketOut.from_orm(b) for b in new_buckets]

@router.get("/session/active", response_model=Optional[PaycheckSessionOut])
def get_active_paycheck_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(PaycheckSession).filter(
        PaycheckSession.user_id == current_user.id,
        PaycheckSession.status == "in_progress"
    ).order_by(PaycheckSession.id.desc()).first()
    if not session:
        return None
    return format_session_out(session)

@router.post("/session/start", response_model=PaycheckSessionOut)
def start_paycheck_session(
    payload: PaycheckStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cycle_days = {"weekly": 7, "biweekly": 14, "monthly": 30}.get(payload.cycle_type)
    if payload.cycle_type == "custom":
        cycle_days = payload.cycle_days
        if cycle_days is None:
            raise HTTPException(status_code=400, detail="Isi durasi siklus kustom.")
    if payload.save_cycle_default and cycle_days is None:
        raise HTTPException(status_code=400, detail="Pilih siklus yang akan dijadikan default.")
    cycle_date = payload.date or datetime.now(WIB).date()
    cycle_end = None
    if cycle_days is not None:
        try:
            cycle_end = cycle_date + timedelta(days=cycle_days - 1)
        except OverflowError:
            raise HTTPException(status_code=400, detail="Tanggal akhir siklus tidak valid.")

    # Cancel any existing active session to avoid stale dangling sessions
    active = db.query(PaycheckSession).filter(
        PaycheckSession.user_id == current_user.id,
        PaycheckSession.status == "in_progress"
    ).all()
    if active and cycle_end is not None:
        raise HTTPException(status_code=409, detail="Selesaikan atau batalkan checklist gajian yang aktif.")
    for s in active:
        s.status = "cancelled"
    db.commit()

    cfg = get_or_seed_config(db, current_user.id)
    buckets = get_or_seed_buckets(db, cfg.id)
    amounts = compute_bucket_amounts(payload.total_amount, buckets, payload.allocations)
    steps = generate_steps(cfg, buckets, amounts)

    # Pre-record income for auto steps (e.g. Sisa di BRI 1 and Sisa di Jago)
    for s in steps:
        if s.is_auto and s.is_done and s.creates_income:
            tx = Transaction(
                user_id=current_user.id,
                type="income",
                amount=s.amount,
                account=s.target_account,
                category="Gajian",
                description=f"Gajian (Alokasi {s.target_account})",
                date=cycle_date,
            )
            db.add(tx)
            db.flush()
            s.transaction_id = tx.id

    steps_dicts = [s.dict() for s in steps]

    session = PaycheckSession(
        user_id=current_user.id,
        total_amount=payload.total_amount,
        date=cycle_date,
        status="in_progress",
        note=payload.note,
        steps_json=json.dumps(steps_dicts),
    )
    db.add(session)
    if cycle_end is not None:
        db.flush()
        db.add(PaycheckCycle(session_id=session.id, end_date=cycle_end))
        if payload.save_cycle_default:
            if (cfg.cycle_type, cfg.cycle_days) != (payload.cycle_type, cycle_days):
                preserve_legacy_cycles(db, cfg, datetime.now(WIB).date())
            cfg.cycle_type = payload.cycle_type
            cfg.cycle_days = cycle_days
    db.commit()
    db.refresh(session)

    return format_session_out(session)

@router.post("/session/{session_id}/step/{step_id}/toggle", response_model=PaycheckSessionOut)
def toggle_paycheck_step(
    session_id: int,
    step_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(PaycheckSession).filter(
        PaycheckSession.id == session_id,
        PaycheckSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi gajian tidak ditemukan")

    steps_data = json.loads(session.steps_json)
    target_step = None
    for s in steps_data:
        if s["id"] == step_id:
            target_step = s
            break

    if not target_step:
        raise HTTPException(status_code=404, detail="Langkah transfer tidak ditemukan")

    # Toggle
    now_done = not target_step["is_done"]
    target_step["is_done"] = now_done

    if now_done:
        # If creates_income and no tx yet, create income transaction
        if target_step.get("creates_income") and not target_step.get("transaction_id"):
            tx = Transaction(
                user_id=current_user.id,
                type="income",
                amount=target_step["amount"],
                account=target_step["target_account"],
                category="Gajian",
                description=f"Gajian (Alokasi {target_step['target_account']})",
                date=session.date,
            )
            db.add(tx)
            db.flush()
            target_step["transaction_id"] = tx.id
    else:
        # If untoggled, remove transaction if created
        tx_id = target_step.get("transaction_id")
        if tx_id:
            tx = db.query(Transaction).filter(Transaction.id == tx_id, Transaction.user_id == current_user.id).first()
            if tx:
                db.delete(tx)
            target_step["transaction_id"] = None

    # Cascade for gate steps that carry secondary funds (e.g. gate_to_bank_jago -> residual_bank_jago)
    if target_step["id"].startswith("gate_to_"):
        target_account_name = target_step["target_account"].lower().replace(" ", "_")
        residual_id = f"residual_{target_account_name}"
        for s in steps_data:
            if s["id"] == residual_id:
                s["is_done"] = now_done
                if now_done:
                    if s.get("creates_income") and not s.get("transaction_id"):
                        tx = Transaction(
                            user_id=current_user.id,
                            type="income",
                            amount=s["amount"],
                            account=s["target_account"],
                            category="Gajian",
                            description=f"Gajian (Alokasi {s['target_account']})",
                            date=session.date,
                        )
                        db.add(tx)
                        db.flush()
                        s["transaction_id"] = tx.id
                else:
                    tx_id = s.get("transaction_id")
                    if tx_id:
                        tx = db.query(Transaction).filter(Transaction.id == tx_id, Transaction.user_id == current_user.id).first()
                        if tx:
                            db.delete(tx)
                        s["transaction_id"] = None
                break

    # Check if all steps are completed
    all_done = all(s["is_done"] for s in steps_data)
    if all_done:
        session.status = "completed"
        cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == current_user.id).first()
        if cfg:
            cfg.cycle_start_date = session.date
            db.add(cfg)
        # Auto sync Google Sheets snapshot in background (User #1 only)
        if current_user.id == 1:
            try:
                from app.services.sheets_sync import sync_cycle_snapshot
                sync_cycle_snapshot(db, user_id=current_user.id, cycle_start_date=session.date)
            except Exception as e:
                print(f"[Paycheck Sync Warning] Failed to auto sync sheets: {e}")
    else:
        session.status = "in_progress"

    session.steps_json = json.dumps(steps_data)
    db.commit()
    db.refresh(session)

    return format_session_out(session)

@router.post("/session/{session_id}/complete_all", response_model=PaycheckSessionOut)
def complete_all_paycheck_steps(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(PaycheckSession).filter(
        PaycheckSession.id == session_id,
        PaycheckSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi gajian tidak ditemukan")

    steps_data = json.loads(session.steps_json)
    for s in steps_data:
        if not s["is_done"]:
            s["is_done"] = True
            if s.get("creates_income") and not s.get("transaction_id"):
                tx = Transaction(
                    user_id=current_user.id,
                    type="income",
                    amount=s["amount"],
                    account=s["target_account"],
                    category="Gajian",
                    description=f"Gajian (Alokasi {s['target_account']})",
                    date=session.date,
                )
                db.add(tx)
                db.flush()
                s["transaction_id"] = tx.id

    session.status = "completed"
    session.steps_json = json.dumps(steps_data)
    cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == current_user.id).first()
    if cfg:
        cfg.cycle_start_date = session.date
        db.add(cfg)
    db.commit()
    db.refresh(session)

    if current_user.id == 1:
        try:
            from app.services.sheets_sync import sync_cycle_snapshot
            sync_cycle_snapshot(db, user_id=current_user.id, cycle_start_date=session.date)
        except Exception as e:
            print(f"[Paycheck Sync Warning] Failed to auto sync sheets: {e}")

    return format_session_out(session)

@router.post("/session/{session_id}/cancel")
def cancel_paycheck_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(PaycheckSession).filter(
        PaycheckSession.id == session_id,
        PaycheckSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi gajian tidak ditemukan")

    # Clean up transactions created during this session
    steps_data = json.loads(session.steps_json)
    for s in steps_data:
        tx_id = s.get("transaction_id")
        if tx_id:
            tx = db.query(Transaction).filter(Transaction.id == tx_id, Transaction.user_id == current_user.id).first()
            if tx:
                db.delete(tx)

    session.status = "cancelled"
    db.commit()
    return {"message": "Sesi alokasi gajian dibatalkan dan transaksi dibersihkan"}
