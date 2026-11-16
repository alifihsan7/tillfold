from sqlalchemy import case

from app.models.transaction import Transaction

POSITIVE_TYPES = ("income", "transfer_in", "adjustment_in")
NEGATIVE_TYPES = ("expense", "transfer_out", "adjustment_out")


def signed_amount():
    return case(
        (Transaction.type.in_(POSITIVE_TYPES), Transaction.amount),
        (Transaction.type.in_(NEGATIVE_TYPES), -Transaction.amount),
        else_=0,
    )


# Opening balances are stored as income rows so account balances stay a plain
# sum of the ledger, but they are not earnings: keep them out of income totals.
OPENING_BALANCE_CATEGORY = "Saldo Awal"


def is_opening_balance():
    return (Transaction.type == "income") & (Transaction.category == OPENING_BALANCE_CATEGORY)


def is_earned_income():
    return (Transaction.type == "income") & (Transaction.category != OPENING_BALANCE_CATEGORY)
