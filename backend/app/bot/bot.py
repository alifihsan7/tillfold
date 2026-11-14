import os
import sys
import re
import time
import logging
import requests
from datetime import datetime, date, timedelta
import calendar
import zoneinfo
import json
import uuid

logger = logging.getLogger("ai7-finance-bot")

from typing import Optional, List, Dict
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, case, event
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.parser import parse_transaction, parse_multi_transactions, parse_amount
from app.core.transfer import find_paired_transfer
from app.db.session import SessionLocal, Base, engine
from app.models.transaction import Transaction
from app.core.ledger import POSITIVE_TYPES, NEGATIVE_TYPES
from app.models.account import Account
from app.models.pocket import Pocket
from app.models.internal_loan import InternalLoan
from app.schemas.internal_loan import InternalLoanCreate, InternalLoanSettleRequest
from app.services.internal_loans import (
    create_internal_loan,
    settle_internal_loan,
    get_active_internal_loans,
    get_total_active_loan_amount,
    get_internal_loan_by_id,
)
from app.models.paycheck import PaycheckConfig, PaycheckBucket, PaycheckReceipt, PaycheckCycle
from app.models.subscription import Subscription
from app.models.goal import Goal
from app.models.user import User, TelegramProcessedMessage

from app.services.analytics import compute_safe_to_spend_metrics, resolve_pocket_account
from app.services.paycheck_cycles import recorded_cycle_ends, receipt_allocations
from app.api.v1.endpoints.analytics import get_monthly_date_bounds

API_BASE = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
WIB = zoneinfo.ZoneInfo(settings.TIMEZONE)

def format_rp(amount: int) -> str:
    return f"Rp {amount:,}".replace(",", ".")

def get_user_cycle_info(db: Session, user_id: int) -> dict:
    now_wib = datetime.now(WIB)
    today_wib = now_wib.date()

    cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == user_id).first()
    cycle_days = cfg.cycle_days if cfg and cfg.cycle_days and cfg.cycle_days > 0 else 14
    cycle_type = cfg.cycle_type if cfg and cfg.cycle_type else "biweekly"
    anchor_start = cfg.cycle_start_date if cfg and cfg.cycle_start_date else None
    paycheck_day = cfg.paycheck_day if cfg and cfg.paycheck_day else (anchor_start.day if anchor_start else 25)

    user_accs = db.query(Account).filter(Account.user_id == user_id).all()
    pocket_account = resolve_pocket_account(db, user_id, user_accs=user_accs, cfg=cfg)

    latest_paycheck = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.type == "income",
        Transaction.category.in_(["Gajian", "Gaji", "Pemasukan", "Uang Saku Ortu", "Income"]) | Transaction.description.ilike("%gajian%") | Transaction.description.ilike("%pemasukan%")
    ).order_by(desc(Transaction.date), desc(Transaction.id)).first()

    cycle_ends = recorded_cycle_ends(db, user_id)
    active_recorded_start = max((day for day, end in cycle_ends.items() if day <= today_wib <= end), default=None)

    if active_recorded_start:
        cycle_start = active_recorded_start
        cycle_end = cycle_ends[active_recorded_start]
        cycle_days = (cycle_end - cycle_start).days + 1
        cycle_label = f"Siklus {cycle_days} Hari"
    elif cycle_type == "monthly_date":
        cycle_start, cycle_end = get_monthly_date_bounds(today_wib, paycheck_day)
        cycle_days = (cycle_end - cycle_start).days + 1
        cycle_label = f"Siklus Bulanan (Tgl {paycheck_day})"
    else:
        if latest_paycheck and latest_paycheck.date:
            base_start = latest_paycheck.date
            if anchor_start and anchor_start > latest_paycheck.date:
                base_start = anchor_start
        elif anchor_start:
            base_start = anchor_start
        else:
            base_start = today_wib

        cycle_start = base_start
        cycle_end = cycle_start + timedelta(days=cycle_days - 1)
        if cycle_start in cycle_ends:
            cycle_end = cycle_ends[cycle_start]
            cycle_days = (cycle_end - cycle_start).days + 1

        if cycle_type == "weekly" or cycle_days == 7:
            cycle_label = "Siklus Mingguan"
        elif cycle_type == "biweekly" or cycle_days == 14:
            cycle_label = "Siklus 2-Mingguan"
        elif cycle_type == "monthly" or cycle_days == 30:
            cycle_label = "Siklus Bulanan (30 Hari)"
        else:
            cycle_label = f"Siklus {cycle_days} Hari"

    days_passed = (today_wib - cycle_start).days + 1
    day_of_cycle = min(cycle_days, max(1, days_passed))
    days_remaining = max(1, cycle_days - day_of_cycle + 1)

    return {
        "cfg": cfg,
        "cycle_type": cycle_type,
        "cycle_days": cycle_days,
        "cycle_label": cycle_label,
        "cycle_start": cycle_start,
        "cycle_end": cycle_end,
        "pocket_account": pocket_account,
        "day_of_cycle": day_of_cycle,
        "days_remaining": days_remaining,
        "latest_paycheck": latest_paycheck
    }

def get_pocket_envelopes(cycle_days: int) -> dict:
    base_ratio = cycle_days / 30.0
    # Plafon dasar (referensi 30 hari / 1 bulan)
    base_limits = {
        "Makanan & Minuman": 450000,
        "Jajan / Ngopi": 100000,
        "Laundry": 70000,
        "Galon & Air": 44000,
    }
    return {cat: int(round(limit * base_ratio)) for cat, limit in base_limits.items()}

# Backward compatibility alias
get_mandiri_envelopes = get_pocket_envelopes


def is_matching_pocket_account(acc_name: Optional[str], pocket_account: str) -> bool:
    if not acc_name:
        return False
    a_low = acc_name.strip().lower()
    p_low = pocket_account.strip().lower()
    if a_low == p_low:
        return True
    if a_low in ["mandiri", "saku", "operasional", "rekening utama"] and p_low in ["mandiri", "saku", "operasional", "rekening utama"]:
        return True
    return False


def get_pocket_account_variants(pocket_account: str) -> List[str]:
    variants = {pocket_account.strip().lower()}
    if pocket_account.strip().lower() in ["mandiri", "saku", "operasional", "rekening utama"]:
        variants.update(["mandiri", "saku", "operasional", "rekening utama"])
    return list(variants)

def get_safe_to_spend_snippet(db: Session, user_id: int) -> str:
    c_info = get_user_cycle_info(db, user_id=user_id)
    cycle_start = c_info["cycle_start"]
    cycle_end = c_info["cycle_end"]
    today_wib = datetime.now(WIB).date()

    metrics = compute_safe_to_spend_metrics(
        db=db,
        user_id=user_id,
        start_date=cycle_start,
        end_date=cycle_end,
        period_type="cycle",
        today_wib=today_wib,
        cfg=c_info["cfg"]
    )

    if metrics.pace_status in ("ahead", "on_track"):
        pace_icon = "🟢"
        pace_label = "Pace Aman"
    else:
        pace_icon = "🔴"
        pace_label = "Agak Boros"

    return f"🛡️ *Safe-to-Spend:* {format_rp(metrics.safe_daily)} / hari ({pace_icon} {pace_label} • Sisa {metrics.days_remaining} hari)"

def get_main_keyboard() -> dict:
    url = settings.APP_BASE_URL
    dashboard_btn = (
        {"text": "🚀 Buka Dashboard", "web_app": {"url": url}}
        if url.startswith("https://")
        else {"text": "🌐 Web Dashboard"}
    )
    return {
        "keyboard": [
            [{"text": "📊 Rekap"}, {"text": "💳 Saldo"}],
            [{"text": "🎯 Pacing"}, {"text": "🔔 Tagihan / Subs"}],
            [{"text": "🎯 Target & Goals"}, {"text": "🔄 Transfer"}],
            [{"text": "📜 Transaksi"}, {"text": "💰 Info Gajian"}],
            [dashboard_btn],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }

def setup_bot_commands():
    commands = [
        {"command": "menu", "description": "📱 Buka tombol menu navigasi"},
        {"command": "saldo", "description": "💳 Estimasi saldo seluruh rekening"},
        {"command": "pacing", "description": "🎯 Status burn rate & safe-to-spend"},
        {"command": "rekap", "description": "📊 Rekap pengeluaran & pacing (siklus/bulan)"},
        {"command": "goals", "description": "🎯 Target tabungan & milestone finansial"},
        {"command": "transfer", "description": "🔄 Transfer antar rekening"},
        {"command": "pinjam", "description": "💸 Catat & cek status dana talangan internal"},
        {"command": "lunasi", "description": "💳 Pelunasan dana talangan internal"},
        {"command": "subs", "description": "🔔 Jadwal langganan & tagihan rutin"},
        {"command": "transaksi", "description": "📜 5 transaksi terakhir"},
        {"command": "gajian", "description": "💰 Catat gajian & siapkan alokasi pos"},
        {"command": "sheets", "description": "📑 Sinkronisasi snapshot ke Google Sheets"},
        {"command": "set_sheet", "description": "🔗 Tautkan link Google Sheet pribadi"},
        {"command": "batal", "description": "↩️ Hapus/batalkan transaksi terakhir"},
        {"command": "help", "description": "ℹ️ Panduan cara input bot"},
    ]
    try:
        requests.post(f"{API_BASE}/setMyCommands", json={"commands": commands}, timeout=10)
    except Exception as e:
        print(f"Error registering bot commands: {e}")

    url = settings.APP_BASE_URL
    if url.startswith("https://"):
        try:
            requests.post(
                f"{API_BASE}/setChatMenuButton",
                json={
                    "menu_button": {
                        "type": "web_app",
                        "text": "📊 Dashboard",
                        "web_app": {"url": url}
                    }
                },
                timeout=10
            )
        except Exception as e:
            print(f"Error registering bot menu button: {e}")

def send_message(chat_id: int, text: str, parse_mode: Optional[str] = "Markdown", reply_to_message_id: Optional[int] = None, reply_markup: Optional[dict] = None, bot_token: Optional[str] = None):
    token = bot_token or settings.TELEGRAM_BOT_TOKEN
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        res = requests.post(url, json=payload, timeout=10)
        data = res.json()
        if not data.get("ok"):
            print(f"Telegram API warning sending message to {chat_id}: {data}")
            if parse_mode:
                payload.pop("parse_mode", None)
                retry_res = requests.post(url, json=payload, timeout=10)
                return retry_res.json()
        return data
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

def handle_menu(chat_id: int, bot_token: Optional[str] = None):
    msg = "📱 **Menu Tillfold**\n\nGunakan tombol di bawah atau ketik pengeluaran lo, misalnya `makan siang 25k`."
    send_message(chat_id, msg, reply_markup=get_main_keyboard(), bot_token=bot_token)

def send_dashboard_link(chat_id: int, bot_token: Optional[str] = None):
    url = settings.APP_BASE_URL
    if url.startswith("https://"):
        inline_kb = {
            "inline_keyboard": [
                [{"text": "🚀 Buka Mini App (In-App)", "web_app": {"url": url}}],
                [{"text": "🔗 Buka di Browser Luar", "url": url}]
            ]
        }
        msg = f"🌐 **Dashboard Tillfold**\n`{url}`\n\nBuka dashboard lewat tombol di bawah."
    else:
        inline_kb = {
            "inline_keyboard": [
                [{"text": "🚀 Buka Web Dashboard", "url": url}]
            ]
        }
        msg = f"🌐 **Dashboard Tillfold**\n`{url}`\n\nLihat laporan dan detail transaksi."
    send_message(chat_id, msg, reply_markup=inline_kb, bot_token=bot_token)

def handle_start(chat_id: int, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return
    user_name = user.full_name or "Kawan"
    msg = f"""👋 **Halo, {user_name}! Selamat datang di Tillfold.**

Bot ini terhubung ke akun Tillfold lo.

💡 **Cara Input Praktis:**
• ✍️ **Ketik Teks Bebas:** `nasi padang 25k`, `kopi tuku 22k`, `laundry 35rb`, `isi galon 8k`
• 📸 **Kirim Foto Struk / QRIS:** Cukup kirim foto struk belanja kasir atau screenshot QRIS
• 🎙️ **Kirim Voice Note:** Rekam suara lo (misal: *"beli makan siang 28 ribu pakai saku"*)
• 🔄 **Transfer Rekening:** `tf 100k utama ke tabungan`

📌 **Perintah Tersedia:**
• `/saldo` - Estimasi saldo per rekening & total net worth
• `/pacing` - Status laju pengeluaran & sisa safe-to-spend
• `/rekap` - Rekap pengeluaran & pacing sesuai siklus budget (atau `/rekap bulan`, `/rekap lalu`)
• `/transaksi` - 5 transaksi terakhir
• `/batal` - Hapus/batalkan transaksi terakhir jika salah
• `/subs` - Cek jadwal langganan & tagihan rutin
• `/goals` - Pantau target finansial & milestone
• `/gajian [nominal]` - Catat gajian & siapkan rencana alokasi rekening
• `/transfer` - Pindahkan saldo antar rekening
• `/pinjam` - Catat atau cek status dana talangan internal
• `/lunasi` - Pelunasan dana talangan internal
• `/menu` - Tampilkan tombol menu cepat

Tinggal ketik catatan pengeluaran/pemasukan lo kapan saja!"""
    send_message(chat_id, msg, reply_markup=get_main_keyboard(), bot_token=bot_token)

def handle_rekap(
    chat_id: int,
    db: Session,
    text: Optional[str] = None,
    user: Optional[User] = None,
    bot_token: Optional[str] = None,
    **kwargs
):
    if isinstance(text, User):
        user = text
        text = kwargs.get("text", None)

    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return
    user_id = user.id
    now = datetime.now(WIB)

    # Tentukan mode: cycle (default), month, atau prev_cycle
    mode = "cycle"
    if text:
        clean_text = text.strip().lower()
        if any(k in clean_text for k in ["bulan", "month"]):
            mode = "month"
        elif any(k in clean_text for k in ["lalu", "prev", "sebelum", "kemarin"]):
            mode = "prev_cycle"

    c_info = get_user_cycle_info(db, user_id=user_id)
    cycle_days = c_info["cycle_days"]
    cycle_type = c_info["cycle_type"]
    cycle_label = c_info["cycle_label"]
    cfg = c_info.get("cfg")
    paycheck_day = cfg.paycheck_day if cfg and cfg.paycheck_day else 25

    if mode == "month":
        month_names = [
            "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"
        ]
        month_name = month_names[now.month]
        start_date = date(now.year, now.month, 1)
        next_month = date(now.year + 1, 1, 1) if now.month == 12 else date(now.year, now.month + 1, 1)
        end_date = next_month - timedelta(days=1)
        header_title = f"📊 **Rekap Keuangan — Bulan {month_name} {now.year}**"
        period_sub = f"📅 Periode: `{start_date.strftime('%d %b')} s/d {end_date.strftime('%d %b %Y')}` (Bulan Kalender)"
    elif mode == "prev_cycle":
        cur_cycle_start = c_info["cycle_start"]
        prev_end = cur_cycle_start - timedelta(days=1)
        cycle_ends = recorded_cycle_ends(db, user_id)
        prev_candidates = [(s, e) for s, e in cycle_ends.items() if e < cur_cycle_start]
        if prev_candidates:
            start_date, end_date = max(prev_candidates, key=lambda item: item[1])
        elif cycle_type == "monthly_date":
            start_date, end_date = get_monthly_date_bounds(prev_end, paycheck_day)
        else:
            end_date = prev_end
            start_date = end_date - timedelta(days=cycle_days - 1)

        dur_days = (end_date - start_date).days + 1
        header_title = f"📊 **Rekap Keuangan — Siklus Sebelumnya ({dur_days} Hari)**"
        period_sub = f"📅 Periode: `{start_date.strftime('%d %b')} s/d {end_date.strftime('%d %b %Y')}` (Siklus Lalu)"
    else:  # mode == "cycle"
        start_date = c_info["cycle_start"]
        end_date = c_info["cycle_end"]
        day_of_cycle = c_info["day_of_cycle"]
        days_remaining = c_info["days_remaining"]
        header_title = f"📊 **Rekap Keuangan — {cycle_label}**"
        period_sub = (
            f"📅 Periode: `{start_date.strftime('%d %b')} s/d {end_date.strftime('%d %b %Y')}` "
            f"(Hari ke-{day_of_cycle}/{cycle_days} • Sisa {days_remaining} hari)"
        )

    totals = db.query(
        Transaction.type,
        func.coalesce(func.sum(Transaction.amount), 0).label("total")
    ).filter(
        Transaction.user_id == user_id,
        Transaction.date >= start_date,
        Transaction.date <= end_date
    ).group_by(Transaction.type).all()

    income_total = 0
    expense_total = 0
    for r in totals:
        if r.type == "income":
            income_total = int(r.total)
        elif r.type == "expense":
            expense_total = int(r.total)

    net_total = income_total - expense_total

    cat_rows = db.query(
        Transaction.category,
        func.sum(Transaction.amount).label("total"),
        func.count(Transaction.id).label("count")
    ).filter(
        Transaction.user_id == user_id,
        Transaction.date >= start_date,
        Transaction.date <= end_date,
        Transaction.type == "expense"
    ).group_by(Transaction.category).order_by(func.sum(Transaction.amount).desc()).all()

    lines = [
        f"{header_title}\n{period_sub}\n",
        f"💰 **Total Pemasukan:** {format_rp(income_total)}",
        f"💸 **Total Pengeluaran:** {format_rp(expense_total)}",
        f"📈 **Net Cashflow:** {format_rp(net_total)}\n",
        "📂 **Rincian Pengeluaran per Kategori:**"
    ]

    if not cat_rows:
        period_name = "siklus ini" if mode == "cycle" else ("bulan ini" if mode == "month" else "siklus tersebut")
        lines.append(f"_Belum ada pengeluaran yang tercatat {period_name}._")
    else:
        for cat in cat_rows:
            pct = (int(cat.total) / expense_total * 100) if expense_total > 0 else 0
            lines.append(f"• **{cat.category or 'Lain-lain'}**: {format_rp(int(cat.total))} ({pct:.0f}%, {cat.count}x)")

    if mode == "cycle":
        lines.append(f"\n{get_safe_to_spend_snippet(db, user_id=user_id)}")
        lines.append("\n💡 _Tips: Ketik `/rekap bulan` untuk kalender, atau `/rekap lalu` untuk siklus sebelumnya._")
    elif mode == "prev_cycle":
        lines.append("\n💡 _Tips: Ketik `/rekap` untuk kembali ke siklus aktif saat ini._")
    else:
        lines.append("\n💡 _Tips: Ketik `/rekap` untuk melihat rekap siklus budget aktif._")

    send_message(chat_id, "\n".join(lines), reply_markup=get_main_keyboard(), bot_token=bot_token)

def handle_saldo(chat_id: int, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return
    user_id = user.id
    from app.api.v1.endpoints.accounts import ensure_default_accounts
    ensure_default_accounts(db, user_id)

    # Real ledger balance from transactions
    acc_rows = db.query(
        Transaction.account,
        func.sum(
            case(
                (Transaction.type.in_(POSITIVE_TYPES), Transaction.amount),
                (Transaction.type.in_(NEGATIVE_TYPES), -Transaction.amount),
                else_=0
            )
        ).label("balance")
    ).filter(Transaction.user_id == user_id).group_by(Transaction.account).all()
    balance_map = {r.account: int(r.balance or 0) for r in acc_rows}

    accounts = db.query(Account).filter(Account.user_id == user_id).order_by(Account.id.asc()).all()
    if not accounts:
        send_message(chat_id, "ℹ️ Belum ada data rekening terdaftar.", bot_token=bot_token)
        return

    all_user_pockets = db.query(Pocket).filter(
        Pocket.user_id == user_id,
        Pocket.is_active == True,
    ).all()

    pocket_by_account: dict[int, list[Pocket]] = {}
    for p in all_user_pockets:
        if p.account_id:
            pocket_by_account.setdefault(p.account_id, []).append(p)

    lines = ["💳 **Estimasi Saldo per Rekening & Kantong:**\n"]
    total = 0

    for acc in accounts:
        bal = balance_map.get(acc.name, 0)
        total += bal
        tag_str = f" • _{acc.tag}_" if acc.tag else ""
        lines.append(f"• **{acc.name}**: {format_rp(bal)}{tag_str}")

        acc_pockets = pocket_by_account.get(acc.id, [])
        if not acc_pockets and any(k in acc.name.lower() for k in ["kantong", "pocket", "jago"]):
            acc_pockets = [p for p in all_user_pockets if p.account_id is None]

        if acc_pockets:
            sub_pockets = [p for p in acc_pockets if not p.slug.startswith("utama")]
            sum_sub_bal = sum(int(p.balance or 0) for p in sub_pockets)
            for p in acc_pockets:
                if p.slug.startswith("utama"):
                    p_amt = max(0, bal - sum_sub_bal)
                else:
                    p_amt = int(p.balance or 0)
                role_icon = "🛍️" if p.role == "operasional" else "🔒"
                lines.append(f"  └ {role_icon} {p.name}: {format_rp(p_amt)}")

    lines.append(f"\n💵 **Total Keseluruhan:** {format_rp(total)}")

    total_active_loan_amount = get_total_active_loan_amount(db, user_id)
    if total_active_loan_amount > 0:
        lines.append(f"\n⚠️ **Dana Talangan Aktif:** {format_rp(total_active_loan_amount)}\n(Ketik /pinjam untuk melihat rincian kewajiban)")

    lines.append(f"\n{get_safe_to_spend_snippet(db, user_id=user_id)}")
    send_message(chat_id, "\n".join(lines), bot_token=bot_token)

def handle_pacing(chat_id: int, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return
    user_id = user.id
    now_wib = datetime.now(WIB)
    today_wib = now_wib.date()
    c_info = get_user_cycle_info(db, user_id=user_id)
    cycle_start = c_info["cycle_start"]
    cycle_end = c_info["cycle_end"]
    cycle_label = c_info["cycle_label"]

    metrics = compute_safe_to_spend_metrics(
        db=db,
        user_id=user_id,
        start_date=cycle_start,
        end_date=cycle_end,
        period_type="cycle",
        today_wib=today_wib,
        cfg=c_info["cfg"]
    )

    pocket_budget = metrics.pocket_budget
    pocket_spent = metrics.pocket_spent
    pocket_remaining = metrics.pocket_remaining
    safe_daily = metrics.safe_daily
    day_of_cycle = metrics.day_of_cycle
    days_remaining = metrics.days_remaining
    cycle_days = metrics.cycle_days
    pocket_account = metrics.pocket_account

    ratio = min(1.0, pocket_spent / pocket_budget) if pocket_budget > 0 else 0
    filled = int(round(ratio * 10))
    bar = f"[{'█' * filled}{'░' * (10 - filled)}] {int(ratio * 100)}%"

    if metrics.pace_status == "ahead":
        pace_status = "🟢 On Track (Pengeluaran hemat & terkontrol)"
    elif metrics.pace_status == "on_track":
        pace_status = "🟢 On Track (Pengeluaran sesuai laju harian)"
    else:
        pace_status = "🔴 Pacing Warning (Pengeluaran melebihi laju harian)"

    lines = [
        f"🎯 **AI7.Steward — Status Pacing Belanja ({cycle_label})**",
        f"📅 Siklus: `{cycle_start} s/d {cycle_end}` (Hari ke-{day_of_cycle}/{cycle_days})",
        f"🕒 `{now_wib.strftime('%d %B %Y - %H:%M WIB')}`",
        "──────────────────────────────",
        f"💳 **Rekening Kantong:** `{pocket_account}`",
        f"📊 **Burn Rate:** `{bar}`",
        f"• Terpakai: `{format_rp(pocket_spent)}` / `{format_rp(pocket_budget)}`",
        f"• Sisa Budget Siklus: **{format_rp(pocket_remaining)}** ({days_remaining} hari lagi)",
        f"• Batas Aman Belanja: **{format_rp(safe_daily)} / hari**",
        "",
        f"🛡️ **Status Disiplin:** {pace_status}",
    ]
    send_message(chat_id, "\n".join(lines), bot_token=bot_token)

def handle_obsidian(chat_id: int, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return
    user_id = user.id
    if user_id != 1:
        send_message(chat_id, "ℹ️ Fitur ekspor Obsidian hanya aktif untuk akun utama Alif.", bot_token=bot_token)
        return

    now_wib = datetime.now(WIB)
    today_wib = now_wib.date()
    vault_path = "/home/alifihsan/SecondBrainAI7"
    finance_dir = os.path.join(vault_path, "2 Areas", "Finance")
    os.makedirs(finance_dir, exist_ok=True)

    c_info = get_user_cycle_info(db, user_id=user_id)
    cycle_start = c_info["cycle_start"]
    cycle_end = c_info["cycle_end"]
    cycle_days = c_info["cycle_days"]
    pocket_account = c_info["pocket_account"]

    metrics = compute_safe_to_spend_metrics(
        db=db,
        user_id=user_id,
        start_date=cycle_start,
        end_date=cycle_end,
        period_type="cycle",
        today_wib=today_wib,
        cfg=c_info["cfg"]
    )

    pocket_budget = metrics.pocket_budget
    pocket_spent = metrics.pocket_spent
    pocket_remaining = metrics.pocket_remaining
    safe_daily = metrics.safe_daily
    day_of_cycle = metrics.day_of_cycle
    days_remaining = metrics.days_remaining

    accounts = db.query(Account).filter(Account.user_id == user_id).order_by(Account.id.asc()).all()
    acc_rows = db.query(
        Transaction.account,
        func.sum(
            case(
                (Transaction.type.in_(POSITIVE_TYPES), Transaction.amount),
                (Transaction.type.in_(NEGATIVE_TYPES), -Transaction.amount),
                else_=0
            )
        ).label("balance")
    ).filter(Transaction.user_id == user_id).group_by(Transaction.account).all()
    bal_map = {r.account: int(r.balance or 0) for r in acc_rows}

    filename = f"Siklus_{cycle_start}_sd_{cycle_end}.md"
    file_path = os.path.join(finance_dir, filename)

    doc = f"""---
type: finance-cycle
cycle_start: {cycle_start}
cycle_end: {cycle_end}
budget: "{pocket_budget}"
spent: "{pocket_spent}"
remaining: "{pocket_remaining}"
updated_at: "{now_wib.strftime('%Y-%m-%d %H:%M:%S WIB')}"
tags: [finance, cycle-snapshot, operasional, pacing]
---

# 🏛️ Laporan Siklus Keuangan: {cycle_start} s/d {cycle_end}

> Diekspor secara otomatis oleh **AI7.Steward** pada {now_wib.strftime('%d %B %Y, %H:%M WIB')}.

## 🎯 Ringkasan Pacing Kantong ({pocket_account})
- **Hari Siklus:** H-{day_of_cycle}/{cycle_days} ({days_remaining} hari tersisa)
- **Alokasi Budget Kantong:** {format_rp(pocket_budget)}
- **Total Belanja Terpakai:** {format_rp(pocket_spent)}
- **Sisa Budget Siklus:** {format_rp(pocket_remaining)}
- **Safe-to-Spend Harian:** {format_rp(safe_daily)} / hari

---

## 💳 Posisi Saldo Rekening
| Rekening | Estimasi Saldo |
| --- | --- |
"""
    for a in accounts:
        doc += f"| {a.name} | {format_rp(bal_map.get(a.name, 0))} |\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(doc)

    cmd = f'cd "{vault_path}" && git add . && git commit -m "finance: sync cycle snapshot {cycle_start} sd {cycle_end}" && git push origin main'
    os.system(cmd)

    send_message(
        chat_id,
        f"✅ **Snapshot Finansial Berhasil Diekspor ke Obsidian!**\n\n"
        f"📄 File: `SecondBrainAI7/2 Areas/Finance/{filename}`\n"
        f"🔄 Berhasil di-commit dan di-push ke GitHub!\n"
        f"Safe-to-Spend saat ini: **{format_rp(safe_daily)} / hari** 🛡️",
        bot_token=bot_token
    )

def handle_transaksi(chat_id: int, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return
    user_id = user.id
    recent = db.query(Transaction).filter(Transaction.user_id == user_id).order_by(desc(Transaction.id)).limit(5).all()
    if not recent:
        send_message(chat_id, "ℹ️ Belum ada riwayat transaksi.", bot_token=bot_token)
        return

    lines = ["🕒 **5 Transaksi Terakhir:**\n"]
    for t in recent:
        icon = "💰" if t.type == "income" else "💸"
        time_str = t.created_at.astimezone(WIB).strftime("%Y-%m-%d %H:%M") if t.created_at else str(t.date)
        if t.type in ("adjustment_in", "adjustment_out"):
            icon = "Penyesuaian (+)" if t.type == "adjustment_in" else "Penyesuaian (-)"
        lines.append(f"{icon} **{t.description}** ({t.category})\n   {format_rp(t.amount)} via `{t.account}` • _{time_str}_\n")

    send_message(chat_id, "\n".join(lines), bot_token=bot_token)

def handle_subs(chat_id: int, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return
    user_id = user.id
    from app.models.subscription import Subscription
    from app.api.v1.endpoints.subscriptions import compute_due_info, monthly_commitment_twelfths
    from app.services.subscription_payments import payment_status

    subs = db.query(Subscription).filter(Subscription.user_id == user_id, Subscription.is_active == True).all()
    if not subs:
        send_message(chat_id, "ℹ️ Belum ada langganan / tagihan rutin yang aktif.", bot_token=bot_token)
        return

    now_date = datetime.now(WIB).date()
    lines = ["💳 **Daftar Langganan & Tagihan Rutin:**\n"]
    total = 0

    # Sort subs by due date: active, soonest days_until_due
    def get_sort_key(s):
        days, _ = compute_due_info(s, now_date)
        return (days is None, days if days is not None else 999)

    subs.sort(key=get_sort_key)

    for s in subs:
        payment = payment_status(db, s, now_date)
        if not (s.billing_type == "exact_date" and payment["is_paid"]):
            total += monthly_commitment_twelfths(s)
        days_until, next_date = compute_due_info(s, now_date)
        if days_until is None:
            due_str = "Atur tanggal tagihan tahunan"
        elif (s.billing_type or "fixed_day") == "exact_date" and s.exact_due_date:
            if days_until < 0:
                due_str = f"❌ **Expired ({abs(days_until)} hari lalu)**"
            elif days_until == 0:
                due_str = "🚨 **Berakhir HARI INI!**"
            elif days_until <= 3:
                due_str = f"⚠️ Berakhir {days_until} hari lagi (`{next_date}`)"
            else:
                due_str = f"⏳ Berakhir tgl {next_date} ({days_until} hari lagi)"
        else:
            if days_until == 0:
                due_str = "🚨 **Jatuh tempo HARI INI!**"
            elif days_until <= 3:
                due_str = f"⚠️ Jatuh tempo {days_until} hari lagi (`{next_date}`)"
            else:
                due_str = f"🗓️ {next_date} ({days_until} hari lagi)"

        if payment["is_paid"]:
            due_str = f"Lunas periode ini pada {payment['paid_date']} ({format_rp(payment['paid_amount'])})"
        unit = "periode" if (s.billing_type or "fixed_day") == "exact_date" else "tahun" if s.billing_cycle == "yearly" else "bulan"
        cycle_badge = " [Tahunan]" if s.billing_cycle == "yearly" else ""
        account_str = f" • `{s.account}`" if s.account else ""
        lines.append(f"• **{s.name}**: {format_rp(s.amount)}/{unit}{cycle_badge}\n  └ {due_str} ({s.category}{account_str})")

    lines.append(f"\n💵 **Total Komitmen Bulanan:** {format_rp((total + 6) // 12)}")
    send_message(chat_id, "\n".join(lines), bot_token=bot_token)

def handle_goals(chat_id: int, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return
    user_id = user.id
    from app.models.goal import Goal
    from app.api.v1.endpoints.goals import compute_goal_metrics

    goals = db.query(Goal).filter(Goal.user_id == user_id, Goal.is_active == True).order_by(Goal.id.asc()).all()
    if not goals:
        send_message(chat_id, "🎯 **Belum ada Target Finansial**\n\nBuat target baru via Web Dashboard.", bot_token=bot_token)
        return

    lines = ["🎯 **PROGRESS TARGET & GOALS FINANSIAL**\n"]
    for idx, g in enumerate(goals, 1):
        m = compute_goal_metrics(g, user_id, db)
        pct = m["percentage"]
        blocks_filled = min(10, max(0, int(round(pct / 10))))
        bar = "█" * blocks_filled + "░" * (10 - blocks_filled)

        status_line = ""
        if m["remaining_amount"] == 0:
            status_line = "🎉 **Target Tercapai!**"
        elif m["estimated_cycles"] is not None:
            c = m["estimated_cycles"]
            mo = m["estimated_months"]
            target_str = m["estimated_finish_date"].strftime("%d %b %Y") if m["estimated_finish_date"] else ""
            status_line = f"⏳ **Estimasi:** ~{c} siklus gajian lagi (~{mo} bln • {target_str})"

        linked_info = f" • _{m['linked_account']}_" if m.get("linked_account") else ""

        lines.append(
            f"{g.icon} **{g.name}**{linked_info}\n"
            f"   `[{bar}]` **{pct}%**\n"
            f"   • Terkumpul: `{format_rp(m['current_amount'])}` / `{format_rp(m['target_amount'])}`\n"
            f"   • Sisa Target: **{format_rp(m['remaining_amount'])}**\n"
            f"   • {status_line}\n"
        )

    lines.append("💡 _Saldo terupdate otomatis dari mutasi rekening atau dapat disesuaikan di Web Dashboard._")
    send_message(chat_id, "\n".join(lines), bot_token=bot_token)

def send_chat_action(chat_id: int, action: str = "typing", bot_token: Optional[str] = None):
    token = bot_token or settings.TELEGRAM_BOT_TOKEN
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendChatAction", json={"chat_id": chat_id, "action": action}, timeout=5)
    except Exception:
        pass

def download_telegram_file(file_id: str, bot_token: Optional[str] = None):
    token = bot_token or settings.TELEGRAM_BOT_TOKEN
    try:
        url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200 and resp.json().get("ok"):
            file_path = resp.json()["result"]["file_path"]
            dl_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
            dl_resp = requests.get(dl_url, timeout=30)
            if dl_resp.status_code == 200:
                return dl_resp.content, file_path
    except Exception as e:
        print(f"Error downloading Telegram file {file_id}: {e}")
    return None, None

def get_acc_balance(acc_name: str, db: Session, user_id: int) -> int:
    row = db.query(
        func.coalesce(
            func.sum(
                case(
                    (Transaction.type.in_(POSITIVE_TYPES), Transaction.amount),
                    (Transaction.type.in_(NEGATIVE_TYPES), -Transaction.amount),
                    else_=0
                )
            ), 0
        )
    ).filter(Transaction.user_id == user_id, Transaction.account == acc_name).scalar()
    return int(row or 0)

def normalize_account(raw: str, db: Optional[Session] = None, user_id: Optional[int] = None):
    if not isinstance(raw, str) or not raw.strip():
        return None
    r = raw.strip().lower()
    if db is not None and user_id is not None:
        names = [acc.name for acc in db.query(Account).filter(Account.user_id == user_id, Account.is_archived == False).all()]
        exact = [name for name in names if name.casefold() == r.casefold()]
        if len(exact) == 1:
            return exact[0]
        matches = [name for name in names if re.search(r"(?<!\w)" + re.escape(r) + r"(?!\w)", name.casefold())]
        return matches[0] if len(matches) == 1 else None
    if "mandiri" in r:
        return "Mandiri"
    elif "bibit" in r:
        return "Bibit"
    elif "jago" in r:
        return "Bank Jago"
    elif "bri 1" in r or "bri1" in r:
        return "BRI 1"
    elif "bri 2" in r or "bri2" in r:
        return "BRI 2"
    elif "cash" in r or "tunai" in r:
        return "Cash"
    elif "utama" in r:
        return "Rekening Utama"
    elif "tagihan" in r:
        return "Rekening Tagihan"
    elif "tabungan" in r:
        return "Tabungan"
    return raw.strip().title()

def resolve_account_from_list(raw: str, accounts: List[Account]) -> Optional[Account]:
    if not isinstance(raw, str) or not raw.strip():
        return None
    cleaned = raw.strip()
    c_lower = cleaned.lower()
    c_compact = re.sub(r"\s+", "", c_lower)

    # 1. Exact case-insensitive match
    for acc in accounts:
        if acc.name.casefold() == c_lower:
            return acc

    # 2. Compact match (ignoring whitespace differences, e.g. "bri 2" == "bri2")
    for acc in accounts:
        if re.sub(r"\s+", "", acc.name.lower()) == c_compact:
            return acc

    # 3. Word boundary regex match
    for acc in accounts:
        if re.search(r"(?<!\w)" + re.escape(c_lower) + r"(?!\w)", acc.name.lower()):
            return acc

    # 4. Known common aliases
    alias_map = {
        "jago": ["bank jago", "jago"],
        "mandiri": ["mandiri", "bank mandiri"],
        "bca": ["bca", "bank bca"],
        "bri": ["bri"],
        "bri1": ["bri 1", "bri1"],
        "bri 1": ["bri 1", "bri1"],
        "bri2": ["bri 2", "bri2"],
        "bri 2": ["bri 2", "bri2"],
        "bibit": ["bibit"],
        "cash": ["cash", "tunai"],
        "tunai": ["cash", "tunai"],
        "utama": ["rekening utama", "utama"],
    }
    for alias_key, targets in alias_map.items():
        if c_compact == re.sub(r"\s+", "", alias_key):
            for acc in accounts:
                acc_compact = re.sub(r"\s+", "", acc.name.lower())
                if any(re.sub(r"\s+", "", t) in acc_compact for t in targets):
                    return acc

    # 5. Unambiguous substring containment
    substr_matches = [acc for acc in accounts if c_lower in acc.name.lower()]
    if len(substr_matches) == 1:
        return substr_matches[0]

    return None

def handle_transfer(chat_id: int, text: str, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return
    user_id = user.id
    clean = text.strip()

    user_accs = db.query(Account).filter(Account.user_id == user_id, Account.is_archived == False).order_by(Account.id.asc()).with_for_update().all()
    acc_options_str = ", ".join(f"`{a.name}`" for a in user_accs) if user_accs else "Belum ada rekening. Tambahkan melalui web."

    if clean.lower() in ["/transfer", "/tf", "transfer", "tf", "🔄 transfer"]:
        guide = f"""🔄 **Panduan Transfer Antar Rekening**

Gunakan format:
`/transfer [nominal] dari [asal] ke [tujuan] [catatan]`
atau singkat:
`tf 100k utama ke tabungan [catatan]`

💡 **Contoh Praktis:**
• `/transfer 200k dari utama ke tabungan dana darurat`
• `tf 150rb utama ke tagihan top up subs`
• `tf 50k tabungan ke utama tarik tunai`

🏦 **Pilihan Rekening Anda:**
{acc_options_str}

ℹ️ _Transfer antar rekening memindahkan saldo via mutasi berpasangan (transfer out & transfer in) dan tidak memotong kuota Safe-to-Spend operasional._"""
        send_message(chat_id, guide, bot_token=bot_token)
        return

    pattern = re.compile(r"^(?:/transfer|/tf|transfer|tf)\s+([\d.,kKrbRB]+)\s+(?:dari\s+)?(.+?)\s+ke\s+(.+)$", re.IGNORECASE)
    match = pattern.match(clean)
    if not match:
        send_message(chat_id, "Format transfer tidak dikenali. Contoh: `tf 100k rekening asal ke rekening tujuan`.", bot_token=bot_token)
        return

    amt_str, from_raw, destination = match.groups()
    to_raw, transfer_note = destination, ""
    for account in sorted(user_accs, key=lambda row: len(row.name), reverse=True):
        named = re.match(re.escape(account.name) + r"(?=$|[\s:\-])(.*)$", destination, re.IGNORECASE)
        if named:
            to_raw, transfer_note = account.name, named.group(1).strip(" :-")
            break
    else:
        for cut in range(len(destination.split()), 0, -1):
            words = destination.split()
            candidate = " ".join(words[:cut]).rstrip(":-")
            if normalize_account(candidate, db, user_id=user_id):
                to_raw, transfer_note = candidate, " ".join(words[cut:]).lstrip(":-").strip()
                break
    from app.core.parser import parse_amount
    try:
        amt, _ = parse_amount(amt_str)
    except (ValueError, OverflowError):
        amt = None
    if not amt or not 0 < amt <= 9_000_000_000_000_000:
        send_message(chat_id, "⚠️ Nominal transfer tidak valid.", bot_token=bot_token)
        return

    if not user_accs:
        send_message(chat_id, "Tambahkan rekening di web sebelum mencatat transfer.", bot_token=bot_token)
        return
    from_acc = normalize_account(from_raw, db, user_id=user_id)
    to_acc = normalize_account(to_raw, db, user_id=user_id)

    if not from_acc:
        send_message(chat_id, f"Rekening asal tidak dikenali. Gunakan nama lengkap dari daftar:\n{acc_options_str}", bot_token=bot_token)
        return
    if not to_acc:
        send_message(chat_id, f"Rekening tujuan tidak dikenali. Gunakan nama lengkap dari daftar:\n{acc_options_str}", bot_token=bot_token)
        return

    if from_acc.lower() == to_acc.lower():
        send_message(chat_id, "⚠️ Rekening asal dan rekening tujuan tidak boleh sama.", bot_token=bot_token)
        return

    desc = transfer_note or "Transfer Antar Rekening"
    if len(desc) + max(len(from_acc), len(to_acc)) + 20 > 255:
        send_message(chat_id, "Catatan transfer terlalu panjang. Persingkat lalu kirim ulang.", bot_token=bot_token)
        return
    now_wib = datetime.now(WIB)
    tx_date = now_wib.date()

    from app.api.v1.endpoints.transactions import add_transfer_pair
    tx_out, tx_in = add_transfer_pair(
        db=db,
        user_id=user_id,
        from_account=from_acc,
        to_account=to_acc,
        amount=int(amt),
        tx_date=tx_date,
        desc=desc
    )
    db.commit()

    bal_from = get_acc_balance(from_acc, db, user_id=user_id)
    bal_to = get_acc_balance(to_acc, db, user_id=user_id)

    res_msg = f"""🔄 **Transfer Antar Rekening Berhasil!**

💸 **Nominal:** `{format_rp(int(amt))}`
📤 **Dari:** {from_acc} (Sisa Saldo: `{format_rp(bal_from)}`)
📥 **Ke:** {to_acc} (Saldo Baru: `{format_rp(bal_to)}`)
📝 **Keterangan:** {desc}

ℹ️ _Saldo berhasil dipindahkan via ledger berpasangan. Transaksi ini tidak memotong kuota Safe-to-Spend._"""
    send_message(chat_id, res_msg, bot_token=bot_token)

def handle_pinjam(chat_id: int, text: str, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return
    user_id = user.id

    user_accs = db.query(Account).filter(Account.user_id == user_id, Account.is_archived == False).order_by(Account.id.asc()).with_for_update().all()
    acc_options_str = ", ".join(f"`{a.name}`" for a in user_accs) if user_accs else "Belum ada rekening. Tambahkan melalui web."

    clean = text.strip()
    clean_args = re.sub(r"^(?:/pinjam|/talangan|pinjam|talangan)\s*", "", clean, flags=re.IGNORECASE).strip()

    # Case A: Tanpa argumen -> Tampilkan daftar pinjaman aktif atau panduan
    if not clean_args:
        active_loans = get_active_internal_loans(db, user_id)
        if not active_loans:
            guide = f"""ℹ️ **Tidak Ada Dana Talangan Aktif**

Semua kas darurat & dana talangan internal telah lunas.

📌 **Format Pencatatan Talangan:**
`/pinjam <nominal> dari <asal> ke <tujuan> [alasan]`
atau singkat:
`/pinjam 300k BRI 2 ke Mandiri ganti ban bocor`

💡 **Contoh Praktis:**
• `/pinjam 300k dari BRI 2 ke Mandiri ganti ban bocor`
• `/talangan 500rb dari Tabungan ke Mandiri bayar kosan`

🏦 **Pilihan Rekening Anda:**
{acc_options_str}"""
            send_message(chat_id, guide, bot_token=bot_token)
            return

        acc_map = {a.id: a.name for a in user_accs}
        lines = ["📋 **Daftar Dana Talangan Internal Aktif:**\n"]
        total_active = 0
        for loan in active_loans:
            total_active += loan.remaining_amount
            src_name = acc_map.get(loan.source_account_id, "Rekening Kreditor")
            dst_name = acc_map.get(loan.target_account_id, "Rekening Debitur")
            dt_str = loan.created_at.strftime("%d %b %Y") if loan.created_at else "-"
            note_str = f"  • Alasan: {loan.note}\n" if loan.note else ""
            lines.append(
                f"• **Pinjaman #{loan.id}:** `{src_name}` ➔ `{dst_name}`\n"
                f"  • Nominal Awal: {format_rp(loan.amount)}\n"
                f"  • Sisa Kewajiban: **{format_rp(loan.remaining_amount)}**\n"
                f"{note_str}"
                f"  • Tanggal: {dt_str}\n"
            )

        lines.append(f"💵 **Total Dana Talangan Belum Dilunasi:** {format_rp(total_active)}")
        first_id = active_loans[0].id
        lines.append(
            f"\n💡 **Cara Pelunasan:**\n"
            f"Ketik `/lunasi <ID> [nominal]` untuk mengembalikan dana.\n"
            f"Contoh: `/lunasi {first_id}` (lunas penuh) atau `/lunasi {first_id} 100k` (cicil)"
        )
        send_message(chat_id, "\n".join(lines), bot_token=bot_token)
        return

    # Case B: Dengan argumen
    if not user_accs:
        send_message(chat_id, "Tambahkan rekening di web sebelum mencatat dana talangan.", bot_token=bot_token)
        return

    pattern = re.compile(r"^([\d.,kKrbRBjtJTmM]+)\s+(?:dari\s+)?(.+?)\s+ke\s+(.+)$", re.IGNORECASE)
    match = pattern.match(clean_args)

    amt_str = None
    from_raw = None
    to_raw = None
    loan_note = ""

    if match:
        amt_str, from_raw, destination = match.groups()
        to_raw, loan_note = destination, ""
        for account in sorted(user_accs, key=lambda row: len(row.name), reverse=True):
            named = re.match(re.escape(account.name) + r"(?=$|[\s:\-])(.*)$", destination, re.IGNORECASE)
            if named:
                to_raw, loan_note = account.name, named.group(1).strip(" :-")
                break
        else:
            words = destination.split()
            for cut in range(len(words), 0, -1):
                candidate = " ".join(words[:cut]).rstrip(":-")
                matched_acc = resolve_account_from_list(candidate, user_accs)
                if matched_acc:
                    to_raw = matched_acc.name
                    loan_note = " ".join(words[cut:]).lstrip(":-").strip()
                    break
    else:
        m2 = re.match(r"^([\d.,kKrbRBjtJTmM]+)\s+(?:dari\s+)?(.+)$", clean_args, re.IGNORECASE)
        if m2:
            amt_str, rest = m2.groups()
            for acc1 in sorted(user_accs, key=lambda r: len(r.name), reverse=True):
                m_from = re.match(re.escape(acc1.name) + r"(?=$|[\s:\-])(.*)$", rest, re.IGNORECASE)
                if m_from:
                    from_raw = acc1.name
                    rem2 = m_from.group(1).strip(" :-")
                    rem2 = re.sub(r"^(?:ke|menuju)\s+", "", rem2, flags=re.IGNORECASE).strip()
                    for acc2 in sorted(user_accs, key=lambda r: len(r.name), reverse=True):
                        m_to = re.match(re.escape(acc2.name) + r"(?=$|[\s:\-])(.*)$", rem2, re.IGNORECASE)
                        if m_to:
                            to_raw = acc2.name
                            loan_note = m_to.group(1).strip(" :-")
                            break
                    if to_raw:
                        break

    if not amt_str or not from_raw or not to_raw:
        send_message(
            chat_id,
            "⚠️ Format perintah talangan tidak dikenali.\n"
            "Gunakan format: `/pinjam <nominal> dari <asal> ke <tujuan> [alasan]`\n"
            "Contoh: `/pinjam 300k dari BRI 2 ke Mandiri ganti ban bocor`",
            bot_token=bot_token,
        )
        return

    if loan_note:
        loan_note = re.sub(r"^(?:untuk|karena|alasan|sebab)\s*", "", loan_note, flags=re.IGNORECASE).strip()

    from app.core.parser import parse_amount
    try:
        amt, _ = parse_amount(amt_str)
    except (ValueError, OverflowError):
        amt = None

    if not amt or not (0 < amt <= 9_000_000_000_000_000):
        send_message(chat_id, "⚠️ Nominal pinjaman tidak valid.", bot_token=bot_token)
        return

    source_acc = resolve_account_from_list(from_raw, user_accs)
    target_acc = resolve_account_from_list(to_raw, user_accs)

    if not source_acc:
        send_message(chat_id, f"⚠️ Rekening sumber '{from_raw}' tidak dikenali. Pilihan rekening:\n{acc_options_str}", bot_token=bot_token)
        return
    if not target_acc:
        send_message(chat_id, f"⚠️ Rekening tujuan '{to_raw}' tidak dikenali. Pilihan rekening:\n{acc_options_str}", bot_token=bot_token)
        return

    if source_acc.id == target_acc.id:
        send_message(chat_id, "⚠️ Rekening asal dan tujuan tidak boleh sama.", bot_token=bot_token)
        return

    try:
        payload = InternalLoanCreate(
            source_account_id=source_acc.id,
            source_pocket_id=None,
            target_account_id=target_acc.id,
            target_pocket_id=None,
            amount=int(amt),
            note=loan_note or None,
        )
        loan = create_internal_loan(db, current_user=user, payload=payload)
    except HTTPException as e:
        send_message(chat_id, f"⚠️ {e.detail}", bot_token=bot_token)
        return

    bal_source = get_acc_balance(source_acc.name, db, user_id=user_id)
    bal_target = get_acc_balance(target_acc.name, db, user_id=user_id)

    catatan_line = f"• Catatan: {loan.note}\n" if loan.note else ""
    msg = (
        f"✅ **Dana Talangan Berhasil Dicatat!**\n"
        f"• ID Pinjaman: #{loan.id}\n"
        f"• Nominal: {format_rp(loan.amount)}\n"
        f"• Dari: {source_acc.name} (Kreditor)\n"
        f"• Ke: {target_acc.name} (Debitur)\n"
        f"{catatan_line}\n"
        f"Saldo terkini:\n"
        f"• {source_acc.name}: {format_rp(bal_source)}\n"
        f"• {target_acc.name}: {format_rp(bal_target)}\n\n"
        f"Gunakan /lunasi {loan.id} saat ingin mengembalikan dana."
    )
    send_message(chat_id, msg, bot_token=bot_token)

def handle_lunasi(chat_id: int, text: str, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return
    user_id = user.id

    clean = text.strip()
    clean_args = re.sub(r"^(?:/lunasi|/bayar_pinjam|/bayar-pinjam|lunasi|bayar pinjam|bayar_pinjam)\s*", "", clean, flags=re.IGNORECASE).strip()

    user_accs = db.query(Account).filter(Account.user_id == user_id).all()
    acc_map = {a.id: a.name for a in user_accs}

    # Case A: Tanpa argumen
    if not clean_args:
        active_loans = get_active_internal_loans(db, user_id)
        if not active_loans:
            send_message(chat_id, "ℹ️ **Tidak Ada Pinjaman Aktif**\n\nSemua dana talangan internal sudah lunas.", bot_token=bot_token)
            return

        lines = ["💳 **Daftar Dana Talangan yang Perlu Dilunasi:**\n"]
        total_active = 0
        for loan in active_loans:
            total_active += loan.remaining_amount
            src_name = acc_map.get(loan.source_account_id, "Rekening Kreditor")
            dst_name = acc_map.get(loan.target_account_id, "Rekening Debitur")
            note_str = f" • _{loan.note}_" if loan.note else ""
            lines.append(
                f"• **#{loan.id}:** `{dst_name}` berhutang ke `{src_name}`\n"
                f"  Sisa Kewajiban: **{format_rp(loan.remaining_amount)}**{note_str}"
            )

        lines.append(f"\n💵 **Total Kewajiban Belum Dilunasi:** {format_rp(total_active)}")
        first_id = active_loans[0].id
        lines.append(
            f"\n💡 **Cara Pelunasan:**\n"
            f"Ketik `/lunasi <ID> [nominal]`\n"
            f"Contoh:\n"
            f"• `/lunasi {first_id}` (lunas penuh)\n"
            f"• `/lunasi {first_id} 100k` (cicil sebagian)"
        )
        send_message(chat_id, "\n".join(lines), bot_token=bot_token)
        return

    # Case B: Dengan argumen
    parts = clean_args.split(maxsplit=1)
    raw_id = parts[0].lstrip("#")
    if not raw_id.isdigit():
        send_message(
            chat_id,
            "⚠️ ID pinjaman tidak valid.\n"
            "Format: `/lunasi <ID> [nominal]`\n"
            "Contoh: `/lunasi 1` atau `/lunasi 1 100k`",
            bot_token=bot_token,
        )
        return
    loan_id = int(raw_id)

    loan = get_internal_loan_by_id(db, user_id=user_id, loan_id=loan_id)
    if not loan:
        send_message(chat_id, f"⚠️ Pinjaman internal dengan ID `#{loan_id}` tidak ditemukan.", bot_token=bot_token)
        return

    if loan.status != "active":
        send_message(chat_id, f"ℹ️ Pinjaman `#{loan_id}` sudah tidak aktif (status: `{loan.status}`).", bot_token=bot_token)
        return

    settle_amt = None
    if len(parts) > 1 and parts[1].strip():
        from app.core.parser import parse_amount
        try:
            amt, _ = parse_amount(parts[1].strip())
        except (ValueError, OverflowError):
            amt = None

        if not amt or not (0 < amt <= 9_000_000_000_000_000):
            send_message(chat_id, "⚠️ Nominal pelunasan tidak valid.", bot_token=bot_token)
            return
        settle_amt = int(amt)

    target_acc = db.query(Account).filter(Account.id == loan.target_account_id, Account.user_id == user_id).first()
    source_acc = db.query(Account).filter(Account.id == loan.source_account_id, Account.user_id == user_id).first()
    if not target_acc or not source_acc:
        send_message(chat_id, "⚠️ Rekening terkait pinjaman ini tidak ditemukan.", bot_token=bot_token)
        return

    to_pay = min(settle_amt, loan.remaining_amount) if settle_amt else loan.remaining_amount
    target_bal = get_acc_balance(target_acc.name, db, user_id=user_id)
    if target_bal < to_pay:
        send_message(
            chat_id,
            f"⚠️ Saldo rekening peminjam '{target_acc.name}' tidak mencukupi untuk pelunasan "
            f"(Tersedia: {format_rp(target_bal)}, Dibutuhkan: {format_rp(to_pay)}).",
            bot_token=bot_token,
        )
        return

    try:
        payload = InternalLoanSettleRequest(amount=settle_amt, note=None)
        settled_loan = settle_internal_loan(db, current_user=user, loan_id=loan_id, payload=payload)
    except HTTPException as e:
        send_message(chat_id, f"⚠️ {e.detail}", bot_token=bot_token)
        return

    bal_target = get_acc_balance(target_acc.name, db, user_id=user_id)
    bal_source = get_acc_balance(source_acc.name, db, user_id=user_id)

    is_lunas = (settled_loan.remaining_amount == 0)
    status_str = "LUNAS 🎉" if is_lunas else f"Sisa: {format_rp(settled_loan.remaining_amount)}"

    msg = (
        f"✅ **Pelunasan Dana Talangan Berhasil!**\n"
        f"• ID Pinjaman: #{settled_loan.id}\n"
        f"• Nominal Dilunasi: {format_rp(to_pay)}\n"
        f"• Sisa Pinjaman: **{status_str}**\n"
        f"• Dari: {target_acc.name} (Debitur)\n"
        f"• Ke: {source_acc.name} (Kreditor)\n\n"
        f"Saldo terkini:\n"
        f"• {target_acc.name}: {format_rp(bal_target)}\n"
        f"• {source_acc.name}: {format_rp(bal_source)}"
    )
    if not is_lunas:
        msg += f"\n\n💡 Gunakan /lunasi {settled_loan.id} saat ingin mengembalikan sisa dana."

    send_message(chat_id, msg, bot_token=bot_token)

def handle_batal(chat_id: int, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return
    user_id = user.id
    last = db.query(Transaction).filter(Transaction.user_id == user_id).order_by(desc(Transaction.id)).with_for_update().first()
    if not last:
        send_message(chat_id, "⚠️ Tidak ada transaksi yang bisa dibatalkan.", bot_token=bot_token)
        return

    if last.type in ("adjustment_in", "adjustment_out"):
        send_message(chat_id, "Catatan penyesuaian disimpan sebagai riwayat. Gunakan rekonsiliasi baru di dashboard untuk koreksi.", bot_token=bot_token)
        return

    from fastapi import HTTPException
    from app.api.v1.endpoints.transactions import delete_transaction
    deleted_info = {field: getattr(last, field) for field in ("description", "amount", "account", "category", "type")}
    pair = find_paired_transfer(db, last) if last.type in ("transfer_out", "transfer_in") else None
    pair_account = pair.account if pair else None
    try:
        result = delete_transaction(last.id, current_user=user, db=db)
    except HTTPException as exc:
        send_message(chat_id, str(exc.detail), bot_token=bot_token)
        return
    is_paired_transfer = len(result["deleted_ids"]) == 2

    if is_paired_transfer:
        msg = f"""🗑️ **Transfer Berpasangan Berhasil Dibatalkan!**

• **Nominal:** {format_rp(deleted_info['amount'])}
• **Rekening Terkait:** `{deleted_info['account']}` & `{pair_account}`
• **Kategori:** Transfer
• **Keterangan:** {deleted_info['description']}

Kedua sisi mutasi transfer (keluar & masuk) telah dihapus dari database secara sinkron."""
    else:
        msg = f"""↩️ **Transaksi Berhasil Dibatalkan / Dihapus!**

• **Deskripsi:** {deleted_info['description']}
• **Nominal:** {format_rp(deleted_info['amount'])} ({deleted_info['type']})
• **Kategori:** {deleted_info['category']}
• **Rekening:** {deleted_info['account']}

Catatan tersebut sudah dihapus dari database PostgreSQL."""
    send_message(chat_id, msg, bot_token=bot_token)

def handle_gajian(chat_id: int, text: str, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return
    user_id = user.id
    now_wib = datetime.now(WIB)
    today_wib = now_wib.date()

    from app.api.v1.endpoints.paycheck import get_or_seed_config, get_or_seed_buckets, compute_bucket_amounts
    from app.services.paycheck_cycles import receipt_allocations
    import uuid

    if not db.query(Account.id).filter(Account.user_id == user_id, Account.is_archived == False).first():
        send_message(chat_id, "Tambahkan rekening di web sebelum mencatat gaji.", bot_token=bot_token)
        return
    cfg = get_or_seed_config(db, user_id)
    buckets = get_or_seed_buckets(db, cfg.id)
    user_accs = db.query(Account).filter(Account.user_id == user_id, Account.is_archived == False).order_by(Account.id.asc()).with_for_update().all()
    accounts_by_name = {a.name: a for a in user_accs}
    accounts_by_id = {a.id: a.name for a in user_accs}

    source_account = cfg.source_account if (cfg.source_account and cfg.source_account in accounts_by_name) else (user_accs[0].name if user_accs else "Rekening Utama")
    source_acc_obj = accounts_by_name.get(source_account)
    active_debts = []
    if source_acc_obj:
        active_debts = db.query(InternalLoan).filter(
            InternalLoan.user_id == user_id,
            InternalLoan.target_account_id == source_acc_obj.id,
            InternalLoan.status == "active",
            InternalLoan.remaining_amount > 0,
        ).order_by(InternalLoan.created_at.asc()).all()

    cycle_start = today_wib
    if cfg.cycle_type == "monthly_date":
        from app.api.v1.endpoints.analytics import get_monthly_date_bounds
        payday = cfg.paycheck_day or cycle_start.day
        _, cycle_end = get_monthly_date_bounds(cycle_start, payday)
        cycle_days = (cycle_end - cycle_start).days + 1
        cycle_label = f"Siklus Bulanan (Tgl {payday})"
    else:
        cycle_days = cfg.cycle_days if cfg.cycle_days and cfg.cycle_days > 0 else 14
        cycle_end = cycle_start + timedelta(days=cycle_days - 1)
        if cfg.cycle_type == "weekly" or cycle_days == 7:
            cycle_label = "Siklus Mingguan"
        elif cfg.cycle_type == "biweekly" or cycle_days == 14:
            cycle_label = "Siklus 2-Mingguan"
        elif cfg.cycle_type == "monthly" or cycle_days == 30:
            cycle_label = "Siklus Bulanan (30 Hari)"
        else:
            cycle_label = f"Siklus {cycle_days} Hari"

    parts = text.split()
    parsed_amt = None
    if len(parts) > 1:
        from app.core.parser import parse_amount
        try:
            parsed_amt, _ = parse_amount(parts[1])
        except (ValueError, OverflowError):
            send_message(chat_id, "Nominal gaji tidak valid.", bot_token=bot_token)
            return

    if not parsed_amt or parsed_amt <= 0:
        debt_status_section = ""
        if active_debts:
            total_debt = sum(d.remaining_amount for d in active_debts)
            debt_status_lines = [
                f"\n\n⚠️ **Pengingat Dana Talangan Internal:**",
                f"Rekening `{source_account}` memiliki kewajiban talangan aktif sebesar **{format_rp(total_debt)}**:",
            ]
            for d in active_debts:
                creditor_name = accounts_by_id.get(d.source_account_id, "Rekening Kreditor")
                debt_status_lines.append(f"• Pinjaman #{d.id}: {format_rp(d.remaining_amount)} ke `{creditor_name}`")
            debt_status_lines.append("💡 _Segera kembalikan uang dingin dengan perintah:_ `/lunasi <ID>`")
            debt_status_section = "\n".join(debt_status_lines)

        latest_receipt = db.query(PaycheckReceipt).join(
            Transaction, Transaction.id == PaycheckReceipt.transaction_id
        ).filter(
            PaycheckReceipt.user_id == user_id,
            Transaction.type == "income"
        ).order_by(PaycheckReceipt.transaction_id.desc()).first()

        if latest_receipt:
            tx = db.get(Transaction, latest_receipt.transaction_id)
            accounts_by_id = {a.id: a.name for a in user_accs}
            allocs = receipt_allocations(db, latest_receipt)

            alloc_lines = []
            for item in allocs:
                acc_name = accounts_by_id.get(item["account_id"], "Rekening")
                is_done = bool(item.get("transfer_id"))
                status_badge = "✅ Ditransfer" if is_done else "⏳ Belum ditransfer"
                alloc_lines.append(f"• **{acc_name}:** {format_rp(item['amount'])} ({status_badge})")

            alloc_str = "\n".join(alloc_lines) if alloc_lines else "_Tidak ada alokasi transfer sekunder._"
            end_str = latest_receipt.cycle_end.strftime('%d %b %Y') if latest_receipt.cycle_end else str(cycle_end)

            msg = f"""💰 **Status Payroll & Gajian Terakhir ({cycle_label})**

💵 **Gaji Diterima:** `{format_rp(tx.amount)}`
🏦 **Rekening:** `{tx.account}`
📅 **Tanggal Masuk:** `{tx.date}` (Siklus berakhir `{end_str}`)

📋 **Status Rencana Alokasi Transfer:**
{alloc_str}{debt_status_section}

💡 *Untuk mencatat gajian baru:*
Ketik: `/gajian [nominal]` (contoh: `/gajian 5.000.000` atau `/gajian 5jt`)"""
            send_message(chat_id, msg, bot_token=bot_token)
            return
        else:
            debt_info = f"\n{debt_status_section}\n" if debt_status_section else "\n"
            msg = f"""💰 **Pencatatan Gajian & Payroll**

Gunakan perintah ini untuk mencatat gaji masuk secara rapi dan menyiapkan alur pembagian ke rekening/pos anggaran.

📌 **Cara Pakai:**
`/gajian [nominal]`
Contoh: `/gajian 5.000.000` atau `/gajian 5jt`

🏦 **Rekening Penampung Default:** `{source_account}`
📅 **Siklus Tanggal Anggaran:** `{cycle_label}`{debt_info}
ℹ️ _Gaji akan dicatat sebagai pemasukan riil di rekening penampung. Pos alokasi rekening lain disiapkan sebagai rencana transfer terpisah._"""
            send_message(chat_id, msg, bot_token=bot_token)
            return

    total = int(parsed_amt)
    if not 0 < total <= 9_000_000_000_000_000:
        send_message(chat_id, "Nominal gaji tidak valid.", bot_token=bot_token)
        return

    # 1. Record single income transaction in receiver account (source_account)
    tx = Transaction(
        user_id=user_id,
        type="income",
        amount=total,
        account=source_account,
        category="Gaji",
        description="Gaji",
        raw_text=f"paycheck record /gajian: {total}",
        date=cycle_start
    )
    db.add(tx)
    db.flush()

    # 2. Compute dynamic bucket allocations without hardcoding
    bucket_amounts = compute_bucket_amounts(total, buckets)
    allocations_json_data = []
    remaining = total

    for b in buckets:
        amt = bucket_amounts.get(b.account, 0)
        if b.account != source_account and b.account in accounts_by_name and amt > 0 and remaining > 0:
            alloc_amt = min(amt, remaining)
            allocations_json_data.append({
                "account_id": accounts_by_name[b.account].id,
                "amount": alloc_amt,
                "transfer_id": None
            })
            remaining -= alloc_amt

    # 3. Create PaycheckReceipt linking the transaction and optional transfer allocations
    receipt = PaycheckReceipt(
        transaction_id=tx.id,
        user_id=user_id,
        request_key=str(uuid.uuid4()),
        cycle_end=cycle_end,
        allocations_json=json.dumps(allocations_json_data)
    )
    db.add(receipt)

    # 4. Synchronize cycle start date in PaycheckConfig
    cfg.cycle_start_date = cycle_start
    db.add(cfg)
    db.commit()

    # 5. Sheets auto-sync if user has configured google_spreadsheet_id
    sheet_info = ""
    if user and getattr(user, "google_spreadsheet_id", None):
        try:
            from app.services.sheets_sync import sync_cycle_snapshot
            res = sync_cycle_snapshot(db, user_id=user_id, cycle_start_date=cycle_start)
            sheet_info = f"\n\n📑 **Google Sheets:** Tab `{res['sheet_title']}` otomatis dibuat & disinkronkan!"
        except Exception as e:
            logger.warning(f"Sheets auto-sync error: {e}")

    # Build response message
    distrib_lines = []
    for b in buckets:
        amt = bucket_amounts.get(b.account, 0)
        pct = round(amt / total * 100, 1) if total > 0 else 0
        is_source = (b.account == source_account)
        source_note = " *(Penampung Gaji Utama)*" if is_source else ""
        distrib_lines.append(f"• **{b.account} ({pct}%):** {format_rp(amt)}{source_note}\n  └ *{b.purpose}*")

    distrib_str = "\n".join(distrib_lines)

    debt_section = ""
    if active_debts:
        total_debt = sum(d.remaining_amount for d in active_debts)
        debt_lines = [
            f"\n⚠️ **Pengingat Pelunasan Dana Talangan Internal:**",
            f"Rekening operasional `{source_account}` memiliki kewajiban talangan aktif sebesar **{format_rp(total_debt)}**:",
        ]
        for d in active_debts:
            creditor_name = accounts_by_id.get(d.source_account_id, "Rekening Kreditor")
            d_note = f" ({d.note})" if d.note else ""
            debt_lines.append(f"• Pinjaman #{d.id}: {format_rp(d.remaining_amount)} ke `{creditor_name}`{d_note}")
        debt_lines.append("💡 _Rekomendasi: Kembalikan uang dingin segera dengan perintah:_ `/lunasi <ID>`\n")
        debt_section = "\n".join(debt_lines)

    msg = f"""🎉 **GAJIAN MASUK & ALUR ANGGARAN TERCATAT!**

💰 **Total Gaji Masuk:** {format_rp(total)}
📥 **Rekening Penerima:** `{source_account}`
📅 **{cycle_label}:** {cycle_start.strftime('%d %b')} – {cycle_end.strftime('%d %b %Y')}

📊 **Rencana Alokasi Pos ({len(buckets)} Pos Anggaran):**
{distrib_str}
{debt_section}
ℹ️ _Pemasukan gaji dicatat utuh di rekening `{source_account}`. Alokasi transfer ke rekening/pos lain dapat dieksekusi terpisah via `/transfer` atau Checklist Dashboard._
🌐 [Buka dashboard Tillfold]({settings.APP_BASE_URL}){sheet_info}"""

    send_message(chat_id, msg, bot_token=bot_token)

def handle_set_sheet(chat_id: int, text: str, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return

    parts = text.strip().split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        msg = (
            "Kirim `/set_sheet <link_spreadsheet>` untuk menautkan Google Sheet kamu.\n\n"
            "Pastikan kamu sudah membagikan akses Editor pada spreadsheet-mu ke email bot:\n"
            "`tillfold@tillfold.iam.gserviceaccount.com`"
        )
        send_message(chat_id, msg, bot_token=bot_token)
        return

    from app.core.helpers import extract_spreadsheet_id
    raw_arg = parts[1].strip()
    sheet_id = extract_spreadsheet_id(raw_arg)
    if not sheet_id:
        send_message(chat_id, "⚠️ Link atau Spreadsheet ID tidak valid. Silakan periksa kembali.", bot_token=bot_token)
        return

    user.google_spreadsheet_id = sheet_id
    db.commit()
    db.refresh(user)

    msg = (
        f"✅ **Google Spreadsheet Berhasil Ditautkan!**\n"
        f"ID: `{sheet_id}`\n\n"
        f"Sekarang kamu bisa mengetik `/sheets` kapan saja untuk menyinkronkan laporan keuanganmu!"
    )
    send_message(chat_id, msg, bot_token=bot_token)

def handle_sheets(chat_id: int, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return
    user_id = user.id
    if not user.google_spreadsheet_id:
        msg = (
            "⚠️ Google Spreadsheet belum ditautkan.\n\n"
            "Kirim `/set_sheet <link_spreadsheet>` untuk menautkan Google Sheet kamu.\n\n"
            "Pastikan kamu sudah membagikan akses Editor pada spreadsheet-mu ke email bot:\n"
            "`tillfold@tillfold.iam.gserviceaccount.com`"
        )
        send_message(chat_id, msg, bot_token=bot_token)
        return

    send_message(chat_id, "⏳ _Sedang menyinkronkan data snapshot siklus ke Google Sheets..._", bot_token=bot_token)
    try:
        from app.services.sheets_sync import sync_cycle_snapshot
        res = sync_cycle_snapshot(db, user_id=user_id)
        msg = f"""📑 **GOOGLE SHEETS DISINKRONKAN!**

• **Tab:** `{res['sheet_title']}`
• **Periode:** `{res['cycle_range']}`
• **Total Transaksi:** `{res['transaction_count']} catatan`
• **Amplop Terpantau:** `{res['envelopes_count']} pos dinamis`
• **Realisasi Belanja:** {format_rp(res['pocket_spent'])} (Sisa {format_rp(res['pocket_remaining'])})
• **Total Net Worth:** {format_rp(res['total_balance'])}

🔗 [Buka Lembar Google Sheets]({res['spreadsheet_url']})"""
        send_message(chat_id, msg, bot_token=bot_token)
    except Exception as e:
        send_message(chat_id, f"❌ Gagal sinkronisasi ke Google Sheets: {str(e)}", bot_token=bot_token)

def prepare_bot_items(items, db: Session, user_id: int, text_items=False):
    from app.schemas.transaction import TransactionCreate
    accounts = db.query(Account).filter(Account.user_id == user_id, Account.is_archived == False).order_by(Account.id).with_for_update().all()
    if not accounts:
        raise ValueError("Tambahkan rekening di web sebelum mencatat transaksi.")
    known_accounts = db.query(Account).filter(Account.user_id == user_id).all()
    cfg = db.query(PaycheckConfig).filter(PaycheckConfig.user_id == user_id).first()
    names = {account.name for account in accounts}
    normalized = []
    if not isinstance(items, list) or not items:
        raise ValueError("Tidak ada transaksi yang dapat dicatat.")
    for original in items:
        if not isinstance(original, dict):
            raise ValueError("Rincian transaksi tidak valid. Belum ada transaksi yang dicatat.")
        item = dict(original)
        if text_items:
            raw = item.get("raw_text", "")
            matched = [account.name for account in known_accounts if re.search(
                r"(?<!\w)" + re.escape(account.name) + r"(?!\w)", raw, re.IGNORECASE)]
            # Prefer the complete account name over another name contained inside it.
            matched = [name for name in matched if not any(name.casefold() in other.casefold() and name != other for other in matched)]
            if len(matched) > 1:
                raise ValueError("Sebutkan satu rekening untuk setiap transaksi. Untuk pindah saldo, gunakan /transfer.")
            if matched:
                remainder = re.sub(re.escape(matched[0]), " ", raw, flags=re.IGNORECASE)
                item = parse_transaction(remainder)
                if not item.get("success"):
                    raise ValueError("Nominal transaksi tidak ditemukan setelah nama rekening dibaca.")
                item.update(account=matched[0], account_explicit=True, raw_text=raw)
            if not item.get("account_explicit"):
                item["account"] = None
        kind = item.get("type", "expense")
        amount = item.get("amount")
        if type(amount) is not int or not 0 < amount <= 9_000_000_000_000_000:
            raise ValueError("Nominal transaksi harus berupa rupiah bulat, lebih dari 0, dan tidak melebihi batas.")
        if kind not in ("income", "expense", "transfer") or (text_items and kind == "transfer"):
            raise ValueError("Tipe transaksi tidak valid. Gunakan /transfer untuk pindah saldo.")
        item["type"] = kind
        item["description"] = str(item.get("description") or "Transaksi Telegram").strip()
        item["category"] = str(item.get("category") or "Lainnya").strip()
        if len(item["description"]) > 255 or len(item["category"]) > 100:
            raise ValueError("Keterangan atau kategori terlalu panjang.")
        if kind == "transfer":
            for field in ("from_account", "to_account"):
                item[field] = normalize_account(item.get(field), db, user_id=user_id)
                if item[field] not in names:
                    raise ValueError("Rekening transfer tidak dikenali. Pilih rekening milik Anda dari web.")
            if item["from_account"] == item["to_account"]:
                raise ValueError("Rekening asal dan tujuan tidak boleh sama.")
        else:
            supplied = item.get("account")
            if supplied:
                account = normalize_account(supplied, db, user_id=user_id)
            elif kind == "income":
                account = cfg.source_account if cfg and cfg.source_account in names else accounts[0].name
            else:
                account = resolve_pocket_account(db, user_id, user_accs=accounts, cfg=cfg)
            if account not in names:
                raise ValueError("Rekening tidak dikenali atau namanya ambigu. Gunakan nama rekening lengkap milik Anda.")
            item["account"] = account
            TransactionCreate(type=kind, amount=amount, account=account,
                              category=item["category"], description=item["description"])
        normalized.append(item)
    return normalized


def handle_text_message(chat_id: int, text: str, message_id: int, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None, voice_prefix: str = ""):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", reply_to_message_id=message_id, bot_token=bot_token)
        return
    user_id = user.id
    try:
        items = parse_multi_transactions(text)
    except (ValueError, OverflowError):
        send_message(chat_id, "Nominal transaksi tidak valid.", reply_to_message_id=message_id, bot_token=bot_token)
        return
    if not items:
        # Fall back to single parser to report specific error
        fallback = parse_transaction(text)
        err_msg = fallback.get("error", "Format tidak terdeteksi.")
        send_message(chat_id, f"{voice_prefix}❌ {err_msg}", reply_to_message_id=message_id, bot_token=bot_token)
        return

    try:
        items = prepare_bot_items(items, db, user_id, text_items=True)
    except (ValueError, OverflowError) as exc:
        send_message(chat_id, "Rincian transaksi tidak valid. " + str(exc), reply_to_message_id=message_id, bot_token=bot_token)
        return

    now_wib = datetime.now(WIB)
    time_str = now_wib.strftime("%Y-%m-%d %H:%M:%S")

    c_info = get_user_cycle_info(db, user_id=user_id)
    cycle_start = c_info["cycle_start"]
    cycle_end = c_info["cycle_end"]
    cycle_days = c_info["cycle_days"]
    cycle_label = c_info["cycle_label"]
    pocket_account = c_info["pocket_account"]
    POCKET_ENVELOPES = get_pocket_envelopes(cycle_days)
    MANDIRI_ENVELOPES = POCKET_ENVELOPES

    # If single transaction
    if len(items) == 1:
        parsed = items[0]
        tx = Transaction(
            user_id=user_id,
            type=parsed["type"],
            amount=parsed["amount"],
            account=parsed["account"],
            category=parsed["category"],
            description=parsed["description"],
            raw_text=parsed.get("raw_text", ""),
            date=now_wib.date()
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)

        type_label = "Pemasukan" if tx.type == "income" else "Pengeluaran"
        icon = "💰" if tx.type == "income" else "💸"

        reply = f"""{voice_prefix}✅ **Tercatat!**

{icon} **{type_label}:** {format_rp(tx.amount)}
📂 **Kategori:** {tx.category}
💳 **Rekening:** {tx.account}
📝 **Keterangan:** {tx.description}
🕒 _{time_str} WIB_"""

        if tx.type == "expense" and is_matching_pocket_account(tx.account, pocket_account) and tx.category in POCKET_ENVELOPES:
            limit = POCKET_ENVELOPES[tx.category]
            pocket_variants = get_pocket_account_variants(pocket_account)
            spent = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
                Transaction.user_id == user_id,
                func.lower(Transaction.account).in_(pocket_variants),
                Transaction.type == "expense",
                Transaction.category == tx.category,
                Transaction.date >= cycle_start,
                Transaction.date <= cycle_end
            ).scalar()
            spent_int = int(spent or 0)
            rem = limit - spent_int
            pct = round(spent_int / limit * 100, 1) if limit > 0 else 0
            status_icon = "⚠️" if pct > 85 else "📊"
            reply += f"\n\n{status_icon} **Status Amplop Belanja Harian ({cycle_label}):**\n• Kuota Terpakai: {format_rp(spent_int)} / {format_rp(limit)} ({pct}%)\n• Sisa Kuota: **{format_rp(rem)}**"

        if tx.type == "expense":
            reply += f"\n\n{get_safe_to_spend_snippet(db, user_id=user_id)}"

        send_message(chat_id, reply, reply_to_message_id=message_id, bot_token=bot_token)
        return

    # If multiple transactions in one message
    created_txs = []
    total_amount = 0
    categories_touched = set()

    for parsed in items:
        tx = Transaction(
            user_id=user_id,
            type=parsed["type"],
            amount=parsed["amount"],
            account=parsed["account"],
            category=parsed["category"],
            description=parsed["description"],
            raw_text=parsed.get("raw_text", ""),
            date=now_wib.date()
        )
        db.add(tx)
        created_txs.append(tx)
        total_amount += tx.amount
        if is_matching_pocket_account(tx.account, pocket_account) and tx.type == "expense":
            categories_touched.add(tx.category)

    db.commit()
    for tx in created_txs:
        db.refresh(tx)

    lines = [f"✅ **{len(created_txs)} Transaksi Berhasil Dicatat!**\n"]
    for idx, tx in enumerate(created_txs, 1):
        icon = "💰" if tx.type == "income" else "💸"
        lines.append(f"{idx}. {icon} **{format_rp(tx.amount)}** • {tx.description}\n   📂 `{tx.category}` • 💳 `{tx.account}`")

    lines.append(f"\n💵 **Total:** {format_rp(total_amount)}")
    lines.append(f"🕒 _{time_str} WIB_")

    # Add envelope updates for all affected pocket categories
    pocket_status_lines = []
    pocket_variants = get_pocket_account_variants(pocket_account)
    for cat in categories_touched:
        if cat in POCKET_ENVELOPES:
            limit = POCKET_ENVELOPES[cat]
            spent = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
                Transaction.user_id == user_id,
                func.lower(Transaction.account).in_(pocket_variants),
                Transaction.type == "expense",
                Transaction.category == cat,
                Transaction.date >= cycle_start,
                Transaction.date <= cycle_end
            ).scalar()
            spent_int = int(spent or 0)
            rem = limit - spent_int
            pct = round(spent_int / limit * 100, 1) if limit > 0 else 0
            pocket_status_lines.append(f"• **{cat}:** {format_rp(spent_int)} / {format_rp(limit)} ({pct}%) ➔ Sisa: {format_rp(rem)}")

    if pocket_status_lines:
        lines.append(f"\n📊 **Status Amplop Belanja Harian ({cycle_label}):**\n" + "\n".join(pocket_status_lines))

    lines.append(f"\n{get_safe_to_spend_snippet(db, user_id=user_id)}")

    send_message(chat_id, "\n".join(lines), reply_to_message_id=message_id, bot_token=bot_token)

def handle_media_message(chat_id: int, message: dict, message_id: int, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", reply_to_message_id=message_id, bot_token=bot_token)
        return
    user_id = user.id
    photo = message.get("photo")
    doc = message.get("document")
    voice = message.get("voice")
    audio = message.get("audio")
    caption = (message.get("caption") or "").strip()

    file_id = None
    media_type = "image"
    mime_type = "image/jpeg"
    action_type = "upload_photo"

    if photo:
        file_id = photo[-1]["file_id"]
        media_type = "image"
        mime_type = "image/jpeg"
        action_type = "upload_photo"
    elif doc:
        mime = (doc.get("mime_type") or "").lower()
        fn = (doc.get("file_name") or "").lower()
        audio_exts = (".mp3", ".m4a", ".wav", ".ogg", ".oga", ".aac", ".flac", ".opus", ".wma", ".caf")
        if mime.startswith("image/") or fn.endswith((".jpg", ".jpeg", ".png", ".webp")):
            file_id = doc["file_id"]
            media_type = "image"
            mime_type = mime or "image/jpeg"
            action_type = "upload_photo"
        elif mime.startswith("audio/") or any(fn.endswith(ext) for ext in audio_exts):
            file_id = doc["file_id"]
            media_type = "audio"
            mime_type = mime or "audio/mp3"
            action_type = "record_voice"
        else:
            send_message(chat_id, "⚠️ Dokumen ini bukan format gambar atau rekaman audio yang didukung.", reply_to_message_id=message_id, bot_token=bot_token)
            return
    elif voice:
        file_id = voice["file_id"]
        media_type = "audio"
        mime_type = voice.get("mime_type") or "audio/ogg"
        action_type = "record_voice"
    elif audio:
        file_id = audio["file_id"]
        media_type = "audio"
        mime_type = audio.get("mime_type") or "audio/mp3"
        action_type = "record_voice"
    else:
        return

    send_chat_action(chat_id, action_type, bot_token=bot_token)
    file_bytes, file_path = download_telegram_file(file_id, bot_token=bot_token)
    if not file_bytes:
        send_message(chat_id, "❌ Gagal mengunduh media dari Telegram. Silakan coba kirim ulang.", reply_to_message_id=message_id, bot_token=bot_token)
        return

    if media_type == "image" and file_path:
        if file_path.lower().endswith(".png"):
            mime_type = "image/png"
        elif file_path.lower().endswith(".webp"):
            mime_type = "image/webp"

    transcribed_text = ""
    if media_type == "audio":
        try:
            import httpx
            fn = os.path.basename(file_path) if file_path else "audio.ogg"
            response = httpx.post(
                "http://127.0.0.1:8090/v1/audio/transcriptions",
                files={"file": (fn, file_bytes)},
                data={"language": "id", "prompt": "pengeluaran, pemasukan, transfer, nominal, rekening"},
                timeout=60.0,
            )
            if response.status_code == 200:
                transcribed_text = (response.json().get("text") or "").strip()
        except Exception as exc:
            logger.warning("Transkripsi lokal tidak tersedia: %s", exc)
    if transcribed_text:
        full_text = f"{transcribed_text} ({caption})" if caption else transcribed_text
        handle_text_message(chat_id, full_text, message_id, db, user=user, bot_token=bot_token,
                            voice_prefix=f"Suara: {transcribed_text}\n\n")
        return

    db_accounts = [a.name for a in db.query(Account).filter(Account.user_id == user_id, Account.is_archived == False).all()]
    all_accounts = db_accounts

    from app.services.ai_extractor import extract_from_media
    extraction = extract_from_media(
        media_bytes=file_bytes,
        mime_type=mime_type,
        media_type=media_type,
        caption=caption,
        accounts=all_accounts
    )

    if not extraction.get("success"):
        err = extraction.get("error", "Gagal memproses media.")
        send_message(chat_id, f"❌ {err}", reply_to_message_id=message_id, bot_token=bot_token)
        return

    if not extraction.get("detected") or not extraction.get("transactions"):
        reason = extraction.get("transcription") or "Tidak ditemukan rincian nominal pembayaran, struk, atau pengeluaran."
        kind_name = "gambar/struk" if media_type == "image" else "voice note"
        send_message(
            chat_id,
            f"⚠️ **Tidak Terdeteksi Transaksi pada {kind_name}**\n\n_{reason}_\n\n💡 _Tips: Pastikan foto struk/QRIS terang dan terbaca jelas, atau sebutkan nominal dan pengeluaran secara spesifik pada voice note._",
            reply_to_message_id=message_id,
            bot_token=bot_token
        )
        return

    try:
        items = prepare_bot_items(extraction.get("transactions", []), db, user_id)
    except (ValueError, OverflowError) as exc:
        send_message(chat_id, "Rincian transaksi tidak valid. " + str(exc), reply_to_message_id=message_id, bot_token=bot_token)
        return
    from app.api.v1.endpoints.transactions import add_transfer_pair
    today = datetime.now(WIB).date()
    lines = [f"Tercatat: {len(items)} transaksi."]
    for item in items:
        if item["type"] == "transfer":
            add_transfer_pair(db, user_id, item["from_account"], item["to_account"], item["amount"], today, item["description"])
            lines.append(f"Transfer {format_rp(item['amount'])}: {item['from_account']} → {item['to_account']}")
        else:
            db.add(Transaction(user_id=user_id, type=item["type"], amount=item["amount"], account=item["account"],
                               category=item["category"], description=item["description"],
                               raw_text=f"ai media: {item['description']}", date=today))
            label = "Masuk" if item["type"] == "income" else "Keluar"
            lines.append(f"{label} {format_rp(item['amount'])} • {item['account']} • {item['description']}")
    db.commit()
    lines.append(get_safe_to_spend_snippet(db, user_id=user_id))
    send_message(chat_id, "\n".join(lines), reply_to_message_id=message_id, bot_token=bot_token)


def handle_callback_query(callback_query: dict, bot_token: Optional[str] = None):
    cb_id = callback_query.get("id")
    tg_user = callback_query.get("from", {})
    sender_id = tg_user.get("id")
    msg = callback_query.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    msg_id = msg.get("message_id")
    data = callback_query.get("data", "")
    token = bot_token or settings.TELEGRAM_BOT_TOKEN

    if not sender_id or not cb_id:
        return

    try:
        requests.post(f"https://api.telegram.org/bot{token}/answerCallbackQuery", json={"callback_query_id": cb_id}, timeout=5)
    except Exception:
        pass

    db = SessionLocal()
    try:
        user = db.query(User).filter(
            User.telegram_chat_id == sender_id,
            User.is_active == True,
        ).first()

        if not user:
            try:
                requests.post(f"https://api.telegram.org/bot{token}/answerCallbackQuery", json={
                    "callback_query_id": cb_id,
                    "text": "Akses ditolak: Akun Telegram belum terhubung ke Tillfold.",
                    "show_alert": True,
                }, timeout=5)
            except Exception:
                pass
            return

        if not data.startswith("rcpt_"):
            return

        parts = data.split(":")
        action = parts[0]
        ref_num = parts[1] if len(parts) > 1 else ""

        from app.core.receipt_store import get_pending_receipt, delete_pending_receipt

        if action == "rcpt_ign":
            delete_pending_receipt(ref_num)
            edit_text = (
                f"❌ **RECEIPT DIABAIKAN**\n"
                f"Struk referensi `{ref_num}` telah diabaikan dan tidak dicatat ke Tillfold."
            )
            requests.post(f"https://api.telegram.org/bot{token}/editMessageText", json={
                "chat_id": chat_id,
                "message_id": msg_id,
                "text": edit_text,
                "parse_mode": "Markdown",
                "reply_markup": {"inline_keyboard": []},
            }, timeout=8)

        elif action == "rcpt_rec":
            chosen_acc = parts[2] if len(parts) > 2 else "Mandiri"
            entry = get_pending_receipt(ref_num)
            if not entry:
                requests.post(f"https://api.telegram.org/bot{token}/editMessageText", json={
                    "chat_id": chat_id,
                    "message_id": msg_id,
                    "text": f"⚠️ **TRANSAKSI KEDALUWARSA**\nData draf struk `{ref_num}` tidak ditemukan atau sudah diproses.",
                    "parse_mode": "Markdown",
                    "reply_markup": {"inline_keyboard": []},
                }, timeout=8)
                return

            p = entry.get("parsed", entry)
            nominal = p.get("nominal", 0)
            merchant = p.get("merchant", "Transaksi")
            cat_name = p.get("category", "Makanan & Minuman")
            bank = p.get("bank", "Bank").upper()
            tx_date_str = p.get("date")

            try:
                tx_date = datetime.fromisoformat(tx_date_str).date()
            except Exception:
                tx_date = datetime.now(WIB).date()

            existing = db.query(Transaction).filter(
                Transaction.user_id == user.id,
                Transaction.raw_text.like(f"%[receipt_radar:ref_{ref_num}]%"),
            ).first()

            if existing:
                edit_text = (
                    f"ℹ️ **SUDAH TERCATAT SEBELUMNYA**\n"
                    f"Transaksi referensi `{ref_num}` sudah ada di buku besar Tillfold."
                )
            else:
                acc = db.query(Account).filter(Account.user_id == user.id, Account.name == chosen_acc).first()
                if not acc:
                    chosen_acc = "Mandiri"

                tx = Transaction(
                    user_id=user.id,
                    type="expense",
                    amount=nominal,
                    account=chosen_acc,
                    category=cat_name,
                    description=f"{merchant} (Struk {bank})",
                    raw_text=f"[receipt_radar:ref_{ref_num}] Auto-recorded via Telegram approval from {bank}",
                    date=tx_date,
                )
                db.add(tx)

                if p.get("is_transfer", False) and p.get("admin_fee", 0) > 0:
                    admin_fee = int(p.get("admin_fee", 0))
                    tx_fee = Transaction(
                        user_id=user.id,
                        type="expense",
                        amount=admin_fee,
                        account=chosen_acc,
                        category="Biaya Admin",
                        description=f"Biaya Admin Transfer ke {merchant} (Ref: {ref_num})",
                        raw_text=f"[receipt_radar:ref_{ref_num}_admin] Auto-recorded transfer admin fee",
                        date=tx_date,
                    )
                    db.add(tx_fee)

                db.commit()
                db.refresh(tx)

                s2s_snippet = get_safe_to_spend_snippet(db, user_id=user.id)
                delete_pending_receipt(ref_num)

                edit_text = (
                    f"✅ **TRANSAKSI BERHASIL DICATAT KE TILLFOLD**\n\n"
                    f"• **Merchant**: `{merchant}`\n"
                    f"• **Nominal**: `Rp {nominal:,}`\n"
                    f"• **Rekening**: `{chosen_acc}`\n"
                    f"• **Kategori**: `{cat_name}`\n"
                    f"• **No. Ref**: `{ref_num}`\n\n"
                    f"{s2s_snippet}"
                )

            requests.post(f"https://api.telegram.org/bot{token}/editMessageText", json={
                "chat_id": chat_id,
                "message_id": msg_id,
                "text": edit_text,
                "parse_mode": "Markdown",
                "reply_markup": {"inline_keyboard": []},
            }, timeout=8)

        elif action == "rcpt_xfer":
            # format: rcpt_xfer:<ref_num>:<source_acc>:<dest_acc>:<admin_fee>
            source_acc = parts[2] if len(parts) > 2 else "Mandiri"
            dest_acc = parts[3] if len(parts) > 3 else "Bank Jago"
            admin_fee_str = parts[4] if len(parts) > 4 else "0"
            try:
                admin_fee = int(admin_fee_str)
            except ValueError:
                admin_fee = 0

            entry = get_pending_receipt(ref_num)
            if not entry:
                requests.post(f"https://api.telegram.org/bot{token}/editMessageText", json={
                    "chat_id": chat_id,
                    "message_id": msg_id,
                    "text": f"⚠️ **TRANSAKSI KEDALUWARSA**\nData draf struk `{ref_num}` tidak ditemukan atau sudah diproses.",
                    "parse_mode": "Markdown",
                    "reply_markup": {"inline_keyboard": []},
                }, timeout=8)
                return

            p = entry.get("parsed", entry)
            nominal = p.get("nominal", 0)
            tx_date_str = p.get("date")

            try:
                tx_date = datetime.fromisoformat(tx_date_str).date()
            except Exception:
                tx_date = datetime.now(WIB).date()

            existing = db.query(Transaction).filter(
                Transaction.user_id == user.id,
                Transaction.raw_text.like(f"%[receipt_radar:ref_{ref_num}]%"),
            ).first()

            if existing:
                edit_text = (
                    f"ℹ️ **SUDAH TERCATAT SEBELUMNYA**\n"
                    f"Transaksi referensi `{ref_num}` sudah ada di buku besar Tillfold."
                )
            else:
                tx_out = Transaction(
                    user_id=user.id,
                    type="transfer_out",
                    account=source_acc,
                    amount=nominal,
                    category="Transfer",
                    description=f"Transfer ke {dest_acc} (Ref: {ref_num})",
                    raw_text=f"[receipt_radar:ref_{ref_num}] Auto-recorded transfer",
                    date=tx_date,
                )
                tx_in = Transaction(
                    user_id=user.id,
                    type="transfer_in",
                    account=dest_acc,
                    amount=nominal,
                    category="Transfer",
                    description=f"Transfer dari {source_acc} (Ref: {ref_num})",
                    raw_text=f"[receipt_radar:ref_{ref_num}] Auto-recorded transfer",
                    date=tx_date,
                )
                db.add(tx_out)
                db.add(tx_in)
                db.flush()

                # Link pair via pair_id tag
                tx_out.raw_text = f"{tx_out.raw_text} [pair_id:{tx_in.id}]"
                tx_in.raw_text = f"{tx_in.raw_text} [pair_id:{tx_out.id}]"

                if admin_fee > 0:
                    tx_fee = Transaction(
                        user_id=user.id,
                        type="expense",
                        account=source_acc,
                        amount=admin_fee,
                        category="Biaya Admin",
                        description=f"Biaya Admin Transfer ke {dest_acc} (Ref: {ref_num})",
                        raw_text=f"[receipt_radar:ref_{ref_num}_admin] Auto-recorded transfer admin fee",
                        date=tx_date,
                    )
                    db.add(tx_fee)

                db.commit()
                delete_pending_receipt(ref_num)

                edit_text = (
                    f"✅ **TRANSFER ANTAR-REKENING BERHASIL DICATAT**\n\n"
                    f"• **Dari**: `{source_acc}`\n"
                    f"• **Ke**: `{dest_acc}`\n"
                    f"• **Nominal**: `Rp {nominal:,}`\n"
                    f"• **Biaya Admin**: `Rp {admin_fee:,}`\n"
                    f"• **No. Ref**: `{ref_num}`"
                )

            requests.post(f"https://api.telegram.org/bot{token}/editMessageText", json={
                "chat_id": chat_id,
                "message_id": msg_id,
                "text": edit_text,
                "parse_mode": "Markdown",
                "reply_markup": {"inline_keyboard": []},
            }, timeout=8)
    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
    finally:
        db.close()


def process_update(update: dict, bot_token: Optional[str] = None, user_override: Optional[User] = None):
    callback_query = update.get("callback_query")
    if callback_query:
        handle_callback_query(callback_query, bot_token=bot_token)
        return

    message = update.get("message")
    if not message:
        return

    tg_user = message.get("from", {})
    chat_id = message.get("chat", {}).get("id")
    text = (message.get("text") or "").strip()
    message_id = message.get("message_id")

    logger.info("Telegram update received: chat_id=%s", chat_id)

    if not chat_id:
        return

    # Financial commands are only accepted from the sender's private conversation.
    if message.get("chat", {}).get("type") != "private" or tg_user.get("id") != chat_id or tg_user.get("is_bot"):
        return
    if bot_token or user_override:
        return

    db = SessionLocal()
    try:
        if text.startswith("/start link_"):
            from app.services.telegram_link import consume_link

            linked = consume_link(db, text[len("/start link_"):], int(chat_id))
            reply = ("Telegram terhubung ke Tillfold. Ketik /menu untuk mulai."
                     if linked else "Tautan tidak valid, kedaluwarsa, atau Telegram sudah terhubung ke akun lain. Buat tautan baru dari profil Tillfold.")
            send_message(chat_id, reply, parse_mode=None)
            return
        user = db.query(User).filter(
            User.telegram_chat_id == chat_id, User.is_active == True, User.telegram_mode == "shared",
        ).first()
        if not user:
            unlinked_msg = f"""Selamat datang di Tillfold.

Buka {settings.APP_BASE_URL}, masuk ke akun kamu, lalu pilih Profil → Integrasi Telegram → Hubungkan Telegram.

Tekan Start di bot dari tautan tersebut untuk menyelesaikan koneksi."""
            send_message(chat_id, unlinked_msg, bot_token=bot_token)
            return

        if type(message_id) is not int or message_id <= 0:
            return
        key = (chat_id, message_id)
        if db.get(TelegramProcessedMessage, key):
            return
        marker = TelegramProcessedMessage(chat_id=chat_id, message_id=message_id, user_id=user.id)

        def mark_financial_message(session, flush_context, instances):
            if any(isinstance(obj, Transaction) for obj in [*session.new, *session.dirty, *session.deleted]):
                session.add(marker)

        event.listen(db, "before_flush", mark_financial_message)
        try:
            dispatch_message(chat_id, message, message_id, text, db, user, bot_token)
            db.add(marker)
            db.commit()
        except IntegrityError:
            db.rollback()
            if not db.get(TelegramProcessedMessage, key):
                raise
        finally:
            event.remove(db, "before_flush", mark_financial_message)
    finally:
        db.close()

def dispatch_message(chat_id, message, message_id, text, db, user, bot_token):
    has_media = bool(message.get("photo") or message.get("voice") or message.get("audio") or message.get("document"))

    if has_media:
        handle_media_message(chat_id, message, message_id, db, user=user, bot_token=bot_token)
        return

    if not text:
        return

    lower_text = text.lower()
    cmd = text.split()[0].lower().split("@")[0] if text.split() else ""
    if (
        lower_text in ["📊 rekap", "rekap"]
        or cmd in ["/rekap", "/bulan", "/siklus"]
        or lower_text in ["rekap bulan", "rekap lalu", "rekap prev", "rekap siklus", "rekap kemarin"]
        or cmd == "/rekap"
    ):
        handle_rekap(chat_id, db, text=text, user=user, bot_token=bot_token)
    elif lower_text in ["💳 saldo", "saldo"] or cmd in ["/saldo"]:
        handle_saldo(chat_id, db, user=user, bot_token=bot_token)
    elif lower_text in ["🎯 pacing", "pacing", "pace", "burn rate"] or cmd in ["/pacing", "/pace", "/status"]:
        handle_pacing(chat_id, db, user=user, bot_token=bot_token)
    elif lower_text in ["🎯 target & goals", "🎯 target", "target", "goals", "milestone"] or cmd in ["/goals", "/target", "/milestone"]:
        handle_goals(chat_id, db, user=user, bot_token=bot_token)
    elif lower_text in ["🔔 tagihan / subs", "tagihan", "subs", "langganan"] or cmd in ["/subs", "/langganan", "/tagihan"]:
        handle_subs(chat_id, db, user=user, bot_token=bot_token)
    elif lower_text in ["📜 transaksi", "transaksi", "history"] or cmd in ["/transaksi", "/history"]:
        handle_transaksi(chat_id, db, user=user, bot_token=bot_token)
    elif lower_text in ["💰 info gajian"] or cmd == "/gajian" or lower_text.startswith("gajian ") or cmd == "gajian":
        handle_gajian(chat_id, text, db, user=user, bot_token=bot_token)
    elif lower_text in ["🔄 transfer", "transfer", "tf"] or cmd in ["/transfer", "/tf"] or lower_text.startswith("transfer ") or lower_text.startswith("tf "):
        handle_transfer(chat_id, text, db, user=user, bot_token=bot_token)
    elif lower_text in ["💸 pinjam", "pinjam", "talangan"] or cmd in ["/pinjam", "/talangan"] or lower_text.startswith(("pinjam ", "talangan ")):
        handle_pinjam(chat_id, text, db, user=user, bot_token=bot_token)
    elif lower_text in ["💳 lunasi", "lunasi", "bayar pinjam", "bayar_pinjam"] or cmd in ["/lunasi", "/bayar_pinjam", "/bayar-pinjam"] or lower_text.startswith(("lunasi ", "bayar_pinjam ", "bayar pinjam ")):
        handle_lunasi(chat_id, text, db, user=user, bot_token=bot_token)
    elif cmd in ["/set_sheet", "/setsheet", "/set-sheet"] or lower_text.startswith(("/set_sheet", "/setsheet", "/set-sheet", "set_sheet", "setsheet")):
        handle_set_sheet(chat_id, text, db, user=user, bot_token=bot_token)
    elif lower_text in ["📑 google sheets", "google sheets", "sheets"] or cmd in ["/sheets", "/sheet", "/sync_sheets"]:
        handle_sheets(chat_id, db, user=user, bot_token=bot_token)
    elif lower_text in ["🌐 web dashboard", "dashboard", "web"] or cmd in ["/web", "/dashboard"]:
        send_dashboard_link(chat_id, bot_token=bot_token)
    elif lower_text in ["📱 menu", "menu"] or cmd in ["/menu"]:
        handle_menu(chat_id, bot_token=bot_token)
    elif cmd in ["/start", "/help"]:
        handle_start(chat_id, user=user, bot_token=bot_token)
    elif lower_text in ["📓 obsidian", "obsidian"] or cmd in ["/obsidian", "/export"]:
        handle_obsidian(chat_id, db, user=user, bot_token=bot_token)
    elif cmd in ["/batal", "/undo", "/hapus"]:
        handle_batal(chat_id, db, user=user, bot_token=bot_token)
    else:
        handle_text_message(chat_id, text, message_id, db, user=user, bot_token=bot_token)


def main():
    print("Connecting to PostgreSQL and creating tables if not exist...")
    Base.metadata.create_all(bind=engine)
    from app.db.account_schema import ensure_account_archive_schema, ensure_user_spreadsheet_schema
    ensure_account_archive_schema(engine)
    ensure_user_spreadsheet_schema(engine)
    print("Setting up Telegram bot commands menu...")
    setup_bot_commands()
    print("Tillfold shared bot started listening...")

    offset = 0
    while True:
        try:
            url = f"{API_BASE}/getUpdates?offset={offset}&timeout=30"
            resp = requests.get(url, timeout=35)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        process_update(update)
                        offset = update["update_id"] + 1
            else:
                time.sleep(2)
        except requests.exceptions.Timeout:
            continue
        except requests.exceptions.RequestException as e:
            print(f"Network error: {e}")
            time.sleep(3)
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
