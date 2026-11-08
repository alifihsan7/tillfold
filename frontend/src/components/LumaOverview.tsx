"use client";

import React from "react";
import { Plus, ArrowUpRight, Eye, EyeOff, ArrowDownLeft } from "lucide-react";
import { Skeleton } from "./ui/Skeleton";
import { HiddenAmount } from "./ui/HiddenAmount";

interface LumaOverviewProps {
  totalBalance: number;
  income: number;
  expense: number;
  accountCount: number;
  safeDaily: number;
  pocketAccount: string;
  pocketRemaining: number;
  pocketBudget: number | null;
  dayOfCycle: number;
  cycleDays: number;
  daysRemaining: number;
  paceStatus: "ahead" | "on_track" | "warning";
  periodEnded: boolean;
  formatRupiah: (val: number) => string;
  loading?: boolean;
  isGuest?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onSignIn?: () => void;
  onAddTransaction: () => void;
  onOpenPaycheck: () => void;
  hideBalance?: boolean;
  onToggleBalance?: () => void;
}

export function LumaOverview({ totalBalance, income, expense, accountCount, safeDaily,
  pocketAccount, pocketRemaining, pocketBudget, dayOfCycle, cycleDays, daysRemaining,
  paceStatus, periodEnded, formatRupiah, loading, isGuest, error, onRetry, onSignIn,
  onAddTransaction, onOpenPaycheck, hideBalance = false, onToggleBalance }: LumaOverviewProps) {
  const flowMax = Math.max(income, expense, 1);
  const remainingPct = pocketBudget && pocketBudget > 0
    ? Math.min(100, Math.max(0, pocketRemaining / pocketBudget * 100)) : null;
  const privateAmount = (amount: number) => hideBalance ? <HiddenAmount /> : formatRupiah(amount);

  if (loading) return <div className="luma-overview-grid" aria-busy="true" aria-label="Memuat ringkasan">
    <span className="sr-only" role="status">Memuat saldo dan transaksi Anda.</span>
    <div className="luma-balance-panel space-y-6"><Skeleton className="h-4 w-28" /><Skeleton className="h-12 w-3/4" /><Skeleton className="h-11 w-40" /></div>
    <div className="luma-overview-side"><div className="luma-glass p-6"><Skeleton className="h-24 w-full" /></div><div className="luma-glass p-6"><Skeleton className="h-24 w-full" /></div></div>
  </div>;

  if (error) return <section className="luma-data-state" role="alert">
    <h2>Ringkasan belum dapat dimuat</h2><p>{error}</p>
    <button type="button" className="luma-action-primary" onClick={onRetry}>Coba lagi</button>
  </section>;

  if (isGuest) return <div className="luma-overview-grid">
    <section className="luma-balance-panel luma-guest-panel" aria-label="Mulai mencatat keuangan">
      <p className="luma-panel-label">Keuangan pribadi</p>
      <h2>Saldo, jatah belanja,<br />dan catatan harian.</h2>
      <p>Masuk untuk melihat rekening dan transaksi Anda.<br />Data keuangan belum ditampilkan.</p>
      <div className="luma-balance-actions"><button type="button" className="luma-action-primary" onClick={onSignIn}>Masuk ke akun</button></div>
      <div className="luma-guest-inset">Catat pengeluaran lewat web atau bot Telegram yang terhubung.</div>
    </section>
    <section className="luma-matte luma-guest-guide" aria-label="Panduan ringkasan">
      <h2>Yang bisa Anda lihat di sini</h2>
      <dl><div><dt>Saldo rekening</dt><dd>Total kas dari rekening yang Anda catat.</dd></div>
        <div><dt>Jatah belanja harian</dt><dd>Batas belanja berdasarkan sisa anggaran dan waktu dalam siklus gajian.</dd></div>
        <div><dt>Catatan transaksi</dt><dd>Riwayat pemasukan, pengeluaran, dan transfer.</dd></div></dl>
    </section>
  </div>;

  return <div className="luma-overview-grid">
    <section className="luma-balance-panel" aria-label="Total saldo kas">
      <div className="luma-balance-top">
        <h2 className="luma-panel-label">Total saldo kas</h2>
        <button type="button" className="luma-icon-button" onClick={onToggleBalance}
          aria-label="Sembunyikan saldo" title={hideBalance ? "Tampilkan saldo" : "Sembunyikan saldo"} aria-pressed={hideBalance}>
          {hideBalance ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
        </button>
      </div>
      <div className="luma-balance-body">
        <p className="luma-balance-number" aria-live="polite">{privateAmount(totalBalance)}</p>
        <p className="text-xs text-luma-ivory/70">Tersimpan di {accountCount} rekening Anda</p>
        <div className="luma-balance-actions">
          <button type="button" className="luma-action-primary" onClick={onAddTransaction}><Plus size={16} aria-hidden="true" /> Catat transaksi</button>
          <button type="button" className="luma-action-secondary" onClick={onOpenPaycheck}>Catat gaji</button>
        </div>
      </div>
      <div className="luma-balance-stats">
        <div><span><ArrowDownLeft size={13} aria-hidden="true" /> Pemasukan</span><strong>{privateAmount(income)}</strong></div>
        <div><span><ArrowUpRight size={13} aria-hidden="true" /> Pengeluaran</span><strong>{privateAmount(expense)}</strong></div>
      </div>
    </section>
    <div className="luma-overview-side">
      <section className="luma-matte luma-flow-panel" aria-label="Arus kas periode ini">
        <div className="luma-section-heading"><h2>Arus kas</h2><span>Periode ini</span></div>
        <div className="luma-flow-line"><span>Masuk</span><div className="luma-flow-track"><div style={{ width: `${Math.max(0, income) / flowMax * 100}%` }} className="luma-flow-income" /></div><strong>{privateAmount(income)}</strong></div>
        <div className="luma-flow-line"><span>Keluar</span><div className="luma-flow-track"><div style={{ width: `${Math.max(0, expense) / flowMax * 100}%` }} className="luma-flow-expense" /></div><strong>{privateAmount(expense)}</strong></div>
        <div className="luma-flow-net"><span>Selisih</span><span className={income - expense < 0 ? "text-luma-coral" : "text-luma-ivory"}>{privateAmount(income - expense)}</span></div>
      </section>
      <section className="luma-matte luma-daily-panel" data-pace={paceStatus} aria-label="Batas belanja harian">
        <div className="luma-section-heading"><h2>Batas belanja harian</h2></div>
        {pocketBudget === null ? <div className="luma-budget-empty"><p>Anggaran belum diatur.</p><button type="button" className="luma-text-action" onClick={onOpenPaycheck}>Atur siklus gajian</button></div> : <>
        <div className="luma-daily-amount">{periodEnded ? "Periode berakhir" : privateAmount(safeDaily)}{!periodEnded && <span>/ hari</span>}</div>
        <div className="luma-daily-caption"><span>{periodEnded ? "Siklus selesai" : paceStatus === "warning" ? "Belanja melebihi laju anggaran" : "Belanja dalam batas anggaran"}</span><span>{periodEnded ? "Mulai siklus baru" : `${daysRemaining} hari tersisa`}</span></div>
        {remainingPct !== null && <div className="luma-quota-track" role="progressbar" aria-label={`Sisa anggaran ${pocketAccount}`} aria-valuenow={Math.round(remainingPct)} aria-valuemin={0} aria-valuemax={100}><div style={{ width: `${remainingPct}%` }} /></div>}
        <div className="luma-daily-caption"><span>Sisa {pocketAccount}: {privateAmount(pocketRemaining)}</span><span>Hari {dayOfCycle}/{cycleDays}</span></div>
        </>}
      </section>
    </div>
  </div>;
}
