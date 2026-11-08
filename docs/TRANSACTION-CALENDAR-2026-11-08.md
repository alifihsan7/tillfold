# Kalender transaksi

Buka Transaksi → Kalender. Kalender memakai grid bulanan tujuh kolom Senin sampai Minggu. Setiap tanggal menampilkan total pemasukan dan pengeluaran dengan tanda plus/minus serta warna semantik. Tanggal tanpa transaksi tetap kosong. Hari ini diberi penanda.

Pilih bulan dan tahun dengan CustomSelect, pindah lewat tombol sebelumnya/berikutnya, gunakan filter rekening, atau kembali melalui Hari ini. Tahun yang mempunyai data lama ikut tersedia pada pilihan tahun. Nominal ringkas menyesuaikan lebar konten kalender, sehingga sidebar pada tablet tidak membuat angka terpotong. Nilai lengkap tersedia pada label aksesibilitas tanggal dan rincian harian.

Klik tanggal untuk membuka transaksi hari tersebut dalam CustomModal. Rincian memakai pagination 25 catatan per halaman dan mendukung alur edit/hapus yang sudah ada. Transfer masuk/keluar dan penyesuaian saldo ditampilkan terpisah, tidak masuk total pemasukan/pengeluaran atau selisihnya. Mutasi non-pemasukan/pengeluaran ditandai dengan jumlah mutasi pada tanggal terkait.

## Data

GET /api/v1/transactions/calendar menerima year, month, dan filter account opsional. Kueri hanya memakai user_id yang sedang masuk. Agregasi dilakukan di database atas seluruh transaksi yang cocok dan mengembalikan semua tanggal bulan, total bulanan, serta metadata tahun milik pengguna. Tidak menggunakan 100 catatan dashboard atau baris halaman riwayat sebagai sumber hitungan.

Kalender tidak dibatasi periode dashboard. Rekening arsip dapat dipilih untuk membaca sejarah. Rincian tanggal memakai endpoint history dengan batas tanggal yang sama dan rekening yang sama. Pembaruan data web setelah transaksi berubah ikut memuat ulang kalender. Permintaan yang tertinggal dibatalkan.

Tidak ada perubahan skema database atau dependency. Setelah pull, restart API dan refresh web. Static build disertakan di repo. Production belum diubah melalui sesi ini.

## Verifikasi dan gerbang desain

- Hard Gate PASS: build Next.js dan empat pemeriksaan frontend lulus. Bulan, tahun, rekening, sebelumnya/berikutnya, Hari ini, buka/tutup rincian, tahun kabisat, bulan kosong, error/retry bulanan dan harian dijalankan di preview. Dua halaman untuk hari dengan 36 catatan diuji. Edit transaksi dummy mengubah pengeluaran pada kalender dari Rp226.000 ke Rp246.000 sebelum penambahan data uji pagination. Escape menutup dialog. Tombol tanggal mempunyai label lengkap, aria-current untuk hari ini, fokus terlihat, dan ukuran kotak seragam.
- Purpose Gate PASS: grid tujuh kolom adalah struktur utama fitur. Garis internal dan sudut kotak tanggal mengikuti kalender, sementara sudut luar memakai token panel aplikasi. Scope CSS kalender mencegah aturan tombol lama mengecilkan tanggal kosong. Plus/minus serta sage/coral membedakan arah arus kas; ikon mutasi menandai transfer atau penyesuaian. Tidak ada aset, warna, font, atau animasi dekoratif baru.
- Liveliness PASS: ENERGY 1 / RHYTHM 1 / MOTION 1 mengikuti Ink & Silver yang disetujui. Judul bulan dan grid menjadi fokus; navigasi dan ringkasan bulanan berada di atasnya. Konten menyesuaikan lebar kalender, termasuk saat sidebar mengambil ruang.
- Craftsmanship PASS: 302 tes backend lulus, termasuk 16 kasus kalender baru. Kasus mencakup hari dengan 155 baris ledger, pemisahan transfer/penyesuaian, kesesuaian dengan riwayat, rekening arsip, isolasi pengguna dan metadata tahun, autentikasi, tahun kabisat/abad, tahun 1 dan 9999, serta parameter tidak valid. Pemeriksaan helper frontend menguji offset Senin, batas bulan/tahun, tahun kabisat, dan nominal ringkas. `git diff --check` bersih; peringatan lint lama tetap ada.
- Responsive PASS: diuji pada desktop, lebar 820px, dan 390px dalam light/dark mode. Seluruh tombol tanggal berukuran tinggi 120px pada desktop/tablet dan 100px pada ponsel. Pemeriksaan DOM menemukan nol kotak tanggal dengan overflow setelah perbaikan container query.
- Contrast PASS: rasio minimum teks sage/coral/smoke terhadap charcoal/coal di kedua tema adalah 5.00:1, dihitung memakai rumus luminansi WCAG dan melewati 4,5:1.

Semua uji UI memakai data dummy SQLite pada port 3115; tidak mengirim atau mengubah transaksi production. Tangkapan layar memperlihatkan data dummy, termasuk transfer, penyesuaian, dan transaksi tambahan untuk pagination. Pengujian bukan uji beban PostgreSQL production.
