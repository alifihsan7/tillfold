# Perapihan anti-slop Tillfold

Reading this as: aplikasi keuangan pribadi, Ink & Silver yang tenang, ENERGY 1 / RHYTHM 2 / MOTION 1 untuk kontrol yang diubah.

## Keputusan desain

- Warna: aksen tetap menunjukkan pemasukan, pengeluaran, transfer, atau status; panel tagihan kembali netral agar warna peringatan tidak memenuhi seluruh kartu.
- Layout: filter kalender memakai grid berdasarkan lebar konten agar label bulan, tahun, dan rekening tetap terbaca saat sidebar terbuka atau di HP.
- Hierarki: kalender menjadi fokus; tiga angka ringkasan memakai pembatas tipis, bukan tiga kartu tambahan.
- Tipografi: gunakan ukuran UI yang sudah ada, angka tabular, dan judul halaman singkat; tidak menambah font.
- Spasi: bulan dan tahun satu kelompok, rekening terpisah, navigasi bulan di kanan; ketiganya menjadi baris terpisah saat ruang sempit.
- Status: hilangkan emoji sirene/silang dan badge jenis tagihan yang mengulang tanggal; status teks dan aksen cukup menjelaskan keadaan.
- Bentuk: radius panel 20px, kontrol 10px, badge 6px; pilihan tab memakai aksen yang sama dengan filter.
- Interaksi: dropdown mengembalikan fokus ke pemicu; panah, Home, End memilih fokus opsi, Enter memilih, Escape menutup.
- Ikon: ikon kalender, panah bulan, dan rekening menyatakan fungsi; tidak membuat aset, ilustrasi, navigasi, atau metrik baru.
- Motion: kontrol yang diubah hanya memakai transisi warna; tidak menambah loop atau animasi dekoratif.

Audit ini mencakup kalender transaksi, tab Rencana/Pengaturan, dan kartu tagihan. Tidak mengklaim audit ulang seluruh alur keuangan atau performa lapangan.

## Delivery Gate

Status di bawah berlaku untuk perubahan dalam dokumen ini. Bukti runtime menggunakan server lokal 3115 dengan SQLite sementara dan banner data dummy, bukan data production.

### Hard Gate

- R-02 PASS: judul halaman yang disentuh dan status tagihan tidak memakai em dash.
- R-03 PASS: viewport 390px dan 820px memiliki scrollWidth sama dengan viewport; bulan, tahun, rekening tidak terpotong; tidak ada sel kalender yang overflow.
- R-17 PASS: semua angka berasal dari props/API; tidak membuat metrik baru.
- R-18 PASS: tidak menambah testimonial atau identitas fiktif.
- R-23 PASS: tidak membuat aset, logo, avatar, atau struktur navigasi baru.
- R-24 PASS: rute yang disentuh tetap rute aplikasi yang sudah ada; tab Rencana/Pengaturan diuji lewat keyboard.
- R-25 PASS: memakai token semantik yang sudah diukur minimum 4.60:1 pada light dan 5.14:1 pada dark termasuk tint badge 20%; tidak menambah warna.
- R-26 PASS: bulan, tahun, rekening, navigasi bulan, Hari ini, tab, dan satu tombol Tambah tagihan berfungsi; tombol membuka form yang dapat dibatalkan.
- R-27 PASS: useEffect kalender, loading Skeleton, pesan kosong dan error/retry tetap ada; Desember 2026 menampilkan keadaan kosong.
- R-28 PASS: tidak ada FAQ pada komponen yang diubah.
- R-32 PASS: Enter membuka/memilih; ArrowDown memindah November ke Desember; Home memindah fokus tahun; Escape menutup dan mengembalikan fokus; ArrowRight berpindah tab.
- R-33 PASS: perubahan ditulis langsung pada TSX/CSS melalui patch; tidak menambah script pengubah desain.
- R-34 PASS: kalender dan tagihan diperiksa pada dark/light, termasuk mobile.
- R-35 PASS: Next production build dan empat check script lulus; kontrol yang berubah diperiksa di browser.
- R-36 PASS: tidak menambah klaim keamanan/performa; ringkasan tidak lagi menyiratkan autodebet otomatis.
- R-37 PASS: arah Ink & Silver dari keputusan pengguna; Design Read dan dials tercatat sebelum penyelesaian.
- R-38 PASS: preview menampilkan banner data uji; implementasi tetap mengambil data pengguna dari API.
- R-39 PASS: kontrol tetap native button dengan nama, hover/disabled/focus; fokus dropdown kembali ke pemicu, Escape dropdown tidak menutup modal induk; tidak menambah motion.
- R-40 PASS: tidak menambah media atau script pihak ketiga; Skeleton mempertahankan ruang loading; tidak melaporkan angka performa.

### Purpose-Gate

- R-01 PASS: tidak menambah gradient, pattern, atau glow; panel tagihan berwarna netral.
- R-04 PASS: ikon kalender, panah bulan, rekening, dan check menunjukkan fungsi; emoji status dekoratif dihapus.
- R-06 PASS: font/ukuran mengikuti token UI lama; angka tabular untuk membandingkan nominal.
- R-07 PASS: garis kalender menunjukkan tanggal, bukan pola latar dekoratif.
- R-08 PASS: panah dipakai untuk navigasi bulan, tidak ditambah ke CTA.
- R-09 PASS: badge jenis tagihan yang mengulang informasi tanggal dihapus; status tersisa menunjukkan keadaan nyata.
- R-10 PASS: tidak menambah backdrop blur/glass; summary kalender dan tagihan menjadi baris tanpa kartu.
- R-12 PASS: kartu tagihan tidak lagi memakai shadow; tidak menambah elevasi.
- R-13 PASS: tidak menambah glow.
- R-14 PASS: ringkasan dan daftar memiliki komposisi berbeda; kartu hanya mengelompokkan satu tagihan dan aksinya.
- R-19 PASS: kontrol yang berubah hanya memakai transisi warna, tanpa loop baru.
- R-22 PASS: tidak menambah ilustrasi.

### Liveliness

- Dials PASS: ENERGY 1 / RHYTHM 2 / MOTION 1; tidak menambah dekorasi atau motion yang bertentangan.
- Fokus PASS: kalender menjadi area utama di Transaksi; daftar pembayaran menjadi area utama di Tagihan.
- Whitespace PASS: filter, ringkasan, dan daftar dipisahkan berdasarkan tugas; bukan kotak berulang.
- Aksen PASS: biru abu untuk pilihan; amber/coral/sage untuk status dan uang, panel tetap netral.
- Identitas PASS: mempertahankan Ink & Silver, angka tabular dan pola kontrol Tillfold.
- Design Read PASS: arah dan alasan tertulis di awal dokumen.

### Craftsmanship dan Quality Locks

- C-1 PASS: alasan warna, layout, tipografi, spasi, bentuk, dan interaksi tercatat.
- C-2 PASS: satu tombol tambah diuji membuka form; seluruh kontrol kalender yang berubah memiliki handler asli.
- C-3 PASS: kartu Perintah Telegram dan dua CTA berulang dihapus, menyisakan angka yang mendukung daftar tagihan.
- C-4 PASS: mobile/tablet/desktop, dua tema, keadaan kosong, dan navigasi keyboard diperiksa dalam lingkup perubahan.
- C-5 PASS: tidak menambah klaim atau angka buatan pada aplikasi.
- R-05 PASS: strip ringkasan, toolbar, kalender, dan daftar mengikuti tugas, tanpa bagian template baru.
- R-11 PASS: memakai radius panel 20px/kontrol 10px; ringkasan tidak memakai radius/kartu.
- R-15 PASS: CTA menyebut tindakan konkret, Tambah tagihan dan Hari ini.
- R-16 PASS: teks baru tidak memakai jargon pemasaran.
- R-20 PASS: mempertahankan identitas keuangan pribadi Tillfold dan pola navigasi yang disetujui.
- R-21 PASS: kedua tema yang disetujui tetap tersedia dan diperiksa.
- R-29 PASS: tidak menambah warna; mengurangi luas warna pada panel tagihan.
- R-30 PASS: tidak meniru produk lain atau menambah template halaman.
- R-31 PASS: setiap keputusan besar memiliki alasan satu baris di atas.

## Pemeriksaan teknis

- `check-transaction-calendar.cjs`, `check-api-response.cjs`, `check-overview.cjs`, `check-dashboard-data.cjs`: lulus.
- Next.js production build: lulus, dengan peringatan lint hook/img lama yang tidak berubah.
- Browser: hanya satu tombol Tambah tagihan; form membuka dan Batal bekerja.
- Dropdown di modal: Escape menutup opsi, modal induk tetap terbuka, fokus kembali ke rekening.
- Tidak mengubah backend, migrasi, atau perhitungan keuangan.

## Revisi respons tombol: warna saja

Pilihan pengguna: perubahan warna yang halus, tanpa mengecil atau bergeser.

- Aturan bersama tombol halaman, dialog dan dropdown menetapkan `transform: none` saat ditekan. Aturan ini juga mengalahkan utility scale lama agar perilaku tidak berbeda antar komponen.
- Transisi hanya mencakup background, border, teks dan filter selama 140ms. Tekanan mengubah border dan brightness 0.98, tanpa menggeser layout.
- Ikon tema tidak lagi berputar saat hover; ikon pemilih periode tidak lagi membesar.
- `prefers-reduced-motion: reduce` menghapus durasi transisi tombol. Perubahan fungsi seperti membuka sidebar atau kalender tetap bekerja.

Delivery Gate untuk revisi interaksi:

- Hard Gate PASS: Next production build lulus; runtime CSS menunjukkan active transform none; tombol halaman, dialog, dropdown dan tombol tambah mobile memakai transisi warna 140ms. Dialog dan dropdown tetap dapat dibuka/ditutup lewat keyboard. Token semantik saat brightness 0.98 memiliki minimum kontras 4.53:1 pada base/panel dan tint 0/10/20% kedua tema. Tidak mengubah data, API, label, aset, atau navigasi.
- Purpose-Gate PASS: penggelapan 2% dan perubahan border hanya menandai tekanan; tidak menambah glow, shadow, gradient, skala, geseran, atau putaran dekoratif.
- Liveliness PASS: ENERGY 1 / RHYTHM 2 / MOTION 1; respons warna mempertahankan affordance tanpa gerakan pada kontrol.
- Craftsmanship PASS: satu aturan tombol berlaku juga untuk portal dialog/dropdown; focus ring dan disabled tetap ada. Pemeriksaan browser dilakukan pada light mode, dengan aturan yang sama untuk dark mode; palet tidak berubah. Aturan reduced-motion diperiksa pada sumber CSS, bukan melalui emulasi OS.

Peringatan lint hook/img lama masih muncul saat build. Tidak ada klaim pengujian ulang seluruh alur aplikasi untuk perubahan visual ini.

## Revisi dari anotasi: latar rekening dan warna alokasi

- Rekening kas memakai surface panel dan border yang sama dengan panel lain; alasan: batas kelompok rekening terbaca di light mode, tidak menyatu dengan halaman.
- Grafik memakai delapan warna kategorikal dan legenda yang cocok satu per satu. Warna hanya membedakan rekening dalam grafik ini, bukan status finansial atau pengganti aksen fungsi aplikasi.
- Versi light memakai warna lebih gelap dengan label putih; dark memakai warna lebih terang dengan label gelap. Kontras minimum label: light 4.98:1, dark 6.79:1. Kontras minimum warna seri terhadap panel: light 4.90:1, dark 6.04:1.
- Legenda mendapat tint 8% dan swatch lebih besar supaya pemetaan warna terlihat. Deskripsi memakai text-smoke penuh agar tidak terlalu pucat.
- Label 12.5% tidak dibulatkan menjadi 13%; untuk delapan alokasi sama besar, tampilan tidak lagi menyiratkan total 104%. Proporsi data tidak berubah.
- Di konten di bawah 700px, angka tetap ada di legenda dan label segmen disembunyikan agar tidak menumpuk.

Delivery Gate revisi anotasi:

- Hard Gate PASS: production build lulus; browser menunjukkan panel rekening #fdfdfe di light dan #232326 di dark; delapan warna bar sama dengan swatch legenda; viewport mobile 390px tidak overflow. Tidak menambah interaksi, data, aset, atau klaim.
- Purpose-Gate PASS: latar mengelompokkan rekening; warna kategorikal memisahkan seri aktual; tidak menambah gradient, glow, motion, atau shadow. Batas antarsegmen memakai gap netral.
- Liveliness PASS: ENERGY 1 / RHYTHM 2 / MOTION 1 tetap; fokus pada grafik alokasi, warna di luar grafik tidak ditambah.
- Craftsmanship PASS: kedua tema diperiksa pada ukuran anotasi 1915x884; legenda tetap memuat delapan nama dan persentase di mobile. Empty/loading dan perhitungan lama dipertahankan; tidak mengklaim pengujian ulang seluruh alur keuangan.
