import React, { useEffect, useState } from "react";
import { CheckCircle2, Landmark } from "lucide-react";
import { CustomModal } from "@/components/ui/CustomModal";
import { CurrencyInput } from "@/components/ui/CurrencyInput";
import {
  PocketItem,
  PocketsSummaryResponse,
  updatePockets,
} from "@/lib/api";

export type JagoPocketItem = PocketItem;
export type JagoPocketsSummaryResponse = PocketsSummaryResponse;
export const updateJagoPockets = updatePockets;

export interface EditPocketsModalProps {
  accountId?: number;
  accountName?: string;
  isOpen: boolean;
  pockets: PocketItem[];
  formatRupiah: (val: number) => string;
  onClose: () => void;
  onSuccess: (updated: PocketsSummaryResponse) => void;
}

export type EditJagoPocketsModalProps = EditPocketsModalProps;

export function EditPocketsModal({
  accountId,
  accountName,
  isOpen,
  pockets,
  formatRupiah,
  onClose,
  onSuccess,
}: EditPocketsModalProps) {
  const [targets, setTargets] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      const initial: Record<string, string> = {};
      pockets.forEach((p) => {
        initial[p.slug] = (p.target_amount ?? 0).toString();
      });
      setTargets(initial);
      setError(null);
    }
  }, [isOpen, pockets]);

  const totalDraft = pockets.reduce((sum, p) => {
    const raw = (targets[p.slug] ?? "").replace(/[^\d]/g, "");
    return sum + (raw ? parseInt(raw, 10) : 0);
  }, 0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (pockets.length === 0) {
      setError("Belum ada sub-kantong yang dapat diperbarui");
      return;
    }

    const payload = pockets
      .filter((p) => !p.subscription_id)
      .map((p) => {
        const raw = (targets[p.slug] ?? "").replace(/[^\d]/g, "");
        const amount = raw ? parseInt(raw, 10) : 0;
        if (Number.isNaN(amount) || amount < 0) {
          throw new Error(`Nominal target ${p.name} tidak valid`);
        }
        return {
          id: p.id,
          slug: p.slug,
          target_amount: amount,
        };
      });

    setLoading(true);
    try {
      const updated = await updatePockets(payload, accountId);
      onSuccess(updated);
      onClose();
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "Terjadi kesalahan saat memperbarui target kantong";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <CustomModal
      isOpen={isOpen}
      onClose={onClose}
      title="Atur Target Kantong Rekening"
      subtitle={
        accountName
          ? `Atur target komitmen sinking fund dalam ${accountName}`
          : "Perbarui target komitmen kantong rekening"
      }
      icon={<Landmark className="w-5 h-5 text-luma-gold" />}
      accent="amber"
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-3 bg-luma-coral/10 border border-luma-coral/30 rounded-2xl text-luma-coral text-xs">
            {error}
          </div>
        )}

        <div className="space-y-3">
          {pockets.map((pocket) => (
            <fieldset
              disabled={!!pocket.subscription_id || loading}
              key={pocket.slug}
              className="bg-obsidian-panel border border-luma-smokeline rounded-2xl p-4 space-y-2.5"
            >
              <div className="flex items-center justify-between gap-2">
                <label
                  htmlFor={`pocket-target-${pocket.slug}`}
                  className="text-xs font-semibold text-zinc-300"
                >
                  {pocket.name}
                </label>
                <span className="text-xs font-sans text-luma-smoke tabular-nums">
                  Saldo kas:{" "}
                  <strong className="text-luma-ivory font-medium">
                    {formatRupiah(pocket.balance ?? pocket.remaining_amount ?? 0)}
                  </strong>
                </span>
              </div>
              <CurrencyInput
                id={`pocket-target-${pocket.slug}`}
                value={targets[pocket.slug] ?? ""}
                onChange={(raw) =>
                  setTargets((prev) => ({ ...prev, [pocket.slug]: raw }))
                }
                placeholder="0"
                accent="amber"
              />
              {pocket.subscription_id ? (
                <p className="text-xs text-luma-smoke">
                  Target sinkron dengan tagihan {pocket.subscription_name || "terhubung"}. Lepaskan hubungan tagihan untuk mengaturnya manual.
                </p>
              ) : pocket.slug === "utama" ? (
                <p className="text-xs text-luma-smoke">
                  Kantong Utama adalah kas bebas / unallocated pool. Target dapat diisi 0.
                </p>
              ) : null}
            </fieldset>
          ))}
        </div>

        <div className="flex items-center justify-between gap-2 px-1 text-xs font-sans">
          <span className="text-zinc-400">Total target komitmen</span>
          <span className="font-semibold text-luma-ivory tabular-nums">
            {formatRupiah(totalDraft)}
          </span>
        </div>

        <div className="flex justify-end gap-3 pt-3 border-t border-luma-smokeline mt-5">
          <button
            type="button"
            onClick={onClose}
            className="min-h-[44px] px-5 py-2.5 rounded-full text-xs sm:text-sm font-medium text-luma-smoke hover:text-luma-ivory border border-luma-smokeline hover:border-white/[0.16] transition cursor-pointer"
          >
            Batal
          </button>
          <button
            type="submit"
            disabled={loading || pockets.every((pocket) => !!pocket.subscription_id)}
            className="min-h-[44px] px-6 py-2.5 rounded-full text-xs sm:text-sm bg-luma-ivory text-luma-charcoal font-semibold hover:bg-white transition flex items-center gap-2 shadow-sm disabled:opacity-50 cursor-pointer active:scale-95"
          >
            {loading ? (
              "Menyimpan..."
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4 stroke-[2.5]" aria-hidden="true" />
                Simpan Target
              </>
            )}
          </button>
        </div>
      </form>
    </CustomModal>
  );
}

export const EditJagoPocketsModal = EditPocketsModal;
export const EditOperationalPocketsModal = EditPocketsModal;
export default EditPocketsModal;
