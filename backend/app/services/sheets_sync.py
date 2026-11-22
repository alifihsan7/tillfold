import os
import json
import logging
from collections import defaultdict
from hashlib import sha256
from secrets import randbelow
import zoneinfo
from datetime import date, datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ledger import NEGATIVE_TYPES, OPENING_BALANCE_CATEGORY, POSITIVE_TYPES, signed_amount
from app.models.account import Account
from app.models.paycheck import PaycheckConfig
from app.models.pocket import Pocket
from app.models.sheets_cycle import SheetsCycle
from app.models.transaction import Transaction
from app.models.user import User
from app.services.analytics import compute_safe_to_spend_metrics
from app.services.paycheck_cycles import recorded_cycle_ends

WIB = zoneinfo.ZoneInfo(settings.TIMEZONE)
logger = logging.getLogger(__name__)
REPORT_VERSION = 2
MONTH_NAMES_ID = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
REPORT_TITLE = "Tillfold · Laporan siklus"
LEGACY_TITLE = "TILLFOLD — LAPORAN SIKLUS "
COLUMN_WIDTHS = (175, 235, 155, 150, 150, 150, 145, 145)
CURRENCY = {"type": "CURRENCY", "pattern": '"Rp "#,##0;-"Rp "#,##0'}
DATE_FORMAT = {"type": "DATE", "pattern": "dd mmm yyyy"}
SHEETS_EPOCH = date(1899, 12, 30)
TRANSACTION_LABELS = {
    "income": "Pemasukan", "expense": "Pengeluaran",
    "transfer_in": "Transfer masuk", "transfer_out": "Transfer keluar",
    "adjustment_in": "Penyesuaian masuk", "adjustment_out": "Penyesuaian keluar",
}
ROLES = {
    "operasional": "Operasional", "gaji": "Gaji", "gajian": "Gajian", "tagihan": "Tagihan",
    "darurat": "Dana darurat", "tabungan": "Tabungan", "investasi": "Investasi",
    "ewallet": "Dompet digital", "e-wallet": "Dompet digital",
}


def format_date_short_id(value: date) -> str:
    return f"{value.day} {MONTH_NAMES_ID[value.month - 1]}"


def format_date_id(value: date) -> str:
    return f"{format_date_short_id(value)} {value.year}"


def get_google_sheets_client():
    creds_file = settings.GOOGLE_SERVICE_ACCOUNT_FILE
    if not os.path.exists(creds_file):
        raise FileNotFoundError(f"Service account file not found: {creds_file}")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return gspread.authorize(Credentials.from_service_account_file(creds_file, scopes=scopes))


def sheet_value(value):
    if isinstance(value, int):
        return {"userEnteredValue": {"numberValue": value}}
    if isinstance(value, date):
        return {"userEnteredValue": {"numberValue": (value - SHEETS_EPOCH).days}}
    if value is None or value == "":
        return {}
    return {"userEnteredValue": {"stringValue": str(value)}}


def is_report_sheet(sheet):
    top = sheet.get("A1:B2")
    first = top[0][0] if top and top[0] else ""
    legacy = top[1][1] if len(top) > 1 and len(top[1]) > 1 else ""
    return first == REPORT_TITLE or (isinstance(legacy, str) and legacy.startswith(LEGACY_TITLE))


def cycle_tab_title(start, end):
    return f"Siklus {format_date_short_id(start)} - {format_date_id(end)}"


def find_report_sheet(sheets, title):
    worksheets = {sheet.title: sheet for sheet in sheets}
    candidates = (title, f"{title} · Tillfold")
    for candidate in candidates:
        sheet = worksheets.get(candidate)
        if sheet is not None and is_report_sheet(sheet):
            return candidate, sheet
    for candidate in candidates:
        if candidate not in worksheets:
            return candidate, None
    raise ValueError("Nama tab laporan sudah dipakai. Ganti nama salah satu tab lalu sinkronkan ulang.")


def linked_spreadsheet(db, user_id):
    user = db.get(User, user_id)
    spreadsheet_id = (user.google_spreadsheet_id or "").strip() if user else ""
    if not spreadsheet_id:
        raise ValueError("Google Spreadsheet belum ditautkan. Kirim /set_sheet <link> di Telegram atau atur di Pengaturan.")
    return spreadsheet_id


def report_cycles(db, user_id, today):
    from app.api.v1.endpoints.analytics import list_available_cycles
    from app.api.v1.endpoints.pockets import get_current_cycle_bounds

    cycles = {
        date.fromisoformat(item["start"]): date.fromisoformat(item["end"])
        for item in list_available_cycles(db, user_id, today)
    }
    cycles.update(recorded_cycle_ends(db, user_id))
    # Preserve automatically generated cycles after a payroll configuration change.
    for state in db.query(SheetsCycle).filter_by(user_id=user_id):
        cycles.setdefault(state.cycle_start, state.cycle_end)
    for day in (today, today - timedelta(days=1)):
        start, end = get_current_cycle_bounds(db, user_id, day)
        cycles.setdefault(start, end)
    activity_days = db.query(Transaction.date).filter(
        Transaction.user_id == user_id, Transaction.date <= today,
    ).distinct().order_by(Transaction.date.desc())
    for (day,) in activity_days:
        if any(start <= day <= end for start, end in cycles.items()):
            continue
        start, end = get_current_cycle_bounds(db, user_id, day)
        if start <= day <= end:
            cycles.setdefault(start, end)
    return sorted(((start, end) for start, end in cycles.items() if start <= today), reverse=True)


def sync_all_cycles(db: Session, user_id: int, *, closed_only=False, now=None) -> dict:
    now = now or datetime.now(WIB)
    spreadsheet_id = linked_spreadsheet(db, user_id)
    cycles = report_cycles(db, user_id, now.date())
    if closed_only:
        done = {state.cycle_start: state.cycle_end for state in db.query(SheetsCycle).filter_by(
            user_id=user_id, spreadsheet_id=spreadsheet_id, exported_closed=True,
        )}
        cycles = [(start, end) for start, end in cycles if end < now.date() and done.get(start) != end]

    results = []
    workbook = None
    for start, end in cycles:
        result, workbook = sync_report(db, user_id, spreadsheet_id, start, end, now, workbook)
        results.append(result)
    updated = sum(item["updated"] for item in results)
    return {
        "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit",
        **(results[0] if results else {}),
        "success": True,
        "cycles_checked": len(results),
        "cycles_updated": updated,
        "cycles_skipped": len(results) - updated,
        "transaction_count": sum(item["transaction_count"] for item in results),
    }


def sync_closed_cycles():
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        users = [user_id for (user_id,) in db.query(User.id).filter(
            User.is_active.is_(True), User.google_spreadsheet_id.is_not(None),
        )]
    for user_id in users:
        with SessionLocal() as db:
            try:
                sync_all_cycles(db, user_id, closed_only=True)
            except Exception:
                logger.warning("Automatic Sheets sync failed for user %s", user_id, exc_info=True)


def sync_cycle_snapshot(db: Session, user_id: int, cycle_start_date: date | None = None) -> dict:
    from app.api.v1.endpoints.pockets import get_current_cycle_bounds

    if cycle_start_date is None:
        return sync_all_cycles(db, user_id)
    now = datetime.now(WIB)
    start, end = get_current_cycle_bounds(db, user_id, cycle_start_date)
    if start != cycle_start_date:
        cfg = db.query(PaycheckConfig).filter_by(user_id=user_id).first()
        end = cycle_start_date + timedelta(days=(cfg.cycle_days if cfg and cfg.cycle_days > 0 else 14) - 1)
    end = recorded_cycle_ends(db, user_id).get(cycle_start_date, end)
    result, _ = sync_report(db, user_id, linked_spreadsheet(db, user_id), cycle_start_date, end, now, None)
    return {**result, "cycles_checked": 1, "cycles_updated": int(result["updated"]), "cycles_skipped": int(not result["updated"])}


def sync_report(db, user_id, spreadsheet_id, cycle_start, cycle_end, now, workbook):
    from app.api.v1.endpoints.pockets import compute_pockets_summary

    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(7341951, :user_id)"), {"user_id": user_id})
    state = db.get(SheetsCycle, (user_id, cycle_start), populate_existing=True)
    if state is None:
        state = SheetsCycle(user_id=user_id, cycle_start=cycle_start, cycle_end=cycle_end)
        db.add(state)
    previous_end = state.cycle_end
    if state.cycle_end != cycle_end:
        state.closed_pockets = None
        state.exported_closed = False
    state.cycle_end = cycle_end
    closed = cycle_end < now.date()
    balance_date = min(now.date(), cycle_end)
    cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == user_id).first()
    cycle_range = f"{format_date_id(cycle_start)} – {format_date_id(cycle_end)}"

    accounts = db.query(Account).filter(Account.user_id == user_id).order_by(Account.name, Account.id).all()
    metrics = compute_safe_to_spend_metrics(db, user_id, cycle_start, cycle_end, "cycle", now.date(), accounts, cfg)
    transactions = db.query(Transaction).filter(
        Transaction.user_id == user_id, Transaction.date.between(cycle_start, cycle_end),
    ).order_by(Transaction.date.desc(), Transaction.id.desc()).all()
    income = sum(tx.amount for tx in transactions if tx.type == "income" and tx.category != OPENING_BALANCE_CATEGORY)
    opening = sum(tx.amount for tx in transactions if tx.type == "income" and tx.category == OPENING_BALANCE_CATEGORY)
    expense = sum(tx.amount for tx in transactions if tx.type == "expense")
    balances = {name: int(amount or 0) for name, amount in db.query(
        Transaction.account, func.sum(signed_amount()),
    ).filter(Transaction.user_id == user_id, Transaction.date <= balance_date).group_by(Transaction.account)}
    accounts_by_name = {account.name: account for account in accounts}
    account_rows = []
    for name in sorted(set(accounts_by_name) | set(balances), key=str.casefold):
        account = accounts_by_name.get(name)
        if closed and name not in balances:
            continue
        account_rows.append([
            name, ROLES.get(account.type, account.type) if account else None,
            balances.get(name, 0), "Diarsipkan" if account and account.is_archived else "Aktif" if account else "Riwayat",
        ])
    total_balance = sum(balances.values())

    pockets = db.query(Pocket).filter(Pocket.user_id == user_id).all()
    pocket_names = {pocket.id: pocket.name for pocket in pockets}
    pocket_account_ids = {pocket.account_id for pocket in pockets if pocket.is_active}
    pocket_rows = state.closed_pockets
    if pocket_rows is None:
        pocket_rows = []
        for account in accounts:
            if account.id not in pocket_account_ids:
                continue
            summary = compute_pockets_summary(db, user_id, account.id, cycle_start, cycle_end, persist=False, balance_through=balance_date)
            pocket_rows.extend([
                account.name, pocket.name, ROLES.get(pocket.role, pocket.role),
                pocket.target_amount, pocket.allocation_amount, pocket.spent_amount, pocket.remaining_amount,
                pocket.subscription_name,
            ] for pocket in summary.pockets)
        if cycle_end == now.date() - timedelta(days=1):
            state.closed_pockets = pocket_rows
    category_totals = defaultdict(lambda: [0, 0])
    for tx in transactions:
        if tx.type in ("income", "expense") and not (tx.type == "income" and tx.category == OPENING_BALANCE_CATEGORY):
            total = category_totals[tx.type, tx.category or "Tanpa kategori"]
            total[0] += tx.amount
            total[1] += 1
    categories = [
        [TRANSACTION_LABELS[kind], name, amount, count]
        for (kind, name), (amount, count) in sorted(
            category_totals.items(), key=lambda item: (item[0][0] == "expense", -item[1][0], item[0][1]),
        )
    ]

    rows = [
        [REPORT_TITLE], ["Periode", cycle_range],
        ["Disinkronkan", f"{format_date_id(now.date())}, {now:%H:%M} WIB"],
    ]
    sections = []
    number_ranges = []

    def section(title, headers, data, formats=(), empty=None):
        rows.append([])
        sections.append(len(rows))
        rows.extend([[title], headers])
        start_row = len(rows)
        rows.extend(data or ([[empty]] if empty else []))
        if data:
            number_ranges.extend((start_row, len(rows), first, last, fmt) for first, last, fmt in formats)

    section("Ringkasan siklus", ["Indikator", "Nilai"], [
        ["Pemasukan", income], ["Saldo awal tercatat", opening], ["Pengeluaran", expense],
        ["Arus kas bersih", income - expense],
        ["Rekening belanja", metrics.pocket_account],
        ["Anggaran belanja", metrics.pocket_budget],
        ["Belanja operasional", metrics.pocket_spent],
        ["Sisa anggaran", metrics.pocket_remaining],
        ["Batas belanja per hari", metrics.safe_daily if cycle_start <= now.date() <= cycle_end else None],
    ], ((1, 2, CURRENCY),))
    section("Rekening · saldo akhir siklus" if closed else "Rekening · saldo saat sinkron", ["Rekening", "Jenis", "Saldo", "Status"],
            account_rows + [["Total saldo rekening", None, total_balance]], ((2, 3, CURRENCY),))
    section("Kantong · saat siklus ditutup" if state.closed_pockets is not None else "Kantong · saat sinkron",
            ["Rekening", "Kantong", "Jenis", "Target", "Dialokasikan", "Belanja periode", "Saldo tersisa", "Tagihan"],
            pocket_rows, ((3, 7, CURRENCY),), "Belum ada kantong.")
    section("Kategori", ["Arus", "Kategori", "Total", "Jumlah transaksi"],
            categories, ((2, 3, CURRENCY),), "Belum ada pemasukan atau pengeluaran.")
    section("Transaksi siklus",
            ["Tanggal", "Keterangan", "Kategori", "Rekening", "Tipe", "Nominal", "Kantong", "ID transaksi"], [
                [tx.date, tx.description, tx.category, tx.account,
                 "Saldo awal" if tx.type == "income" and tx.category == OPENING_BALANCE_CATEGORY else TRANSACTION_LABELS.get(tx.type, tx.type),
                 tx.amount if tx.type in POSITIVE_TYPES else -tx.amount if tx.type in NEGATIVE_TYPES else 0,
                 pocket_names.get(tx.pocket_id), tx.id]
                for tx in transactions
            ], ((0, 1, DATE_FORMAT), (5, 6, CURRENCY)), "Belum ada transaksi pada periode ini.")

    content_hash = sha256(json.dumps([REPORT_VERSION, rows[:2], rows[3:]], ensure_ascii=False, default=str).encode()).hexdigest()
    try:
        if workbook is None:
            doc = get_google_sheets_client().open_by_key(spreadsheet_id)
            sheets = doc.worksheets()
        else:
            doc, sheets = workbook
        title = cycle_tab_title(cycle_start, cycle_end)
        known_sheet = None
        if state.spreadsheet_id == spreadsheet_id and state.sheet_id is not None:
            known_sheet = next((item for item in sheets if item.id == state.sheet_id), None)
            if known_sheet is None and workbook is not None:
                sheets = doc.worksheets()
                known_sheet = next((item for item in sheets if item.id == state.sheet_id), None)
        same_content = known_sheet is not None and state.content_hash == content_hash
        if known_sheet is not None and (same_content or is_report_sheet(known_sheet)):
            sheet_title, sheet = known_sheet.title, known_sheet
            if previous_end != cycle_end and sheet_title == cycle_tab_title(cycle_start, previous_end):
                if not any(item.title == title for item in sheets):
                    sheet_title = title
        else:
            sheet_title, sheet = find_report_sheet(sheets, title)
        sheet_id = sheet.id if sheet is not None else randbelow(2**31 - 1) + 1
        updated = not same_content
        if updated:
            write_report(doc, sheet, sheet_id, sheet_title, rows, sections, number_ranges)
    except Exception:
        # Keep the closing snapshot so the next sync preserves it.
        db.commit()
        raise
    state.spreadsheet_id = spreadsheet_id
    state.sheet_id = sheet_id
    state.content_hash = content_hash
    state.exported_closed = closed
    db.commit()

    return {
        "success": True,
        "updated": updated,
        "sheet_title": sheet_title,
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit#gid={sheet_id}",
        "synced_at": f"{format_date_id(now.date())} {now:%H:%M} WIB",
        "cycle_range": cycle_range,
        "transaction_count": len(transactions),
        "pocket_count": len(pocket_rows),
        "envelopes_count": len(pocket_rows),
        "pocket_spent": metrics.pocket_spent,
        "pocket_remaining": metrics.pocket_remaining,
        "total_balance": total_balance,
    }, (doc, sheets)


def write_report(doc, sheet, sheet_id, title, rows, sections, number_ranges):
    width = len(COLUMN_WIDTHS)
    row_count = max(sheet.row_count if sheet is not None else 100, len(rows))

    def grid(start, end, first=0, last=width):
        return {"sheetId": sheet_id, "startRowIndex": start, "endRowIndex": end,
                "startColumnIndex": first, "endColumnIndex": last}

    def style(area, fmt, fields="userEnteredFormat"):
        return {"repeatCell": {"range": area, "cell": {"userEnteredFormat": fmt}, "fields": fields}}

    ink = {"red": .08, "green": .10, "blue": .13}
    white = {"red": 1, "green": 1, "blue": 1}
    section_colors = [
        {"red": .86, "green": .91, "blue": .98},
        {"red": .88, "green": .94, "blue": .91},
        {"red": .94, "green": .90, "blue": .98},
        {"red": .98, "green": .93, "blue": .84},
        {"red": .88, "green": .93, "blue": .96},
    ]
    props = {"sheetId": sheet_id, "gridProperties": {
        "rowCount": row_count, "columnCount": max(sheet.col_count, width) if sheet is not None else width,
        "frozenRowCount": 3,
    }}
    if sheet is None:
        requests = [{"addSheet": {"properties": {**props, "title": title}}}]
    else:
        requests = [{"updateSheetProperties": {
            "properties": {**props, "title": title},
            "fields": "title,gridProperties(rowCount,columnCount,frozenRowCount)",
        }}, {"unmergeCells": {"range": grid(0, row_count)}}]
    requests.append({"updateCells": {
        "range": grid(0, row_count), "fields": "userEnteredValue,userEnteredFormat",
        "rows": [{"values": [sheet_value(value) for value in row]} for row in rows],
    }})
    requests.append(style(grid(0, 1), {
        "backgroundColor": ink, "textFormat": {"bold": True, "fontSize": 16, "foregroundColor": white},
        "verticalAlignment": "MIDDLE",
    }))
    for start in [0, *sections]:
        requests.append({"mergeCells": {"range": grid(start, start + 1), "mergeType": "MERGE_ALL"}})
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": start, "endIndex": start + 1},
            "properties": {"pixelSize": 40 if start == 0 else 29}, "fields": "pixelSize",
        }})
    for start, color in zip(sections, section_colors):
        requests.extend([
            style(grid(start, start + 1), {
                "backgroundColor": color, "textFormat": {"bold": True, "foregroundColor": ink},
                "verticalAlignment": "MIDDLE",
            }),
            style(grid(start + 1, start + 2), {"textFormat": {"bold": True}, "wrapStrategy": "WRAP"}),
        ])
    for index, row in enumerate(rows):
        if row and row[0] in ("Arus kas bersih", "Total saldo rekening"):
            requests.append(style(grid(index, index + 1), {
                "backgroundColor": {"red": .94, "green": .96, "blue": .98},
                "textFormat": {"bold": True, "foregroundColor": ink},
            }))
    for start, end, first, last, fmt in number_ranges:
        requests.append(style(grid(start, end, first, last), {"numberFormat": fmt}, "userEnteredFormat.numberFormat"))
    for index, pixels in enumerate(COLUMN_WIDTHS):
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": index, "endIndex": index + 1},
            "properties": {"pixelSize": pixels}, "fields": "pixelSize",
        }})
    doc.batch_update({"requests": requests})
