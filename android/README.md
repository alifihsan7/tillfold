# Tillfold Android

Aplikasi native Kotlin + Jetpack Compose, memakai API dan akun Tillfold yang sama dengan dashboard web. Android 8.0 (API 26) atau lebih baru. Tidak menggunakan WebView.

## Yang tersedia di versi 0.1.0

- Masuk dengan username/email dan kata sandi, daftar akun, serta setup rekening pertama.
- Ringkasan saldo, pemasukan/pengeluaran, batas belanja harian dari server, dan pemilihan siklus/minggu/bulan.
- Riwayat transaksi dengan pencarian, filter, semua waktu, dan pagination; tambah, edit, hapus transaksi dengan konfirmasi.
- Transfer antar-rekening berpasangan dan pencatatan gaji dengan kunci idempotensi.
- Daftar rekening dan kantong, target tabungan dan penambahan target manual, serta status tagihan.
- Tema terang/gelap/mengikuti perangkat, font Plus Jakarta Sans, dan komponen Fold tanpa border pada kartu.
- Demo berlabel yang terpisah dari akun asli; seluruh penulisan data dinonaktifkan dalam demo.

Pengelolaan rekening/kategori/kantong, pembayaran tagihan, alokasi gaji lanjutan, rekonsiliasi, dana talangan, cadangan, dan integrasi Sheets/Telegram masih melalui dashboard web. Tombol pengaturan lanjutan membuka browser. Login Google native belum tersedia: akun Google dapat mengatur kata sandi dari profil web lalu masuk memakai akun yang sama. Aplikasi memerlukan koneksi; tidak ada antrean transaksi offline atau notifikasi push.

## Build

Gunakan JDK 17, Android SDK platform 36, Build Tools 35.0.0, dan koneksi ke Google Maven/Maven Central saat build pertama. Buka direktori `android` di Android Studio atau jalankan dari direktori tersebut:

```bash
# Atau isi sdk.dir di local.properties, yang tidak masuk Git.
export ANDROID_HOME=/path/to/android-sdk
./gradlew :app:assembleDebug
```

APK: `app/build/outputs/apk/debug/app-debug.apk`. APK debug sudah ditandatangani untuk pemasangan percobaan. Versi ini belum ditandatangani dengan kunci distribusi/Play Store. Build release (`./gradlew :app:assembleRelease`) melakukan minifikasi tetapi menghasilkan APK unsigned; siapkan kunci distribusi sendiri sebelum menerbitkan. Jangan commit kunci/password signing.

Default API: `https://tillfold.alifihsan.my.id/api/v1/`. Untuk server uji dengan sertifikat HTTPS valid:

```bash
./gradlew :app:assembleDebug -PtillfoldApiUrl=https://staging.example.com/api/v1/
```

## Validasi

```bash
./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleRelease
# Memerlukan emulator atau perangkat uji yang tersambung:
./gradlew :app:connectedDebugAndroidTest
```

Tes JVM mencakup kontrak HTTP, bilangan rupiah besar, pemisahan saldo awal, parameter periode, pengosongan kantong saat rekening berubah, penanganan error, pencegahan ketukan ganda, dan sesi kedaluwarsa. Tes UI Compose memakai Robolectric API 34 dan menggambar layar native ke `app/build/screenshots/`; semua datanya fixture, tanpa menyentuh produksi. Tes perangkat memverifikasi penyimpanan token menggunakan Android Keystore. Tes tersebut memerlukan perangkat dan tidak digantikan oleh Robolectric.

## Data dan sesi

Nominal rupiah menggunakan `Long`; perhitungan buku kas dan anggaran tetap bersumber dari backend. Token disimpan terenkripsi AES-GCM memakai kunci Android Keystore. Kata sandi dan respons keuangan tidak disimpan ke disk oleh lapisan data. Logout membersihkan token dan state akun. Backup aplikasi dimatikan. HTTPS wajib dan tidak ada logging isi permintaan/token.

Permintaan finansial biasa tidak diulang otomatis saat koneksi terputus. Pesan error meminta pengguna memuat ulang untuk memastikan hasil sebelum mencoba lagi. Pencatatan gaji memakai UUID yang bertahan selama formulir terbuka. Edit transfer mengikuti endpoint pasangan; penyesuaian saldo dan dana talangan tidak bisa diedit lewat formulir transaksi biasa. Pembayaran/tagihan dan pembagian gaji tetap mendapat validasi khusus dari backend.

Font disalin dari aset web; lisensi OFL ada di `FONT-LICENSE.txt`.
