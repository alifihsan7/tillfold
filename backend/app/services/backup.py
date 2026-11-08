import json
import math
import re
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String
from sqlalchemy.orm import Session

from app.core.transfer import find_paired_transfer
from app.core.ledger import POSITIVE_TYPES, NEGATIVE_TYPES
from app.models.account import Account
from app.models.category import Category
from app.models.goal import Goal
from app.models.jago_pocket import JagoPocket
from app.models.paycheck import (
    LegacyPaycheckCycle, PaycheckBucket, PaycheckConfig, PaycheckCycle,
    PaycheckReceipt, PaycheckSession,
)
from app.models.subscription import Subscription, SubscriptionPayment
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.paycheck import PaycheckStep
from pydantic import ValidationError


MODELS = {
    "accounts": Account, "categories": Category, "transactions": Transaction,
    "subscriptions": Subscription, "goals": Goal, "paycheck_configs": PaycheckConfig,
    "paycheck_buckets": PaycheckBucket, "paycheck_sessions": PaycheckSession,
    "paycheck_cycles": PaycheckCycle, "legacy_paycheck_cycles": LegacyPaycheckCycle,
    "paycheck_receipts": PaycheckReceipt, "pockets": JagoPocket,
    "subscription_payments": SubscriptionPayment,
}
MAX_BYTES = 25 * 1024 * 1024
TAG = re.compile(r"\[(pair_id|paycheck_receipt):(\d+)\]")


def invalid():
    raise HTTPException(400, "File backup tidak valid atau relasi datanya tidak lengkap.")


def scoped(db, model, user_id):
    if model is PaycheckBucket:
        return db.query(model).filter(model.config_id.in_(
            db.query(PaycheckConfig.id).filter(PaycheckConfig.user_id == user_id),
        ))
    if model is PaycheckCycle:
        return db.query(model).filter(model.session_id.in_(
            db.query(PaycheckSession.id).filter(PaycheckSession.user_id == user_id),
        ))
    return db.query(model).filter(model.user_id == user_id)


def fields(model):
    return [column for column in model.__table__.columns if column.name != "user_id"]


def export_backup(db: Session, user_id: int):
    data = {}
    for name, model in MODELS.items():
        rows = []
        for obj in scoped(db, model, user_id).order_by(*model.__table__.primary_key.columns):
            row = {}
            for column in fields(model):
                value = getattr(obj, column.name)
                row[column.name] = value.isoformat() if isinstance(value, (date, datetime)) else value
            if model is Transaction and obj.type in ("transfer_in", "transfer_out"):
                pair = find_paired_transfer(db, obj)
                if pair:
                    raw = row["raw_text"] or ""
                    if re.search(r"\[pair_id:\d+\]", raw):
                        row["raw_text"] = re.sub(r"\[pair_id:\d+\]", f"[pair_id:{pair.id}]", raw)
                    else:
                        row["raw_text"] = f"[pair_id:{pair.id}] {raw}"
            rows.append(row)
        data[name] = rows
    return {"format": "tillfold-backup", "version": 3,
            "exported_at": datetime.now(timezone.utc).isoformat(), "data": data}


def decode_value(column, value):
    if value is None:
        if not column.nullable:
            invalid()
        return None
    kind = column.type
    if isinstance(kind, Boolean):
        if type(value) is not bool:
            invalid()
    elif isinstance(kind, Integer):
        if type(value) is not int or not -(2**63) <= value < 2**63:
            invalid()
        if column.name in ("id", "account_id", "subscription_id", "config_id", "session_id", "transaction_id") and value <= 0:
            invalid()
    elif isinstance(kind, Float):
        if type(value) not in (int, float) or not math.isfinite(value):
            invalid()
    elif isinstance(kind, DateTime):
        if not isinstance(value, str):
            invalid()
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            invalid()
    elif isinstance(kind, Date):
        if not isinstance(value, str):
            invalid()
        try:
            return date.fromisoformat(value)
        except ValueError:
            invalid()
    elif isinstance(kind, String):
        if not isinstance(value, str) or (kind.length and len(value) > kind.length):
            invalid()
    return value


def json_rows(value):
    try:
        rows = json.loads(value)
    except (ValueError, TypeError, RecursionError):
        invalid()
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        invalid()
    return rows


def validate_backup(payload):
    if not isinstance(payload, dict) or payload.get("format") != "tillfold-backup" or type(payload.get("version")) is not int or payload["version"] not in (1, 2, 3):
        invalid()
    data = payload.get("data")
    if isinstance(data, dict) and payload["version"] in (1, 2):
        if set(data) == set(MODELS) - {"subscription_payments"}:
            data = {**data, "subscription_payments": []}
        elif data.get("subscription_payments"):
            invalid()
    if not isinstance(data, dict) or set(data) != set(MODELS):
        invalid()
    parsed = {}
    count = 0
    for name, model in MODELS.items():
        if not isinstance(data[name], list):
            invalid()
        count += len(data[name])
        if count > 100_000:
            invalid()
        columns = fields(model)
        required = {column.name for column in columns}
        rows, keys = [], set()
        for row in data[name]:
            if not isinstance(row, dict) or set(row) != required:
                invalid()
            decoded = {column.name: decode_value(column, row[column.name]) for column in columns}
            key = tuple(decoded[column.name] for column in model.__table__.primary_key.columns if column.name != "user_id")
            if key in keys:
                invalid()
            keys.add(key)
            rows.append(decoded)
        parsed[name] = rows
    indexes = {name: {row["id"]: row for row in rows} for name, rows in parsed.items() if rows and "id" in rows[0]}
    for name, field, target in [
        ("paycheck_buckets", "config_id", "paycheck_configs"),
        ("paycheck_cycles", "session_id", "paycheck_sessions"),
        ("paycheck_receipts", "transaction_id", "transactions"),
        ("pockets", "account_id", "accounts"), ("pockets", "subscription_id", "subscriptions"),
        ("subscription_payments", "subscription_id", "subscriptions"),
        ("subscription_payments", "transaction_id", "transactions"),
    ]:
        for row in parsed[name]:
            if row[field] is not None and row[field] not in indexes.get(target, {}):
                invalid()
    if len(parsed["paycheck_configs"]) > 1:
        invalid()
    if len({row["name"] for row in parsed["accounts"]}) != len(parsed["accounts"]):
        invalid()
    if len({(row["name"], row["type"]) for row in parsed["categories"]}) != len(parsed["categories"]):
        invalid()
    if len({row["slug"] for row in parsed["pockets"]}) != len(parsed["pockets"]):
        invalid()
    linked = [row["subscription_id"] for row in parsed["pockets"] if row["subscription_id"] is not None]
    if len(linked) != len(set(linked)):
        invalid()
    paid_transactions, paid_periods = set(), set()
    for payment in parsed["subscription_payments"]:
        tx = indexes["transactions"][payment["transaction_id"]]
        period = (payment["subscription_id"], payment["period_key"])
        if payment["transaction_id"] in paid_transactions or (payment["subscription_id"] is not None and period in paid_periods):
            invalid()
        paid_transactions.add(payment["transaction_id"])
        paid_periods.add(period)
        if tx["type"] != "expense" or (tx["amount"], tx["account"], tx["date"]) != (payment["amount"], payment["account"], payment["paid_date"]):
            invalid()
    for row in parsed["transactions"]:
        if row["type"] not in (*POSITIVE_TYPES, *NEGATIVE_TYPES):
            invalid()
    for row in parsed["paycheck_sessions"]:
        for step in json_rows(row["steps_json"]):
            try:
                PaycheckStep.model_validate(step, strict=True)
            except ValidationError:
                invalid()
            tx_id = step.get("transaction_id")
            if tx_id is not None and type(tx_id) is not int:
                invalid()
    for row in parsed["paycheck_receipts"]:
        if indexes["transactions"][row["transaction_id"]]["type"] != "income":
            invalid()
        allocations = json_rows(row["allocations_json"])
        seen = set()
        for allocation in allocations:
            if set(allocation) != {"account_id", "amount", "transfer_id"}:
                invalid()
            if type(allocation["account_id"]) is not int or type(allocation["amount"]) is not int or allocation["amount"] < 0:
                invalid()
            if allocation["account_id"] in seen:
                invalid()
            seen.add(allocation["account_id"])
            if allocation["transfer_id"] is not None and type(allocation["transfer_id"]) is not int:
                invalid()
        if sum(item["amount"] for item in allocations) > indexes["transactions"][row["transaction_id"]]["amount"]:
            invalid()
    return parsed


def summary(data):
    balances = {row["name"]: 0 for row in data["accounts"]}
    for row in data["transactions"]:
        sign = 1 if row["type"] in POSITIVE_TYPES else -1
        balances[row["account"]] = balances.get(row["account"], 0) + sign * row["amount"]
    return {"counts": {name: len(rows) for name, rows in data.items()},
            "total_balance": sum(balances.values()), "balances": balances}


def restore_backup(db: Session, user: User, data):
    db.query(User).filter(User.id == user.id).with_for_update().one()
    populated = any(scoped(db, model, user.id).first() is not None for model in (
        Account, Transaction, Subscription, Goal, PaycheckSession, PaycheckReceipt, LegacyPaycheckCycle, SubscriptionPayment,
    ))
    from app.api.v1.endpoints.jago_pockets import DEFAULT_POCKET_SPECS

    defaults = {spec["slug"]: spec for spec in DEFAULT_POCKET_SPECS}
    for pocket in scoped(db, JagoPocket, user.id):
        spec = defaults.get(pocket.slug)
        if (not spec or pocket.account_id is not None or pocket.subscription_id is not None
                or pocket.name != spec["name"] or pocket.role != spec.get("role", "operasional")
                or pocket.target_amount != spec["default_target"] or not pocket.is_active):
            populated = True
    if populated:
        raise HTTPException(409, "Restore hanya tersedia untuk akun dengan data keuangan kosong.")
    # A new account may already have seeded categories and paycheck defaults.
    scoped(db, JagoPocket, user.id).delete(synchronize_session=False)
    scoped(db, PaycheckBucket, user.id).delete(synchronize_session=False)
    scoped(db, PaycheckConfig, user.id).delete(synchronize_session=False)
    scoped(db, Category, user.id).delete(synchronize_session=False)
    maps = {}
    for name, model in MODELS.items():
        maps[name] = {}
        for original in data[name]:
            row = dict(original)
            old_id = row.pop("id", None)
            if "user_id" in model.__table__.columns:
                row["user_id"] = user.id
            if name == "paycheck_buckets":
                row["config_id"] = maps["paycheck_configs"][row["config_id"]]
            elif name == "paycheck_cycles":
                row["session_id"] = maps["paycheck_sessions"][row["session_id"]]
            elif name == "paycheck_receipts":
                row["transaction_id"] = maps["transactions"][row["transaction_id"]]
                allocations = json_rows(row["allocations_json"])
                for item in allocations:
                    item["account_id"] = maps["accounts"].get(item["account_id"], -abs(item["account_id"]))
                    item["transfer_id"] = maps["transactions"].get(item["transfer_id"])
                row["allocations_json"] = json.dumps(allocations)
            elif name == "paycheck_sessions":
                steps = json_rows(row["steps_json"])
                for step in steps:
                    step["transaction_id"] = maps["transactions"].get(step.get("transaction_id"))
                row["steps_json"] = json.dumps(steps)
            elif name == "pockets":
                if row["account_id"] is not None:
                    row["account_id"] = maps["accounts"][row["account_id"]]
                if row["subscription_id"] is not None:
                    row["subscription_id"] = maps["subscriptions"][row["subscription_id"]]
            elif name == "subscription_payments":
                row["transaction_id"] = maps["transactions"][row["transaction_id"]]
                if row["subscription_id"] is not None:
                    row["subscription_id"] = maps["subscriptions"][row["subscription_id"]]
            obj = model(**row)
            db.add(obj)
            db.flush()
            if old_id is not None:
                maps[name][old_id] = obj.id
    for original in data["transactions"]:
        if original["raw_text"]:
            def remap(match):
                target = maps["transactions"].get(int(match[2]))
                return f"[{match[1]}:{target}]" if target is not None else ""
            db.get(Transaction, maps["transactions"][original["id"]]).raw_text = TAG.sub(remap, original["raw_text"])
    user.is_onboarded = True
    db.flush()
    result = summary(export_backup(db, user.id)["data"])
    if result != summary(data):
        raise HTTPException(400, "Saldo atau jumlah data hasil restore tidak cocok.")
    db.commit()
    return result
