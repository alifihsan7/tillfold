"""Financial invariants reproduced during the November 2026 audit."""

from datetime import date
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.api.deps import get_current_user
from app.api.v1.endpoints import categories, transactions, accounts, goals, paycheck
from app.api.v1.endpoints.pockets import compute_pockets_summary, get_current_cycle_bounds
from app.core.ledger import signed_amount
from app.db.session import Base, get_db
from app.models.account import Account
from app.models.category import Category
from app.models.goal import Goal
from app.models.paycheck import PaycheckConfig
from app.models.pocket import Pocket
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.services.analytics import compute_safe_to_spend_metrics
from app.services.sheets_sync import report_cycles
START, END, TODAY = (date(2026, 11, 22), date(2026, 12, 5), date(2026, 11, 23))

@pytest.fixture
def isolated():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)

    @event.listens_for(engine, 'connect')
    def fk(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user = User(id=1, username='audit', full_name='Audit', hashed_password='dummy', is_active=True)
        db.add(user)
        db.flush()
        db.add_all([Account(id=1, user_id=1, name='Bank', type='operasional', initial_balance=0), Account(id=2, user_id=1, name='Cash', type='operasional', initial_balance=0)])
        db.add(PaycheckConfig(user_id=1, source_account='Bank', pocket_account='Bank', cycle_type='biweekly', cycle_days=14, cycle_start_date=START, use_gate=False))
        db.commit()
        app = FastAPI()
        for name, router in [('categories', categories.router), ('transactions', transactions.router), ('accounts', accounts.router), ('goals', goals.router), ('paycheck', paycheck.router)]:
            app.include_router(router, prefix='/' + name)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: user
        with TestClient(app) as client:
            yield (client, db, user)
    engine.dispose()

def tx(db, kind, amount, category='Lainnya', account='Bank', pocket_id=None, description='Audit', day=START):
    row = Transaction(user_id=1, type=kind, amount=amount, category=category, account=account, pocket_id=pocket_id, description=description, date=day)
    db.add(row)
    db.commit()
    return row

def seed_pockets(db):
    db.add_all([Pocket(id=1, user_id=1, account_id=1, name='Kantong Utama', slug='utama-1', role='operasional', target_amount=0), Pocket(id=2, user_id=1, account_id=1, name='Biaya rutin', slug='rutin', role='tagihan', target_amount=500000, allocation_amount=500000)])
    db.commit()

def metrics(db):
    return compute_safe_to_spend_metrics(db, 1, START, END, 'cycle', TODAY)

def test_category_rename_must_not_rename_other_type(isolated):
    c, db, _ = isolated
    db.add_all([Category(id=1, user_id=1, name='Hadiah', type='expense'), Category(id=2, user_id=1, name='Hadiah', type='income')])
    db.commit()
    tx(db, 'expense', 100000, category='Hadiah')
    income = tx(db, 'income', 200000, category='Hadiah')
    assert c.put('/categories/1', json={'name': 'Kado'}).status_code == 200
    db.refresh(income)
    assert income.category == 'Hadiah', f'Income silently renamed to {income.category}'

def test_category_delete_must_not_leave_subscription_reference(isolated):
    c, db, _ = isolated
    db.add(Category(id=1, user_id=1, name='Internet', type='expense'))
    db.add(Subscription(user_id=1, name='WiFi', category='Internet', account='Bank', amount=100000, billing_day=1))
    db.commit()
    r = c.delete('/categories/1')
    assert r.status_code in (400, 409), f'Deleted category without fallback while subscription still uses it: {r.status_code}'

def test_category_sync_must_create_same_name_for_both_types(isolated):
    _, db, _ = isolated
    tx(db, 'expense', 100, category='Hadiah')
    tx(db, 'income', 100, category='Hadiah')
    categories.sync_transaction_categories(db, 1)
    kinds = {r.type for r in db.query(Category).filter_by(user_id=1, name='Hadiah')}
    assert kinds == {'expense', 'income'}, f'Missing type: {kinds}'

def test_safe_to_spend_cannot_exceed_real_cash(isolated):
    _, db, _ = isolated
    seed_pockets(db)
    tx(db, 'income', 1000000, category='Gaji')
    tx(db, 'expense', 100000, category='Tagihan', description='Pembayaran listrik', pocket_id=2)
    cash = db.query(func.sum(signed_amount())).filter(Transaction.user_id == 1, Transaction.account == 'Bank').scalar()
    m = metrics(db)
    assert m.pocket_remaining <= cash, f'Allowance {m.pocket_remaining} exceeds bank cash {cash}'

def test_safe_to_spend_must_honor_explicit_protected_pocket(isolated):
    _, db, _ = isolated
    seed_pockets(db)
    tx(db, 'income', 1000000, category='Gaji')
    tx(db, 'expense', 100000, pocket_id=2)
    p = compute_pockets_summary(db, 1, 1, START, END, persist=False)
    assert next((x.spent_amount for x in p.pockets if x.id == 2)) == 100000
    assert metrics(db).pocket_spent == 0, 'Explicit bill pocket was charged as operational spending'

def test_account_breakdown_must_match_pocket_endpoint(isolated):
    c, db, _ = isolated
    seed_pockets(db)
    tx(db, 'income', 1000000, category='Gaji')
    tx(db, 'expense', 100000, pocket_id=2)
    p = compute_pockets_summary(db, 1, 1, START, END, persist=False)
    expected = next((x.balance for x in p.pockets if x.id == 2))
    r = c.get('/accounts')
    assert r.status_code == 200
    account = next((x for x in r.json() if x['id'] == 1))
    actual = next((x['balance'] for x in account['pockets'] if x['id'] == 2))
    assert actual == expected, f'Account shows {actual}, pockets show {expected}'

def test_goal_estimate_requires_evidence_of_saving_rate(isolated):
    c, _, _ = isolated
    r = c.post('/goals', json={'name': 'Manual', 'target_amount': 1000000, 'manual_current_amount': 0})
    assert r.status_code == 200
    assert r.json()['estimated_cycles'] is None, f'Invented estimate with no saving history: {r.json()['estimated_cycles']} cycles'

def test_goal_linked_account_is_exact_not_sql_pattern(isolated):
    c, db, _ = isolated
    db.add_all([Account(user_id=1, name='Bank_1', type='tabungan'), Account(user_id=1, name='BankA1', type='tabungan')])
    db.commit()
    tx(db, 'income', 100000, account='Bank_1')
    tx(db, 'income', 200000, account='BankA1')
    r = c.post('/goals', json={'name': 'Linked', 'target_amount': 1000000, 'linked_account': 'Bank_1'})
    assert r.status_code == 200
    assert r.json()['current_amount'] == 100000, f'Wrong accounts included: {r.json()['current_amount']}'

def test_receipt_must_reject_unknown_account(isolated):
    c, _, _ = isolated
    r = c.post('/transactions/receipts/record', json={'ref_number': 'audit-ref-unknown', 'merchant': 'Audit', 'amount': 10000, 'account': 'Missing bank', 'category': 'Test', 'date': str(TODAY), 'type': 'expense'})
    assert r.status_code in (400, 404, 409, 422), f'Unknown account silently recorded: {r.json()}'

def test_receipt_cannot_create_unpaired_transfer(isolated):
    c, db, _ = isolated
    r = c.post('/transactions/receipts/record', json={'ref_number': 'audit-ref-transfer', 'merchant': 'Audit', 'amount': 10000, 'account': 'Bank', 'category': 'Transfer', 'date': str(TODAY), 'type': 'transfer_in'})
    assert r.status_code in (400, 422), f'Unpaired transfer accepted ({r.status_code}), rows={db.query(Transaction).count()}'

def test_cycle_bounds_must_contain_historical_reference(isolated):
    _, db, _ = isolated
    reference = date(2026, 10, 15)
    start, end = get_current_cycle_bounds(db, 1, reference)
    assert start <= reference <= end, f'Historical {reference} mapped to {start}..{end}'

def test_sheets_must_include_historical_transactions_before_anchor(isolated):
    _, db, _ = isolated
    reference = date(2026, 10, 15)
    tx(db, 'expense', 100000, day=reference)
    cycles = report_cycles(db, 1, TODAY)
    assert any((start <= reference <= end for start, end in cycles)), f'No report covers older transaction: {cycles}'

def test_transaction_rejects_pocket_from_another_parent_account(isolated):
    c, db, _ = isolated
    seed_pockets(db)
    r = c.post('/transactions', json={'type': 'expense', 'amount': 100000, 'account': 'Cash', 'category': 'Test', 'description': 'Audit', 'date': str(TODAY), 'pocket_id': 2})
    assert r.status_code in (400, 409, 422), f'Cash expense linked to Bank pocket accepted: {r.status_code}'

def test_pocket_balances_do_not_refill_when_cycle_filter_changes(isolated):
    _, db, _ = isolated
    seed_pockets(db)
    tx(db, 'income', 1000000, category='Gaji')
    tx(db, 'expense', 100000, pocket_id=2)
    before = compute_pockets_summary(db, 1, 1, START, END, persist=False)
    after = compute_pockets_summary(db, 1, 1, date(2026, 12, 6), date(2026, 12, 19), persist=False)
    a = next((p.balance for p in before.pockets if p.id == 2))
    b = next((p.balance for p in after.pockets if p.id == 2))
    assert a == b, f'No allocation moved but bill pocket changed from {a} to {b}'

def test_paycheck_configuration_rejects_invalid_cycle_duration(isolated):
    c, _, _ = isolated
    r = c.put('/paycheck/config', json={'source_account': 'Bank', 'pocket_account': 'Bank', 'use_gate': False, 'gate_name': 'Gate', 'cycle_type': 'custom', 'cycle_days': 0, 'paycheck_day': 25})
    assert r.status_code in (400, 422), f'Zero-day cycle persisted: {r.status_code}'

def test_allocation_anchor_migration_preserves_cash_and_is_idempotent(isolated):
    from sqlalchemy import text
    from app.db.pocket_schema import ensure_pocket_schema
    c, db, _ = isolated
    seed_pockets(db)
    tx(db, 'income', 1000000, category='Gaji')
    tx(db, 'expense', 300000, pocket_id=2, day=date(2026, 10, 15))
    tx(db, 'expense', 100000, pocket_id=2)
    engine = db.get_bind()
    db.commit()
    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE pockets DROP COLUMN allocation_start_date'))
    ensure_pocket_schema(engine)
    db.expire_all()
    assert db.get(Pocket, 2).allocation_start_date == START
    current = compute_pockets_summary(db, 1, 1, START, END, persist=False)
    assert next((p.balance for p in current.pockets if p.id == 2)) == 400000
    assert current.total_remaining_amount == current.total_balance == 600000
    db.query(PaycheckConfig).filter_by(user_id=1).one().cycle_start_date = date(2026, 12, 6)
    db.commit()
    ensure_pocket_schema(engine)
    db.expire_all()
    assert db.get(Pocket, 2).allocation_start_date == START
    later = compute_pockets_summary(db, 1, 1, date(2026, 12, 6), date(2026, 12, 19), persist=False)
    assert next((p.balance for p in later.pockets if p.id == 2)) == 400000
    assert db.query(Transaction).count() == 3

def test_backup_preserves_anchor_and_upgrades_version_six(isolated):
    from app.services.backup import export_backup, validate_backup
    _, db, _ = isolated
    seed_pockets(db)
    db.get(Pocket, 2).allocation_start_date = START
    db.commit()
    payload = export_backup(db, 1)
    assert payload['version'] == 7
    parsed = validate_backup(payload)
    assert next((p['allocation_start_date'] for p in parsed['pockets'] if p['id'] == 2)) == START
    payload['version'] = 6
    payload['exported_at'] = '2026-11-23T00:00:00+00:00'
    for pocket in payload['data']['pockets']:
        pocket.pop('allocation_start_date')
    parsed = validate_backup(payload)
    assert all((p['allocation_start_date'] == START for p in parsed['pockets']))

def test_receipt_reference_wildcards_are_literal_and_archived_accounts_rejected(isolated):
    c, db, _ = isolated

    def record(reference, account='Bank'):
        return c.post('/transactions/receipts/record', json={'ref_number': reference, 'merchant': 'Audit', 'amount': 10000, 'account': account, 'category': 'Test', 'date': str(TODAY)})
    assert record('ABC123').status_code == 200
    second = record('ABC%')
    assert second.status_code == 200
    assert second.json()['already_recorded'] is False
    assert record('ABC%').json()['already_recorded'] is True
    assert db.query(Transaction).count() == 2
    db.get(Account, 2).is_archived = True
    db.commit()
    assert record('archived-account', 'Cash').status_code == 400
