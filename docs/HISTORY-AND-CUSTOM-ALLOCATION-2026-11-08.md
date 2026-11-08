# Riwayat Telegram dan pembagian gaji kustom

## Perbaikan riwayat

Saldo rekening dihitung dari seluruh ledger, tetapi riwayat sebelumnya menerima hanya 100 transaksi dalam periode dashboard. Akibatnya pilihan Semua waktu tidak benar-benar mencakup semua catatan. Transaksi Telegram yang berada di luar rentang dashboard bisa mengubah saldo tanpa terlihat di riwayat tersebut.

Riwayat sekarang memakai `/transactions/history` dengan filter, urutan, dan pagination server sendiri. Total transaksi dan pemasukan/pengeluaran dihitung sebelum pagination. Transfer dan penyesuaian tetap tidak dihitung sebagai pemasukan/pengeluaran. Setiap kueri dibatasi ke pengguna yang masuk.

Filter periode dashboard tetap berlaku untuk ringkasan dan laporan. Riwayat memakai filter tanggal di halamannya sendiri. Web memuat pembaruan saat kembali aktif dan setiap 30 detik selama terlihat, tanpa mengganti ringkasan dengan skeleton saat pembaruan latar belakang. Permintaan riwayat yang tertinggal dibatalkan agar tidak menimpa filter baru.

Tidak ada transaksi Telegram yang dibuat ulang. Penyebab pada konfigurasi production tertentu belum diamati langsung; celah filter dan batas data di sumber telah direproduksi dan diperbaiki.

## Sesuaikan pembagian gaji

Buka Catat gaji, simpan atau lanjutkan gaji sebelumnya, pilih Bagi gaji lalu Sesuaikan pembagian. Ubah nominal, tambah atau hapus tujuan, dan simpan pembagian. Sisa gaji ditampilkan sebagai dana yang tetap di rekening penerima.

Perubahan rencana tidak memindahkan saldo dan tidak mengganti default alokasi. Catat transfer tetap diperlukan setelah perpindahan uang dilakukan. Baris yang sudah ditransfer dikunci. API memeriksa kepemilikan rekening, rekening asal berbeda dari tujuan, duplikasi, batas total gaji, serta perubahan rencana sejak form dibuka. Rencana kosong yang masih memiliki rekening tujuan bisa dibuka kembali.

## Verifikasi

- PASS fungsi: 254 tes backend lulus, 66 peringatan. Kasus baru membuktikan transaksi bot tersedia di riwayat web meskipun periode dashboard berbeda; 131 transaksi terpaginasikan tanpa terpotong pada 100; statistik dihitung atas semua hasil filter; alokasi kustom tidak mengubah saldo hingga transfer dicatat; baris terbayar dan form kedaluwarsa dilindungi.
- PASS frontend: tiga skrip pemeriksaan frontend dan build Next.js produksi lulus. Peringatan lint lama tetap ada.
- PASS UI: preview SQLite sementara menampilkan 375 transaksi lintas periode dan pencarian menemukan catatan Agustus saat dashboard berada di November. Editor diuji untuk ubah nominal, tambah/hapus tujuan, total melebihi gaji, simpan, buka ulang, dan penguncian transfer tercatat. Tampilan diperiksa pada desktop dan lebar 390px, dark serta light mode. Fokus input terlihat dan kontrol memakai komponen kustom yang sudah ada.
- PASS arah desain: Ink & Silver dipertahankan. ENERGY 1 / RHYTHM 1 / MOTION 1; daftar alokasi mengikuti urutan kerja, nominal menjadi fokus, permukaan matte memisahkan ringkasan dan formulir. Tidak ada aset, warna, font, atau pola animasi baru.
- PASS kontras teks yang digunakan: dark smoke: 8.40:1; dark sage: 9.69:1; light smoke: 5.00:1; light sage: 5.26:1. Semua di atas 4,5:1 menurut rumus luminansi WCAG.
- PASS kualitas: `git diff --check` bersih; dialog memakai CustomModal, pilihan memakai CustomSelect, nominal memakai CurrencyInput, dan tanggal tetap DateField. Error/retry riwayat, tombol simpan nonaktif saat total berlebih, pengunci status terbayar, serta label input tersedia. Tidak ada kontrol atau klaim pemasaran baru.

## Penerapan

Hasil frontend diekspor ke folder static yang dilacak repo. Setelah pull, restart backend API dan refresh web. Tidak ada skema database baru untuk perubahan ini. Preview di port 3111 menggunakan data dummy dalam memori, bukan data production. Uji konkurensi PostgreSQL dan konfirmasi transaksi production asli belum dilakukan.
