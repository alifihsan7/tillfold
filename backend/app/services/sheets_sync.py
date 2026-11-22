import os
from secrets import randbelow
import zoneinfo
from datetime import date, datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ledger import NEGATIVE_TYPES, OPENING_BALANCE_CATEGORY, POSITIVE_TYPES, signed_amount
from app.models.account import Account
from app.models.paycheck import PaycheckConfig
from app.models.pocket import Pocket
from app.models.transaction import Transaction
from app.models.user import User
from app.services.analytics import compute_safe_to_spend_metrics
from app.services.paycheck_cycles import recorded_cycle_ends

WIB = zoneinfo.ZoneInfo(settings.TIMEZONE)
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


def find_report_sheet(doc, title):
    worksheets = {sheet.title: sheet for sheet in doc.worksheets()}
    candidates = (title, f"{title} · Tillfold")
    for candidate in candidates:
        sheet = worksheets.get(candidate)
        if sheet is None:
            continue
        top = sheet.get("A1:B2")
        first = top[0][0] if top and top[0] else ""
        legacy = top[1][1] if len(top) > 1 and len(top[1]) > 1 else ""
        if first == REPORT_TITLE or (isinstance(legacy, str) and legacy.startswith(LEGACY_TITLE)):
            return candidate, sheet
    for candidate in candidates:
        if candidate not in worksheets:
            return candidate, None
    raise ValueError("Nama tab laporan sudah dipakai. Ganti nama salah satu tab lalu sinkronkan ulang.")


def sync_cycle_snapshot(db: Session, user_id: int, cycle_start_date: date | None = None) -> dict:
    from app.api.v1.endpoints.pockets import compute_pockets_summary, get_current_cycle_bounds

    user = db.query(User).filter(User.id == user_id).first()
    spreadsheet_id = (user.google_spreadsheet_id or "").strip() if user else ""
    if not spreadsheet_id:
        raise ValueError("Google Spreadsheet belum ditautkan. Kirim /set_sheet <link> di Telegram atau atur di Pengaturan.")

    now = datetime.now(WIB)
    cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == user_id).first()
    if cycle_start_date is None:
        cycle_start, cycle_end = get_current_cycle_bounds(db, user_id, now.date())
    else:
        cycle_start = cycle_start_date
        cycle_end = recorded_cycle_ends(db, user_id).get(cycle_start)
        if cycle_end is None:
            start, end = get_current_cycle_bounds(db, user_id, cycle_start)
            cycle_days = cfg.cycle_days if cfg and cfg.cycle_days and cfg.cycle_days > 0 else 14
            cycle_end = end if start == cycle_start else cycle_start + timedelta(days=cycle_days - 1)
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
    ).filter(Transaction.user_id == user_id).group_by(Transaction.account)}
    accounts_by_name = {account.name: account for account in accounts}
    account_rows = []
    for name in sorted(set(accounts_by_name) | set(balances), key=str.casefold):
        account = accounts_by_name.get(name)
        account_rows.append([
            name, ROLES.get(account.type, account.type) if account else None,
            balances.get(name, 0), "Diarsipkan" if account and account.is_archived else "Aktif" if account else "Riwayat",
        ])
    total_balance = sum(balances.values())

    pockets = db.query(Pocket).filter(Pocket.user_id == user_id).all()
    pocket_names = {pocket.id: pocket.name for pocket in pockets}
    pocket_account_ids = {pocket.account_id for pocket in pockets if pocket.is_active}
    pocket_rows = []
    for account in accounts:
        if account.id not in pocket_account_ids:
            continue
        summary = compute_pockets_summary(db, user_id, account.id, cycle_start, cycle_end, persist=False)
        pocket_rows.extend([
            account.name, pocket.name, ROLES.get(pocket.role, pocket.role),
            pocket.target_amount, pocket.allocation_amount, pocket.spent_amount, pocket.remaining_amount,
            pocket.subscription_name,
        ] for pocket in summary.pockets)

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
    section("Rekening · saldo saat sinkron", ["Rekening", "Jenis", "Saldo", "Status"],
            account_rows + [["Total saldo rekening", None, total_balance]], ((2, 3, CURRENCY),))
    section("Kantong · target dan alokasi saat sinkron",
            ["Rekening", "Kantong", "Jenis", "Target", "Dialokasikan", "Belanja periode", "Saldo tersisa", "Tagihan"],
            pocket_rows, ((3, 7, CURRENCY),), "Belum ada kantong.")
    section("Transaksi siklus",
            ["Tanggal", "Keterangan", "Kategori", "Rekening", "Tipe", "Nominal", "Kantong", "ID transaksi"], [
                [tx.date, tx.description, tx.category, tx.account,
                 "Saldo awal" if tx.type == "income" and tx.category == OPENING_BALANCE_CATEGORY else TRANSACTION_LABELS.get(tx.type, tx.type),
                 tx.amount if tx.type in POSITIVE_TYPES else -tx.amount if tx.type in NEGATIVE_TYPES else 0,
                 pocket_names.get(tx.pocket_id), tx.id]
                for tx in transactions
            ], ((0, 1, DATE_FORMAT), (5, 6, CURRENCY)), "Belum ada transaksi pada periode ini.")

    doc = get_google_sheets_client().open_by_key(spreadsheet_id)
    title = f"Siklus {format_date_short_id(cycle_start)} - {format_date_id(cycle_end)}"
    sheet_title, sheet = find_report_sheet(doc, title)
    sheet_id = sheet.id if sheet is not None else randbelow(2**31 - 1) + 1
    write_report(doc, sheet, sheet_id, sheet_title, rows, sections, number_ranges)

    return {
        "success": True,
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
    }


def write_report(doc, sheet, sheet_id, title, rows, sections, number_ranges):
    width = len(COLUMN_WIDTHS)
    row_count = max(sheet.row_count if sheet is not None else 100, len(rows))

    def grid(start, end, first=0, last=width):
        return {"sheetId": sheet_id, "startRowIndex": start, "endRowIndex": end,
                "startColumnIndex": first, "endColumnIndex": last}

    def style(area, fmt, fields="userEnteredFormat"):
        return {"repeatCell": {"range": area, "cell": {"userEnteredFormat": fmt}, "fields": fields}}

    ink = {"red": .08, "green": .10, "blue": .13}
    silver = {"red": .91, "green": .93, "blue": .95}
    white = {"red": 1, "green": 1, "blue": 1}
    props = {"sheetId": sheet_id, "gridProperties": {
        "rowCount": row_count, "columnCount": max(sheet.col_count, width) if sheet is not None else width,
        "frozenRowCount": 3,
    }}
    if sheet is None:
        requests = [{"addSheet": {"properties": {**props, "title": title}}}]
    else:
        requests = [{"updateSheetProperties": {
            "properties": props,
            "fields": "gridProperties(rowCount,columnCount,frozenRowCount)",
        }}, {"unmergeCells": {"range": grid(0, row_count)}}]
    requests.append({"updateCells": {
        "range": grid(0, row_count), "fields": "userEnteredValue,userEnteredFormat",
        "rows": [{"values": [sheet_value(value) for value in row]} for row in rows],
    }})
    requests.append(style(grid(0, 1), {
        "backgroundColor": ink, "textFormat": {"bold": True, "fontSize": 14, "foregroundColor": white},
    }))
    for start in sections:
        requests.extend([
            style(grid(start, start + 1), {
                "backgroundColor": silver, "textFormat": {"bold": True, "foregroundColor": ink},
            }),
            style(grid(start + 1, start + 2), {"textFormat": {"bold": True}, "wrapStrategy": "WRAP"}),
        ])
    for start, end, first, last, fmt in number_ranges:
        requests.append(style(grid(start, end, first, last), {"numberFormat": fmt}, "userEnteredFormat.numberFormat"))
    for index, pixels in enumerate(COLUMN_WIDTHS):
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": index, "endIndex": index + 1},
            "properties": {"pixelSize": pixels}, "fields": "pixelSize",
        }})
    doc.batch_update({"requests": requests})
