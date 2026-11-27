import hmac
from collections.abc import Callable

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionUpdate

PREFIX = "txn:"
PAGE_SIZE = 8


def _signature(tx: Transaction, chat_id: int, callback: str) -> str:
    context = f"{tx.user_id}:{chat_id}:{tx.created_at.isoformat()}:{callback}"
    return hmac.digest(settings.JWT_SECRET_KEY.encode(), context.encode(), "sha256").hex()[:16]


def _button(label: str, tx: Transaction, chat_id: int, action: str, value: int = 0) -> dict:
    callback = f"{PREFIX}{tx.id}:{action}:{value}"
    return {"text": label, "callback_data": f"{callback}:{_signature(tx, chat_id, callback)}"}


def correction_markup(transactions: list[Transaction], chat_id: int) -> dict:
    if len(transactions) == 1:
        tx = transactions[0]
        rows = [[
            _button("Ubah kategori", tx, chat_id, "cats"),
            _button("Ubah rekening", tx, chat_id, "accs"),
        ], [_button("Batalkan", tx, chat_id, "ask")]]
    else:
        rows = [[_button(f"Koreksi {index} · {tx.description[:36]}", tx, chat_id, "open")]
                for index, tx in enumerate(transactions, 1)]
    return {"inline_keyboard": rows}


def _choices(db: Session, tx: Transaction, chat_id: int, action: str, page: int) -> tuple[str, dict]:
    if action == "cats":
        query = db.query(Category.id, Category.name).filter(
            Category.user_id == tx.user_id, Category.type == tx.type,
        ).order_by(func.lower(Category.name), Category.id)
        title, selected, apply = "Pilih kategori", tx.category, "cat"
    else:
        query = db.query(Account.id, Account.name).filter(
            Account.user_id == tx.user_id, Account.is_archived.is_(False),
        ).order_by(func.lower(Account.name), Account.id)
        title, selected, apply = "Pilih rekening", tx.account, "acc"

    options = query.offset(page * PAGE_SIZE).limit(PAGE_SIZE + 1).all()
    rows = [[_button(f"✓ {name}" if name == selected else name, tx, chat_id, apply, row_id)]
            for row_id, name in options[:PAGE_SIZE]]
    navigation = []
    if page:
        navigation.append(_button("Sebelumnya", tx, chat_id, action, page - 1))
    if len(options) > PAGE_SIZE:
        navigation.append(_button("Berikutnya", tx, chat_id, action, page + 1))
    if navigation:
        rows.append(navigation)
    rows.append([_button("Kembali", tx, chat_id, "menu")])
    return (title if options else "Belum ada pilihan. Kelola daftar di dashboard."), {"inline_keyboard": rows}


def handle_transaction_action(
    db: Session, user: User, chat_id: int, message_id: int, data: str, token: str,
    *, send_message: Callable[..., object], edit_message: Callable[..., object], format_rp: Callable[[int], str],
) -> None:
    from app.api.v1.endpoints.transactions import delete_transaction, update_transaction

    callback, _, signature = data.rpartition(":")
    parts = callback.split(":")
    if len(parts) != 4 or not all(part.isascii() and part.isdecimal() for part in (parts[1], parts[3])):
        return
    tx_id, action, value = int(parts[1]), parts[2], int(parts[3])
    tx = db.query(Transaction).filter(
        Transaction.id == tx_id, Transaction.user_id == user.id,
        Transaction.type.in_(("expense", "income")),
    ).with_for_update().first()
    if not tx:
        send_message(chat_id, "Transaksi ini sudah dihapus atau tidak tersedia.", parse_mode=None, bot_token=token)
        return
    if not hmac.compare_digest(signature, _signature(tx, chat_id, callback)):
        return

    title = "Transaksi tercatat"
    markup = correction_markup([tx], chat_id)
    if action in ("cats", "accs"):
        title, markup = _choices(db, tx, chat_id, action, value)
    elif action == "ask":
        title = "Batalkan transaksi ini?"
        markup = {"inline_keyboard": [[
            _button("Ya, batalkan", tx, chat_id, "del"),
            _button("Kembali", tx, chat_id, "menu"),
        ]]}
    elif action in ("cat", "acc", "del"):
        try:
            if action == "del":
                summary = f"{tx.description} · {format_rp(tx.amount)}"
                delete_transaction(tx_id, current_user=user, db=db)
                edit_message(chat_id, message_id, f"Transaksi dibatalkan.\n\n{summary}", {"inline_keyboard": []}, token)
                return
            if action == "cat":
                option = db.query(Category).filter(
                    Category.id == value, Category.user_id == user.id, Category.type == tx.type,
                ).first()
                payload = TransactionUpdate(category=option.name) if option else None
            else:
                option = db.query(Account).filter(
                    Account.id == value, Account.user_id == user.id, Account.is_archived.is_(False),
                ).first()
                payload = TransactionUpdate(account=option.name) if option else None
            if payload is None:
                db.rollback()
                send_message(chat_id, "Pilihan ini sudah tidak tersedia. Buka daftar lagi.", parse_mode=None, bot_token=token)
                return
            tx = update_transaction(tx_id, payload, current_user=user, db=db)
            title = "Transaksi diperbarui"
        except HTTPException as exc:
            db.rollback()
            send_message(chat_id, str(exc.detail), parse_mode=None, bot_token=token)
            return
    elif action not in ("open", "menu"):
        return

    text = f"{title}\n\n{tx.description} · {format_rp(tx.amount)}\nKategori: {tx.category}\nRekening: {tx.account}"
    db.rollback()  # Release row locks before sending a Telegram request.
    if action == "open":
        send_message(chat_id, text, parse_mode=None, reply_markup=markup, bot_token=token)
    else:
        edit_message(chat_id, message_id, text, markup, token)
