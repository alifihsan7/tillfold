# Pencarian global Tillfold

Buka Cari di top bar atau gunakan Ctrl+K / Command+K saat tidak sedang mengisi form atau membuka dialog lain. Ketik minimal dua karakter. Hasil dapat diklik untuk membuka form catatan pada halaman terkait; perubahan baru disimpan ketika pengguna memilih Simpan pada form tersebut.

## Cakupan

- Transaksi: keterangan, kategori, rekening, nominal rupiah bulat, dan tanggal ISO YYYY-MM-DD. Semua periode tercakup, termasuk transaksi lama di luar siklus dashboard.
- Rekening: nama, label, dan tipe. Rekening arsip tetap ditemukan dan statusnya ditampilkan. Saldo hasil pencarian dihitung dari ledger pengguna.
- Tagihan: nama, rekening, kategori, dan catatan. Tagihan nonaktif tetap ditemukan dengan penanda statusnya.
- Target tabungan: nama, kategori, rekening tertaut, dan catatan. Target nonaktif tetap ditemukan.

API GET /api/v1/search mewajibkan autentikasi dan membatasi setiap kueri ke user_id yang sedang masuk. Teks SQL LIKE diloloskan sehingga persen, underscore, dan backslash dicari sebagai karakter biasa. Nomor internal/raw_text transaksi tidak digunakan sebagai bidang pencarian.

Frontend menunggu 250 ms setelah ketikan, membatalkan permintaan yang tertinggal, menampilkan loading/kosong/error, dan menyediakan Coba lagi serta Hapus pencarian. Maksimum lima hasil per kelompok ditampilkan dengan keterangan bila masih ada hasil lain; pengguna dapat memperjelas kata pencarian. API menerima limit 1 sampai 10, dengan panjang pencarian maksimum 120 karakter.

## Verifikasi dan gerbang desain

- Hard Gate PASS: build Next.js dan tiga pemeriksaan frontend lulus. Dialog memakai CustomModal, input teks berlabel dan tombol hapus kustom; tidak memakai kontrol pencarian bawaan browser. Semua empat jenis hasil dibuka ke form yang sesuai dalam preview. Ctrl+K, Escape, fokus input, hapus pencarian, hasil kosong, dan pergantian kueri cepat dijalankan. Kegagalan HTTP 503 disimulasikan pada preview lalu pulih melalui Coba lagi. Tampilan diperiksa pada desktop dan lebar 390px, dark dan light mode.
- Purpose Gate PASS: ikon Search dipakai untuk tindakan pencarian. Daftar hasil dikelompokkan menurut jenis catatan agar nama sama tidak tertukar. Tidak ada aset, warna, font, radius, glow, atau animasi baru; dialog dan aksen mengikuti komponen Ink & Silver yang sudah ada.
- Liveliness PASS: ENERGY 1 / RHYTHM 1 / MOTION 1 dipertahankan. Input menjadi fokus awal, tipe catatan menjadi ritme kelompok, dan nominal memakai angka tabular. Ruang dan komponen matte mengikuti hierarki aplikasi yang disetujui.
- Craftsmanship PASS: 286 tes backend lulus, termasuk 16 kasus pencarian baru yang menguji autentikasi, pemisahan empat jenis data antar pengguna, arsip/nonaktif, lintas periode, nominal/tanggal, wildcard literal, batas hasil dan penanda hasil lanjutan, kueri tidak valid, serta tidak adanya perubahan data akibat pencarian. `git diff --check` bersih. Build masih memiliki peringatan lint lama.

Screenshot memakai data dummy SQLite lokal. Tidak ada data production atau transaksi keuangan yang diubah dalam pengujian. Tidak ada perubahan skema database atau dependency. Setelah pull, restart API dan refresh web; hasil build frontend disertakan pada folder static yang dilacak repo.
