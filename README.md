# Tillfold 💸

> **Production-ready, multi-tenant personal finance ecosystem** engineered for friction-free daily expense capture via Telegram and deep analytical budgeting via a modern dark-themed web dashboard.
>
> 🌐 **Live Production:** [tillfold.alifihsan.my.id](https://tillfold.alifihsan.my.id)  
> 🤖 **Official Telegram Companion:** [@tillfold_bot](https://t.me/tillfold_bot)

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js_14-black?logo=next.js&logoColor=white)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Tailwind CSS](https://img.shields.io/badge/UI-Tailwind_CSS-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🌟 Highlights & Capabilities

- **⚡ Zero-Friction Telegram Capture:** Log expenses in under a second using regex natural language parsing (`kopi 25k mandiri`, `bensin 50rb cash`, `gaji 5jt`).
- **🤖 Official Companion Bot ([@tillfold_bot](https://t.me/tillfold_bot)):** Direct shared bot architecture. Connect your account securely via one-time 10-minute linking codes from **Profil → Integrasi Telegram** with zero multi-tenant leakage.
- **📱 Telegram Mini App (TMA):** Access the entire Next.js financial dashboard natively within Telegram via the persistent "📊 Dashboard" menu button, featuring zero-click cryptographic auto-login (HMAC-SHA256 Single Sign-On).
- **📅 Transaction Calendar View:** Visual Monday-first monthly calendar grid mapping daily income, expense totals, transfers, and balance reconciliation adjustments with responsive compact currency formatting.
- **🔍 Global Search (Ctrl+K / ⌘K):** Instant modal search across transactions, bank accounts, recurring bills, and savings goals across all periods—including archived records and formatted currency figures.
- **📦 Account Archive & Historical Ledger:** Safely archive dormant bank accounts without corrupting past double-entry balance transfers. Seamlessly falls back to remaining active default accounts.
- **⚖️ Balance Reconciliation:** Reconcile real-world bank balances directly via **Pengaturan → Rekening → Cocokkan saldo**. Automatically records balance correction adjustments without falsifying operational P&L.
- **🔔 Bill & Subscription Tracker:** Manage fixed commitments, active recurring subscriptions, and manual payments with single-click payment records and automatic pocket ledger sync.
- **💾 Snapshot Backup & Atomic Restore:** Export full encrypted or versioned JSON snapshots (accounts, transactions, categories, pockets, bills, goals, paycheck settings). Full atomic import with schema migration guards.
- **🔄 Dynamic Budget Cycles:** Flexible budget periods tailored to your actual paycheck cycle—**Weekly (7 Days)**, **Bi-Weekly (14 Days)**, or **Monthly (30 Days)**—with automated cycle rollover and historical tracking.
- **📉 Burn-Rate Trajectory & Pacing:** Real-time safe-to-spend velocity meter (`Rp/hari`), pacing status indicators (🟢 Pace Aman vs 🔴 Agak Boros), and ideal cumulative pace lines.
- **🛡️ Telegram Ledger Idempotency:** Persistent `(chat_id, message_id)` idempotency guard prevents double-entry anomalies under network retries or accidental duplicate sends.

---

## 🏗️ System Architecture

```text
               +-------------------------------------------------------------+
               |                       Telegram Clients                      |
               |  (Voice Notes, Photos/Receipts, Text Tx, Telegram Mini App) |
               +------------------------------+------------------------------+
                                              |
                                              v
                                +---------------------------+
                                |    Tillfold Bot Engine    |
                                |      (@tillfold_bot)      |
                                +-------------+-------------+
                                              |
                                              v
+-----------------------+      +-------------------------------+      +-----------------------+
|   Next.js 14 Client   |<---->|      FastAPI REST Server      |<---->|   PostgreSQL RDBMS    |
| (TMA & Web Dashboard) |      |  (/api/v1/ auth, tx, summary) |      | (ACID Multi-Tenant DB)|
+-----------------------+      +---------------+---------------+      +-----------------------+
                                              |
                                              v
                              +-------------------------------+
                              |    Background Cron Services   |
                              |  (Pacing Watchdog, Sub Alert) |
                              +-------------------------------+
```

---

## 📚 Technical Specifications & Documentation

- 🏛️ **[Spesifikasi Arsitektur Sistem (docs/ARCHITECTURE.md)](docs/ARCHITECTURE.md)** — Penjelasan mendalam mengenai isolasi multi-tenant, ERD database PostgreSQL, formula matematika *Safe-to-Spend*, spesifikasi parser regex nominal, dan verifikasi kriptografis TMA.
- 🚀 **[Panduan Production Deployment (docs/DEPLOYMENT.md)](docs/DEPLOYMENT.md)** — Panduan operasi server Linux 24/7 dengan systemd services, setup database PostgreSQL, reverse proxy HTTPS, dan konfigurasi Google OAuth 2.0.
- 🔍 **[Global Search Specification (docs/GLOBAL-SEARCH-2026-11-08.md)](docs/GLOBAL-SEARCH-2026-11-08.md)** — Spesifikasi modal global search (Ctrl+K) dan indexing lintas periode.
- 📅 **[Transaction Calendar Design (docs/TRANSACTION-CALENDAR-2026-11-08.md)](docs/TRANSACTION-CALENDAR-2026-11-08.md)** — Arsitektur kalender transaksi visual dan kalkulasi agregasi harian.
- 📦 **[Account Archive Design (docs/ACCOUNT-ARCHIVE-2026-11-08.md)](docs/ACCOUNT-ARCHIVE-2026-11-08.md)** — Kebijakan pengarsipan akun tanpa merusak integritas buku besar transfer atomik.

---

## 🚀 Quickstart Guide

### Prerequisites
- **Python 3.10+**
- **Node.js 18+** & `npm`
- **PostgreSQL 14+**
- Telegram Bot token from [@BotFather](https://t.me/BotFather)

---

### 1. Clone & Set Up Python Environment

```bash
git clone https://github.com/alifihsan7/tillfold.git
cd tillfold

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt
```

---

### 2. Configure Environment Variables

```bash
cp .env.example backend/.env
```

Open `backend/.env` and update the required keys:

```env
# PostgreSQL connection string
DATABASE_URL=postgresql://alifihsan:***@localhost:5432/ai7_finance

# JWT secret (generate one with: openssl rand -hex 32)
JWT_SECRET_KEY=your_generated_32_char_secret_key

# Telegram Bot Token from @BotFather
BOT_TOKEN=your_bot_token_from_botfather

# Base URL for Web Dashboard and OAuth
APP_BASE_URL=https://tillfold.alifihsan.my.id

# Local Timezone
TIMEZONE=Asia/Jakarta
```

---

### 3. Build Web Dashboard Frontend

```bash
cd frontend
npm install
npm run build
cd ..

# Sync static export to FastAPI static root
rm -rf static/*
cp -r frontend/out/* static/
cp frontend/public/manifest.json static/
```

---

### 4. Run Services

#### Starting the Web API & Dashboard
```bash
./run_web.sh
# Server starts at http://localhost:8080
```

#### Starting the Telegram Bot
```bash
./run_bot.sh
```

---

## 💬 Telegram Bot Quick Ingestion Syntax

The bot parses natural language strings instantly with zero LLM token costs:

| User Input | Type | Amount | Account | Category | Description |
|---|---|---|---|---|---|
| `kopi 25k mandiri` | Expense | Rp 25.000 | Mandiri | Jajan / Ngopi | Kopi |
| `makan siang 35rb mandiri` | Expense | Rp 35.000 | Mandiri | Makanan & Minuman | Makan siang |
| `bensin 50000 cash` | Expense | Rp 50.000 | Cash | Transportasi | Bensin |
| `gaji 5000000 mandiri` | Income | Rp 5.000.000 | Mandiri | Gaji & Pendapatan | Gaji |
| `tf 100k bri 2 ke bri 1` | Transfer | Rp 100.000 | BRI 2 -> BRI 1 | Transfer Saldo | Pindah dana |

### Supported Bot Commands
- `/start` — Check authorization or link Telegram account with a 10-minute sync token from web profile.
- `/menu` — Interactive keyboard with quick access to all bot features.
- `/saldo` — View real-time wallet balances across all bank accounts and pockets.
- `/pacing` — View safe-to-spend pacing and days remaining in the active paycheck cycle.
- `/rekap` — Get a summary of current period income, expenses, and savings rate.
- `/goals` — View savings milestones and goal progression.
- `/subs` — View and manage fixed commitments, monthly and annual subscriptions.
- `/transaksi` — Display last 5 logged transactions with quick cancellation options.
- `/transfer` — Transfer balance between pockets or bank accounts.
- `/gajian` — Log paycheck income and execute percentage-based envelope allocations.
- `/sheets` — Trigger Google Sheets sync snapshot.
- `/batal` — Revert the most recently recorded transaction safely.
- `/help` — Display syntax examples and usage guide.

---

## 🛠️ Production Deployment

Untuk panduan operasi 24/7 di server Linux (Ubuntu/Debian) dengan systemd:

1. **Layanan Background:** Dikelola melalui unit systemd `ai7-finance-web.service` (FastAPI backend & web dashboard di port 8080) dan `ai7-finance.service` (Telegram companion bot).
2. **Reverse Proxy & SSL:** Menggunakan Cloudflare Tunnel atau Nginx reverse proxy untuk meneruskan traffic HTTPS ke backend lokal (`http://127.0.0.1:8080`).
3. **Autentikasi Google:** Daftarkan origin domain publik (`https://tillfold.alifihsan.my.id`) di Google Cloud Console (*Authorized JavaScript origins* & *Authorized redirect URIs*).

👉 **[Detail Lengkap Panduan Deployment (docs/DEPLOYMENT.md)](docs/DEPLOYMENT.md)**

---

## 🔒 Security & Privacy

- **SQL Injection Prevention:** 100% parametrized queries via SQLAlchemy ORM.
- **Stateless Bearer Tokens:** HS256 JWT tokens with configurable TTL.
- **Tenant Data Isolation:** Every query explicitly scopes by authenticated `user_id`.
- **Zero Secrets in Repository:** Credentials, `.env`, tokens, and service account JSONs are strictly gitignored.
- **Telegram Webhook / Polling Guard:** Cryptographic verification and sender ownership validation prevent impersonation.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
