import React, { useEffect, useMemo, useState } from "react";
import { ArrowLeftRight, CheckCircle2, ArrowDown } from "lucide-react";
import { CustomModal } from "@/components/ui/CustomModal";
import { CustomSelect, SelectOption } from "@/components/ui/CustomSelect";
import { CurrencyInput } from "@/components/ui/CurrencyInput";
import { PocketItem, transferPocketBalance } from "@/lib/api";

export type JagoPocketItem = PocketItem;

export interface TransferPocketModalProps {
  isOpen: boolean;
  onClose: () => void;
  accountId?: number;
  accountName?: string;
  pockets: PocketItem[];
  initialSourcePocketId?: number;
  initialTargetPocketId?: number;
  formatRupiah: (val: number) => string;
  onSuccess: () => void;
}

export function TransferPocketModal({
  isOpen,
  onClose,
  accountId,
  accountName,
  pockets,
  initialSourcePocketId,
  initialTargetPocketId,
  formatRupiah,
  onSuccess,
}: TransferPocketModalProps) {
  // Sort pockets: Utama first, then by name
  const sortedPockets = useMemo(() => {
    return [...pockets].sort((a, b) => {
      if (a.slug === "utama") return -1;
      if (b.slug === "utama") return 1;
      return a.name.localeCompare(b.name);
    });
  }, [pockets]);

  // Default source: either initialSourcePocketId or "utama" or first pocket
  const defaultSource = useMemo(() => {
    if (initialSourcePocketId && sortedPockets.some((p) => p.id === initialSourcePocketId)) {
      return String(initialSourcePocketId);
    }
    const utama = sortedPockets.find((p) => p.slug === "utama");
    return utama ? String(utama.id) : sortedPockets[0] ? String(sortedPockets[0].id) : "";
  }, [initialSourcePocketId, sortedPockets]);

  // Default target: either initialTargetPocketId or first non-source pocket
  const defaultTarget = useMemo(() => {
    if (initialTargetPocketId && sortedPockets.some((p) => p.id === initialTargetPocketId)) {
      return String(initialTargetPocketId);
    }
    const candidate = sortedPockets.find((p) => String(p.id) !== defaultSource);
    return candidate ? String(candidate.id) : "";
  }, [initialTargetPocketId, defaultSource, sortedPockets]);

  const [fromPocketId, setFromPocketId] = useState<string>(defaultSource);
  const [toPocketId, setToPocketId] = useState<string>(defaultTarget);
  const [amount, setAmount] = useState<string>("");
  const [note, setNote] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync initial values when modal opens
  useEffect(() => {
    if (isOpen) {
      setFromPocketId(defaultSource);
      setToPocketId(defaultTarget);
      setAmount("");
      setNote("");
      setError(null);
    }
  }, [isOpen, defaultSource, defaultTarget]);

  const sourcePocket = sortedPockets.find((p) => String(p.id) === fromPocketId);
  const targetPocket = sortedPockets.find((p) => String(p.id) === toPocketId);

  const sourceBalance = sourcePocket?.balance ?? sourcePocket?.remaining_amount ?? 0;
  const targetBalance = targetPocket?.balance ?? targetPocket?.remaining_amount ?? 0;

  const numericAmount = useMemo(() => {
    const raw = amount.replace(/[^\d]/g, "");
    return raw ? parseInt(raw, 10) : 0;
  }, [amount]);

  const sourceOptions: SelectOption[] = useMemo(() => {
    return sortedPockets.map((p) => ({
      value: String(p.id),
      label: p.name,
      description: `Saldo: ${formatRupiah(p.balance ?? p.remaining_amount ?? 0)}`,
    }));
  }, [sortedPockets, formatRupiah]);

  const targetOptions: SelectOption[] = useMemo(() => {
    return sortedPockets.map((p) => ({
      value: String(p.id),
      label: p.name,
      description: `Saldo: ${formatRupiah(p.balance ?? p.remaining_amount ?? 0)}${
        p.target_amount > 0 ? ` · Target: ${formatRupiah(p.target_amount)}` : ""
      }`,
    }));
  }, [sortedPockets, formatRupiah]);

  const handleSwap = () => {
    setFromPocketId(toPocketId);
    setToPocketId(fromPocketId);
    setError(null);
  };

  const handleSetMax = () => {
    if (sourceBalance > 0) {
      setAmount(String(sourceBalance));
      setError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!fromPocketId || !toPocketId) {
      setError("Pilih kantong asal dan kantong tujuan");
      return;
    }

    if (fromPocketId === toPocketId) {
      setError("Kantong asal dan kantong tujuan tidak boleh sama");
      return;
    }

    if (numericAmount <= 0) {
      setError("Nominal pindah saldo harus lebih besar dari 0");
      return;
    }

    if (numericAmount > sourceBalance) {
      setError(
        `Saldo ${sourcePocket?.name || "kantong asal"} tidak mencukupi (${formatRupiah(sourceBalance)})`
      );
      return;
    }

    setLoading(true);
    try {
      await transferPocketBalance({
        account_id: accountId,
        from_pocket_id: Number(fromPocketId),
        to_pocket_id: Number(toPocketId),
        amount: numericAmount,
        note: note.trim() || undefined,
      });

      onSuccess();
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal memindahkan saldo kantong";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <CustomModal
      isOpen={isOpen}
      onClose={() => {
        if (!loading) onClose();
      }}
      title="Pindah Saldo Kas"
      subtitle={
        accountName
          ? `Alokasikan saldo kas fisik antar-kantong di ${accountName}`
          : "Pindah dana kas riil antar sub-kantong"
      }
      icon={<ArrowLeftRight className="w-5 h-5 text-luma-gold" />}
      accent="amber"
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div
            role="alert"
            className="p-3.5 bg-luma-coral/10 border border-luma-coral/30 rounded-2xl text-luma-coral text-xs leading-relaxed"
          >
            {error}
          </div>
        )}

        {/* Source & Destination Selector with tactile swap */}
        <div className="space-y-3">
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-zinc-300">
                Dari Kantong (Sumber)
              </label>
              {sourcePocket && (
                <span className="text-xs text-luma-smoke tabular-nums">
                  Saldo:{" "}
                  <strong className="text-luma-ivory font-medium">
                    {formatRupiah(sourceBalance)}
                  </strong>
                </span>
              )}
            </div>
            <CustomSelect
              value={fromPocketId}
              onChange={(val) => {
                setFromPocketId(val);
                setError(null);
              }}
              options={sourceOptions}
              disabled={loading}
              placeholder="Pilih kantong sumber"
            />
          </div>

          <div className="flex justify-center -my-1">
            <button
              type="button"
              onClick={handleSwap}
              disabled={loading}
              title="Tukar kantong asal dan tujuan"
              className="p-2 rounded-full bg-white/[0.04] border border-luma-smokeline hover:bg-white/[0.08] hover:border-white/[0.2] text-luma-smoke hover:text-luma-ivory transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
            >
              <ArrowDown className="w-3.5 h-3.5" aria-hidden="true" />
              <span className="sr-only">Tukar posisi kantong</span>
            </button>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-zinc-300">
                Ke Kantong (Tujuan)
              </label>
              {targetPocket && (
                <span className="text-xs text-luma-smoke tabular-nums">
                  Saldo:{" "}
                  <strong className="text-luma-ivory font-medium">
                    {formatRupiah(targetBalance)}
                  </strong>
                  {targetPocket.target_amount > 0 && (
                    <span className="text-zinc-500">
                      {" "}
                      / Target {formatRupiah(targetPocket.target_amount)}
                    </span>
                  )}
                </span>
              )}
            </div>
            <CustomSelect
              value={toPocketId}
              onChange={(val) => {
                setToPocketId(val);
                setError(null);
              }}
              options={targetOptions}
              disabled={loading}
              placeholder="Pilih kantong tujuan"
            />
          </div>
        </div>

        {/* Nominal with CurrencyInput */}
        <div className="space-y-1.5 pt-1">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-zinc-300">
              Nominal Pindah Dana
            </label>
            {sourceBalance > 0 && (
              <button
                type="button"
                onClick={handleSetMax}
                disabled={loading}
                className="text-xs text-luma-gold hover:underline cursor-pointer font-medium"
              >
                Pindah Semua ({formatRupiah(sourceBalance)})
              </button>
            )}
          </div>
          <CurrencyInput
            value={amount}
            onChange={(val) => {
              setAmount(val);
              setError(null);
            }}
            placeholder="0"
            required
            accent="amber"
            quickAmounts={[50000, 100000, 200000, 500000]}
          />
        </div>

        {/* Real-time Balance Preview */}
        {numericAmount > 0 && sourcePocket && targetPocket && fromPocketId !== toPocketId && (
          <div className="p-3.5 rounded-2xl bg-white/[0.03] border border-luma-smokeline space-y-2">
            <span className="text-xs text-zinc-400 font-medium block">
              Pratinjau Saldo Setelah Pindah:
            </span>
            <div className="grid grid-cols-2 gap-3 text-xs tabular-nums">
              <div className="bg-obsidian-panel/60 p-2.5 rounded-xl border border-white/[0.04]">
                <span className="text-zinc-400 block truncate">{sourcePocket.name}</span>
                <span
                  className={`font-semibold block mt-0.5 ${
                    sourceBalance - numericAmount < 0 ? "text-luma-coral" : "text-luma-ivory"
                  }`}
                >
                  {formatRupiah(sourceBalance - numericAmount)}
                </span>
              </div>
              <div className="bg-obsidian-panel/60 p-2.5 rounded-xl border border-white/[0.04]">
                <span className="text-zinc-400 block truncate">{targetPocket.name}</span>
                <span className="font-semibold text-luma-sage block mt-0.5">
                  {formatRupiah(targetBalance + numericAmount)}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Keterangan / Note (Optional) */}
        <div className="space-y-1.5">
          <label htmlFor="pocket-transfer-note" className="text-xs font-semibold text-zinc-300">
            Catatan / Keperluan (Opsional)
          </label>
          <input
            id="pocket-transfer-note"
            type="text"
            maxLength={255}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            disabled={loading}
            placeholder="Contoh: Alokasi iuran bulanan GYM"
            className="w-full bg-obsidian-panel border border-luma-smokeline rounded-2xl px-3.5 py-2.5 text-xs sm:text-sm text-luma-ivory placeholder-zinc-500 focus:outline-none focus:border-luma-gold transition"
          />
        </div>

        {/* Action Buttons */}
        <div className="flex justify-end gap-2.5 pt-4 border-t border-luma-smokeline">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2.5 rounded-full border border-luma-smokeline text-xs font-semibold text-luma-smoke hover:bg-white/[0.04] hover:text-luma-ivory transition cursor-pointer disabled:opacity-50 min-h-[44px]"
          >
            Batal
          </button>
          <button
            type="submit"
            disabled={loading || numericAmount <= 0 || fromPocketId === toPocketId}
            className="px-5 py-2.5 rounded-full bg-luma-ivory hover:bg-white text-luma-charcoal text-xs font-semibold transition active:scale-95 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed min-h-[44px] flex items-center gap-2"
          >
            {loading ? (
              <span>Memproses...</span>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4" aria-hidden="true" />
                <span>Pindah Saldo</span>
              </>
            )}
          </button>
        </div>
      </form>
    </CustomModal>
  );
}
