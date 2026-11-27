const guestCopy: Record<string, { title: string; description: string }> = {
  Transaksi: {
    title: "Masuk untuk lihat transaksi",
    description: "Setelah masuk, kamu bisa mencatat pemasukan dan pengeluaran, mencari transaksi, dan melihatnya di kalender.",
  },
  Anggaran: {
    title: "Masuk untuk lihat anggaran",
    description: "Cek batas belanja harian, pembagian gaji, dan saldo kantong per siklus.",
  },
  Rencana: {
    title: "Masuk untuk buka rencana keuangan",
    description: "Buat target tabungan dan catat tagihan yang perlu dibayar.",
  },
  Laporan: {
    title: "Masuk untuk lihat laporan",
    description: "Lihat arus kas harian dan kategori yang paling banyak kamu belanjakan.",
  },
  Pengaturan: {
    title: "Masuk untuk kelola akun",
    description: "Atur rekening, kategori, profil, dan koneksi Telegram dari akunmu.",
  },
};

export function GuestView({ page, loading, onSignIn }: {
  page: string;
  loading: boolean;
  onSignIn: () => void;
}) {
  const copy = guestCopy[page] ?? {
    title: "Masuk ke Tillfold",
    description: "Masuk untuk melihat catatan keuanganmu.",
  };

  return (
    <section className="fold-card fold-message fold-guest-view" aria-labelledby={loading ? undefined : "guest-view-title"} aria-busy={loading}>
      {loading ? <p role="status">Memeriksa sesi…</p> : <>
        <h2 id="guest-view-title" className="ai7-type-section">{copy.title}</h2>
        <p className="text-sm text-luma-smoke">{copy.description}</p>
        <button type="button" className="luma-action-primary" onClick={onSignIn}>Masuk ke akun</button>
      </>}
    </section>
  );
}
