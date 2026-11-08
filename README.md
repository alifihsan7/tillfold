# Tillfold 💸

> **Production-ready, multi-tenant personal finance ecosystem** engineered for friction-free daily expense capture via Telegram and deep analytical budgeting via a modern dark-themed web dashboard.
>
> 🌐 **Live Production:** [tillfold.alifihsan.my.id](https://tillfold.alifihsan.my.id)

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js_14-black?logo=next.js&logoColor=white)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Tailwind CSS](https://img.shields.io/badge/UI-Tailwind_CSS-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🌟 Highlights

- **⚡ Zero-Friction Telegram Capture:** Log expenses in under a second using regex natural language parsing (`kopi 25k bca`, `bensin 50rb cash`, `gaji 5jt`).
- **📱 Telegram Mini App (TMA):** Access the entire Next.js financial dashboard natively within Telegram via the persistent "📊 Dashboard" menu button, featuring zero-click cryptographic auto-login (HMAC-SHA256 Single Sign-On).
- **🔐 Multi-Tenant Architecture:** Built from the ground up with secure user isolation, Argon2/Bcrypt password hashing, JWT bearer tokens, and Google OAuth 2.0 Sign-In.
- **🤖 Shared Telegram Bot:** All users connect to the server-managed bot from Profile → Integrasi Telegram. A one-time link expires after 10 minutes and links the private Telegram sender to their Tillfold account. Run one polling worker with `run_bot.sh` using `BOT_TOKEN` (or `TELEGRAM_BOT_TOKEN`). Restart both the API and polling worker after upgrading. Existing custom-bot users reconnect through their profile.
- **🔄 Dynamic Budget Cycles:** Flexible budget periods tailored to your actual paycheck cycle—**Weekly (7 Days)**, **Bi-Weekly (14 Days)**, or **Monthly (30 Days)**—with automated cycle rollover and historical tracking.
- **📉 Burn-Rate Trajectory & Pacing:** Real-time safe-to-spend velocity meter (`Rp/hari`), pacing status indicators (🟢 Pace Aman vs 🔴 Agak Boros), and ideal cumulative pace lines.
- **📦 Envelope Budgeting (Strata Allocation):** Dynamic percentage-based distribution across customizable buckets (Operational Saku, Fixed Bills, Investments, Emergency Reserve) connected directly to live account balances.
- **🧾 AI Receipt & Voice Extractor:** Optional multimodal integration with OpenAI-compatible vision/audio models to ingest physical paper receipts and Telegram voice notes.
- **📅 Tillfold Calendar & Controls:** Custom month-and-year picker popover, accessible form controls (`CustomSelect`, `CurrencyInput`), high-contrast dark/light mode, and unassigned salary preservation.
- **Backup & restore:** Open **Utilitas → Backup & restore** to download a versioned JSON file containing accounts, transactions, categories, pockets, bills, goals, and paycheck settings/history. Restore previews the counts and total balance, then imports atomically into an account with empty financial data. Existing financial data blocks restore. Maximum file size is 25 MB. Login credentials, Telegram links, and server settings are excluded.
- **Balance reconciliation:** Open **Pengaturan → Rekening → Cocokkan saldo**, enter the actual balance and a note, then review the difference. Adjustments change balances without counting as income or expenses. The history is retained, so subsequent corrections use another reconciliation. Backup format 2 includes adjustments and the current importer also accepts format 1.
- **Bill payments:** Use **Tagihan → Catat pembayaran** to record one full payment for the current monthly/yearly period or a one-time bill. Select an existing matching expense when the payment was already entered. Repeated submissions reuse the payment record. Deleting its expense reopens the bill, while linked pockets and Telegram show the payment status. Backup format 4 preserves payment links and archived accounts; the importer still accepts formats 1, 2, and 3.
- **Transaction calendar:** Open **Transaksi → Kalender** for a Monday-first month grid with daily income/expense totals. Choose month/year, filter an account (including archived history), or jump to **Hari ini**. Click a date for paginated daily transactions. Transfers and balance adjustments are shown separately. Calendar sums include every matching transaction, independently of the dashboard period and the list page limit. Compact amounts adapt to the calendar's available width.
- **Global search:** Use **Cari** in the top bar or **Ctrl+K / ⌘K** outside another form/dialog. Search transactions, accounts, bills, and savings goals across all periods, including archived accounts and inactive records. Amounts such as `25.000` and ISO transaction dates are supported. Results open the existing record form on its related page; nothing changes until saved. Each group shows up to five results and asks you to refine the query when more match. Restart the API and refresh the frontend after upgrading.
- **Account archive:** Open **Pengaturan → Rekening**, choose **Arsipkan rekening**, and confirm. The **Arsip** view keeps balances and history visible and offers **Aktifkan kembali**. Archived accounts are excluded from new transactions, transfers, payroll and bill payments, including Telegram. At least one account must stay active. When archiving a default salary/spending account, another active account replaces that default; no money is moved. Restart both the API and bot after upgrading so the startup migration adds `accounts.is_archived` to existing databases.
- **Telegram ledger safety:** Repeated delivery of the same private-chat message is ignored using a persistent `(chat_id, message_id)` key committed with the ledger changes. A new message with identical text is a new request. Text and media validate owned accounts and positive whole-rupiah amounts before saving; media batches include paired transfers atomically. `/batal` uses the same paycheck and bill-payment safeguards as the web. Message keys are operational metadata excluded from financial backups. Restart the API and bot after upgrading to create the message-key table through startup.

---

## 📚 Dokumentasi & Buku Panduan

- 🏛️ **[Spesifikasi Arsitektur Sistem (docs/ARCHITECTURE.md)](docs/ARCHITECTURE.md)** — Penjelasan mendalam mengenai isolasi multi-tenant, ERD database PostgreSQL, formula matematika *Safe-to-Spend* dan burn-rate trajectory, spesifikasi engine parser regex, verifikasi kriptografis Telegram Mini App, serta katalog REST API lengkap.
- 🚀 **[Panduan Production Deployment (docs/DEPLOYMENT.md)](docs/DEPLOYMENT.md)** — Panduan operasi server Linux 24/7 dengan systemd services, setup PostgreSQL, environment variables, reverse proxy, dan konfigurasi Google OAuth 2.0.
- 📕 **[Buku Panduan Pengguna PDF (docs/Panduan_Pengguna_AI7_Finance.pdf)](docs/Panduan_Pengguna_AI7_Finance.pdf)** — Panduan lama. Bagian Shared/BYOB sudah digantikan alur satu bot melalui Profil → Integrasi Telegram.

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
                                |    Telegram Bot Engine    |
                                |       (Shared Bot)        |
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

## 🚀 Quickstart Guide

### Prerequisites
- **Python 3.10+**
- **Node.js 18+** & `npm`
- **PostgreSQL 14+**
- (Optional) Telegram Bot token from [@BotFather](https://t.me/BotFather)

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
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai7_finance

# JWT secret (generate one with: openssl rand -hex 32)
JWT_SECRET_KEY=your_generated_32_char_secret_key

# Telegram Bot Token (Optional if using web-only mode)
BOT_TOKEN=your_bot_token_from_botfather

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

# Sync static build to web server root
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
| `kopi 25k bca` | Expense | Rp 25.000 | BCA | Jajan / Ngopi | Kopi |
| `makan siang 35rb mandiri` | Expense | Rp 35.000 | Mandiri | Makanan & Minuman | Makan siang |
| `bensin 50000 cash` | Expense | Rp 50.000 | Cash | Transportasi | Bensin |
| `gaji 5000000 mandiri` | Income | Rp 5.000.000 | Mandiri | Gaji & Pendapatan | Gaji |
| `tf 100k mandiri ke jago` | Transfer | Rp 100.000 | Mandiri -> Jago | Transfer Saldo | Pindah dana |

### Supported Bot Commands
- `/start` — Check authorization or link Telegram account with a 6-digit sync code from the web.
- `/menu` — Interactive keyboard with quick access to all bot features.
- `/saldo` — View real-time wallet balances and Bank Jago pocket mappings.
- `/transfer` — Transfer balance between pockets or bank accounts.
- `/pacing` — View safe-to-spend pacing and days remaining in the active paycheck cycle.
- `/gajian` — Log paycheck income and execute percentage-based envelope allocations.
- `/subs` — View and manage fixed commitments, monthly and annual subscriptions.
- `/rekap` — Get a summary of current period income, expenses, and savings rate.
- `/help` — Display syntax examples and usage guide.

---

## 🛠️ Production Deployment

Untuk panduan deployment langkah-demi-langkah di server Linux (Ubuntu/Debian), konfigurasi database PostgreSQL, environment variables, reverse proxy, dan konfigurasi Google OAuth 2.0, silakan pelajari dokumen terpisah:

👉 **[Panduan Production Deployment (docs/DEPLOYMENT.md)](docs/DEPLOYMENT.md)**

Ringkasan cepat operasi 24/7 di server Linux:
1. **Layanan Background:** Dikelola melalui unit systemd `ai7-finance-web.service` (FastAPI backend & web dashboard di port 8080) dan `ai7-finance.service` (Telegram companion bot).
2. **Reverse Proxy & SSL:** Menggunakan Cloudflare Tunnel atau reverse proxy standar (seperti Nginx atau Caddy) untuk meneruskan lalu lintas HTTPS ke backend lokal (`http://127.0.0.1:8080`).
3. **Autentikasi Google:** Daftarkan origin domain publik (`https://tillfold.alifihsan.my.id`) di Google Cloud Console (*Authorized JavaScript origins* & *Authorized redirect URIs*).

---

## 🔒 Security & Privacy

- **SQL Injection Prevention:** 100% parametrized queries via SQLAlchemy ORM.
- **Stateless Bearer Tokens:** HS256 JWT tokens with configurable TTL.
- **Tenant Data Isolation:** Every query explicitly scopes by authenticated `user_id`.
- **Zero Secrets in Repository:** Credentials, `.env`, tokens, and service account JSONs are strictly gitignored.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
