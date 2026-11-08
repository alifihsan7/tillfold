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
- Label segmen mengikuti lebar konten dengan ukuran 9-12px dan padding 2px, sehingga tidak menghilang saat panel menyempit. Segmen di bawah 4% tetap dirinci lewat legenda dan label aksesibel grafik.

Delivery Gate revisi anotasi:

- Hard Gate PASS: production build lulus; browser menunjukkan panel rekening #fdfdfe di light dan #232326 di dark; delapan warna bar sama dengan swatch legenda; viewport mobile 390px tidak overflow. Tidak menambah interaksi, data, aset, atau klaim.
- Purpose-Gate PASS: latar mengelompokkan rekening; warna kategorikal memisahkan seri aktual; tidak menambah gradient, glow, motion, atau shadow. Batas antarsegmen memakai gap netral.
- Liveliness PASS: ENERGY 1 / RHYTHM 2 / MOTION 1 tetap; fokus pada grafik alokasi, warna di luar grafik tidak ditambah.
- Craftsmanship PASS: kedua tema diperiksa pada ukuran anotasi 1915x884; legenda tetap memuat delapan nama dan persentase di mobile. Empty/loading dan perhitungan lama dipertahankan; tidak mengklaim pengujian ulang seluruh alur keuangan.

## Ukuran kontrol desktop

Pengguna menyetujui toolbar desktop 36px, input/tombol dialog 40px, mobile 44px. Ini menggantikan batas 44px universal dari skill hanya untuk layar minimal 768px dengan pointer fine. Perangkat sentuh dan layar sempit tetap memakai ukuran lama. Kontrol desktop tetap di atas minimum WCAG 2.2 sebesar 24px dan mempertahankan focus ring serta jarak antar tombol.

- Toolbar: periode, tema, Cari, Utilitas, dan Catat transaksi sama-sama 36px, teks 13px, padding 7px vertikal. Ikon tema 36x36px.
- Dialog: input pencarian dan tombol 40px, teks input 14px; bingkai nominal/tanggal 40px termasuk border. Tombol kalender di dalam bingkai tanggal 38px agar total tetap 40px.
- Dropdown: minimum 40px; opsi dengan deskripsi dua baris boleh lebih tinggi agar teks tidak terpotong.
- Mobile: tombol terlihat tetap 44px; nominal input tetap 16px untuk menghindari zoom saat fokus.

Delivery Gate revisi ukuran:

- Hard Gate PASS: production build lulus; browser mengukur kelima tombol toolbar 36px pada dark/light, input Cari 40px, bingkai nominal/tanggal 40px. Lebar 390px mengembalikan tombol ke 44px dan input nominal 16px. Pencarian, Utilitas, dialog, dropdown, Escape dan Batal diuji tanpa menyimpan transaksi. Pengecualian 44px mengikuti persetujuan pengguna di atas.
- Purpose-Gate PASS: ukuran membedakan kebutuhan mouse dan sentuhan; warna, radius, motion, aset, dan data tidak ditambah.
- Liveliness PASS: ENERGY 1 / RHYTHM 2 / MOTION 1 tetap; CTA utama menonjol lewat warna dengan tinggi sama seperti toolbar.
- Craftsmanship PASS: tidak mengubah sidebar, grid kalender, atau perhitungan; fokus keyboard tetap terlihat, transisi warna saja tetap berlaku, dan dua tema memakai ukuran sama. Peringatan lint hook/img lama tetap ada.

## Penyelarasan atas toolbar

Jarak atas baris kontrol dan bingkai sidebar desktop memakai token `--luma-shell-inset: 16px` agar sejajar, termasuk setelah sidebar diciutkan. Sticky header tetap bekerja pada wadah scroll yang sama; mobile tetap memakai padding atas 10px.

- Hard Gate PASS: build lulus; browser mengukur sidebar dan baris kontrol sama-sama y=16px pada viewport 1915x884, sidebar terbuka maupun ciut. Mobile 390px tetap padding 10px dan scrollWidth 390px.
- Purpose-Gate PASS: satu token menyatakan batas tepi shell; tidak menambah panel atau dekorasi.
- Liveliness PASS: dials tetap 1/2/1, tidak menambah motion.
- Craftsmanship PASS: perubahan hanya menyelaraskan posisi desktop; tombol dan navigasi tetap bekerja, tidak mengubah data atau tema.

## Ukuran toolbar dikembalikan

Anotasi pengguna berikutnya meminta toolbar kembali ke ukuran sebelum perapihan, sambil mempertahankan posisi sejajar. Toolbar desktop sekarang 44px dengan teks 14px; dialog tetap 40px. Bagian ini menggantikan keputusan toolbar 36px di atas.

- Hard Gate PASS: build lulus; browser mengukur kelima kontrol toolbar 44px/14px, tepi atas baris kontrol dan sidebar sama-sama 16px pada viewport anotasi 1915x884.
- Purpose-Gate PASS: mengembalikan ukuran yang dipilih pengguna; tidak menambah dekorasi atau motion.
- Liveliness PASS: dials tetap 1/2/1.
- Craftsmanship PASS: aturan dialog/mobile serta token posisi sidebar tetap; tidak mengubah data, API, atau interaksi.

## Dropdown rekening tanpa pengulangan

Anotasi pengguna menyorot nama yang ditambah catatan dalam kurung, lalu catatan yang sama diulang di baris kedua. Pilihan rekening sekarang memakai nama asli saja, tanpa titik warna dekoratif. Catatan rekening tetap tersimpan di Pengaturan. Nilai yang dikirim ke API tetap nama rekening seperti sebelumnya; penanda arsip di editor transaksi tetap dipertahankan.

Status terpilih memakai latar tipis dan centang; garis bawah seperti tab dihapus dari opsi dropdown. Focus ring keyboard tetap ada.

- Hard Gate PASS: production build lulus; delapan opsi dummy diperiksa satu baris, tinggi 40px, tanpa dot atau deskripsi berulang. Memilih Cash Uji memperbarui pemicu; Escape menutup opsi dan mengembalikan fokus tanpa menutup form. Tidak menyimpan transaksi.
- Purpose-Gate PASS: menghapus informasi berulang dan dekorasi yang tidak membantu memilih rekening; tidak mengubah palet atau menambah aset.
- Liveliness PASS: ENERGY 1 / RHYTHM 2 / MOTION 1; pilihan lebih mudah dipindai tanpa animasi baru.
- Craftsmanship PASS: dark/light diperiksa pada viewport anotasi 1095x884, nama akun dan nilai pemilihan tetap sama; catatan tidak dihapus dari data. Aturan tinggi mobile tetap 44px.

## Audit light mode terarah

Sesuai batas pemakaian yang diminta pengguna, perubahan difokuskan pada token bersama, permukaan, aksen fungsi dan kontrol. Ini bukan audit ulang seluruh fitur atau setiap kombinasi kelas opacity aplikasi.

- Halaman #e9eef3, sidebar #dde5ee, panel #fbfcfe, input/inset #f2f5f8, hover #e0e7ef. Perbedaan ini menunjukkan lapisan tanpa menambah kotak atau dekorasi.
- Panel saldo #d5e0eb menjadi fokus utama; gradient lama di light mode dihapus. Inset transparan tetap mengelompokkan pemasukan/pengeluaran.
- Tombol utama #2d4159 dan hover #202f42 memakai karakter ink biru abu. Warna fungsi sage/coral/amber/transfer tidak berubah.
- Teks sekunder #445368, border input #7b899a. RGB dan hex disamakan agar komponen lama dan baru konsisten.
- Shadow menyeluruh pada bg-obsidian-card/panel dihapus. Dialog dan dropdown memakai shadow untuk menandai posisi di depan halaman.
- Hover tombol utama di panel saldo kini mengikuti token hover; sebelumnya tertahan warna tetap. Tombol tema light mengikuti token kontrol, tidak memakai Slate hardcode.

Validasi: satu production build lulus; check-overview dan check-dashboard-data lulus. Peringatan lint hook/img lama tetap ada. Browser lokal memeriksa overview, transaksi, laporan, form transaksi, dropdown, perpindahan tema, dan lebar mobile 390px. Tidak mengubah backend atau data.

Delivery Gate untuk lingkup ini:

- Hard Gate PASS: token teks semantik dan sekunder diuji pada halaman/panel/inset/hover serta tint 10/20%, termasuk brightness tekan 0.98, minimum 4.55:1. Border input terhadap input 3.26:1; teks tombol utama 10.17:1. Input, dropdown, Escape dan Batal bekerja; laporan mobile memiliki scrollWidth 390px pada viewport 390px. Tidak membuat angka, aset, atau klaim produk baru.
- Purpose-Gate PASS: warna permukaan menunjukkan tingkat informasi, aksen menunjukkan fungsi, dan shadow hanya pada overlay. Tidak menambah glow, gradient, ilustrasi atau motion.
- Liveliness PASS: ENERGY 1 / RHYTHM 2 / MOTION 1; ink dan lapisan abu kebiruan memberi karakter light mode tanpa menambah aksen kategori baru.
- Craftsmanship PASS: browser memverifikasi halaman/panel/input berbeda warna, dan dark mode tetap #151517/#232326. Ukuran kontrol, radius, posisi toolbar, serta perilaku keyboard dipertahankan. Pengujian ini tidak mengklaim kontras setiap teks pada semua layar atau pengukuran performa lapangan.

## Grain dan kilau statis panel saldo

Pengguna memilih grain tipis dan kilau tepi pada panel saldo saja. Tujuannya menandai satu permukaan glass utama, sementara panel data lain tetap solid.

- Grain berupa tile SVG grayscale 160px yang tertanam dalam CSS, tanpa file eksternal atau library. Opacity dark 0.075 dan light 0.045.
- Pantulan tepi atas berupa garis gradient putih setinggi 1px, bukan gradient tambahan pada seluruh permukaan.
- Kedua pseudo-element memakai pointer-events none dan z-index 0; isi panel tetap di z-index 1. Tidak menutup teks, menangkap klik, atau mengubah ukuran panel.
- Tidak ada animation, event pointer, parallax, atau loop; reduced-motion tidak membutuhkan animasi pengganti.

Delivery Gate lingkup visual ini:

- Hard Gate PASS: production build lulus; browser memverifikasi animation none, lapisan isi di atas tekstur, dan sembunyikan/tampilkan saldo tetap bekerja. Mobile 390px tidak overflow. Tidak mengubah data, API, label atau navigasi.
- Purpose-Gate PASS: grain dan kilau diminta pengguna untuk menandai satu panel glass; tidak menyebar efek ke seluruh kartu atau menambah glow.
- Liveliness PASS: ENERGY 1 / RHYTHM 2 / MOTION 1 tetap; karakter datang dari tekstur statis yang tipis.
- Craftsmanship PASS: dark/light diperiksa dengan opacity berbeda; tidak ada library, unduhan aset, atau motion baru. Peringatan lint hook/img lama tetap ada; tidak melaporkan angka performa yang tidak diukur.

## Bug fokus Tab dari dropdown portal

Reproduksi lokal: buka form Catat transaksi, buka rekening, End ke opsi terakhir, tekan Tab. Sebelumnya fokus menjadi BODY di luar dialog sementara menu tetap terbuka. Dropdown memakai portal ke body sehingga tidak termasuk urutan fokus dialog.

Perbaikan: Tab/Shift+Tab menutup opsi dan memindahkan fokus relatif terhadap tombol pemicu, mengikuti kontrol terlihat dan aktif di dialog induk. Kontrol menu portal dan tabindex negatif dikecualikan. Di luar dialog, urutan mengikuti kontrol halaman. Pilihan rekening dan isi form tidak diubah.

- Hard Gate PASS: build dan checker kalender/highlight lulus. Browser membuktikan Tab dari opsi terakhir fokus ke Kategori di dalam dialog; Shift+Tab fokus ke Keterangan; menu tertutup dan draft tetap ada. Dropdown bulan di kalender meneruskan Tab ke tahun. Tidak menyimpan transaksi saat pengujian.
- Purpose-Gate PASS: tidak menambah fitur atau dekorasi; memperbaiki urutan fokus yang terputus oleh portal.
- Liveliness PASS: tidak mengubah dials, warna, layout atau motion.
- Craftsmanship PASS: perilaku diuji di dalam dan luar dialog dengan form asli; API/data tidak berubah. Ini satu bug yang direproduksi dan diperbaiki, bukan klaim seluruh aplikasi bebas bug. Peringatan lint hook/img lama tetap ada.

## Bug fokus popup kalender di dalam dialog

Reproduksi: pada form Catat transaksi, buka pemilih tanggal dan Tab dari tanggal terakhir. Fokus sebelumnya keluar ke BODY, karena focus trap hanya mencari tombol di panel dalam, sedangkan kalender di-portal ke root dialog.

Perbaikan: focus trap mengambil kontrol dari root dialog miliknya, sehingga kalender termasuk dalam urutan Tab tanpa mengambil kontrol dari halaman belakang.

- Hard Gate PASS: build lulus; sebelum perbaikan browser menunjukkan fokus BODY di luar dialog. Setelah perbaikan, Tab tanggal terakhir menuju tombol Tutup dialog, Shift+Tab kembali ke tanggal terakhir. Escape pertama menutup kalender dan fokus ke Pilih tanggal; Escape berikutnya menutup form. Tidak menyimpan transaksi.
- Purpose-Gate PASS: memperbaiki cakupan fokus saja; tidak menambah fitur, dependency, dekorasi atau motion.
- Liveliness PASS: dials dan visual tetap.
- Craftsmanship PASS: diuji melalui form dan popup asli; perubahan satu lokasi, tidak mengubah nilai tanggal, data, atau API. Peringatan lint hook/img lama tetap ada.
