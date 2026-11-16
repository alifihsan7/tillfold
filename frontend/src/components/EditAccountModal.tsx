import React, { useState, useEffect } from "react";
import { Wallet, Check } from "lucide-react";
import { CustomModal } from "@/components/ui/CustomModal";
import { CustomSelect } from "@/components/ui/CustomSelect";
import { authFetch } from "@/lib/api";
import { AccountItem } from "@/components/AccountGrid";

interface EditAccountModalProps {
  account: AccountItem | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (updatedAccount?: AccountItem) => void;
}

const TYPE_OPTIONS = [
  { value: "operasional", label: "Operasional / saku harian", description: "Pos belanja konsumtif & kebutuhan aktif" },
  { value: "tagihan", label: "Tagihan & autodebet", description: "Listrik, wifi, kuota, gym, langganan berkala" },
  { value: "gajian", label: "Gajian / pemasukan utama", description: "Rekening penampung payroll / uang saku" },
  { value: "tabungan", label: "Tabungan / dana dingin", description: "Simpanan jangka menengah" },
  { value: "investasi", label: "Investasi portofolio", description: "Reksadana, saham, emas" },
  { value: "darurat", label: "Dana darurat", description: "Cadangan proteksi darurat" },
  { value: "ewallet", label: "E-wallet / dompet digital", description: "GoPay, OVO, ShopeePay, DANA" },
];

const COLOR_OPTIONS = [
  { value: "amberGold", label: "Amber Gold", color: "bg-amber-500", description: "Aksen emas elegan" },
  { value: "cyanHub", label: "Cyan", color: "bg-cyan-500", description: "Biru cerah" },
  { value: "teal", label: "Teal / Hijau Mint", color: "bg-teal-500", description: "Hijau sejuk" },
  { value: "purpleLock", label: "Purple", color: "bg-purple-500", description: "Ungu elegan" },
  { value: "blue", label: "Royal Blue", color: "bg-blue-600", description: "Biru perbankan" },
  { value: "coralFall", label: "Coral / Merah Muda", color: "bg-rose-500", description: "Aksen tegas" },
];

export function EditAccountModal({ account, isOpen, onClose, onSuccess }: EditAccountModalProps) {
  const [name, setName] = useState("");
  const [type, setType] = useState("operasional");
  const [tag, setTag] = useState("");
  const [color, setColor] = useState("amberGold");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (account) {
      setName(account.name || "");
      setType(account.type || "operasional");
      setTag(account.tag || "");
      setColor(account.color || "amberGold");
      setError(null);
    }
  }, [account, isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!account?.id) return;
    setError(null);

    const nameTrim = name.trim();
    if (!nameTrim) {
      setError("Nama rekening tidak boleh kosong");
      return;
    }

    setLoading(true);
    try {
      const res = await authFetch(`/api/v1/accounts/${account.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: nameTrim,
          type,
          tag: tag.trim() || undefined,
          color,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Gagal memperbarui data rekening");
      }

      const updatedAccount: AccountItem = await res.json();
      onSuccess(updatedAccount);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Terjadi kesalahan saat menyimpan rekening");
    } finally {
      setLoading(false);
    }
  };

  if (!account) return null;

  return (
    <CustomModal
      isOpen={isOpen}
      onClose={onClose}
      title="Ubah rekening"
      subtitle={`Perbarui parameter rekening ${account.name}`}
      icon={<Wallet className="w-5 h-5 text-luma-smoke" />}
      accent="amber"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="bg-coralFall/10 border border-coralFall/30 rounded-xl p-3 text-xs sm:text-sm text-coralFall flex items-center gap-2">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
            Nama rekening / akun *
          </label>
          <input
            type="text"
            required
            placeholder="Misal: BCA, SeaBank, Rekening Utama"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full bg-obsidian-panel border border-luma-smokeline rounded-2xl px-3.5 py-2.5 text-xs sm:text-sm text-white focus:outline-none focus:border-luma-ember transition"
          />
          {name.trim() !== account.name && (
            <p className="text-xs text-amberGold/80 mt-1">
              Catatan: Mengubah nama rekening akan otomatis memperbarui seluruh riwayat transaksi dan alokasi yang terkait.
            </p>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 relative z-30">
          <div>
            <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
              Tipe rekening
            </label>
            <CustomSelect
              value={type}
              onChange={setType}
              options={TYPE_OPTIONS}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
              Warna
            </label>
            <CustomSelect
              value={color}
              onChange={setColor}
              options={COLOR_OPTIONS}
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
            Label singkat
          </label>
          <input
            type="text"
            placeholder="Misal: Saku Belanja, Tabungan Dingin, Cadangan Pokok"
            value={tag}
            onChange={(e) => setTag(e.target.value)}
            className="w-full bg-obsidian-panel border border-luma-smokeline rounded-2xl px-3.5 py-2.5 text-xs sm:text-sm text-white focus:outline-none focus:border-luma-ember transition"
          />
        </div>

        <div className="pt-3 flex justify-end gap-3 border-t border-luma-smokeline mt-5">
          <button
            type="button"
            onClick={onClose}
            className="luma-action-secondary"
          >
            Batal
          </button>
          <button
            type="submit"
            disabled={loading}
            className="luma-action-primary"
          >
            {loading ? (
              <span>Menyimpan...</span>
            ) : (
              <>
                <Check className="w-4 h-4 stroke-[2.5]" />
                <span>Simpan perubahan</span>
              </>
            )}
          </button>
        </div>
      </form>
    </CustomModal>
  );
}
