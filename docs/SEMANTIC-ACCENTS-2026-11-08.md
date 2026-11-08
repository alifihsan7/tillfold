# Aksen berdasarkan fungsi

Basis Ink & Silver tetap netral. Tombol utama tetap silver. Tidak menambah glow, gradient, atau lapisan glass.

- Sage: pemasukan, progres tabungan, tagihan lunas.
- Coral: pengeluaran, nilai selisih negatif, tagihan lewat batas.
- Amber: tagihan hari ini/mendekat dan peringatan laju anggaran.
- Blue-gray: transfer masuk/keluar, mutasi kalender, navigasi/filter terpilih.
- Penyesuaian saldo tetap netral; bukan pemasukan/pengeluaran.

Warna rekening/kategori yang dipilih pengguna tetap disimpan. Badge peran rekening memakai fungsi, bukan warna kategori. Label, tanda +/−, ikon, dan status teks tetap ada agar informasi tidak bergantung pada warna saja.

## Kontras

WCAG relative luminance, minimum teks pada base/panel, termasuk tint 10% dan 20%. Dark: #151517 dan #232326. Light: #f3f3f5, #e5e5ea, #fdfdfe.

| Mode | Aksen | Minimum |
| --- | --- | --- |
| Dark | Sage | 5.95:1 |
| Dark | Coral | 5.14:1 |
| Dark | Amber | 6.46:1 |
| Dark | Blue-gray | 5.39:1 |
| Light | Sage | 4.83:1 |
| Light | Coral | 4.75:1 |
| Light | Amber | 4.60:1 |
| Light | Blue-gray | 5.08:1 |

## Validasi

- Empat check script frontend lulus: kalender, respons API, overview, dashboard data.
- Next.js production build lulus. Peringatan lint hook dan img yang sudah ada tetap muncul.
- Browser lokal data dummy: overview, riwayat, kalender, tagihan, tabungan, laporan; dark/light.
- Kalender lebar 390px: scrollWidth sama dengan viewport 390px; 30 sel tanggal tinggi 100px tanpa overflow horizontal.
- Status tagihan hari ini memakai amber; progres tabungan memakai sage; mutasi kalender dan pilihan tampilan memakai blue-gray.
- Tidak ada perubahan API, struktur data, maupun perhitungan keuangan.
