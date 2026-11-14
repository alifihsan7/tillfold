import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  HandCoins,
  Plus,
  RefreshCw,
  ArrowRight,
  ShieldCheck,
  Coins,
  AlertCircle,
  Trash2,
  CheckCircle2,
  Clock,
  Ban,
} from "lucide-react";
import {
  InternalLoan,
  getInternalLoans,
  cancelInternalLoan,
  getPockets,
  PocketItem,
} from "@/lib/api";
import { AccountItem } from "./AccountGrid";
import { Skeleton } from "./ui/Skeleton";
import { ConfirmModal } from "./ui/ConfirmModal";
import { CreateInternalLoanModal } from "./CreateInternalLoanModal";
import { SettleInternalLoanModal } from "./SettleInternalLoanModal";

export interface InternalLoansWidgetProps {
  accounts?: AccountItem[];
  pockets?: PocketItem[];
  formatRupiah: (val: number) => string;
  refreshSignal?: number;
  onToast?: (msg: string) => void;
  onDataChanged?: () => void;
}

function formatDateIndo(dateStr: string): string {
  if (!dateStr) return "-";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString("id-ID", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export function InternalLoansWidget({
  accounts = [],
  pockets = [],
  formatRupiah,
  refreshSignal = 0,
  onToast,
  onDataChanged,
}: InternalLoansWidgetProps) {
  const [loans, setLoans] = useState<InternalLoan[]>([]);
  const [totalActiveAmount, setTotalActiveAmount] = useState<number>(0);
  const [statusFilter, setStatusFilter] = useState<"active" | "settled" | "all">("active");
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [loadedPockets, setLoadedPockets] = useState<PocketItem[]>(pockets);

  useEffect(() => {
    if (pockets && pockets.length > 0) {
      setLoadedPockets(pockets);
    } else {
      getPockets()
        .then((res) => {
          const items = res.pockets || res.items || [];
          setLoadedPockets(items);
        })
        .catch(() => {});
    }
  }, [pockets, refreshSignal]);

  // Modal states
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [settleLoanTarget, setSettleLoanTarget] = useState<InternalLoan | null>(null);
  const [cancelLoanTarget, setCancelLoanTarget] = useState<InternalLoan | null>(null);
  const [cancelling, setCancelling] = useState<boolean>(false);

  const fetchLoans = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    else setRefreshing(true);
    setError(null);

    try {
      const res = await getInternalLoans(statusFilter);
      setLoans(res.items);
      setTotalActiveAmount(res.total_active_loan_amount);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal memuat pinjaman internal";
      setError(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchLoans();
  }, [fetchLoans, refreshSignal]);

  const handleCreateSuccess = (newLoan: InternalLoan) => {
    onToast?.(`Dana talangan sebesar ${formatRupiah(newLoan.amount)} berhasil dicatat.`);
    fetchLoans(true);
    onDataChanged?.();
  };

  const handleSettleSuccess = (updatedLoan: InternalLoan) => {
    const isLunas = updatedLoan.status === "settled" || updatedLoan.remaining_amount === 0;
    onToast?.(
      isLunas
        ? `Talangan #${updatedLoan.id} berhasil dilunasi penuh.`
        : `Pelunasan parsial talangan #${updatedLoan.id} berhasil dicatat.`
    );
    fetchLoans(true);
    onDataChanged?.();
  };

  const handleConfirmCancel = async () => {
    if (!cancelLoanTarget) return;
    setCancelling(true);
    try {
      await cancelInternalLoan(cancelLoanTarget.id);
      onToast?.(`Pinjaman talangan #${cancelLoanTarget.id} berhasil dibatalkan.`);
      setCancelLoanTarget(null);
      fetchLoans(true);
      onDataChanged?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal membatalkan pinjaman";
      onToast?.(msg);
    } finally {
      setCancelling(false);
    }
  };

  const activeLoansCount = useMemo(() => {
    return loans.filter((l) => l.status === "active").length;
  }, [loans]);

  return (
    <section
      aria-labelledby="internal-loans-title"
      className="luma-glass p-5 sm:p-6 lg:p-7 space-y-5 rounded-3xl border border-luma-smokeline relative overflow-hidden"
    >
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-2xl bg-luma-gold/10 border border-luma-gold/30 flex items-center justify-center text-luma-gold shrink-0">
            <HandCoins className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 id="internal-loans-title" className="ai7-type-section text-luma-ivory tracking-tight truncate">
                Dana Talangan Internal
              </h2>
              {totalActiveAmount > 0 ? (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold bg-luma-gold/15 text-luma-gold border border-luma-gold/30 tabular-nums">
                  Kewajiban: {formatRupiah(totalActiveAmount)}
                </span>
              ) : (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-luma-sage/15 text-luma-sage border border-luma-sage/30 flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>Semua Kas Utuh</span>
                </span>
              )}
            </div>
            <p className="text-xs text-luma-smoke mt-0.5 truncate">
              {totalActiveAmount > 0
                ? `Total kas sedang dipinjam: ${formatRupiah(totalActiveAmount)}`
                : "Semua dana dingin utuh. Tidak ada pinjaman internal yang berjalan."}
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 w-full sm:w-auto shrink-0">
          <button
            type="button"
            onClick={() => fetchLoans(true)}
            disabled={loading || refreshing}
            title="Muat ulang daftar talangan"
            aria-label="Muat ulang daftar talangan"
            className="luma-touch p-2.5 rounded-2xl border border-luma-smokeline text-luma-smoke hover:text-luma-ivory hover:border-white/[0.16] bg-white/[0.02] transition cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin text-luma-gold" : ""}`} />
          </button>

          <button
            type="button"
            onClick={() => setIsCreateOpen(true)}
            className="luma-touch flex-1 sm:flex-initial px-4 py-2.5 rounded-2xl bg-luma-gold hover:bg-luma-gold/90 text-luma-charcoal text-xs sm:text-sm font-semibold transition inline-flex items-center justify-center gap-2 shadow-sm cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Pinjam Dana</span>
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1.5 p-1 rounded-2xl bg-black/25 border border-luma-smokeline/60 w-fit">
        {[
          { key: "active", label: "Aktif" },
          { key: "settled", label: "Lunas" },
          { key: "all", label: "Semua" },
        ].map((tab) => {
          const isActive = statusFilter === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setStatusFilter(tab.key as "active" | "settled" | "all")}
              className={`luma-touch px-3.5 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer select-none ${
                isActive
                  ? "bg-white/[0.1] text-luma-ivory border border-white/[0.15] shadow-sm"
                  : "text-luma-smoke hover:text-luma-ivory border border-transparent"
              }`}
            >
              {tab.label}
              {tab.key === "active" && totalActiveAmount > 0 && (
                <span className="ml-1.5 px-1.5 py-0.2 rounded-full text-[10px] bg-luma-gold/20 text-luma-gold font-mono">
                  {activeLoansCount}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="space-y-3 pt-1">
          {[1, 2].map((i) => (
            <div key={i} className="p-4 rounded-2xl bg-white/[0.02] border border-luma-smokeline space-y-3">
              <div className="flex justify-between items-center">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-4 w-20" />
              </div>
              <Skeleton className="h-6 w-56" />
              <div className="flex justify-between items-center">
                <Skeleton className="h-3 w-32" />
                <Skeleton className="h-8 w-24" />
              </div>
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="p-6 rounded-2xl bg-luma-coral/10 border border-luma-coral/30 text-center space-y-3">
          <AlertCircle className="w-6 h-6 text-luma-coral mx-auto" />
          <p className="text-xs sm:text-sm text-luma-coral">{error}</p>
          <button
            type="button"
            onClick={() => fetchLoans()}
            className="px-4 py-2 rounded-xl bg-white/[0.08] hover:bg-white/[0.14] text-xs font-semibold text-luma-ivory transition cursor-pointer"
          >
            Coba Lagi
          </button>
        </div>
      ) : loans.length === 0 ? (
        <div className="p-8 sm:p-10 rounded-2xl bg-white/[0.02] border border-luma-smokeline/70 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-white/[0.04] border border-luma-smokeline flex items-center justify-center text-luma-smoke mx-auto">
            <ShieldCheck className="w-6 h-6 text-luma-sage" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-luma-ivory">
              {statusFilter === "active"
                ? "Semua Dana Dingin Utuh"
                : statusFilter === "settled"
                ? "Belum Ada Riwayat Pelunasan"
                : "Belum Ada Catatan Talangan"}
            </h3>
            <p className="text-xs text-luma-smoke max-w-md mx-auto mt-1 leading-relaxed">
              {statusFilter === "active"
                ? "Semua dana dingin utuh. Tidak ada pinjaman internal yang berjalan."
                : "Setiap transaksi pinjam-meminjam antar-rekening Anda akan tercatat rapi di sini."}
            </p>
          </div>
          {statusFilter === "active" && (
            <button
              type="button"
              onClick={() => setIsCreateOpen(true)}
              className="mt-2 px-4 py-2 rounded-xl bg-white/[0.06] hover:bg-white/[0.1] border border-luma-smokeline text-xs font-semibold text-luma-ivory transition cursor-pointer inline-flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5 text-luma-gold" />
              <span>Pinjam Dana</span>
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 pt-1">
          {loans.map((loan) => {
            const isSettled = loan.status === "settled" || loan.remaining_amount === 0;
            const isCancelled = loan.status === "cancelled";
            const isActive = loan.status === "active" && loan.remaining_amount > 0;

            const settledPct = loan.amount > 0
              ? Math.min(100, Math.max(0, Math.round(((loan.amount - loan.remaining_amount) / loan.amount) * 100)))
              : 0;

            const canCancel = isActive && loan.remaining_amount === loan.amount;

            return (
              <div
                key={loan.id}
                className="p-4 sm:p-5 rounded-2xl bg-white/[0.03] border border-luma-smokeline hover:border-white/[0.14] transition-all space-y-4 flex flex-col justify-between"
              >
                <div className="space-y-3">
                  {/* Top line: Flow direction & Status badge */}
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-xs font-semibold text-luma-smoke font-mono">
                        #{loan.id}
                      </span>
                      <span className="text-[11px] text-luma-smoke">
                        {formatDateIndo(loan.created_at)}
                      </span>
                    </div>

                    <div>
                      {isActive && (
                        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-luma-gold/15 text-luma-gold border border-luma-gold/30">
                          Aktif Terutang
                        </span>
                      )}
                      {isSettled && (
                        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-luma-sage/15 text-luma-sage border border-luma-sage/30 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Lunas</span>
                        </span>
                      )}
                      {isCancelled && (
                        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-white/[0.06] text-luma-smoke border border-luma-smokeline flex items-center gap-1">
                          <Ban className="w-3 h-3" />
                          <span>Dibatalkan</span>
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Flow description: Akun Asal (Kreditor) -> Akun Tujuan (Debitur) */}
                  <div className="p-3 rounded-xl bg-black/20 border border-luma-smokeline/40 flex items-center justify-between gap-2">
                    {/* Sumber / Kreditor */}
                    <div className="min-w-0 flex-1">
                      <span className="text-[10px] uppercase font-semibold text-luma-smoke tracking-wider block">
                        Asal (Kreditor)
                      </span>
                      <p className="text-xs sm:text-sm font-semibold text-luma-ivory truncate mt-0.5">
                        {loan.source_account_name}
                      </p>
                      {loan.source_pocket_name && (
                        <span className="text-[11px] text-luma-smoke truncate block">
                          Kantong: {loan.source_pocket_name}
                        </span>
                      )}
                    </div>

                    <div className="w-7 h-7 rounded-full bg-white/[0.04] border border-luma-smokeline flex items-center justify-center text-luma-smoke shrink-0">
                      <ArrowRight className="w-3.5 h-3.5" />
                    </div>

                    {/* Peminjam / Debitur */}
                    <div className="min-w-0 flex-1 text-right">
                      <span className="text-[10px] uppercase font-semibold text-luma-smoke tracking-wider block">
                        Tujuan (Debitur)
                      </span>
                      <p className="text-xs sm:text-sm font-semibold text-luma-ivory truncate mt-0.5">
                        {loan.target_account_name}
                      </p>
                      {loan.target_pocket_name && (
                        <span className="text-[11px] text-luma-smoke truncate block">
                          Kantong: {loan.target_pocket_name}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Remaining Amount & Progress */}
                  <div className="space-y-1.5">
                    <div className="flex justify-between items-baseline gap-2">
                      <span className="text-xs text-luma-smoke">Sisa Kewajiban</span>
                      <span className="text-base sm:text-lg font-mono font-bold text-luma-ivory tabular-nums">
                        {formatRupiah(loan.remaining_amount)}
                      </span>
                    </div>

                    <div className="flex justify-between text-xs text-luma-smoke font-mono tabular-nums">
                      <span>Total Awal: {formatRupiah(loan.amount)}</span>
                      {settledPct > 0 && <span>{settledPct}% Terlunasi</span>}
                    </div>

                    {/* Progress bar */}
                    <div
                      className="h-1.5 w-full bg-black/30 rounded-full overflow-hidden"
                      role="progressbar"
                      aria-valuenow={settledPct}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={`Progres pelunasan ${settledPct} persen`}
                    >
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          isSettled
                            ? "bg-luma-sage"
                            : isCancelled
                            ? "bg-luma-smoke"
                            : "bg-luma-gold"
                        }`}
                        style={{ width: `${Math.max(2, settledPct)}%` }}
                      />
                    </div>
                  </div>

                  {/* Note */}
                  {loan.note && (
                    <p className="text-xs text-luma-smoke/90 italic truncate">
                      Catatan: &ldquo;{loan.note}&rdquo;
                    </p>
                  )}
                </div>

                {/* Actions row */}
                <div className="pt-3 border-t border-luma-smokeline/60 flex items-center justify-between gap-2 mt-2">
                  <div className="text-[11px] text-luma-smoke">
                    {loan.settled_at && (
                      <span className="flex items-center gap-1 text-luma-sage">
                        <Clock className="w-3 h-3" />
                        <span>Lunas {formatDateIndo(loan.settled_at)}</span>
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {canCancel && (
                      <button
                        type="button"
                        onClick={() => setCancelLoanTarget(loan)}
                        title="Batalkan pinjaman (karena salah input)"
                        className="luma-touch px-3 py-1.5 rounded-xl border border-luma-smokeline text-xs text-luma-smoke hover:text-luma-coral hover:border-luma-coral/30 hover:bg-luma-coral/10 transition cursor-pointer inline-flex items-center gap-1.5"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>Batalkan</span>
                      </button>
                    )}

                    {isActive && (
                      <button
                        type="button"
                        onClick={() => setSettleLoanTarget(loan)}
                        className="luma-touch px-3.5 py-1.5 rounded-xl bg-luma-sage hover:bg-luma-sage/90 text-luma-charcoal text-xs font-semibold transition cursor-pointer inline-flex items-center gap-1.5 shadow-sm"
                      >
                        <Coins className="w-3.5 h-3.5" />
                        <span>Lunasi</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Modals */}
      <CreateInternalLoanModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        accounts={accounts}
        pockets={loadedPockets}
        formatRupiah={formatRupiah}
        onSuccess={handleCreateSuccess}
      />

      <SettleInternalLoanModal
        isOpen={!!settleLoanTarget}
        onClose={() => setSettleLoanTarget(null)}
        loan={settleLoanTarget}
        formatRupiah={formatRupiah}
        onSuccess={handleSettleSuccess}
      />

      <ConfirmModal
        isOpen={!!cancelLoanTarget}
        onClose={() => setCancelLoanTarget(null)}
        onConfirm={handleConfirmCancel}
        title={`Batalkan Pinjaman #${cancelLoanTarget?.id}`}
        message={`Apakah Anda yakin ingin membatalkan dana talangan sebesar ${formatRupiah(
          cancelLoanTarget?.amount || 0
        )}? Tindakan ini hanya boleh dilakukan bila terjadi kesalahan input.`}
        confirmText="Ya, Batalkan Pinjaman"
        cancelText="Tutup"
        danger={true}
        loading={cancelling}
      />
    </section>
  );
}
