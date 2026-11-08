# Heatmap pengeluaran harian

Kalender memakai tint coral statis untuk memudahkan pemindaian pola pengeluaran. Data agregat kalender, filter, dan dialog harian tetap memakai API yang sudah ada. Tidak menambah endpoint, polling, library, atau perubahan data.

## Skala

Empat tingkat dibentuk dari pengeluaran harian dibagi pengeluaran harian terbesar pada bulan dan rekening yang sedang ditampilkan: sampai 25%, 50%, 75%, dan 100%. Nol/negatif atau nilai tidak valid menghasilkan tingkat nol. Intensitas bukan penilaian aman/boros terhadap anggaran, hanya perbandingan dalam konteks tersebut.

Tint memakai coral 4/8/12/16%, naik 4 poin saat hover. Hari kosong, pemasukan saja, transfer dan penyesuaian tanpa pengeluaran tetap netral. Nominal dan label aksesibel tetap ada; warna hanya membantu pemindaian. Legenda relatif tampil saat bulan memiliki pengeluaran.

Reading this as: kalender keuangan pribadi dalam Ink & Silver, ENERGY 1 / RHYTHM 2 / MOTION 1. Tint menyatakan data, tanpa menambah dekorasi atau animasi berulang.

## Validasi dan Delivery Gate

- Hard Gate PASS: checker kalender menguji tanggal, navigasi, nominal, batas empat tingkat, nol/negatif, NaN, Infinity dan clamp. Production build lulus; peringatan lint hook/img lama tetap ada. Kontras teks utama/sekunder/pemasukan/pengeluaran/mutasi pada semua tingkat termasuk hover minimal 4.87:1 light dan 6.10:1 dark.
- Purpose-Gate PASS: warna memakai token coral pengeluaran, tidak menambah palet; tingkat diturunkan dari nilai aktual. Tidak menambah glow, bayangan, ilustrasi, gerakan posisi atau angka buatan.
- Liveliness PASS: dials tetap 1/2/1; fokus tetap kalender dan nominal, intensitas membantu mengenali hari dengan pengeluaran lebih besar.
- Craftsmanship PASS: browser lokal memverifikasi delapan hari berisi memiliki intensitas yang sesuai, tanggal 6 November membuka dialog harian, dan Desember kosong memiliki nol tanggal berwarna serta tanpa legenda. Mobile 390px tidak overflow pada halaman maupun sel. Light/dark diperiksa; tidak mengklaim audit ulang semua fitur atau performa lapangan.
