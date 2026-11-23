import logging
from datetime import date, datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.transaction import Transaction
from app.models.account import Account
from app.models.user import User
from app.bot.bot import get_safe_to_spend_snippet

logger = logging.getLogger("receipt-service")

def record_receipt_mutation(
    db: Session,
    user_id: int,
    ref_number: str,
    merchant: str,
    amount: int,
    account_name: str,
    category: str,
    tx_date: date,
    raw_summary: str = "",
    tx_type: str = "expense"
) -> Dict[str, Any]:
    """
    Records an approved bank receipt transaction into Tillfold PostgreSQL.
    Enforces idempotency using the reference number.
    Format Description: '{merchant} - Ref: {ref_number}'
    Format raw_text: '[receipt_radar:ref_{ref_number}] {raw_summary}'
    """
    clean_ref = str(ref_number).strip()
    if not clean_ref:
        return {"ok": False, "error": "Nomor referensi wajib diisi"}

    if tx_type not in ("expense", "income"):
        return {"ok": False, "error": "Struk hanya dapat mencatat pengeluaran atau pemasukan."}
    # Serialize reference checks per owner, including requests for different accounts.
    db.query(User).filter(User.id == user_id).with_for_update().one()

    # 1. Idempotency Check
    existing = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        (
            Transaction.raw_text.contains(f"[receipt_radar:ref_{clean_ref}]", autoescape=True) |
            Transaction.description.endswith(f" - Ref: {clean_ref}", autoescape=True)
        )
    ).first()

    if existing:
        logger.info(f"Transaction ref {clean_ref} already recorded (ID: {existing.id})")
        s2s_snippet = ""
        try:
            s2s_snippet = get_safe_to_spend_snippet(db, user_id=user_id)
        except Exception as e:
            logger.error(f"Error calculating safe-to-spend snippet for existing tx {existing.id}: {e}", exc_info=True)
        return {
            "ok": True,
            "already_recorded": True,
            "transaction_id": existing.id,
            "merchant": merchant,
            "amount": existing.amount,
            "account": existing.account,
            "category": existing.category,
            "s2s": s2s_snippet,
            "message": f"Transaksi referensi {clean_ref} sudah pernah tercatat."
        }

    # Invalid or archived accounts must never redirect a financial write.
    acc = db.query(Account).filter(
        Account.user_id == user_id, Account.name == account_name,
        Account.is_archived.is_(False),
    ).with_for_update().first()
    if acc is None:
        return {"ok": False, "error": "Pilih rekening aktif yang terdaftar di akun Anda."}

    # 3. Create Transaction
    desc_str = f"{merchant} - Ref: {clean_ref}"
    raw_text_str = f"[receipt_radar:ref_{clean_ref}] {raw_summary or merchant}"

    tx = Transaction(
        user_id=user_id,
        type=tx_type,
        amount=amount,
        account=account_name,
        category=category or "Lainnya",
        description=desc_str[:255],
        raw_text=raw_text_str,
        date=tx_date
    )

    db.add(tx)
    db.commit()
    db.refresh(tx)

    logger.info(f"Recorded receipt transaction ID {tx.id} for ref {clean_ref}: {amount} in {account_name}")

    # 4. Compute updated Safe-to-Spend
    s2s_snippet = ""
    try:
        s2s_snippet = get_safe_to_spend_snippet(db, user_id=user_id)
    except Exception as e:
        logger.error(f"Error calculating safe-to-spend snippet post-commit for tx {tx.id}: {e}", exc_info=True)

    return {
        "ok": True,
        "already_recorded": False,
        "transaction_id": tx.id,
        "merchant": merchant,
        "amount": amount,
        "account": account_name,
        "category": category,
        "date": tx_date.isoformat(),
        "s2s": s2s_snippet
    }
