import re
from typing import Optional
from sqlalchemy.orm import Session
from app.models.transaction import Transaction


def find_paired_transfer(db: Session, tx: Transaction) -> Optional[Transaction]:
    if tx.type not in ("transfer_out", "transfer_in"):
        return None

    target_type = "transfer_in" if tx.type == "transfer_out" else "transfer_out"
    candidates = db.query(Transaction).filter(
        Transaction.user_id == tx.user_id,
        Transaction.type == target_type,
        Transaction.amount == tx.amount,
        Transaction.date == tx.date,
        Transaction.account != tx.account,
    )
    marker = re.search(r"\[pair_id:(\d+)\]", tx.raw_text or "")
    if marker:
        pair = candidates.filter(Transaction.id == int(marker.group(1))).first()
        if pair:
            reverse = re.search(r"\[pair_id:(\d+)\]", pair.raw_text or "")
            if reverse is None or int(reverse.group(1)) == tx.id:
                return pair
        # A broken explicit link must never fall back to an unrelated transfer.
        return None

    # Legacy matches must be unique in both directions, not merely close in ID.
    def legacy_matches(source):
        other_type = "transfer_in" if source.type == "transfer_out" else "transfer_out"
        matches = []
        for other in db.query(Transaction).filter(
            Transaction.user_id == source.user_id, Transaction.type == other_type,
            Transaction.amount == source.amount, Transaction.date == source.date,
            Transaction.account != source.account,
        ).all():
            if re.search(r"\[pair_id:\d+\]", other.raw_text or ""):
                continue
            receipt = re.search(r"\[paycheck_receipt:(\d+)\]", source.raw_text or "")
            other_receipt = re.search(r"\[paycheck_receipt:(\d+)\]", other.raw_text or "")
            if receipt or other_receipt:
                if receipt and other_receipt and receipt.group(1) == other_receipt.group(1):
                    matches.append(other)
                continue
            outgoing, incoming = (source, other) if source.type == "transfer_out" else (other, source)
            if source.category == other.category == "Transfer" and (
                outgoing.description or ""
            ).startswith(f"Transfer ke {incoming.account}:") and (
                incoming.description or ""
            ).startswith(f"Transfer dari {outgoing.account}:"):
                matches.append(other)
        return matches

    matches = legacy_matches(tx)
    if len(matches) == 1:
        reverse = legacy_matches(matches[0])
        if len(reverse) == 1 and reverse[0].id == tx.id:
            return matches[0]
    return None
