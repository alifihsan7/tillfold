# Arsip rekening

Pengaturan → Rekening menyediakan pilihan Aktif dan Arsip. Arsipkan rekening melalui tombol pada kartu, lalu konfirmasi. Aktifkan kembali dari daftar Arsip.

## Perilaku

- Arsip hanya mengubah status rekening. Transaksi, saldo, pasangan transfer, target, tagihan, dan kantong tidak dihapus. Total saldo tetap mencakup rekening arsip.
- Riwayat mempertahankan tab rekening dengan penanda (arsip). Dalam preview, rekening Bank Uji tetap memiliki saldo Rp22.175.000 dan 125 catatan setelah diarsipkan.
- Pilihan transaksi, transfer, gaji, tagihan baru dan kantong baru menggunakan rekening aktif. Validasi backend dan Telegram menolak penulisan baru ke rekening arsip, termasuk jalur gaji lama dan hasil ekstraksi media.
- Bila rekening digunakan sebagai default penerima gaji atau rekening belanja, arsip mengalihkan default tersebut ke rekening aktif lain. Dialog menjelaskan perubahan ini sebelum konfirmasi. Tidak ada perpindahan saldo.
- Rencana alokasi lama tetap tersimpan. Transfer ke/dari rekening arsip diblokir; buka rencana untuk mengganti tujuan atau aktifkan kembali rekening. Transfer yang sudah tercatat tetap tersimpan.
- Edit catatan lama dapat mempertahankan rekening arsipnya. Memindahkan catatan lain ke rekening arsip ditolak. Pemilihan rekening lama untuk edit transaksi, tagihan, dan target tetap dipertahankan.
- Minimal satu rekening aktif harus tersisa. Perubahan arsip dan penghapusan rekening diserialisasi dengan lock pengguna agar pemeriksaan minimum rekening tidak berdiri sendiri.

## Database dan backup

Kolom `accounts.is_archived` bertipe Boolean dengan nilai awal false. Startup API dan bot menjalankan migrasi penambahan kolom untuk database lama. Migrasi aman diulang; PostgreSQL menggunakan ADD COLUMN IF NOT EXISTS.

Export backup menjadi versi 4. Import versi 1, 2, dan 3 mengisi status rekening sebagai aktif ketika field lama belum ada. Status arsip versi 4 dipulihkan bersama saldo dan riwayat. Backup dengan semua rekening diarsipkan ditolak.

Setelah pull, restart API dan polling worker Telegram lalu refresh web. Fitur belum diterapkan ke production dari sesi ini.

## Verifikasi dan gerbang desain

- Hard Gate PASS: build produksi dan tiga pemeriksaan frontend lulus. Kontrol arsip, konfirmasi, pembatalan dengan Escape, pemulihan dengan Enter, tab status, filter transaksi baru, serta tab riwayat arsip dijalankan pada preview SQLite sementara. Tampilan diperiksa pada desktop dan lebar 390px, dark dan light mode. Kontrol baru memakai tombol native, label, aria-pressed, status disabled, dan CustomModal.
- Purpose Gate PASS: tidak ada aset, warna, font, radius, atau efek baru. Pilihan Aktif/Arsip memisahkan pemakaian baru dari catatan yang tetap perlu dibaca. Ringkasan saldo pada kartu tetap menjadi fokus.
- Liveliness PASS: ENERGY 1 / RHYTHM 1 / MOTION 1 mengikuti Ink & Silver yang disetujui. Struktur daftar, kartu saldo, aksen pilihan aktif dan status arsip mengikuti komponen produk yang sudah ada.
- Craftsmanship PASS: 270 tes backend lulus pada regresi lengkap; 63 tes arsip/ledger lulus kembali setelah penyesuaian akhir migrasi dan rencana gaji. Pengujian mencakup saldo/riwayat tetap, batas satu rekening aktif, pemisahan pengguna, transaksi dan Telegram ditolak, rekening pulih, gaji/tagihan, migrasi berulang, backup versi 4, serta kompatibilitas tiga versi sebelumnya. `git diff --check` bersih. Peringatan lint lama tetap ada.

Pengujian memakai SQLite terisolasi, bukan database production atau uji konkurensi PostgreSQL. Pesan Telegram nyata tidak dikirim. Nilai pada tangkapan layar adalah data dummy.
