# Tillfold 💸

> **Ekosistem pencatatan keuangan pribadi dan arus kas siap pakai** yang dirancang untuk pencatatan transaksi harian tanpa friksi lewat Telegram dan analisis anggaran mendalam melalui web dashboard modern bertema gelap.
>
> 🌐 **Aplikasi Web Live:** [tillfold.alifihsan.my.id](https://tillfold.alifihsan.my.id)  
> 🤖 **Bot Telegram:** [@tillfold_bot](https://t.me/tillfold_bot)

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js_14-black?logo=next.js&logoColor=white)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Tailwind CSS](https://img.shields.io/badge/UI-Tailwind_CSS-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![Lisensi: MIT](https://img.shields.io/badge/Lisensi-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🌟 Fitur Utama

- **⚡ Pencatatan Cepat via Telegram:** Catat pengeluaran atau pemasukan dalam hitungan detik menggunakan teks percakapan biasa (`kopi 25k mandiri`, `makan siang 35rb`, `bensin 50rb cash`, `gaji 5jt`).
- **📱 Telegram Mini App (TMA):** Buka dashboard keuangan lengkap langsung di dalam aplikasi Telegram melalui tombol menu "📊 Dashboard" dengan login otomatis yang aman (HMAC-SHA256 Single Sign-On).
- **📉 Burn-Rate & Safe-to-Spend:** Pantau batas aman belanja harian (`Rp/hari`) dan status laju pengeluaran (🟢 Pace Aman vs 🔴 Agak Boros) berdasarkan sisa hari siklus gaji aktif (7, 14, atau 30 hari).
- **📅 Kalender Transaksi:** Tampilan kalender visual bulanan (mulai hari Senin) untuk melihat arus pengeluaran harian, pemasukan, dan mutasi saldo secara sekilas.
- **🔍 Pencarian Global (Ctrl+K / ⌘K):** Modal pencarian instan lintas seluruh periode untuk mencari transaksi, nama rekening, tagihan rutin, maupun target tabungan.
- **⚖️ Rekonsiliasi Saldo Bank:** Cocokkan saldo riil rekening langsung melalui pengaturan tanpa merusak catatan laba-rugi operasional.
- **🔔 Pengingat Tagihan & Langganan:** Kelola komitmen bulanan dan tagihan rutin dengan riwayat pembayaran yang terintegrasi ke buku kas.
- **💾 Cadangkan & Pulihkan Data:** Ekspor seluruh data akun, transaksi, kategori, dan pengaturan ke berkas JSON terenkripsi, lengkap dengan proteksi pemulihan otomatis.

---

## 🏗️ Arsitektur Sistem

```text
               +-------------------------------------------------------------+
               |                       Klien Telegram                        |
               |             (Input Teks Chat & Telegram Mini App)           |
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
|   Klien Next.js 14    |<---->|      FastAPI REST Server      |<---->|   PostgreSQL RDBMS    |
| (TMA & Web Dashboard) |      |  (/api/v1/ auth, tx, summary) |      | (Database Multi-Akun) |
+-----------------------+      +---------------+---------------+      +-----------------------+
```

---

## 🚀 Panduan Memulai Cepat

### Prasyarat Sistem
- **Python 3.10+** & virtualenv
- **Node.js 18+** & `npm`
- **PostgreSQL 14+**
- Token Bot Telegram dari [@BotFather](https://t.me/BotFather)

---

### 1. Pasang Backend & Dependensi

```bash
git clone https://github.com/alifihsan7/tillfold.git
cd tillfold

# Buat dan aktifkan virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Buat berkas konfigurasi
cp .env.example backend/.env
```

Buka `backend/.env` dan isi variabel yang diperlukan:

```env
# Koneksi Database PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/tillfold_db

# Kunci Rahasia JWT (generate via: openssl rand -hex 32)
JWT_SECRET_KEY=kunci_rahasia_32_karakter_kamu

# Token Bot Telegram dari @BotFather
TELEGRAM_BOT_TOKEN=token_bot_telegram_kamu

# URL Dasar Dashboard Web
APP_BASE_URL=https://tillfold.alifihsan.my.id

# Zona Waktu Lokal
TIMEZONE=Asia/Jakarta
```

---

### 2. Bangun Tampilan Frontend

```bash
cd frontend
npm install
npm run build
cd ..

# Salin berkas ekspor statis ke folder FastAPI
rm -rf static/*
cp -r frontend/out/* static/
cp frontend/public/manifest.json static/
```

---

### 3. Menjalankan Layanan Secara Lokal

```bash
# Terminal 1: Menjalankan Web Dashboard & API (Port 8080)
./run_web.sh

# Terminal 2: Menjalankan Bot Telegram
./run_bot.sh
```

---

## 💬 Format Penulisan Chat Bot Telegram

Bot membaca teks bahasa Indonesia secara natural tanpa perlu format kaku:

| Pesan Chat | Jenis | Nominal | Rekening | Kategori | Keterangan |
|---|---|---|---|---|---|
| `kopi 25k mandiri` | Pengeluaran | Rp 25.000 | Mandiri | Jajan / Ngopi | Kopi |
| `makan siang 35rb` | Pengeluaran | Rp 35.000 | Rekening Utama | Makanan & Minuman | Makan siang |
| `bensin 50000 cash` | Pengeluaran | Rp 50.000 | Cash | Transportasi | Bensin |
| `gaji 5000000 mandiri` | Pemasukan | Rp 5.000.000 | Mandiri | Gaji & Pendapatan | Gaji |
| `tf 100k bri 2 ke bri 1` | Transfer | Rp 100.000 | BRI 2 → BRI 1 | Transfer Saldo | Pindah dana |

### Perintah Utama Bot
- `/start` — Menghubungkan akun Telegram ke Tillfold atau cek status login.
- `/menu` — Menampilkan papan tombol menu navigasi cepat.
- `/saldo` — Cek saldo terkini seluruh rekening dan dompet.
- `/pacing` — Cek sisa batas belanja harian (*Safe-to-Spend*) dan sisa hari siklus gaji.
- `/rekap` — Ringkasan total pemasukan, pengeluaran, dan rasio tabungan periode aktif.
- `/transaksi` — Menampilkan 5 transaksi terakhir.
- `/batal` — Membatalkan (undo) transaksi yang baru saja dicatat.
- `/help` — Menampilkan panduan contoh format chat.

---

## 🛠️ Layanan Server Produksi (Systemd)

Untuk penggunaan di server Linux 24/7, aplikasi dikelola oleh dua unit systemd:

1. **`tillfold.service`** — Menjalankan bot Telegram `@tillfold_bot` di latar belakang.
2. **`tillfold-web.service`** — Menjalankan server FastAPI dan web dashboard pada port `8080`.

Perintah pengelolaan layanan:

```bash
# Cek status layanan
sudo systemctl status tillfold tillfold-web

# Restart layanan
sudo systemctl restart tillfold
sudo systemctl restart tillfold-web

# Melihat log langsung (live logs)
journalctl -u tillfold -f
journalctl -u tillfold-web -f
```

---

## 🔒 Keamanan & Privasi

- **Pencegahan SQL Injection:** 100% menggunakan kueri terparameter lewat SQLAlchemy ORM.
- **Isolasi Data Antar-Pengguna:** Setiap kueri database difilter ketat berdasarkan `user_id` pemilik akun.
- **Bebas Kredensial di Repositori:** Token bot, sandi database, dan rahasia JWT sepenuhnya dibaca dari `.env` lokal yang masuk dalam daftar `.gitignore`.
- **Proteksi Idempotensi Telegram:** Pengecekan token update mencegah pencatatan ganda saat ada gangguan sinyal atau pengiriman chat berulang.

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah [Lisensi MIT](LICENSE).
