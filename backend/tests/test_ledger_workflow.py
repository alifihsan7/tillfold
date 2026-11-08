from datetime import date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.api.v1.endpoints import accounts, analytics, paycheck, transactions
from app.db.session import Base, get_db
from app.models.account import Account
from app.models.paycheck import PaycheckConfig, PaycheckBucket
from app.models.transaction import Transaction
from app.models.user import User


@pytest.fixture
def ledger():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(id=1, username="ledger-test", full_name="Test User", hashed_password="unused", is_active=True)
        db.add(user)
        db.add_all([Account(user_id=1, name=name, type="operasional", tag="Test", color="amberGold", initial_balance=0)
                    for name in ("Bank", "Cash")])
        db.commit()
        app = FastAPI()
        app.include_router(transactions.router, prefix="/transactions")
        app.include_router(accounts.router, prefix="/accounts")
        app.include_router(analytics.router, prefix="/analytics")
        app.include_router(paycheck.router, prefix="/paycheck")
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: user
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, db
    engine.dispose()


def balances(client):
    response = client.get("/accounts")
    assert response.status_code == 200, response.text
    return {row["name"]: row["current_balance"] for row in response.json()}


def summary(client):
    response = client.get("/analytics/summary", params={"period_type": "custom", "start": "2026-11-01", "end": "2026-11-30"})
    assert response.status_code == 200, response.text
    return response.json()


def create(client, kind, amount, account="Bank"):
    response = client.post("/transactions", json={"type": kind, "amount": amount, "account": account,
                           "category": "Test", "description": "Data uji", "date": "2026-11-02"})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("cycle_type, expected_count", [("monthly_date", 1), ("biweekly", 2)])
def test_picker_lists_unique_cycles_and_only_one_active(ledger, cycle_type, expected_count):
    client, db = ledger
    today = datetime.now(analytics.WIB).date()
    cfg = paycheck.get_or_seed_config(db, 1)
    cfg.cycle_type = cycle_type
    cfg.cycle_days = 14
    cfg.paycheck_day = today.day
    for day in (today, today + timedelta(days=1)):
        db.add(Transaction(user_id=1, account="Bank", type="income", amount=100,
                           category="Gaji", description="Gaji", date=day))
    if cycle_type == "biweekly":
        db.add(Transaction(user_id=1, account="Bank", type="income", amount=100,
                           category="Gaji", description="Gaji", date=today - timedelta(days=1)))
        expected_count += 1
    db.commit()

    response = client.get("/analytics/periods")
    assert response.status_code == 200
    cycles = response.json()["cycles"]
    assert len({cycle["id"] for cycle in cycles}) == len(cycles) == expected_count
    assert [cycle["start"] for cycle in cycles if cycle["is_current"]] == [today.isoformat()]


def test_previous_week_summary_matches_selected_transactions(ledger):
    client, db = ledger
    today = datetime.now(analytics.WIB).date()
    this_monday = today - timedelta(days=today.weekday())
    last_monday = this_monday - timedelta(days=7)
    last_sunday = this_monday - timedelta(days=1)
    db.add_all([
        Transaction(user_id=1, account="Bank", type=kind, amount=amount,
                    category="Test", description="Data uji", date=day)
        for kind, amount, day in [
            ("income", 400, last_monday), ("expense", 100, last_sunday),
            ("income", 900, this_monday),
        ]
    ])
    db.commit()

    selected = client.get("/analytics/periods").json()["weeks"][1]
    response = client.get("/analytics/summary", params={
        "period_type": "week", "start": selected["start"], "end": selected["end"],
    })
    assert response.status_code == 200, response.text
    report = response.json()
    assert (report["start_date"], report["end_date"]) == (selected["start"], selected["end"])
    assert (report["income"], report["expense"]) == (400, 100)
    assert report["total_balance"] == 1200
    assert [row["date"] for row in report["daily_trend"]] == [selected["start"], selected["end"]]
    assert client.get("/analytics/summary", params={"period_type": "week"}).json()["income"] == 900


def test_short_month_payday_starts_cycle_on_last_day(ledger):
    from app.api.v1.endpoints.jago_pockets import get_current_cycle_bounds

    client, db = ledger
    cfg = paycheck.get_or_seed_config(db, 1)
    cfg.cycle_type = "monthly_date"
    cfg.paycheck_day = 31
    db.add(Transaction(user_id=1, account="Bank", type="income", amount=400,
                       category="Gaji", description="Gaji", date=date(2026, 2, 28)))
    db.commit()

    cycles = client.get("/analytics/periods").json()["cycles"]
    assert [(cycle["start"], cycle["end"]) for cycle in cycles] == [("2026-02-28", "2026-03-30")]
    report = client.get("/analytics/summary", params={"period_type": "cycle", "start": "2026-02-28"}).json()
    assert report["end_date"] == "2026-03-30"
    assert report["income"] == 400
    assert get_current_cycle_bounds(db, 1, date(2026, 2, 28)) == (date(2026, 2, 28), date(2026, 3, 30))


@pytest.mark.parametrize("delete_side", ["transfer_out", "transfer_in"])
def test_salary_is_recorded_once_and_allocation_is_a_paired_transfer(ledger, delete_side):
    client, db = ledger
    payload = {
        "request_key": "f73dd60b-c10a-4634-9e67-87808d01b9f8",
        "total_amount": 1_000_000, "date": date.today().isoformat(),
        "account": "Bank", "cycle_type": "biweekly",
    }
    first = client.post("/paycheck/record", json=payload)
    assert first.status_code == 201, first.text
    data = first.json()
    assert client.post("/paycheck/record", json=payload).json()["id"] == data["id"]
    assert balances(client)["Bank"] == 1_000_000
    assert client.get("/paycheck/record/latest").json()["id"] == data["id"]

    allocation = data["allocations"][0]
    url = f"/paycheck/record/{data['id']}/transfer/{allocation['account_id']}"
    assert client.post(url).status_code == 200
    assert client.post(url).status_code == 200
    assert balances(client)["Bank"] == 500_000
    assert balances(client)["Cash"] == 500_000
    assert sorted(tx.type for tx in db.query(Transaction).all()) == ["income", "transfer_in", "transfer_out"]
    assert client.get("/paycheck/record/latest").json() is None

    transfer = db.query(Transaction).filter_by(type=delete_side).one()
    deleted = client.delete(f"/transactions/{transfer.id}")
    assert deleted.status_code == 200
    assert len(deleted.json()["deleted_ids"]) == 2
    assert balances(client)["Bank"] == 1_000_000
    assert balances(client)["Cash"] == 0
    pending = client.get("/paycheck/record/latest").json()
    assert pending["id"] == data["id"]
    assert pending["allocations"][0]["transfer_id"] is None
    assert client.post(url).status_code == 200
    assert balances(client)["Bank"] == 500_000
    assert balances(client)["Cash"] == 500_000

    payload.update(request_key="b401d1cf-4d31-49c6-a4fc-8a9a13f4daf4", start_cycle=False)
    supplemental = client.post("/paycheck/record", json=payload)
    assert supplemental.status_code == 201
    assert supplemental.json()["cycle_end"] is None
    assert db.get(Transaction, supplemental.json()["id"]).category == "Gaji tambahan"


def test_salary_correction_preserves_paid_transfers_and_blocks_unsafe_delete(ledger):
    client, db = ledger
    db.add(Account(user_id=1, name="Tabungan", type="tabungan", initial_balance=0))
    db.commit()
    today = datetime.now(analytics.WIB).date().isoformat()
    receipt = client.post("/paycheck/record", json={
        "request_key": "b024d618-1c4f-463a-9f79-c82c46cd20b4", "total_amount": 900_000,
        "date": today, "account": "Bank", "cycle_type": "weekly",
    }).json()
    url = f"/transactions/{receipt['id']}"
    first, second = receipt["allocations"]
    result = client.post(f"/paycheck/record/{receipt['id']}/transfer/{first['account_id']}")
    assert result.status_code == 200
    paid = result.json()["allocations"][0]

    assert client.put(url, json={"amount": paid["amount"] - 1}).status_code == 409
    assert client.put(f"/transactions/{paid['transfer_id']}", json={"amount": 1}).status_code == 409
    assert client.delete(url).status_code == 409
    assert client.put(url, json={"amount": 750_000}).status_code == 200
    updated = client.get("/paycheck/record/latest").json()["allocations"]
    assert updated[0]["amount"] == paid["amount"]
    assert updated[1]["amount"] == second["amount"] * (750_000 - paid["amount"]) // (900_000 - paid["amount"])
    assert client.delete(f"/transactions/{paid['transfer_id']}").status_code == 200
    assert client.delete(url).status_code == 200
    assert client.get("/paycheck/record/latest").json() is None
    assert db.query(Transaction).count() == 0
    assert all(amount == 0 for amount in balances(client).values())


def test_daily_budget_uses_funded_payroll_allocation(ledger):
    client, db = ledger
    today = datetime.now(analytics.WIB).date().isoformat()
    cfg = paycheck.get_or_seed_config(db, 1)
    cfg.pocket_account = "Cash"
    db.commit()
    record = client.post("/paycheck/record", json={
        "request_key": "b026d619-1c4f-463a-9f79-c82c46cd20b4", "total_amount": 1_000_000,
        "date": today, "account": "Bank", "cycle_type": "biweekly",
    })
    assert record.status_code == 201, record.text
    receipt = record.json()

    def report():
        response = client.get("/analytics/summary", params={"period_type": "cycle", "start": today})
        assert response.status_code == 200, response.text
        return response.json()

    assert report()["safe_to_spend"]["pocket_budget"] == 0
    allocation = receipt["allocations"][0]
    assert client.post(f"/paycheck/record/{receipt['id']}/transfer/{allocation['account_id']}").status_code == 200
    expense = client.post("/transactions", json={
        "type": "expense", "amount": 100_000, "account": "Cash",
        "category": "Lainnya", "description": "Belanja", "date": today,
    })
    assert expense.status_code == 200
    result = report()
    safe = result["safe_to_spend"]
    assert result["income"] == 1_000_000
    assert (safe["pocket_budget"], safe["pocket_spent"], safe["pocket_remaining"]) == (500_000, 100_000, 400_000)
    assert safe["safe_daily"] == 400_000 // 14
    assert balances(client)["Cash"] == 400_000
    pockets = client.get(f"/accounts/{allocation['account_id']}/pockets", params={
        "cycle_start": today, "cycle_end": receipt["cycle_end"],
    })
    assert pockets.status_code == 200
    assert pockets.json()["total_pocket_balance"] == safe["pocket_remaining"]


@pytest.mark.parametrize("percentages, expected", [
    ((0, 25), (0, 250_000)),
    ((25, 0), (250_000, 0)),
])
def test_partial_paycheck_allocation_keeps_unassigned_salary(ledger, percentages, expected):
    client, db = ledger
    cfg = paycheck.get_or_seed_config(db, 1)
    cfg.pocket_account = "Cash"
    db.add_all([PaycheckBucket(config_id=cfg.id, account=name, percentage=pct,
                              purpose="Test", sort_order=i)
                for i, (name, pct) in enumerate(zip(("Bank", "Cash"), percentages))])
    db.commit()
    today = datetime.now(analytics.WIB).date().isoformat()
    response = client.post("/paycheck/record", json={
        "request_key": "4b6abb4c-079f-454b-b8b8-80d260f846b5", "total_amount": 1_000_000,
        "date": today, "account": "Bank", "cycle_type": "weekly",
    })
    assert response.status_code == 201, response.text
    receipt = response.json()
    assert sum(item["amount"] for item in receipt["allocations"]) == expected[1]
    for item in receipt["allocations"]:
        url = f"/paycheck/record/{receipt['id']}/transfer/{item['account_id']}"
        assert client.post(url).status_code == 200
        assert client.post(url).status_code == 200
    assert balances(client) == {"Bank": 1_000_000 - expected[1], "Cash": expected[1]}
    result = client.get("/analytics/summary", params={"period_type": "cycle", "start": today}).json()
    assert result["income"] == 1_000_000
    assert result["safe_to_spend"]["pocket_budget"] == expected[1]


def test_paycheck_rounding_never_funds_a_zero_percent_bucket():
    buckets = [PaycheckBucket(account=name, percentage=pct)
               for name, pct in (("Bank", 50), ("Cash", 50), ("Zero", 0))]
    amounts = paycheck.compute_bucket_amounts(3, buckets)
    assert sum(amounts.values()) == 3
    assert amounts["Zero"] == 0
    assert sorted((amounts["Bank"], amounts["Cash"])) == [1, 2]


@pytest.mark.parametrize("rows, status", [
    ([("Bank", -1)], 422),
    ([("Bank", 101)], 422),
    ([("Bank", 60), ("Cash", 50)], 400),
    ([("Cash", 20), ("Cash", 30)], 400),
    ([("Other user's bank", 50)], 400),
])
def test_invalid_salary_allocation_does_not_replace_saved_plan(ledger, rows, status):
    client, db = ledger
    original = client.get("/paycheck/config").json()["buckets"]
    response = client.put("/paycheck/buckets", json=[
        {"account": name, "percentage": pct, "purpose": "Test"} for name, pct in rows
    ])
    assert response.status_code == status, response.text
    assert client.get("/paycheck/config").json()["buckets"] == original


def test_default_change_preserves_legacy_cycle_dates(ledger):
    client, db = ledger
    cfg = paycheck.get_or_seed_config(db, 1)
    cfg.cycle_type = "monthly_date"
    cfg.paycheck_day = 25
    for day in (date(2025, 10, 25), date(2025, 11, 1)):
        db.add(Transaction(user_id=1, account="Bank", type="income", amount=100,
                           category="Gaji", description="Gaji", date=day))
    db.commit()

    config = client.get("/paycheck/config").json()["config"]
    config.update(cycle_type="weekly", cycle_days=7)
    assert client.put("/paycheck/config", json=config).status_code == 200
    cycles = client.get("/analytics/periods").json()["cycles"]
    assert [(cycle["start"], cycle["end"]) for cycle in cycles] == [("2025-10-25", "2025-11-24")]
    summary = client.get("/analytics/summary", params={"period_type": "cycle", "start": "2025-10-25"}).json()
    assert summary["end_date"] == "2025-11-24"
    assert summary["income"] == 200


def test_paycheck_cycle_override_and_saved_default(ledger):
    client, db = ledger
    first = client.post("/paycheck/session/start", json={
        "total_amount": 1_000_000, "date": "2026-10-01",
        "cycle_type": "custom", "cycle_days": 19,
    })
    assert first.status_code == 200, first.text
    assert client.get("/paycheck/config").json()["config"]["cycle_type"] == "monthly_date"
    report = client.get("/analytics/summary", params={"period_type": "cycle", "start": "2026-10-01"}).json()
    assert report["end_date"] == "2026-10-19"
    assert report["safe_to_spend"]["cycle_days"] == 19
    active = db.get(paycheck.PaycheckSession, first.json()["id"])
    active.status = "completed"
    db.commit()

    second = client.post("/paycheck/session/start", json={
        "total_amount": 1_000_000, "date": "2026-11-01",
        "cycle_type": "weekly", "save_cycle_default": True,
    })
    assert second.status_code == 200, second.text
    cfg = client.get("/paycheck/config").json()["config"]
    assert (cfg["cycle_type"], cfg["cycle_days"]) == ("weekly", 7)
    periods = client.get("/analytics/periods").json()["cycles"]
    ends = {period["start"]: period["end"] for period in periods}
    assert ends["2026-10-01"] == "2026-10-19"
    assert ends["2026-11-01"] == "2026-11-07"


def test_add_edit_delete_updates_accounts_and_summary(ledger):
    client, _ = ledger
    create(client, "income", 1000000)
    expense = create(client, "expense", 100000)
    assert balances(client)["Bank"] == 900000
    assert summary(client)["expense"] == 100000
    response = client.put(f'/transactions/{expense["id"]}', json={"amount": 250000, "account": "Cash"})
    assert response.status_code == 200, response.text
    assert balances(client) == {"Bank": 1000000, "Cash": -250000}
    assert summary(client)["total_balance"] == 750000
    assert client.delete(f'/transactions/{expense["id"]}').status_code == 200
    assert balances(client) == {"Bank": 1000000, "Cash": 0}
    assert summary(client)["expense"] == 0


def test_transfer_edit_and_delete_preserve_total_balance(ledger):
    client, _ = ledger
    create(client, "income", 1000000)
    response = client.post("/transactions/transfer", json={"from_account": "Bank", "to_account": "Cash", "amount": 200000, "date": "2026-11-02"})
    assert response.status_code == 200, response.text
    pair = response.json()
    response = client.put(f'/transactions/{pair["out_transaction_id"]}', json={"amount": 300000, "date": "2026-11-03"})
    assert response.status_code == 200, response.text
    assert balances(client) == {"Bank": 700000, "Cash": 300000}
    totals = summary(client)
    assert (totals["income"], totals["expense"], totals["total_balance"]) == (1000000, 0, 1000000)
    rows = client.get("/transactions").json()
    assert {row["date"] for row in rows if row["type"].startswith("transfer")} == {"2026-11-03"}
    response = client.delete(f'/transactions/{pair["in_transaction_id"]}')
    assert response.status_code == 200
    assert len(response.json()["deleted_ids"]) == 2
    assert balances(client) == {"Bank": 1000000, "Cash": 0}


def test_legacy_zero_amount_does_not_break_initial_transaction_load(ledger):
    client, db = ledger
    db.add(Transaction(user_id=1, type="income", amount=0, account="Bank", category="Gajian",
                       description="Alokasi lama nol", date=date(2026, 10, 1)))
    db.commit()
    create(client, "income", 1000000)
    response = client.get("/transactions", params={"limit": 100})
    assert response.status_code == 200, response.text
    assert any(row["amount"] == 0 for row in response.json())
    assert client.post("/transactions", json={"type": "income", "amount": 0, "account": "Bank", "category": "Test", "description": "Invalid"}).status_code == 422


def test_transfer_cannot_be_converted_to_expense_or_same_account(ledger):
    client, _ = ledger
    pair = client.post("/transactions/transfer", json={"from_account": "Bank", "to_account": "Cash", "amount": 200000}).json()
    assert client.put(f'/transactions/{pair["out_transaction_id"]}', json={"type": "expense"}).status_code == 400
    assert client.put(f'/transactions/{pair["out_transaction_id"]}', json={"account": "Cash"}).status_code == 400
    assert balances(client) == {"Bank": -200000, "Cash": 200000}


def test_paycheck_does_not_create_zero_allocation_transactions(ledger):
    client, db = ledger
    cfg = PaycheckConfig(user_id=1, source_account="Bank", cycle_days=14)
    db.add(cfg)
    db.flush()
    db.add_all([PaycheckBucket(config_id=cfg.id, account="Bank", percentage=0, purpose="Test", sort_order=0),
                PaycheckBucket(config_id=cfg.id, account="Cash", percentage=100, purpose="Test", sort_order=1)])
    db.commit()
    response = client.post("/transactions/paycheck", json={"total_amount": 1000000, "date": "2026-11-02"})
    assert response.status_code == 200, response.text
    assert [row["amount"] for row in response.json()["created_transactions"]] == [1000000]
    assert db.query(Transaction).filter(Transaction.amount == 0).count() == 0
    assert client.get("/transactions").status_code == 200
    assert balances(client) == {"Bank": 0, "Cash": 1000000}


@pytest.mark.parametrize("kind", ["transfer_in", "transfer_out"])
def test_manual_transaction_cannot_create_one_sided_transfer(ledger, kind):
    client, db = ledger
    response = client.post("/transactions", json={
        "type": kind, "amount": 100, "account": "Bank", "category": "Transfer", "description": "Test",
    })
    assert response.status_code == 400
    assert db.query(Transaction).count() == 0
    assert balances(client) == {"Bank": 0, "Cash": 0}


@pytest.mark.parametrize("account", ["Missing", "Peer", "", " Bank "])
def test_unknown_accounts_cannot_change_ledger(ledger, account):
    client, db = ledger
    db.add(User(id=2, username="peer", full_name="Peer", hashed_password="unused", is_active=True))
    db.flush()
    db.add(Account(user_id=2, name="Peer", type="operasional", initial_balance=0))
    db.commit()
    tx = create(client, "income", 1000)
    assert client.post("/transactions", json={
        "type": "expense", "amount": 100, "account": account, "category": "Test", "description": "Test",
    }).status_code == 400
    assert client.put(f"/transactions/{tx['id']}", json={"account": account}).status_code == 400
    for source, target in [("Bank", account), (account, "Cash")]:
        assert client.post("/transactions/transfer", json={
            "from_account": source, "to_account": target, "amount": 100,
        }).status_code == 400
    assert db.query(Transaction).count() == 1
    assert balances(client) == {"Bank": 1000, "Cash": 0}
    assert summary(client)["total_balance"] == 1000


@pytest.mark.parametrize("bad_link", ["missing", "wrong_reverse", "wrong_date", "same_account"])
def test_broken_transfer_link_never_deletes_an_unrelated_transfer(ledger, bad_link):
    client, db = ledger
    first = client.post("/transactions/transfer", json={"from_account": "Bank", "to_account": "Cash", "amount": 100}).json()
    second = client.post("/transactions/transfer", json={"from_account": "Bank", "to_account": "Cash", "amount": 100}).json()
    out = db.get(Transaction, first["out_transaction_id"])
    incoming = db.get(Transaction, first["in_transaction_id"])
    if bad_link == "missing":
        db.delete(incoming)
    elif bad_link == "wrong_reverse":
        incoming.raw_text = f"[pair_id:{second['out_transaction_id']}]"
    elif bad_link == "wrong_date":
        incoming.date = out.date - timedelta(days=1)
    else:
        incoming.account = out.account
    db.commit()
    assert client.put(f"/transactions/{out.id}", json={"amount": 150}).status_code == 400
    deleted = client.delete(f"/transactions/{out.id}").json()
    assert deleted["deleted_ids"] == [out.id]
    assert db.get(Transaction, second["out_transaction_id"]) is not None
    assert db.get(Transaction, second["in_transaction_id"]) is not None


def test_ambiguous_legacy_transfers_are_not_guessed(ledger):
    client, db = ledger
    from app.core.transfer import find_paired_transfer
    rows = [Transaction(user_id=1, type=kind, amount=100, account=account, category="Transfer",
                        description=description, raw_text="legacy", date=date(2026, 11, 2))
            for kind, account, description in [
                ("transfer_out", "Bank", "Transfer ke Cash: Test"),
                ("transfer_in", "Cash", "Transfer dari Bank: Test"),
                ("transfer_in", "Cash", "Transfer dari Bank: Test"),
            ]]
    db.add_all(rows)
    db.commit()
    assert all(find_paired_transfer(db, row) is None for row in rows)
    assert client.put(f"/transactions/{rows[0].id}", json={"amount": 200}).status_code == 400
    assert db.query(Transaction).count() == 3


@pytest.mark.parametrize("account_name", ["Bank", "Cash"])
def test_account_deletion_cannot_leave_half_a_transfer(ledger, account_name):
    client, db = ledger
    create(client, "income", 1000)
    pair = client.post("/transactions/transfer", json={"from_account": "Bank", "to_account": "Cash", "amount": 200}).json()
    account = db.query(Account).filter_by(user_id=1, name=account_name).one()
    assert client.delete(f"/accounts/{account.id}").status_code == 409
    assert balances(client) == {"Bank": 800, "Cash": 200}
    assert summary(client)["total_balance"] == 1000
    assert db.query(Transaction).count() == 3
    assert client.delete(f"/transactions/{pair['out_transaction_id']}").status_code == 200
    assert client.delete(f"/accounts/{account.id}").status_code == 200
