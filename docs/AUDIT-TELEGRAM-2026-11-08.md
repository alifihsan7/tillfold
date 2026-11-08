# Audit ledger Telegram

Tanggal: 8 November 2026.

## Perubahan

- Rekening teks memakai nama rekening pengguna, termasuk nama panjang, angka, dan simbol. Nama ambigu ditolak. Bila rekening tidak disebut, pengeluaran memakai rekening belanja yang dikonfigurasi dan pemasukan memakai rekening penerima. Nama bank bawaan parser tidak lagi dipakai sebagai rekening otomatis.
- Input transfer mendukung `/transfer`, `/tf`, dan `tf`, mengutamakan nama rekening tujuan lengkap, lalu menyimpan pasangan keluar/masuk. Nominal dan panjang keterangan divalidasi sebelum perubahan ledger.
- Ekstraksi media hanya diberi daftar rekening pengguna. Seluruh hasil media divalidasi sebelum penyimpanan; batch campuran pengeluaran dan transfer disimpan dalam satu transaksi database. Nominal negatif, nol, pecahan, tipe ilegal, rekening asing, dan transfer ke rekening yang sama ditolak.
- `/batal` memakai fungsi penghapusan ledger yang sama dengan web. Menghapus pembagian gaji membuka kembali alokasinya; gaji yang masih punya pembagian tidak dapat dihapus. Membatalkan pengeluaran pembayaran membuka kembali status tagihan.
- Tabel `telegram_processed_messages` memiliki kunci unik gabungan chat dan pesan. Penanda ikut flush/commit perubahan ledger, sehingga rollback juga membatalkan penanda. Percobaan duplikat yang lolos pemeriksaan awal tetap dibatasi oleh keunikan database.
- Kegagalan balasan setelah commit tidak mengulang perubahan keuangan pada pengiriman ulang. Jalur transkripsi audio tidak lagi meneruskan kegagalan handler pencatatan ke ekstraksi kedua.
- Offset polling maju setelah pemrosesan selesai. Input nominal yang terlalu besar ditolak tanpa menghalangi pesan berikutnya.
- Hapus akun membersihkan penanda milik akun tersebut. Penanda tidak diekspor dalam backup keuangan.

## Bukti verifikasi

PASS: 242 tes lulus, 58 peringatan, dalam 17,89 detik pada SQLite terisolasi dengan pytest. Regresi mencakup ledger, transfer, tagihan, kantong, rekonsiliasi, backup/restore, pemisahan pengguna, parser, dan Telegram.

PASS: 31 kasus baru di `backend/tests/test_telegram_ledger.py` mencakup pesan duplikat, pesan baru berisi sama, ID pesan sama pada chat berbeda, rollback gaji setelah konfigurasi awal dibuat, konflik kunci pesan pada pembatalan, kegagalan balasan, fallback suara, batch media gagal, serta penghapusan penanda saat akun dihapus.

PASS: input transfer lama dan parser tetap lulus tes yang sudah ada. Pemeriksaan routing memakai sesi database terpisah dan ID pesan seperti pesan Telegram sebenarnya.

PASS: `git diff --check` bersih. Tidak ada perubahan UI, aset frontend, atau dependency; build frontend dan pemeriksaan visual tidak diulang untuk audit backend ini.

## Batas dan penerapan

- Tidak ada pesan ke bot nyata, transaksi production, atau deployment yang dilakukan dalam pengujian.
- Tes konflik mensimulasikan pemeriksaan awal yang tertinggal, bukan uji beban paralel PostgreSQL production.
- Deduplikasi berlaku untuk ID pesan yang sama. Mengirim ulang teks sebagai pesan baru tetap merupakan permintaan baru.
- Tidak memperbaiki transaksi historis secara otomatis.
- Setelah pull, restart API dan polling worker. Startup `Base.metadata.create_all` yang sudah ada membuat tabel penanda baru; jalankan satu polling worker untuk satu bot.
