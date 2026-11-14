import React, { useState, useEffect, useMemo } from "react";
import { CheckCircle2, ArrowRight, AlertCircle, Coins, ShieldCheck } from "lucide-react";
import { CustomModal } from "@/components/ui/CustomModal";
import { CurrencyInput } from "@/components/ui/CurrencyInput";
import { InternalLoan, settleInternalLoan } from "@/lib/api";

export interface SettleInternalLoanModalProps {
  isOpen: boolean;
  onClose: () => void;
  loan: InternalLoan | null;
  formatRupiah: (val: number) => string;
  onSuccess: (updatedLoan: InternalLoan) => void;
}

export function SettleInternalLoanModal({
  isOpen,
  onClose,
  loan,
  formatRupiah,
  onSuccess,
}: SettleInternalLoanModalProps) {
  const [settleMode, setSettleMode] = useState<"full" | "partial">("full");
  const [amount, setAmount] = useState<string>("");
  const [note, setNote] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && loan) {
      setSettleMode("full");
      setAmount(String(loan.remaining_amount));
      setNote("");
      setError(null);
      setLoading(false);
    }
  }, [isOpen, loan]);

  const maxRemaining = loan?.remaining_amount ?? 0;

  const numericAmount = useMemo(() => {
    if (settleMode === "full") return maxRemaining;
    const raw = amount.replace(/[^\d]/g, "");
    return raw ? parseInt(raw, 10) : 0;
  }, [settleMode, amount, maxRemaining]);

  const validationError = useMemo(() => {
    if (!loan) return "Data pinjaman tidak valid.";
    if (loan.status !== "active") return "Pinjaman sudah tidak berstatus aktif.";
    if (maxRemaining <= 0) return "Pinjaman sudah lunas.";

    if (settleMode === "partial") {
      if (numericAmount <= 0) {
        return "Masukkan nominal pelunasan lebih dari Rp 0.";
      }
      if (numericAmount > maxRemaining) {
        return `Nominal pelunasan tidak boleh melebihi sisa pinjaman (${formatRupiah(maxRemaining)}).`;
      }
    }

    return null;
  }, [loan, maxRemaining, settleMode, numericAmount, formatRupiah]);

  if (!loan) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const isFull = settleMode === "full" || numericAmount === maxRemaining;
      const payload: { amount?: number; note?: string } = {
        amount: isFull ? undefined : numericAmount,
        note: note.trim() || undefined,
      };

      const updated = await settleInternalLoan(loan.id, payload);
      onSuccess(updated);
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal melunasi pinjaman dana talangan";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <CustomModal
      isOpen={isOpen}
      onClose={onClose}
      title="Lunasi Dana Talangan Internal"
      subtitle={`Pelunasan kewajiban dari ${loan.target_account_name} kembali ke ${loan.source_account_name}.`}
      icon={<Coins className="w-5 h-5 text-luma-sage" />}
      accent="sage"
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Error banner */}
        {error && (
          <div
            role="alert"
            className="flex items-start gap-2.5 p-3 rounded-2xl bg-luma-coral/10 border border-luma-coral/30 text-luma-coral text-xs"
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <p className="leading-relaxed">{error}</p>
          </div>
        )}

        {/* Loan Overview Card */}
        <div className="rounded-2xl bg-white/[0.03] border border-luma-smokeline p-4 space-y-3.5">
          <div className="flex items-center justify-between gap-2 border-b border-luma-smokeline/60 pb-3">
            <span className="text-xs font-semibold text-luma-smoke uppercase tracking-wider">
              Detail Kewajiban #{loan.id}
            </span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-luma-gold/15 text-luma-gold border border-luma-gold/30 font-medium">
              Aktif Terutang
            </span>
          </div>

          {/* Direction Flow */}
          <div className="flex items-center justify-between gap-2 p-3 rounded-xl bg-black/20 border border-luma-smokeline/40">
            {/* Debtor (Yang membayar balik) */}
            <div className="min-w-0">
              <span className="text-[10px] uppercase font-semibold text-luma-smoke tracking-wider block">
                Peminjam (Membayar)
              </span>
              <p className="text-xs sm:text-sm font-semibold text-luma-ivory truncate mt-0.5">
                {loan.target_account_name}
              </p>
              {loan.target_pocket_name && (
                <span className="text-[11px] text-luma-smoke block truncate">
                  Kantong: {loan.target_pocket_name}
                </span>
              )}
            </div>

            <div className="w-8 h-8 rounded-full bg-white/[0.05] border border-luma-smokeline flex items-center justify-center text-luma-sage shrink-0">
              <ArrowRight className="w-4 h-4" />
            </div>

            {/* Creditor (Yang menerima pelunasan) */}
            <div className="min-w-0 text-right">
              <span className="text-[10px] uppercase font-semibold text-luma-smoke tracking-wider block">
                Sumber Awal (Penerima)
              </span>
              <p className="text-xs sm:text-sm font-semibold text-luma-ivory truncate mt-0.5">
                {loan.source_account_name}
              </p>
              {loan.source_pocket_name && (
                <span className="text-[11px] text-luma-smoke block truncate">
                  Kantong: {loan.source_pocket_name}
                </span>
              )}
            </div>
          </div>

          {/* Balance comparison */}
          <div className="grid grid-cols-2 gap-3 pt-1">
            <div className="p-2.5 rounded-xl bg-white/[0.02] border border-luma-smokeline/40">
              <span className="text-[11px] text-luma-smoke block">Pinjaman Awal</span>
              <p className="text-xs sm:text-sm font-mono font-medium text-luma-smoke mt-0.5 tabular-nums">
                {formatRupiah(loan.amount)}
              </p>
            </div>
            <div className="p-2.5 rounded-xl bg-luma-gold/5 border border-luma-gold/20">
              <span className="text-[11px] text-luma-gold font-medium block">Sisa Kewajiban</span>
              <p className="text-xs sm:text-sm font-mono font-bold text-luma-gold mt-0.5 tabular-nums">
                {formatRupiah(loan.remaining_amount)}
              </p>
            </div>
          </div>

          {loan.note && (
            <p className="text-xs text-luma-smoke italic">
              Catatan: &ldquo;{loan.note}&rdquo;
            </p>
          )}
        </div>

        {/* Settlement Mode Selection */}
        <div className="space-y-2">
          <label className="block text-xs font-medium text-luma-smoke">
            Pilihan Pelunasan
          </label>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => {
                setSettleMode("full");
                setAmount(String(maxRemaining));
                setError(null);
              }}
              className={`luma-touch min-h-[44px] py-2.5 px-3 rounded-2xl border text-xs sm:text-sm font-semibold transition cursor-pointer flex items-center justify-center gap-2 ${
                settleMode === "full"
                  ? "bg-luma-sage/20 border-luma-sage text-luma-sage shadow-sm"
                  : "bg-white/[0.03] border-luma-smokeline text-luma-smoke hover:text-luma-ivory hover:border-white/[0.16]"
              }`}
            >
              <ShieldCheck className="w-4 h-4 shrink-0" />
              <span>Lunas Penuh ({formatRupiah(maxRemaining)})</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setSettleMode("partial");
                setAmount("");
                setError(null);
              }}
              className={`luma-touch min-h-[44px] py-2.5 px-3 rounded-2xl border text-xs sm:text-sm font-semibold transition cursor-pointer flex items-center justify-center gap-2 ${
                settleMode === "partial"
                  ? "bg-luma-gold/20 border-luma-gold text-luma-gold shadow-sm"
                  : "bg-white/[0.03] border-luma-smokeline text-luma-smoke hover:text-luma-ivory hover:border-white/[0.16]"
              }`}
            >
              <Coins className="w-4 h-4 shrink-0" />
              <span>Cicil / Sebagian</span>
            </button>
          </div>
        </div>

        {/* Amount Input (If partial) */}
        {settleMode === "partial" && (
          <div className="space-y-1.5 animate-fadeIn">
            <div className="flex justify-between items-center">
              <label htmlFor="settle-amount-input" className="block text-xs font-medium text-luma-smoke">
                Nominal Pelunasan
              </label>
              <button
                type="button"
                onClick={() => {
                  setAmount(String(maxRemaining));
                  setError(null);
                }}
                className="text-xs font-semibold text-luma-gold hover:underline cursor-pointer"
              >
                Lunasi Semua ({formatRupiah(maxRemaining)})
              </button>
            </div>
            <CurrencyInput
              id="settle-amount-input"
              value={amount}
              onChange={(val) => {
                setAmount(val);
                setError(null);
              }}
              placeholder="0"
              autoFocus
            />
          </div>
        )}

        {/* Note Input */}
        <div className="space-y-1.5">
          <label htmlFor="settle-note-input" className="block text-xs font-medium text-luma-smoke">
            Keterangan Pelunasan (Opsional)
          </label>
          <input
            id="settle-note-input"
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Contoh: Gajian cair, pelunasan sisa talangan..."
            maxLength={255}
            className="w-full bg-obsidian-panel border border-luma-smokeline focus:border-luma-sage/60 focus:ring-1 focus:ring-luma-sage/50 rounded-xl px-3.5 py-2.5 text-sm text-slateText-primary placeholder:text-zinc-500 outline-none transition"
          />
        </div>

        {/* Invariant guarantee footnote */}
        <div className="p-3 rounded-xl bg-white/[0.02] border border-luma-smokeline/50 text-[11px] text-luma-smoke flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-luma-sage shrink-0" />
          <span>
            Dana akan dipindahkan dari {loan.target_account_name} kembali ke {loan.source_account_name} secara atomik.
          </span>
        </div>

        {/* Footer Actions */}
        <div className="flex justify-end gap-3 pt-4 border-t border-luma-smokeline">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="luma-touch px-4 py-2.5 rounded-2xl border border-luma-smokeline text-xs sm:text-sm font-medium text-luma-smoke hover:text-luma-ivory hover:border-white/[0.16] transition cursor-pointer"
          >
            Batal
          </button>
          <button
            type="submit"
            disabled={loading || !!validationError}
            className="luma-touch px-5 py-2.5 rounded-2xl bg-luma-sage hover:bg-luma-sage/90 text-luma-charcoal text-xs sm:text-sm font-semibold transition disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer inline-flex items-center gap-2 shadow-sm"
          >
            {loading ? (
              <span>Memproses...</span>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4" />
                <span>Kembalikan Dana Kas</span>
              </>
            )}
          </button>
        </div>
      </form>
    </CustomModal>
  );
}
