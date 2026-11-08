# Sorotan transaksi baru

Efek informatif singkat pada Ringkasan dan tabel Riwayat: baris mendapat tint biru abu selama 2,4 detik, lalu kembali normal. Tidak ada skala, perpindahan, bunyi, toast, atau loop. Teks status khusus pembaca layar menyatakan transaksi baru ditampilkan.

Implementasi hanya frontend. Data tetap berasal dari fetch/refresh yang sudah ada, termasuk transaksi Telegram ketika refresh web menerimanya. Tidak menambah polling, endpoint, dependensi, penyimpanan browser, atau perubahan perhitungan saldo. Tidak mengklaim transaksi Telegram muncul seketika; tetap mengikuti interval refresh aplikasi.

## Pengaman

- Respons pertama pada setiap konteks membentuk baseline, tanpa sorotan.
- Konteks mencakup periode/pengguna pada Ringkasan; filter, urutan, rentang waktu dan halaman pada Riwayat.
- Hanya ID lebih tinggi dari watermark konteks aktif yang dianggap baru, mengikuti ID integer database yang meningkat.
- Edit nominal/deskripsi, penghapusan, respons identik, dan kemunculan ulang ID lama tidak memicu sorotan.
- Perpindahan konteks menghapus sorotan. Riwayat di-remount saat pengguna berubah.
- Timer dibersihkan saat unmount; hanya watermark dan batch ID sementara yang disimpan di memori.
- Reduced motion memakai tint statis tanpa transisi warna pada baris.

## Pemeriksaan

- `check-transaction-highlights.cjs`: baseline, respons identik, batch baru, edit, hapus, kemunculan ulang, ID lama, duplikat ID, perubahan filter/halaman, dan konteks kosong lulus.
- Next production build lulus; peringatan lint hook/img lama tetap muncul.
- Browser dengan SQLite lokal sementara: pemuatan pertama Ringkasan dan Riwayat menghasilkan nol sorotan. Dua transaksi dummy Rp1.000 memicu sorotan pada masing-masing tampilan, kemudian atribut sorotan hilang otomatis. Tidak menguji bot production langsung.

## Delivery Gate

- Hard Gate PASS: build dan pemeriksaan perilaku lulus; dua penyimpanan dummy melalui form asli membuktikan sorotan aktif dan kedaluwarsa. Tidak mengubah backend, saldo, atau data production. Label, tombol, loading/error lama dipertahankan.
- Purpose-Gate PASS: tint menunjukkan perubahan data nyata; tidak menambah dekorasi, glow, shadow atau motion berulang. Palette memakai token transfer yang sudah ada.
- Liveliness PASS: ENERGY 1 / RHYTHM 2 / MOTION 1; respons berupa warna singkat tanpa gerakan posisi.
- Craftsmanship PASS: konteks berbeda membentuk baseline baru; sr-only status tidak mengubah tata letak, heading tetap dapat wrap. Tidak mengklaim audit ulang seluruh aplikasi atau pengukuran performa lapangan.
