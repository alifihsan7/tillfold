#!/usr/bin/env python3
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Auto-reexec inside the project's dedicated virtualenv to ensure native bcrypt & pydantic support
VENV_PYTHON = os.path.join(BASE_DIR, "venv", "bin", "python")
if sys.executable != VENV_PYTHON and os.path.exists(VENV_PYTHON):
    os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)

import requests
from datetime import datetime
import zoneinfo

# Load env from ai7-finance backend
ENV_PATH = os.path.join(BASE_DIR, "backend", ".env")
env_vars = {}
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip().strip("'\"")

BOT_TOKEN = env_vars.get("BOT_TOKEN")
CHAT_ID = env_vars.get("ALLOWED_USER_ID")
if not CHAT_ID:
    print("ALLOWED_USER_ID not configured; skipping digest.")
    sys.exit(0)

API_URL = "http://127.0.0.1:8080/api/v1/analytics/summary"

sys.path.insert(0, os.path.join(BASE_DIR, "backend"))
try:
    from app.core.security import create_local_job_token
    from app.db.session import SessionLocal
    with SessionLocal() as session:
        AUTH_HEADERS = {"Authorization": f"Bearer {create_local_job_token(session, 1)}"}
except Exception:
    print("Akun pengingat tidak dapat diautentikasi; pengiriman dibatalkan.", file=sys.stderr)
    sys.exit(1)

try:
    wib = zoneinfo.ZoneInfo("Asia/Jakarta")
    now_wib = datetime.now(wib)
except Exception:
    now_wib = datetime.now()

def fmt_rp(val):
    return f"Rp {val:,.0f}".replace(",", ".")

def main():
    try:
        res = requests.get(API_URL, headers=AUTH_HEADERS, timeout=10)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print(f"Error fetching analytics summary: {e}", file=sys.stderr)
        sys.exit(1)

    sts = data.get("safe_to_spend", {})
    accounts = {a.get("account"): a.get("balance", 0) for a in data.get("accounts", [])}
    
    day_cycle = sts.get("day_of_cycle", 1)
    days_rem = sts.get("days_remaining", 14)
    pocket_budget = sts.get("pocket_budget", 825000)
    pocket_spent = sts.get("pocket_spent", 0)
    pocket_rem = sts.get("pocket_remaining", 0)
    safe_daily = sts.get("safe_daily", 0)
    pace_status = sts.get("pace_status", "on_track")

    if pace_status in ["on_track", "ahead"]:
        status_label = "🟢 **On Track** (Pengeluaran hemat & terkontrol)"
    elif pace_status == "warning":
        status_label = "🟡 **Pacing Warning** (Pengeluaran di atas batas rata-rata)"
    else:
        status_label = "🔴 **Over Budget** (Budget amplop 14-hari terlampaui)"

    lines = [
        "🌙 **AI7 Finance — Nightly Pacing Briefing**",
        f"🕒 `{now_wib.strftime('%d %B %Y - %H:%M WIB')}` (Siklus H-{day_cycle}/14)",
        "",
        "🎯 **Pacing Belanja Kantong (Mandiri):**",
        f"• Terpakai: `{fmt_rp(pocket_spent)}` / `{fmt_rp(pocket_budget)}`",
        f"• Sisa Budget Siklus: `{fmt_rp(pocket_rem)}` ({days_rem} hari tersisa)",
        f"• Batas Safe-to-Spend: `{fmt_rp(safe_daily)} / hari`",
        f"• Status: {status_label}",
        "",
        "💳 **Estimasi Saldo Rekening:**",
        f"• Mandiri (Operasional): `{fmt_rp(accounts.get('Mandiri', 0))}`",
        f"• Bank Jago (Subs/Invest): `{fmt_rp(accounts.get('Bank Jago', 0))}`",
        f"• BRI 1 (Emergency): `{fmt_rp(accounts.get('BRI 1', 0))}`",
        f"• BRI 2 (Tabungan): `{fmt_rp(accounts.get('BRI 2', 0))}`",
    ]

    message = "\n".join(lines)

    # Send to Telegram bot
    if BOT_TOKEN and CHAT_ID:
        try:
            tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            requests.post(tg_url, json={
                "chat_id": int(CHAT_ID),
                "text": message,
                "parse_mode": "Markdown"
            }, timeout=10)
        except Exception as e:
            print(f"Error posting to Telegram: {e}", file=sys.stderr)

    # Print to stdout
    print(message)

if __name__ == "__main__":
    main()
