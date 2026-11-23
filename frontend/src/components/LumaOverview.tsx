"use client";

import { ArrowDownLeft, ArrowLeftRight, ArrowUpRight, Eye, EyeOff, Plus } from "@/components/icons";
import { HiddenAmount } from "./ui/HiddenAmount";
import { Skeleton } from "./ui/Skeleton";

interface LumaOverviewProps {
  totalBalance: number;
  income: number;
  openingBalance?: number;
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

const arc = "M 20 127 A 110 110 0 0 1 240 127";

export function LumaOverview({
  totalBalance, income, openingBalance = 0, expense, accountCount, safeDaily,
  pocketAccount, pocketRemaining, pocketBudget, dayOfCycle, cycleDays, daysRemaining,
  paceStatus, periodEnded, formatRupiah, loading, isGuest, error, onRetry, onSignIn,
  onAddTransaction, onOpenPaycheck, hideBalance = false, onToggleBalance,
}: LumaOverviewProps) {
  if (loading) return (
    <div className="fold-grid" aria-busy="true" aria-label="Memuat ringkasan">
      <span className="sr-only" role="status">Memuat saldo dan transaksi Anda.</span>
      <div className="fold-hero fold-loading"><Skeleton className="h-4 w-28" /><Skeleton className="h-14 w-3/4" /></div>
      <div className="fold-card fold-loading"><Skeleton className="h-32 w-full" /></div>
    </div>
  );

  if (error) return (
    <section className="fold-card fold-message" role="alert">
      <h2>Ringkasan belum dapat dimuat</h2>
      <p>{error}</p>
      <button type="button" className="fold-action" onClick={onRetry}>Coba lagi</button>
    </section>
  );

  if (isGuest) return (
    <div className="fold-grid">
      <section className="fold-hero fold-message" aria-label="Mulai mencatat keuangan">
        <h2>Saldo, jatah belanja, dan catatan harian</h2>
        <p>Masuk untuk melihat rekening dan transaksi Anda. Data keuangan belum ditampilkan.</p>
        <button type="button" className="fold-action" onClick={onSignIn}>Masuk ke akun</button>
      </section>
      <section className="fold-card fold-message" aria-label="Panduan ringkasan">
        <h2>Ringkasan keuangan</h2>
        <p>Lihat saldo rekening, batas belanja harian, dan transaksi di satu tempat.</p>
      </section>
    </div>
  );

  const privateAmount = (value: number) => hideBalance ? <HiddenAmount /> : formatRupiah(value);
  const ratio = pocketBudget && pocketBudget > 0
    ? Math.min(100, Math.max(0, pocketRemaining * 100 / pocketBudget))
    : null;
  const inflow = Math.max(0, income);
  const outflow = Math.max(0, expense);
  const net = income - expense;
  const cycleProgress = Math.min(100, Math.max(0, dayOfCycle / Math.max(1, cycleDays) * 100));

  return (
    <>
      <div className="fold-grid">
        <section className="fold-hero" aria-labelledby="fold-balance-title">
          <div className="fold-hero-header">
            <h2 id="fold-balance-title">Total saldo kas</h2>
            <button type="button" className="fold-icon-button" onClick={onToggleBalance}
              aria-label="Sembunyikan saldo" aria-pressed={hideBalance}
              title={hideBalance ? "Tampilkan saldo" : "Sembunyikan saldo"}>
              {hideBalance ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
            </button>
          </div>
          <p className="fold-balance" aria-live="polite">{privateAmount(totalBalance)}</p>
          <p className="fold-balance-caption">Tersimpan di {accountCount} rekening Anda</p>
          {inflow + outflow > 0 && (
            <div className="fold-ratio" aria-hidden="true">
              {hideBalance ? <span className="fold-ratio-hidden" /> : (
                <>
                  {inflow > 0 && <span className="fold-ratio-income" style={{ flexGrow: inflow }} />}
                  {outflow > 0 && <span className="fold-ratio-expense" style={{ flexGrow: outflow }} />}
                </>
              )}
            </div>
          )}
          <dl className="fold-balance-legend">
            <div><dt><ArrowDownLeft size={14} aria-hidden="true" /> Pemasukan</dt><dd>{privateAmount(income)}</dd></div>
            <div><dt><ArrowUpRight size={14} aria-hidden="true" /> Pengeluaran</dt><dd>{privateAmount(expense)}</dd></div>
          </dl>
          <div className="fold-hero-actions">
            <button type="button" className="fold-action" onClick={onAddTransaction}>
              <Plus size={16} aria-hidden="true" /> Catat transaksi
            </button>
            <button type="button" className="fold-action fold-action-secondary" onClick={onOpenPaycheck}>Catat gaji</button>
          </div>
        </section>

        <section className="fold-card fold-budget" data-pace={paceStatus} aria-labelledby="fold-budget-title">
          <h2 id="fold-budget-title">Batas belanja harian</h2>
          {pocketBudget === null ? (
            <div className="fold-message">
              <p>Anggaran belum diatur.</p>
              <button type="button" className="fold-link" onClick={onOpenPaycheck}>Atur siklus gajian</button>
            </div>
          ) : (
            <>
              {periodEnded ? <p className="fold-daily-amount">Periode berakhir</p> : (
                <div className="fold-gauge">
                  <svg viewBox="0 0 260 138" aria-hidden="true">
                    <path className="fold-gauge-track" d={arc} pathLength="100" />
                    {!hideBalance && ratio !== null && ratio > 0 && (
                      <path className="fold-gauge-fill" d={arc} pathLength="100" strokeDasharray={`${ratio} 100`} />
                    )}
                  </svg>
                  <div className="fold-gauge-value">
                    <p className="fold-daily-amount">{privateAmount(safeDaily)}</p>
                    <p>per hari</p>
                  </div>
                  {!hideBalance && ratio !== null && <span className="sr-only" role="progressbar"
                    aria-label={`Sisa anggaran ${pocketAccount}`} aria-valuenow={Math.round(ratio)}
                    aria-valuemin={0} aria-valuemax={100} />}
                </div>
              )}
              <p className="fold-budget-status">
                <span>{periodEnded ? "Siklus selesai" : paceStatus === "warning" ? "Belanja melebihi laju anggaran" : "Belanja dalam batas anggaran"}</span>
                {!periodEnded && <span>{daysRemaining} hari tersisa</span>}
              </p>
              <dl className="fold-budget-stats">
                <div><dt>Sisa {pocketAccount}</dt><dd>{privateAmount(pocketRemaining)}</dd></div>
                <div>
                  <dt>Siklus</dt><dd>Hari {dayOfCycle}/{cycleDays}</dd>
                  <div className="fold-cycle" aria-hidden="true"><span style={{ width: `${cycleProgress}%` }} /></div>
                </div>
              </dl>
            </>
          )}
        </section>
      </div>

      <section className="fold-flow" aria-labelledby="fold-flow-title">
        <header className="fold-section-header"><h2 id="fold-flow-title">Arus kas</h2><span>Periode ini</span></header>
        <dl>
          <div><dt><ArrowDownLeft size={15} aria-hidden="true" /> Pemasukan</dt><dd className="fold-positive">{privateAmount(income)}</dd></div>
          <div><dt><ArrowUpRight size={15} aria-hidden="true" /> Pengeluaran</dt><dd className="fold-negative">{privateAmount(expense)}</dd></div>
          <div><dt><ArrowLeftRight size={15} aria-hidden="true" /> Selisih</dt><dd className={net < 0 && !hideBalance ? "fold-negative" : undefined}>{privateAmount(net)}</dd></div>
        </dl>
        {openingBalance > 0 && <p>Saldo awal {privateAmount(openingBalance)} dicatat terpisah, tidak termasuk pemasukan.</p>}
      </section>
    </>
  );
}
