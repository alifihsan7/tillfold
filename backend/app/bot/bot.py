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
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, case

from app.core.config import settings
from app.core.parser import parse_transaction, parse_multi_transactions, parse_amount
from app.core.transfer import find_paired_transfer
from app.db.session import SessionLocal, Base, engine
from app.models.transaction import Transaction
from app.models.subscription import SubscriptionPayment
from app.core.ledger import POSITIVE_TYPES, NEGATIVE_TYPES
from app.models.account import Account
from app.models.jago_pocket import JagoPocket
from app.models.paycheck import PaycheckConfig, PaycheckBucket, PaycheckReceipt, PaycheckCycle
from app.models.subscription import Subscription
from app.models.goal import Goal
from app.models.user import User

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

    return f"🛡️ **Safe-to-Spend:** {format_rp(metrics.safe_daily)} / hari ({pace_icon} {pace_label} • Sisa {metrics.days_remaining} hari)"

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
        {"command": "rekap", "description": "📊 Rekap pengeluaran & pacing belanja"},
        {"command": "goals", "description": "🎯 Target tabungan & milestone finansial"},
        {"command": "transfer", "description": "🔄 Transfer antar rekening"},
        {"command": "subs", "description": "🔔 Jadwal langganan & tagihan rutin"},
        {"command": "transaksi", "description": "📜 5 transaksi terakhir"},
        {"command": "gajian", "description": "💰 Catat gajian & siapkan alokasi pos"},
        {"command": "sheets", "description": "📑 Sinkronisasi snapshot ke Google Sheets"},
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
• `/rekap` - Ringkasan pengeluaran bulan ini
• `/transaksi` - 5 transaksi terakhir
• `/batal` - Hapus/batalkan transaksi terakhir jika salah
• `/subs` - Cek jadwal langganan & tagihan rutin
• `/goals` - Pantau target finansial & milestone
• `/gajian [nominal]` - Catat gajian & siapkan rencana alokasi rekening
• `/transfer` - Pindahkan saldo antar rekening
• `/menu` - Tampilkan tombol menu cepat

Tinggal ketik catatan pengeluaran/pemasukan lo kapan saja!"""
    send_message(chat_id, msg, reply_markup=get_main_keyboard(), bot_token=bot_token)

def handle_rekap(chat_id: int, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return
    user_id = user.id
    now = datetime.now(WIB)
    month_names = [
        "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember"
    ]
    month_name = month_names[now.month]
    start_date = date(now.year, now.month, 1)
    end_date = date(now.year + 1, 1, 1) if now.month == 12 else date(now.year, now.month + 1, 1)

    totals = db.query(
        Transaction.type,
        func.coalesce(func.sum(Transaction.amount), 0).label("total")
    ).filter(
        Transaction.user_id == user_id,
        Transaction.date >= start_date,
        Transaction.date < end_date
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
        Transaction.date < end_date,
        Transaction.type == "expense"
    ).group_by(Transaction.category).order_by(func.sum(Transaction.amount).desc()).all()

    lines = [
        f"📊 **Rekap Keuangan - {month_name} {now.year}**\n",
        f"💰 **Total Pemasukan:** {format_rp(income_total)}",
        f"💸 **Total Pengeluaran:** {format_rp(expense_total)}",
        f"📈 **Net Cashflow:** {format_rp(net_total)}\n",
        "📂 **Rincian Pengeluaran per Kategori:**"
    ]

    if not cat_rows:
        lines.append("_Belum ada pengeluaran yang tercatat bulan ini._")
    else:
        for cat in cat_rows:
            lines.append(f"• **{cat.category}**: {format_rp(int(cat.total))} ({cat.count}x)")

    lines.append(f"\n{get_safe_to_spend_snippet(db, user_id=user_id)}")
    send_message(chat_id, "\n".join(lines), bot_token=bot_token)

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

    all_user_pockets = db.query(JagoPocket).filter(
        JagoPocket.user_id == user_id,
        JagoPocket.is_active == True,
    ).all()

    pocket_by_account: dict[int, list[JagoPocket]] = {}
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
        if not acc_pockets and any(k in acc.name.lower() for k in ["jago", "pocket"]):
            acc_pockets = [p for p in all_user_pockets if p.account_id is None]

        if acc_pockets:
            sum_other_targets = sum(int(p.target_amount) for p in acc_pockets if not p.slug.startswith("utama"))
            for p in acc_pockets:
                p_amt = int(p.target_amount)
                if p.slug.startswith("utama") and p_amt == 0:
                    p_amt = max(0, bal - sum_other_targets)
                role_icon = "🛍️" if p.role == "operasional" else "🔒"
                lines.append(f"  └ {role_icon} {p.name}: {format_rp(p_amt)}")

    lines.append(f"\n💵 **Total Keseluruhan:** {format_rp(total)}")
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
    if not raw:
        return None
    r = raw.strip().lower()
    if db and user_id is not None:
        for acc in db.query(Account).filter(Account.user_id == user_id).all():
            if acc.name.lower() in r or r in acc.name.lower():
                return acc.name
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

def handle_transfer(chat_id: int, text: str, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return
    user_id = user.id
    clean = text.strip()

    user_accs = db.query(Account).filter(Account.user_id == user_id).order_by(Account.id.asc()).all()
    acc_options_str = ", ".join(f"`{a.name}`" for a in user_accs) if user_accs else "`Rekening Utama`, `Rekening Tagihan`, `Tabungan`"

    if clean.lower() in ["/transfer", "transfer", "tf", "🔄 transfer"]:
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

    pattern = re.compile(r"^(?:/transfer|transfer|tf)\s+([\d\.\,kKrbRB]+)\s+(?:dari\s+)?([a-zA-Z0-9\s]+?)\s+ke\s+([a-zA-Z0-9\s]+?)(?:\s*[:\-]\s*(.*)|\s+(.*))?$", re.IGNORECASE)
    match = pattern.match(clean)
    if not match:
        send_message(chat_id, "⚠️ Format transfer tidak dikenali.\n\nContoh:\n`tf 100k utama ke tabungan`\natau ketik `/transfer` untuk panduan lengkap.", bot_token=bot_token)
        return

    amt_str, from_raw, to_raw, desc1, desc2 = match.groups()
    from app.core.parser import parse_amount
    amt, _ = parse_amount(amt_str)
    if not amt or amt <= 0:
        send_message(chat_id, "⚠️ Nominal transfer tidak valid.", bot_token=bot_token)
        return

    from_acc = normalize_account(from_raw, db, user_id=user_id)
    to_acc = normalize_account(to_raw, db, user_id=user_id)

    valid_acc_names = {a.name.lower(): a.name for a in user_accs}
    if user_accs:
        from_matched = valid_acc_names.get(from_acc.lower()) if from_acc else None
        to_matched = valid_acc_names.get(to_acc.lower()) if to_acc else None
        if not from_matched:
            send_message(chat_id, f"⚠️ Rekening asal `{from_raw}` tidak dikenali.\nPilihan rekening Anda:\n{acc_options_str}", bot_token=bot_token)
            return
        if not to_matched:
            send_message(chat_id, f"⚠️ Rekening tujuan `{to_raw}` tidak dikenali.\nPilihan rekening Anda:\n{acc_options_str}", bot_token=bot_token)
            return
        from_acc = from_matched
        to_acc = to_matched
    else:
        if not from_acc:
            send_message(chat_id, f"⚠️ Rekening asal `{from_raw}` tidak dikenali.\nPilihan rekening Anda:\n{acc_options_str}", bot_token=bot_token)
            return
        if not to_acc:
            send_message(chat_id, f"⚠️ Rekening tujuan `{to_raw}` tidak dikenali.\nPilihan rekening Anda:\n{acc_options_str}", bot_token=bot_token)
            return

    if from_acc.lower() == to_acc.lower():
        send_message(chat_id, "⚠️ Rekening asal dan rekening tujuan tidak boleh sama.", bot_token=bot_token)
        return

    desc = (desc1 or desc2 or "Transfer Antar Rekening").strip()
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

    db.query(SubscriptionPayment).filter(
        SubscriptionPayment.user_id == user_id, SubscriptionPayment.transaction_id == last.id,
    ).delete(synchronize_session=False)
    deleted_info = {
        "description": last.description,
        "amount": last.amount,
        "account": last.account,
        "category": last.category,
        "type": last.type,
    }

    is_paired_transfer = False
    pair_account = None

    if last.type in ("transfer_out", "transfer_in"):
        pair = find_paired_transfer(db, last)
        if pair:
            is_paired_transfer = True
            pair_account = pair.account
            db.delete(pair)

    db.delete(last)
    db.commit()

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

    cfg = get_or_seed_config(db, user_id)
    buckets = get_or_seed_buckets(db, cfg.id)
    user_accs = db.query(Account).filter(Account.user_id == user_id).order_by(Account.id.asc()).all()
    accounts_by_name = {a.name: a for a in user_accs}

    source_account = cfg.source_account if (cfg.source_account and cfg.source_account in accounts_by_name) else (user_accs[0].name if user_accs else "Rekening Utama")

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
        parsed_amt, _ = parse_amount(parts[1])

    if not parsed_amt or parsed_amt <= 0:
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
{alloc_str}

💡 *Untuk mencatat gajian baru:*
Ketik: `/gajian [nominal]` (contoh: `/gajian 5.000.000` atau `/gajian 5jt`)"""
            send_message(chat_id, msg, bot_token=bot_token)
            return
        else:
            msg = f"""💰 **Pencatatan Gajian & Payroll**

Gunakan perintah ini untuk mencatat gaji masuk secara rapi dan menyiapkan alur pembagian ke rekening/pos anggaran.

📌 **Cara Pakai:**
`/gajian [nominal]`
Contoh: `/gajian 5.000.000` atau `/gajian 5jt`

🏦 **Rekening Penampung Default:** `{source_account}`
📅 **Siklus Tanggal Anggaran:** `{cycle_label}`

ℹ️ _Gaji akan dicatat sebagai pemasukan riil di rekening penampung. Pos alokasi rekening lain disiapkan sebagai rencana transfer terpisah._"""
            send_message(chat_id, msg, bot_token=bot_token)
            return

    total = int(parsed_amt)

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

    # 5. Sheets auto-sync for admin account
    sheet_info = ""
    if user_id == 1:
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

    msg = f"""🎉 **GAJIAN MASUK & ALUR ANGGARAN TERCATAT!**

💰 **Total Gaji Masuk:** {format_rp(total)}
📥 **Rekening Penerima:** `{source_account}`
📅 **{cycle_label}:** {cycle_start.strftime('%d %b')} – {cycle_end.strftime('%d %b %Y')}

📊 **Rencana Alokasi Pos ({len(buckets)} Pos Anggaran):**
{distrib_str}

ℹ️ _Pemasukan gaji dicatat utuh di rekening `{source_account}`. Alokasi transfer ke rekening/pos lain dapat dieksekusi terpisah via `/transfer` atau Checklist Dashboard._
🌐 [Buka dashboard Tillfold]({settings.APP_BASE_URL}){sheet_info}"""

    send_message(chat_id, msg, bot_token=bot_token)

def handle_sheets(chat_id: int, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", bot_token=bot_token)
        return
    user_id = user.id
    if user_id != 1:
        send_message(chat_id, "ℹ️ Integrasi Google Sheets dikonfigurasi khusus untuk akun admin utama.", bot_token=bot_token)
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

def handle_text_message(chat_id: int, text: str, message_id: int, db: Session, user: Optional[User] = None, bot_token: Optional[str] = None, voice_prefix: str = ""):
    if not user:
        send_message(chat_id, "⚠️ Pengguna tidak ditemukan atau belum terdaftar.", reply_to_message_id=message_id, bot_token=bot_token)
        return
    user_id = user.id
    items = parse_multi_transactions(text)
    if not items:
        # Fall back to single parser to report specific error
        fallback = parse_transaction(text)
        err_msg = fallback.get("error", "Format tidak terdeteksi.")
        send_message(chat_id, f"{voice_prefix}❌ {err_msg}", reply_to_message_id=message_id, bot_token=bot_token)
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

    if media_type == "audio":
        try:
            import httpx
            fn = os.path.basename(file_path) if file_path else "audio.ogg"
            resp = httpx.post(
                "http://127.0.0.1:8090/v1/audio/transcriptions",
                files={"file": (fn, file_bytes)},
                data={
                    "language": "id",
                    "prompt": "Mandiri, Bank Jago, Bibit, pengeluaran, pemasukan, transfer, warteg, nasi padang, kopi, indomaret, alfamart"
                },
                timeout=60.0
            )
            if resp.status_code == 200:
                stt_res = resp.json()
                transcribed_text = (stt_res.get("text") or "").strip()
                if transcribed_text:
                    full_text = f"{transcribed_text} ({caption})" if caption else transcribed_text
                    handle_text_message(
                        chat_id=chat_id,
                        text=full_text,
                        message_id=message_id,
                        db=db,
                        user=user,
                        bot_token=bot_token,
                        voice_prefix=f"🎙️ *Suara Terdeteksi:* \"_{transcribed_text}_\"\n\n"
                    )
                    return
        except Exception as e:
            logger.error(f"Whisper STT in finance bot failed: {e}")

    db_accounts = [a.name for a in db.query(Account).filter(Account.user_id == user_id).all()]
    all_accounts = list(set(["Mandiri", "Bank Jago", "Bibit", "BRI 1", "BRI 2"] + db_accounts))

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

    tx_list = extraction.get("transactions", [])
    transcription = extraction.get("transcription", "")
    kind = extraction.get("kind", "media")

    if media_type == "image":
        media_header = "🤖📸 **Struk / QRIS Berhasil Dicatat Otomatis!**"
        quote_line = f"🧾 _{transcription}_\n" if transcription else ""
    else:
        media_header = "🤖🎙️ **Voice Note Berhasil Dicatat Otomatis!**"
        quote_line = f"🗣️ _\"{transcription}\"_\n" if transcription else ""

    if len(tx_list) == 1:
        item = tx_list[0]
        tx_type = item.get("type", "expense")

        if tx_type == "transfer":
            from_acc = normalize_account(item.get("from_account", "Mandiri"), db, user_id=user_id) or "Mandiri"
            to_acc = normalize_account(item.get("to_account", "Bibit"), db, user_id=user_id) or "Bibit"
            amt = int(item.get("amount", 0))
            desc = item.get("description", "Transfer Media")

            tx_out = Transaction(
                user_id=user_id,
                type="transfer_out",
                amount=amt,
                account=from_acc,
                category="Transfer",
                description=f"Transfer ke {to_acc}: {desc}",
                raw_text=f"ai media transfer: {kind} {desc}",
                date=now_wib.date()
            )
            tx_in = Transaction(
                user_id=user_id,
                type="transfer_in",
                amount=amt,
                account=to_acc,
                category="Transfer",
                description=f"Transfer dari {from_acc}: {desc}",
                raw_text=f"ai media transfer: {kind} {desc}",
                date=now_wib.date()
            )
            db.add(tx_out)
            db.add(tx_in)
            db.flush()
            tx_out.raw_text = f"{tx_out.raw_text} [pair_id:{tx_in.id}]"
            tx_in.raw_text = f"{tx_in.raw_text} [pair_id:{tx_out.id}]"
            db.commit()

            bal_from = get_acc_balance(from_acc, db, user_id=user_id)
            bal_to = get_acc_balance(to_acc, db, user_id=user_id)

            reply = f"""{media_header}
{quote_line}
🔄 **Transfer Antar Rekening**

💸 **Nominal:** `{format_rp(amt)}`
📤 **Dari:** {from_acc} (Sisa Saldo: `{format_rp(bal_from)}`)
📥 **Ke:** {to_acc} (Saldo Baru: `{format_rp(bal_to)}`)
📝 **Keterangan:** {desc}
🕒 _{time_str} WIB_

ℹ️ _Saldo berhasil dipindahkan. Transaksi ini tidak memotong kuota Safe-to-Spend._"""
            send_message(chat_id, reply, reply_to_message_id=message_id, bot_token=bot_token)
            return

        amt = int(item.get("amount", 0))
        acc = normalize_account(item.get("account", "Mandiri"), db, user_id=user_id) or "Mandiri"
        cat = item.get("category", "Lain-lain")
        desc = item.get("description", "Pengeluaran Media")

        tx = Transaction(
            user_id=user_id,
            type=tx_type,
            amount=amt,
            account=acc,
            category=cat,
            description=desc,
            raw_text=f"ai media {kind}: {desc} {amt}",
            date=now_wib.date()
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)

        type_label = "Pemasukan" if tx.type == "income" else "Pengeluaran"
        icon = "💰" if tx.type == "income" else "💸"

        reply = f"""{media_header}
{quote_line}
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

    # Multiple transactions
    created_txs = []
    total_amount = 0
    categories_touched = set()

    for item in tx_list:
        tx_type = item.get("type", "expense")
        amt = int(item.get("amount", 0))
        acc = normalize_account(item.get("account", "Mandiri"), db, user_id=user_id) or "Mandiri"
        cat = item.get("category", "Lain-lain")
        desc = item.get("description", "Pengeluaran Media")

        tx = Transaction(
            user_id=user_id,
            type=tx_type,
            amount=amt,
            account=acc,
            category=cat,
            description=desc,
            raw_text=f"ai media multi {kind}: {desc} {amt}",
            date=now_wib.date()
        )
        db.add(tx)
        created_txs.append(tx)
        total_amount += amt
        if is_matching_pocket_account(acc, pocket_account) and tx_type == "expense":
            categories_touched.add(cat)

    db.commit()
    for tx in created_txs:
        db.refresh(tx)

    lines = [
        media_header,
        quote_line,
        f"✅ **{len(created_txs)} Transaksi Berhasil Dicatat Sekaligus!**\n"
    ]
    for idx, tx in enumerate(created_txs, 1):
        icon = "💰" if tx.type == "income" else "💸"
        lines.append(f"{idx}. {icon} **{format_rp(tx.amount)}** • {tx.description}\n   📂 `{tx.category}` • 💳 `{tx.account}`")

    lines.append(f"\n💵 **Total:** {format_rp(total_amount)}")
    lines.append(f"🕒 _{time_str} WIB_")

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

    send_message(chat_id, "\n".join([line for line in lines if line]), reply_to_message_id=message_id, bot_token=bot_token)

def process_update(update: dict, bot_token: Optional[str] = None, user_override: Optional[User] = None):
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

        has_media = bool(message.get("photo") or message.get("voice") or message.get("audio") or message.get("document"))

        if has_media:
            handle_media_message(chat_id, message, message_id, db, user=user, bot_token=bot_token)
            return

        if not text:
            return

        lower_text = text.lower()
        cmd = text.split()[0].lower()
        if lower_text in ["📊 rekap", "rekap"] or cmd in ["/rekap", "/bulan"]:
            handle_rekap(chat_id, db, user=user, bot_token=bot_token)
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
    finally:
        db.close()

def main():
    print("Connecting to PostgreSQL and creating tables if not exist...")
    Base.metadata.create_all(bind=engine)
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
                        offset = update["update_id"] + 1
                        process_update(update)
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
