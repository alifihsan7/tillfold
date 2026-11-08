# Audit hitungan lintas fitur

Tanggal: 8 November 2026.

## Perbaikan

1. Input transaksi biasa tidak lagi menerima `transfer_in` atau `transfer_out`. Gunakan endpoint transfer yang mencatat kedua sisi dalam satu commit.
2. Pembuatan transaksi, transfer, dan perubahan rekening transaksi memvalidasi kepemilikan rekening. Nama rekening yang tidak terdaftar ditolak sebelum ledger berubah.
3. Pencarian pasangan transfer memeriksa pemilik, nominal, tanggal, rekening berbeda, dan tautan balik jika tersedia. Tautan eksplisit yang rusak tidak memakai tebakan berdasarkan ID terdekat. Transfer lama tanpa tautan hanya cocok jika informasi rekening atau penanda penerimaan gaji mendukung satu pasangan unik dari kedua arah.
4. Menghapus rekening yang masih memiliki transfer ditolak. Pengguna perlu menghapus transfer terkait lewat alur berpasangan terlebih dahulu agar mutasi di rekening lain tidak tertinggal.

## Validasi

PASS: 211 tes backend lulus, 58 peringatan, melalui pytest dengan database SQLite terisolasi. Cakupan mencakup ledger, transfer, tagihan, kantong, rekonsiliasi, backup/restore, isolasi pengguna, Telegram, kategori, dan peran rekening.

PASS: tes regresi memastikan edit dan hapus transfer menjaga total saldo, perubahan transaksi memperbarui laporan, pembayaran tagihan mengurangi saldo sekali, dan pengeluaran pembayaran masuk ke kantong yang terhubung.

PASS: transfer lama yang teridentifikasi tetap dapat dipulihkan dari backup. Kasus pasangan hilang, tautan balik salah, tanggal berbeda, rekening sama, dan kandidat ambigu tidak mengubah transaksi lain.

PASS: jalur frontend yang ada tetap sesuai. TransferModal menggunakan `/transactions/transfer`; input transaksi biasa menggunakan `/transactions`. Tidak ada perubahan UI atau aset frontend dalam audit ini, sehingga pemeriksaan visual dan build frontend tidak diulang.

## Batas pemeriksaan

- Audit ini tidak mengubah data production, memperbaiki data historis secara otomatis, atau melakukan deployment.
- Tes menggunakan SQLite, bukan uji konkurensi PostgreSQL production.
- Data lama dengan pasangan ambigu perlu ditinjau manual; sistem tidak menebak pasangan untuk edit atau hapus.
- Setelah pull, restart backend API dan bot karena keduanya memakai pencarian pasangan transfer yang sama.
