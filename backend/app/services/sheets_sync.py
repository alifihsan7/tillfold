import os
import zoneinfo
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List

import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy.orm import Session
from sqlalchemy import func, case, desc

from app.core.config import settings
from app.models.transaction import Transaction
from app.core.ledger import POSITIVE_TYPES, NEGATIVE_TYPES
from app.models.account import Account
from app.models.paycheck import PaycheckConfig, PaycheckBucket
from app.models.user import User
from app.core.helpers import extract_spreadsheet_id

WIB = zoneinfo.ZoneInfo(settings.TIMEZONE)

# Indonesian month mapping
MONTH_NAMES_ID = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun",
    7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des"
}

def format_date_id(d: date) -> str:
    return f"{d.day} {MONTH_NAMES_ID[d.month]} {d.year}"

def format_date_short_id(d: date) -> str:
    return f"{d.day} {MONTH_NAMES_ID[d.month]}"

# Default envelope definitions for Mandiri
DEFAULT_ENVELOPES = [
    {"name": "Makan Harian", "categories": ["Makanan & Minuman", "Makan"], "limit": 450000},
    {"name": "Jajan & Kopi", "categories": ["Jajan / Ngopi", "Jajan"], "limit": 100000},
    {"name": "Laundry", "categories": ["Laundry"], "limit": 70000},
    {"name": "Galon & Air", "categories": ["Galon / Air", "Galon"], "limit": 44000},
]

ACCOUNT_FUNCTIONS = {
    "Bibit": "Portofolio Investasi Reksadana & Saham",
    "BRI 2": "Tabungan Dana Dingin Terkunci",
    "Mandiri": "Pos Belanja Operasional Harian",
    "BRI 1": "Penampung Gaji Masuk (Income Hub)",
    "Bank Jago": "Pos Tagihan Langganan Rutin & Gym"
}

def get_google_sheets_client():
    creds_file = settings.GOOGLE_SERVICE_ACCOUNT_FILE
    if not os.path.exists(creds_file):
        raise FileNotFoundError(f"Service account file not found: {creds_file}")
    
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
    return gspread.authorize(creds)

def sync_cycle_snapshot(
    db: Session,
    user_id: int,
    cycle_start_date: Optional[date] = None,
    envelopes_config: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Export snapshot siklus anggaran ke Google Sheets.
    Format Model C: Snapshot Dashboard Eksekutif.
    """
    now_wib = datetime.now(WIB)
    today_wib = now_wib.date()

    # 1. Tentukan tanggal siklus
    cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == user_id).first()
    cycle_days = cfg.cycle_days if cfg and cfg.cycle_days > 0 else 14
    pocket_account = cfg.pocket_account if cfg and cfg.pocket_account else "Mandiri"

    if not cycle_start_date:
        paycheck = db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.type == "income",
            (Transaction.category.in_(["Gajian", "Gaji", "Pemasukan", "Uang Saku Ortu", "Income"])) | (Transaction.description.ilike("%gajian%")) | (Transaction.description.ilike("%pemasukan%"))
        ).order_by(desc(Transaction.date), desc(Transaction.id)).first()
        cycle_start_date = paycheck.date if paycheck else today_wib

    cycle_end_date = cycle_start_date + timedelta(days=cycle_days - 1)
    query_end_date = cycle_end_date + timedelta(days=1)
    
    sheet_title = f"Siklus {format_date_short_id(cycle_start_date)} - {format_date_id(cycle_end_date)}"

    # 2. Ambil data ringkasan siklus
    totals = db.query(
        Transaction.type,
        func.coalesce(func.sum(Transaction.amount), 0).label("total")
    ).filter(
        Transaction.user_id == user_id,
        Transaction.date >= cycle_start_date,
        Transaction.date < query_end_date
    ).group_by(Transaction.type).all()

    income_total = 0
    expense_total = 0
    for r in totals:
        if r.type == "income":
            income_total = int(r.total)
        elif r.type == "expense":
            expense_total = int(r.total)

    # Mandiri Safe to Spend
    total_days = cycle_days
    if today_wib < cycle_start_date:
        day_of_cycle = 1
        days_remaining = total_days
    elif today_wib > cycle_end_date:
        day_of_cycle = total_days
        days_remaining = 0
    else:
        day_of_cycle = (today_wib - cycle_start_date).days + 1
        days_remaining = max(1, total_days - day_of_cycle + 1)

    pocket_spent_row = db.query(
        func.coalesce(func.sum(Transaction.amount), 0).label("spent")
    ).filter(
        Transaction.user_id == user_id,
        Transaction.account == pocket_account,
        Transaction.type == "expense",
        Transaction.date >= cycle_start_date,
        Transaction.date <= cycle_end_date
    ).first()
    pocket_spent = int(pocket_spent_row.spent if pocket_spent_row else 0)
    pocket_budget = int(getattr(cfg, "total_salary", 0) * 0.55) if cfg and getattr(cfg, "total_salary", None) else 825000
    if cfg and cfg.id:
        bucket_match = db.query(PaycheckBucket).join(
            PaycheckConfig, PaycheckBucket.config_id == PaycheckConfig.id
        ).filter(
            PaycheckConfig.user_id == user_id,
            PaycheckBucket.config_id == cfg.id,
            PaycheckBucket.account == pocket_account
        ).first()
        if bucket_match and bucket_match.percentage > 0 and getattr(cfg, "total_salary", None):
            pocket_budget = int(round(cfg.total_salary * (bucket_match.percentage / 100.0)))
    pocket_remaining = max(0, pocket_budget - pocket_spent)
    if days_remaining > 0:
        safe_daily = int(pocket_remaining / days_remaining)
    elif pocket_remaining > 0:
        overdue_days = max(1, (today_wib - cycle_end_date).days)
        grace_divisor = max(1, 3 - overdue_days + 1)
        safe_daily = int(pocket_remaining / grace_divisor)
    else:
        safe_daily = 0

    ideal_daily_rate = pocket_budget / total_days
    ideal_pace_today = int(ideal_daily_rate * day_of_cycle)
    if pocket_spent < ideal_pace_today * 0.9:
        pace_status = "ON TRACK (Hemat)"
    elif pocket_spent <= ideal_pace_today * 1.1:
        pace_status = "ON TRACK (Aman)"
    else:
        pace_status = "PERINGATAN (Overbudget)"

    # 3. Neraca Amplop Mandiri (Dinamis N Pos)
    active_envelopes = envelopes_config or DEFAULT_ENVELOPES
    envelope_results = []
    for env in active_envelopes:
        spent_row = db.query(
            func.coalesce(func.sum(Transaction.amount), 0).label("spent")
        ).filter(
            Transaction.user_id == user_id,
            Transaction.account == "Mandiri",
            Transaction.type == "expense",
            Transaction.date >= cycle_start_date,
            Transaction.date <= cycle_end_date,
            Transaction.category.in_(env["categories"])
        ).first()
        sp = int(spent_row.spent if spent_row else 0)
        lim = env["limit"]
        rem = lim - sp
        pct = (sp / lim) if lim > 0 else 0.0
        
        if pct > 0.85:
            ev_status = "Peringatan"
        elif pct > 0.5:
            ev_status = "Wajar"
        else:
            ev_status = "Sangat Hemat"
            
        envelope_results.append({
            "name": env["name"],
            "limit": lim,
            "spent": sp,
            "remaining": rem,
            "percentage": pct,
            "status": ev_status
        })

    # 4. Saldo Seluruh Rekening (All-time Net Worth)
    acc_rows = db.query(
        Transaction.account,
        func.sum(
            case(
                (Transaction.type.in_(POSITIVE_TYPES), Transaction.amount),
                (Transaction.type.in_(NEGATIVE_TYPES), -Transaction.amount),
                else_=0
            )
        ).label("balance")
    ).filter(
        Transaction.user_id == user_id
    ).group_by(Transaction.account).order_by(
        func.sum(
            case(
                (Transaction.type.in_(POSITIVE_TYPES), Transaction.amount),
                (Transaction.type.in_(NEGATIVE_TYPES), -Transaction.amount),
                else_=0
            )
        ).desc()
    ).all()
    user_accounts = db.query(Account).filter(Account.user_id == user_id).all()
    account_tags = {acc.name: (acc.tag or ACCOUNT_FUNCTIONS.get(acc.name, "Pos Finansial")) for acc in user_accounts}

    balance_map = {a.account: int(a.balance or 0) for a in acc_rows}
    for acc in user_accounts:
        if acc.name not in balance_map:
            balance_map[acc.name] = 0

    accounts = [{"account": name, "balance": bal} for name, bal in sorted(balance_map.items(), key=lambda x: x[1], reverse=True)]
    total_balance = sum(a["balance"] for a in accounts)

    # 5. Seluruh Transaksi dalam Siklus
    tx_rows = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.date >= cycle_start_date,
        Transaction.date <= cycle_end_date
    ).order_by(desc(Transaction.date), desc(Transaction.id)).all()

    # 6. Kirim ke Google Sheets
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.google_spreadsheet_id or not user.google_spreadsheet_id.strip():
        raise ValueError("Google Spreadsheet belum ditautkan. Kirim /set_sheet <link> di bot Telegram atau atur di menu Settings Web.")

    spreadsheet_id = user.google_spreadsheet_id.strip()
    client = get_google_sheets_client()
    doc = client.open_by_key(spreadsheet_id)

    # Cek apakah worksheet sudah ada
    ws = None
    for existing_ws in doc.worksheets():
        if existing_ws.title == sheet_title:
            ws = existing_ws
            ws.clear()
            break
        elif existing_ws.title == "Sheet1" and len(doc.worksheets()) == 1:
            ws = existing_ws
            ws.update_title(sheet_title)
            ws.clear()
            break

    total_rows_needed = max(100, len(tx_rows) + 70)
    if ws is None:
        ws = doc.add_worksheet(title=sheet_title, rows=total_rows_needed, cols=10)
    else:
        if ws.row_count < total_rows_needed:
            ws.add_rows(total_rows_needed - ws.row_count)

    # Siapkan baris data menggunakan NILAI NUMERIK RIIL (Mencegah Formula Syntax #ERROR!)
    rows = []
    # R1: kosong (index 0)
    rows.append(["", "", "", "", "", "", ""])
    # R2: Header Judul (index 1)
    rows.append(["", f"AI7 FINANCE — RAPOR SIKLUS {cycle_days}-HARI (SNAPSHOT)", "", "", "", "", ""])
    # R3: Sub Header (index 2)
    rows.append(["", f"Periode: {format_date_id(cycle_start_date)} – {format_date_id(cycle_end_date)}  •  Status Pacing: {pace_status}  •  Sinkronisasi: {now_wib.strftime('%d %b %Y %H:%M')} WIB", "", "", "", "", ""])
    # R4: Kosong (index 3)
    rows.append(["", "", "", "", "", "", ""])

    # R5: Seksi 1 Title (index 4)
    sec1_title_idx = len(rows)
    rows.append(["", "1. RINGKASAN EKSEKUTIF & PACING BELANJA", "", "", "", "", ""])
    # Header Tabel Seksi 1
    sec1_hdr_idx = len(rows)
    rows.append(["", "Indikator Keuangan", "", "Nilai (IDR)", "", "Keterangan", ""])
    # Data Seksi 1 (Numerik Riil)
    sec1_data_start = len(rows)
    rows.append(["", "Total Pemasukan Siklus", "", income_total, "", f"Gajian ({cycle_days} Hari) & Alokasi Pos", ""])
    rows.append(["", f"Plafon Belanja {pocket_account}", "", pocket_budget, "", f"Pos Saku Operasional {cycle_days} Hari", ""])
    rows.append(["", f"Realisasi Belanja {pocket_account}", "", pocket_spent, "", f"Hari ke-{day_of_cycle} dari {total_days} hari", ""])
    rows.append(["", "Sisa Saldo Aman Belanja", "", pocket_remaining, "", f"Batas aman: Rp {safe_daily:,.0f}/hari".replace(",", "."), ""])
    sec1_end_idx = len(rows) - 1

    rows.append(["", "", "", "", "", "", ""])
    rows.append(["", "", "", "", "", "", ""])

    # Seksi 2: Neraca Amplop Mandiri (Dinamis N Pos)
    num_envelopes = len(envelope_results)
    sec2_title_idx = len(rows)
    rows.append(["", f"2. NERACA AMPLOP BELANJA MANDIRI ({num_envelopes} POS)", "", "", "", "", ""])
    sec2_hdr_idx = len(rows)
    rows.append(["", "Nama Amplop", "Plafon Standar", "Realisasi Belanja", "Sisa Saldo", "% Terpakai", "Evaluasi"])
    sec2_data_start = len(rows)
    for env in envelope_results:
        rows.append([
            "",
            env["name"],
            env["limit"],
            env["spent"],
            env["remaining"],
            env["percentage"],
            env["status"]
        ])
    sec2_end_idx = len(rows) - 1

    rows.append(["", "", "", "", "", "", ""])
    rows.append(["", "", "", "", "", "", ""])

    # Seksi 3: Saldo Rekening & Net Worth
    sec3_title_idx = len(rows)
    rows.append(["", "3. SALDO SELURUH REKENING & PORTOFOLIO (NET WORTH)", "", "", "", "", ""])
    sec3_hdr_idx = len(rows)
    rows.append(["", "Nama Rekening / Pos", "", "Fungsi Alokasi", "", "Saldo Akhir", ""])
    sec3_data_start = len(rows)
    for acc in accounts:
        f_desc = account_tags.get(acc["account"], ACCOUNT_FUNCTIONS.get(acc["account"], "Pos Finansial"))
        rows.append([
            "",
            acc["account"],
            "",
            f_desc,
            "",
            acc["balance"],
            ""
        ])
    sec3_data_end = len(rows) - 1
    sec3_total_idx = len(rows)
    rows.append(["", "TOTAL KEKAYAAN BERSIH (NET WORTH)", "", "", "", total_balance, ""])

    rows.append(["", "", "", "", "", "", ""])
    rows.append(["", "", "", "", "", "", ""])

    # Seksi 4: Buku Kas Transaksi (Numerik Riil dengan Format Display)
    sec4_title_idx = len(rows)
    rows.append(["", f"4. BUKU KAS TRANSAKSI SIKLUS INI ({len(tx_rows)} CATATAN)", "", "", "", "", ""])
    sec4_hdr_idx = len(rows)
    rows.append(["", "Tanggal", "Keterangan", "Kategori", "Rekening", "Tipe", "Nominal"])
    sec4_data_start = len(rows)
    for tx in tx_rows:
        num_val = tx.amount if tx.type in POSITIVE_TYPES else -tx.amount
        rows.append([
            "",
            str(tx.date),
            tx.description or "-",
            tx.category or "-",
            tx.account or "-",
            tx.type.upper(),
            num_val
        ])
    sec4_end_idx = len(rows) - 1

    # Kirim semua data sel dalam satu batch request
    ws.update(range_name="A1", values=rows, value_input_option="USER_ENTERED")

    # Konfigurasi Dimensi & Margin Kolom
    col_widths = {
        0: 30,   # A: Margin
        1: 130,  # B: Tanggal / Label
        2: 240,  # C: Keterangan
        3: 170,  # D: Kategori / Plafon
        4: 150,  # E: Akun / Realisasi
        5: 140,  # F: Tipe / Sisa
        6: 150,  # G: Nominal / Status
    }
    batch_reqs = []
    for col_idx, width in col_widths.items():
        batch_reqs.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": ws.id,
                    "dimension": "COLUMNS",
                    "startIndex": col_idx,
                    "endIndex": col_idx + 1
                },
                "properties": {"pixelSize": width},
                "fields": "pixelSize"
            }
        })

    # Merged header ranges
    merge_ranges = [
        # Title B2:G2
        {"startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 1, "endColumnIndex": 7},
        # Subtitle B3:G3
        {"startRowIndex": 2, "endRowIndex": 3, "startColumnIndex": 1, "endColumnIndex": 7},
        # Section 1 Title
        {"startRowIndex": sec1_title_idx, "endRowIndex": sec1_title_idx + 1, "startColumnIndex": 1, "endColumnIndex": 7},
        # Section 2 Title
        {"startRowIndex": sec2_title_idx, "endRowIndex": sec2_title_idx + 1, "startColumnIndex": 1, "endColumnIndex": 7},
        # Section 3 Title
        {"startRowIndex": sec3_title_idx, "endRowIndex": sec3_title_idx + 1, "startColumnIndex": 1, "endColumnIndex": 7},
        # Section 3 Total Label
        {"startRowIndex": sec3_total_idx, "endRowIndex": sec3_total_idx + 1, "startColumnIndex": 1, "endColumnIndex": 5},
        {"startRowIndex": sec3_total_idx, "endRowIndex": sec3_total_idx + 1, "startColumnIndex": 5, "endColumnIndex": 7},
        # Section 4 Title
        {"startRowIndex": sec4_title_idx, "endRowIndex": sec4_title_idx + 1, "startColumnIndex": 1, "endColumnIndex": 7},
    ]

    for mr in merge_ranges:
        batch_reqs.append({
            "mergeCells": {
                "range": {
                    "sheetId": ws.id,
                    **mr
                },
                "mergeType": "MERGE_ALL"
            }
        })

    if batch_reqs:
        doc.batch_update({"requests": batch_reqs})

    # Batch formatting styling
    formats = [
        # 1. Main Title banner (Obsidian Dark)
        {
            "range": "B2:G2",
            "format": {
                "backgroundColor": {"red": 0.04, "green": 0.05, "blue": 0.07},
                "textFormat": {"bold": True, "fontSize": 15, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE"
            }
        },
        # 2. Subtitle banner
        {
            "range": "B3:G3",
            "format": {
                "backgroundColor": {"red": 0.10, "green": 0.12, "blue": 0.16},
                "textFormat": {"italic": True, "fontSize": 9, "foregroundColor": {"red": 0.85, "green": 0.88, "blue": 0.92}},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE"
            }
        },
        # 3. Section Titles
        {
            "range": f"B{sec1_title_idx + 1}:G{sec1_title_idx + 1}",
            "format": {
                "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": {"red": 0.07, "green": 0.08, "blue": 0.11}},
                "horizontalAlignment": "LEFT"
            }
        },
        {
            "range": f"B{sec2_title_idx + 1}:G{sec2_title_idx + 1}",
            "format": {
                "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": {"red": 0.07, "green": 0.08, "blue": 0.11}},
                "horizontalAlignment": "LEFT"
            }
        },
        {
            "range": f"B{sec3_title_idx + 1}:G{sec3_title_idx + 1}",
            "format": {
                "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": {"red": 0.07, "green": 0.08, "blue": 0.11}},
                "horizontalAlignment": "LEFT"
            }
        },
        {
            "range": f"B{sec4_title_idx + 1}:G{sec4_title_idx + 1}",
            "format": {
                "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": {"red": 0.07, "green": 0.08, "blue": 0.11}},
                "horizontalAlignment": "LEFT"
            }
        },
        # 4. Table Headers (Dark Slate #1E2433 with White text)
        {
            "range": f"B{sec1_hdr_idx + 1}:G{sec1_hdr_idx + 1}",
            "format": {
                "backgroundColor": {"red": 0.12, "green": 0.14, "blue": 0.20},
                "textFormat": {"bold": True, "fontSize": 10, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE"
            }
        },
        {
            "range": f"B{sec2_hdr_idx + 1}:G{sec2_hdr_idx + 1}",
            "format": {
                "backgroundColor": {"red": 0.12, "green": 0.14, "blue": 0.20},
                "textFormat": {"bold": True, "fontSize": 10, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE"
            }
        },
        {
            "range": f"B{sec3_hdr_idx + 1}:G{sec3_hdr_idx + 1}",
            "format": {
                "backgroundColor": {"red": 0.12, "green": 0.14, "blue": 0.20},
                "textFormat": {"bold": True, "fontSize": 10, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE"
            }
        },
        {
            "range": f"B{sec4_hdr_idx + 1}:G{sec4_hdr_idx + 1}",
            "format": {
                "backgroundColor": {"red": 0.12, "green": 0.14, "blue": 0.20},
                "textFormat": {"bold": True, "fontSize": 10, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE"
            }
        },
        # 5. Section 1 Number Formatting (Currency Rp #,##0)
        {
            "range": f"D{sec1_data_start + 1}:D{sec1_end_idx + 1}",
            "format": {
                "numberFormat": {"type": "CURRENCY", "pattern": "\"Rp \"#,##0"},
                "horizontalAlignment": "RIGHT",
                "textFormat": {"bold": True}
            }
        },
        # 6. Section 2 Number Formatting (Currency Rp #,##0 & Percent)
        {
            "range": f"C{sec2_data_start + 1}:E{sec2_end_idx + 1}",
            "format": {
                "numberFormat": {"type": "CURRENCY", "pattern": "\"Rp \"#,##0"},
                "horizontalAlignment": "RIGHT"
            }
        },
        {
            "range": f"F{sec2_data_start + 1}:F{sec2_end_idx + 1}",
            "format": {
                "numberFormat": {"type": "PERCENT", "pattern": "0.0%"},
                "horizontalAlignment": "CENTER",
                "textFormat": {"bold": True}
            }
        },
        {
            "range": f"G{sec2_data_start + 1}:G{sec2_end_idx + 1}",
            "format": {"horizontalAlignment": "CENTER", "textFormat": {"bold": True}}
        },
        # 7. Section 3 Number Formatting (Balances & Net Worth)
        {
            "range": f"F{sec3_data_start + 1}:F{sec3_data_end + 1}",
            "format": {
                "numberFormat": {"type": "CURRENCY", "pattern": "\"Rp \"#,##0"},
                "horizontalAlignment": "RIGHT",
                "textFormat": {"bold": True}
            }
        },
        {
            "range": f"B{sec3_total_idx + 1}:G{sec3_total_idx + 1}",
            "format": {
                "backgroundColor": {"red": 0.07, "green": 0.08, "blue": 0.11},
                "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": {"red": 0.96, "green": 0.62, "blue": 0.04}},
                "horizontalAlignment": "RIGHT",
                "verticalAlignment": "MIDDLE",
                "numberFormat": {"type": "CURRENCY", "pattern": "\"Rp \"#,##0"}
            }
        },
        # 8. Section 4 Alignments & Numeric Format with Sign Prefix (+ Rp ... / - Rp ...)
        {
            "range": f"B{sec4_data_start + 1}:B{sec4_end_idx + 1}",
            "format": {"horizontalAlignment": "CENTER"}
        },
        {
            "range": f"F{sec4_data_start + 1}:F{sec4_end_idx + 1}",
            "format": {"horizontalAlignment": "CENTER", "textFormat": {"bold": True, "fontSize": 9}}
        },
        {
            "range": f"G{sec4_data_start + 1}:G{sec4_end_idx + 1}",
            "format": {
                "numberFormat": {"type": "CURRENCY", "pattern": "\"+\" \"Rp \"#,##0;\"-\" \"Rp \"#,##0"},
                "horizontalAlignment": "RIGHT",
                "textFormat": {"bold": True}
            }
        }
    ]
    ws.batch_format(formats)

    spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit#gid={ws.id}"
    return {
        "success": True,
        "sheet_title": sheet_title,
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": spreadsheet_url,
        "synced_at": now_wib.strftime("%d %b %Y %H:%M WIB"),
        "cycle_range": f"{format_date_id(cycle_start_date)} s/d {format_date_id(cycle_end_date)}",
        "transaction_count": len(tx_rows),
        "envelopes_count": num_envelopes,
        "pocket_spent": pocket_spent,
        "pocket_remaining": pocket_remaining,
        "total_balance": total_balance
    }
