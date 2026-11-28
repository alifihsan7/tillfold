# Receipt Radar forwarding

Tillfold menyediakan alamat forwarding terpisah per akun. Email yang masuk dirutekan lewat envelope recipient dan dibaca oleh parser struk yang sudah ada. Kartu dikirim ke chat pribadi Telegram pemilik akun. Saldo berubah setelah pengguna memilih rekening dan kategori.

## Konfigurasi

1. Siapkan subdomain email khusus, misalnya `receipts.example.com`, agar aturan email utama tidak perlu diubah. Aktifkan MX dan catch-all untuk subdomain tersebut di layanan email routing.
2. Deploy `worker.mjs` sebagai Cloudflare Email Worker. Arahkan aturan catch-all ke Worker. Atur `TILLFOLD_RECEIPT_INGRESS_URL` ke URL HTTPS API Tillfold dengan path `/api/v1/receipt-radar/inbound`. Simpan `TILLFOLD_RECEIPT_INGRESS_TOKEN` sebagai secret Worker.
3. Atur `RECEIPT_RADAR_DOMAIN` dan `RECEIPT_RADAR_INGRESS_TOKEN` di environment Tillfold. Gunakan token acak minimal 32 karakter yang sama di kedua sisi. Restart API agar konfigurasi dan tabel dimuat. Restart bot agar tombol draf bisa digunakan.
4. Di akun uji, hubungkan Telegram, buat alamat forwarding, lalu forward satu contoh struk. Cek bahwa kartu hanya masuk ke chat akun uji dan transaksi baru tercatat setelah dikonfirmasi.

Untuk gateway email lain, kirim MIME asli melalui HTTPS dengan `Authorization: Bearer <token>`, `X-Receipt-Recipient` berisi envelope recipient, dan `X-Receipt-Sender` berisi envelope sender. Jangan gunakan header `To` dari isi pesan untuk menentukan akun tujuan.

## Cakupan

Format pengeluaran awal meliputi Livin’ Mandiri, BRImo, dan Google Play. Lampiran pesan `message/rfc822` didukung, sedangkan struk yang hanya berupa lampiran PDF atau gambar tidak diproses. Email transfer, format yang tidak dikenal, dan email lebih dari 512 KiB ditolak. Email mentah tidak disimpan. Jika Telegram gagal menerima kartu, draft tetap tersimpan untuk percobaan berikutnya dari gateway.

## Gmail otomatis

Opsi Gmail otomatis memakai tombol **Hubungkan Gmail** di Pengaturan → Profil → Receipt Radar. Pengguna memilih akun Google, memberi izin baca, lalu kembali ke Tillfold. Opsi ini memakai URL Tillfold yang sudah ada.

- Buat OAuth client jenis Web Application yang terpisah dari login Tillfold. Aktifkan Gmail API dan gunakan scope `https://www.googleapis.com/auth/gmail.readonly`.
- Daftarkan `https://tillfold.alifihsan.my.id/api/v1/receipt-radar/gmail/callback` sebagai redirect URI. Untuk lingkungan lain, awal URL mengikuti `APP_BASE_URL`.
- Atur `RECEIPT_GMAIL_CLIENT_ID`, `RECEIPT_GMAIL_CLIENT_SECRET`, dan `RECEIPT_GMAIL_ENCRYPTION_KEY`. Gunakan Fernet key yang disimpan di secret manager atau environment VPS. Simpan key tetap konsisten antar restart.
- Konfigurasi reverse proxy supaya access log untuk callback tidak menyimpan query string OAuth. Uvicorn mengecualikan callback tersebut dari access log aplikasi.
- Lakukan uji dengan akun Google yang terdaftar sebagai tester sebelum publikasi. Akses publik dengan scope Gmail restricted memerlukan verifikasi Google dan penilaian keamanan untuk pemrosesan di server.

Tillfold hanya meminta izin baca Gmail. Poller mencari pengirim struk yang didukung mulai dari waktu koneksi pertama. Email diperiksa berkala untuk membuat draf, dan refresh token disimpan terenkripsi. Memutuskan Gmail menghapus koneksi, menghentikan polling, dan mencabut token Google jika layanan pencabutan tersedia. Forwarding manual bisa diaktifkan terpisah.
