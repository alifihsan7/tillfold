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
    print("ALLOWED_USER_ID not configured; skipping subscription alerts.")
    sys.exit(0)

API_URL = "http://127.0.0.1:8080/api/v1/subscriptions"

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

def main():
    try:
        res = requests.get(API_URL, headers=AUTH_HEADERS, timeout=10)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print(f"Error fetching subscriptions: {e}", file=sys.stderr)
        sys.exit(1)

    items = data.get("items", [])
    urgent_items = []

    for item in items:
        if not item.get("is_active"):
            continue
        days = item.get("days_until_due")
        if days in [0, 1]:
            urgent_items.append(item)

    if not urgent_items:
        # Silent exit if nothing is due today or tomorrow
        sys.exit(0)

    # Format Telegram Alert
    lines = ["🔔 **Pengingat Tagihan & Langganan AI7 Finance**", f"🕒 `{now_wib.strftime('%d %B %Y - %H:%M WIB')}`", ""]

    for item in urgent_items:
        name = item.get("name", "Tagihan")
        amt = item.get("amount", 0)
        account = item.get("account", "Jago")
        cat = item.get("category", "Langganan")
        days = item.get("days_until_due")
        date_str = item.get("next_billing_date", "")

        is_exact = item.get("billing_type") == "exact_date"
        action_verb = "Berakhir" if is_exact else "Jatuh tempo"
        due_label = "⚡ **HARI INI**" if days == 0 else "⏳ **BESOK**"
        lines.append(f"• **{name}** — `Rp {amt:,.0f}`".replace(",", "."))
        lines.append(f"  {action_verb}: {due_label} (`{date_str}`)")
        lines.append(f"  Rekening: **{account}** | Kategori: *{cat}*")
        lines.append("")

    lines.append("💡 *Pastikan saldo rekening autodebet lo mencukupi agar layanan tidak terputus.*")
    message = "\n".join(lines)

    # Send to Telegram bot if token available
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
