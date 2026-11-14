import React, { useState, useEffect, useMemo } from "react";
import { HandCoins, ArrowLeftRight, AlertCircle, CheckCircle2 } from "lucide-react";
import { CustomModal } from "@/components/ui/CustomModal";
import { CustomSelect, SelectOption } from "@/components/ui/CustomSelect";
import { CurrencyInput } from "@/components/ui/CurrencyInput";
import { AccountItem } from "./AccountGrid";
import { PocketItem, InternalLoan, createInternalLoan } from "@/lib/api";

export interface CreateInternalLoanModalProps {
  isOpen: boolean;
  onClose: () => void;
  accounts: AccountItem[];
  pockets?: PocketItem[];
  formatRupiah: (val: number) => string;
  onSuccess: (newLoan: InternalLoan) => void;
}

export function CreateInternalLoanModal({
  isOpen,
  onClose,
  accounts,
  pockets = [],
  formatRupiah,
  onSuccess,
}: CreateInternalLoanModalProps) {
  const activeAccounts = useMemo(() => {
    return accounts.filter((a) => !a.is_archived);
  }, [accounts]);

  const defaultSourceId = useMemo(() => {
    if (activeAccounts.length > 0) {
      return String(activeAccounts[0].id ?? "");
    }
    return "";
  }, [activeAccounts]);

  const defaultTargetId = useMemo(() => {
    if (activeAccounts.length > 1) {
      return String(activeAccounts[1].id ?? "");
    }
    return defaultSourceId;
  }, [activeAccounts, defaultSourceId]);

  const [sourceAccountId, setSourceAccountId] = useState<string>(defaultSourceId);
  const [sourcePocketId, setSourcePocketId] = useState<string>("");
  const [targetAccountId, setTargetAccountId] = useState<string>(defaultTargetId);
  const [targetPocketId, setTargetPocketId] = useState<string>("");
  const [amount, setAmount] = useState<string>("");
  const [note, setNote] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Reset or initialize state when opening modal
  useEffect(() => {
    if (isOpen) {
      setSourceAccountId(defaultSourceId);
      setSourcePocketId("");
      setTargetAccountId(defaultTargetId);
      setTargetPocketId("");
      setAmount("");
      setNote("");
      setError(null);
      setLoading(false);
    }
  }, [isOpen, defaultSourceId, defaultTargetId]);

  // Account options
  const accountOptions: SelectOption[] = useMemo(() => {
    return activeAccounts.map((acc) => {
      const balance = acc.current_balance ?? acc.initial_balance ?? 0;
      return {
        value: String(acc.id),
        label: acc.name,
        description: `Saldo: ${formatRupiah(balance)}${acc.type ? ` · ${acc.type}` : ""}`,
      };
    });
  }, [activeAccounts, formatRupiah]);

  // Pockets for source account
  const sourcePockets = useMemo(() => {
    const numId = Number(sourceAccountId);
    return pockets.filter((p) => p.account_id === numId && p.is_active);
  }, [pockets, sourceAccountId]);

  const sourcePocketOptions: SelectOption[] = useMemo(() => {
    const opts: SelectOption[] = [
      {
        value: "",
        label: "Tanpa Kantong (Saldo Rekening Langsung)",
        description: "Gunakan saldo umum rekening",
      },
    ];
    sourcePockets.forEach((p) => {
      const bal = p.balance ?? p.remaining_amount ?? 0;
      opts.push({
        value: String(p.id),
        label: p.name,
        description: `Saldo: ${formatRupiah(bal)}`,
      });
    });
    return opts;
  }, [sourcePockets, formatRupiah]);

  // Pockets for target account
  const targetPockets = useMemo(() => {
    const numId = Number(targetAccountId);
    return pockets.filter((p) => p.account_id === numId && p.is_active);
  }, [pockets, targetAccountId]);

  const targetPocketOptions: SelectOption[] = useMemo(() => {
    const opts: SelectOption[] = [
      {
        value: "",
        label: "Tanpa Kantong (Saldo Rekening Langsung)",
        description: "Masuk ke saldo umum rekening",
      },
    ];
    targetPockets.forEach((p) => {
      const bal = p.balance ?? p.remaining_amount ?? 0;
      opts.push({
        value: String(p.id),
        label: p.name,
        description: `Saldo: ${formatRupiah(bal)}`,
      });
    });
    return opts;
  }, [targetPockets, formatRupiah]);

  // Selected source and target entities
  const selectedSourceAccount = useMemo(() => {
    return activeAccounts.find((a) => String(a.id) === sourceAccountId);
  }, [activeAccounts, sourceAccountId]);

  const selectedSourcePocket = useMemo(() => {
    return sourcePockets.find((p) => String(p.id) === sourcePocketId);
  }, [sourcePockets, sourcePocketId]);

  const selectedTargetAccount = useMemo(() => {
    return activeAccounts.find((a) => String(a.id) === targetAccountId);
  }, [activeAccounts, targetAccountId]);

  const selectedTargetPocket = useMemo(() => {
    return targetPockets.find((p) => String(p.id) === targetPocketId);
  }, [targetPockets, targetPocketId]);

  // Maximum available balance from source
  const sourceAvailableBalance = useMemo(() => {
    if (selectedSourcePocket) {
      return selectedSourcePocket.balance ?? selectedSourcePocket.remaining_amount ?? 0;
    }
    return selectedSourceAccount?.current_balance ?? selectedSourceAccount?.initial_balance ?? 0;
  }, [selectedSourcePocket, selectedSourceAccount]);

  const numericAmount = useMemo(() => {
    const raw = amount.replace(/[^\d]/g, "");
    return raw ? parseInt(raw, 10) : 0;
  }, [amount]);

  // Real-time validation message
  const validationError = useMemo(() => {
    if (!sourceAccountId || !targetAccountId) {
      return "Pilih rekening sumber dan tujuan.";
    }

    if (sourceAccountId === targetAccountId) {
      if (!sourcePocketId || !targetPocketId) {
        return "Rekening sumber tidak boleh sama dengan rekening tujuan (kecuali antar sub-kantong berbeda).";
      }
      if (sourcePocketId === targetPocketId) {
        return "Sub-kantong asal dan tujuan tidak boleh sama.";
      }
    }

    if (numericAmount <= 0) {
      return "Masukkan nominal pinjaman lebih dari Rp 0.";
    }

    if (numericAmount > sourceAvailableBalance) {
      return `Saldo sumber tidak mencukupi (Tersedia: ${formatRupiah(sourceAvailableBalance)}).`;
    }

    return null;
  }, [
    sourceAccountId,
    targetAccountId,
    sourcePocketId,
    targetPocketId,
    numericAmount,
    sourceAvailableBalance,
    formatRupiah,
  ]);

  const handleSwap = () => {
    const tempAcc = sourceAccountId;
    const tempPocket = sourcePocketId;
    setSourceAccountId(targetAccountId);
    setSourcePocketId(targetPocketId);
    setTargetAccountId(tempAcc);
    setTargetPocketId(tempPocket);
    setError(null);
  };

  const handleSetMax = () => {
    if (sourceAvailableBalance > 0) {
      setAmount(String(sourceAvailableBalance));
      setError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const payload = {
        source_account_id: Number(sourceAccountId),
        source_pocket_id: sourcePocketId ? Number(sourcePocketId) : null,
        target_account_id: Number(targetAccountId),
        target_pocket_id: targetPocketId ? Number(targetPocketId) : null,
        amount: numericAmount,
        note: note.trim() || undefined,
      };

      const newLoan = await createInternalLoan(payload);
      onSuccess(newLoan);
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal membuat dana talangan internal";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <CustomModal
      isOpen={isOpen}
      onClose={onClose}
      title="Pinjam Dana Talangan Internal"
      subtitle="Pinjam saldo antar-rekening atau antar-kantong sendiri tanpa mengubah kekayaan bersih."
      icon={<HandCoins className="w-5 h-5 text-luma-gold" />}
      accent="gold"
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Error notification banner */}
        {(error || (validationError && numericAmount > 0 && validationError !== "Masukkan nominal pinjaman lebih dari Rp 0.")) && (
          <div
            role="alert"
            className="flex items-start gap-2.5 p-3 rounded-2xl bg-luma-coral/10 border border-luma-coral/30 text-luma-coral text-xs"
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <p className="leading-relaxed">{error || validationError}</p>
          </div>
        )}

        {/* Source Account & Pocket Card */}
        <div className="rounded-2xl bg-white/[0.03] border border-luma-smokeline p-4 space-y-3.5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-luma-ivory tracking-wide uppercase">
              1. Sumber Dana (Pemberi Pinjaman)
            </span>
            <span className="text-xs font-mono text-luma-smoke tabular-nums">
              Tersedia: {formatRupiah(sourceAvailableBalance)}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-luma-smoke mb-1.5">
                Rekening Sumber
              </label>
              <CustomSelect
                value={sourceAccountId}
                onChange={(val) => {
                  setSourceAccountId(val);
                  setSourcePocketId("");
                  setError(null);
                }}
                options={accountOptions}
                placeholder="Pilih rekening sumber..."
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-luma-smoke mb-1.5">
                Sub-Kantong Sumber (Opsional)
              </label>
              <CustomSelect
                value={sourcePocketId}
                onChange={(val) => {
                  setSourcePocketId(val);
                  setError(null);
                }}
                options={sourcePocketOptions}
                placeholder="Pilih sub-kantong..."
                disabled={sourcePockets.length === 0}
              />
            </div>
          </div>
        </div>

        {/* Swap Control Divider */}
        <div className="relative flex items-center justify-center py-1">
          <div className="absolute inset-0 flex items-center" aria-hidden="true">
            <div className="w-full border-t border-luma-smokeline" />
          </div>
          <button
            type="button"
            onClick={handleSwap}
            title="Tukar arah sumber dan peminjam"
            aria-label="Tukar arah sumber dan peminjam"
            className="luma-touch relative z-10 w-9 h-9 rounded-full bg-luma-coal border border-luma-smokeline hover:border-luma-gold/50 text-luma-smoke hover:text-luma-ivory flex items-center justify-center transition shadow-sm active:scale-95 cursor-pointer"
          >
            <ArrowLeftRight className="w-4 h-4" />
          </button>
        </div>

        {/* Target Account & Pocket Card */}
        <div className="rounded-2xl bg-white/[0.03] border border-luma-smokeline p-4 space-y-3.5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-luma-ivory tracking-wide uppercase">
              2. Tujuan Talangan (Peminjam / Berutang)
            </span>
            {selectedTargetAccount && (
              <span className="text-xs font-mono text-luma-smoke tabular-nums">
                Saldo saat ini: {formatRupiah(
                  selectedTargetPocket
                    ? (selectedTargetPocket.balance ?? selectedTargetPocket.remaining_amount ?? 0)
                    : (selectedTargetAccount.current_balance ?? selectedTargetAccount.initial_balance ?? 0)
                )}
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-luma-smoke mb-1.5">
                Rekening Tujuan
              </label>
              <CustomSelect
                value={targetAccountId}
                onChange={(val) => {
                  setTargetAccountId(val);
                  setTargetPocketId("");
                  setError(null);
                }}
                options={accountOptions}
                placeholder="Pilih rekening tujuan..."
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-luma-smoke mb-1.5">
                Sub-Kantong Tujuan (Opsional)
              </label>
              <CustomSelect
                value={targetPocketId}
                onChange={(val) => {
                  setTargetPocketId(val);
                  setError(null);
                }}
                options={targetPocketOptions}
                placeholder="Pilih sub-kantong..."
                disabled={targetPockets.length === 0}
              />
            </div>
          </div>
        </div>

        {/* Amount Input */}
        <div className="space-y-1.5">
          <div className="flex justify-between items-center">
            <label htmlFor="loan-amount-input" className="block text-xs font-medium text-luma-smoke">
              Nominal Dana Talangan
            </label>
            {sourceAvailableBalance > 0 && (
              <button
                type="button"
                onClick={handleSetMax}
                className="text-xs font-semibold text-luma-gold hover:underline cursor-pointer"
              >
                Gunakan Maksimal
              </button>
            )}
          </div>
          <CurrencyInput
            id="loan-amount-input"
            value={amount}
            onChange={(val) => {
              setAmount(val);
              setError(null);
            }}
            placeholder="0"
            quickAmounts={[50000, 100000, 250000, 500000, 1000000]}
            autoFocus
          />
        </div>

        {/* Note / Keperluan Input */}
        <div className="space-y-1.5">
          <label htmlFor="loan-note-input" className="block text-xs font-medium text-luma-smoke">
            Keterangan / Keperluan (Opsional)
          </label>
          <input
            id="loan-note-input"
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Contoh: Talangi makan siang tim, Beli bensin, Tiket konser..."
            maxLength={255}
            className="w-full bg-obsidian-panel border border-luma-smokeline focus:border-luma-gold/60 focus:ring-1 focus:ring-luma-gold/50 rounded-xl px-3.5 py-2.5 text-sm text-slateText-primary placeholder:text-zinc-500 outline-none transition"
          />
        </div>

        {/* Informational invariant disclaimer */}
        <div className="p-3 rounded-xl bg-white/[0.02] border border-luma-smokeline/50 text-[11px] text-luma-smoke flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-luma-sage shrink-0" />
          <span>
            Pencatatan ini memicu mutasi ledger transfer kas secara otomatis. Total kekayaan bersih (net worth) Anda tetap utuh.
          </span>
        </div>

        {/* Modal Actions */}
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
            className="luma-touch px-5 py-2.5 rounded-2xl bg-luma-gold hover:bg-luma-gold/90 text-luma-charcoal text-xs sm:text-sm font-semibold transition disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer inline-flex items-center gap-2 shadow-sm"
          >
            {loading ? (
              <span>Memproses...</span>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4" />
                <span>Buat Pinjaman Talangan</span>
              </>
            )}
          </button>
        </div>
      </form>
    </CustomModal>
  );
}
