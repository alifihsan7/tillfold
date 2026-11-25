import React, { useState } from "react";
import { PlusCircle, Wallet, AlertTriangle } from "@/components/icons";
import { CustomModal } from "@/components/ui/CustomModal";
import { CustomSelect } from "@/components/ui/CustomSelect";
import { CurrencyInput } from "@/components/ui/CurrencyInput";
import { authFetch } from "@/lib/api";

interface AddAccountModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
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

export function AddAccountModal({ isOpen, onClose, onSuccess }: AddAccountModalProps) {
  const [name, setName] = useState("");
  const [type, setType] = useState("operasional");
  const [tag, setTag] = useState("");
  const [color, setColor] = useState("amberGold");
  const [initialBalance, setInitialBalance] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const nameTrim = name.trim();
    if (!nameTrim) {
      setError("Nama rekening wajib diisi");
      return;
    }

    const numBalance = initialBalance ? parseInt(initialBalance.replace(/[^\d]/g, ""), 10) : 0;

    setLoading(true);
    try {
      const res = await authFetch("/api/v1/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: nameTrim,
          type,
          tag: tag.trim() || undefined,
          color,
          initial_balance: numBalance,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Gagal menambahkan rekening baru");
      }

      // Reset form
      setName("");
      setTag("");
      setInitialBalance("");
      onSuccess();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Terjadi kesalahan saat menambahkan rekening");
    } finally {
      setLoading(false);
    }
  };

  return (
    <CustomModal
      isOpen={isOpen}
      maxWidth="form"
      onClose={onClose}
      title="Tambah rekening"
      subtitle="Tambahkan rekening bank, dompet digital, atau rekening investasi."
      icon={<Wallet className="w-5 h-5" />}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="bg-coralFall/10 border border-coralFall/30 rounded-xl p-3 text-xs sm:text-sm text-coralFall flex items-center gap-2">
            <AlertTriangle className="size-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-luma-smoke mb-1.5">
            Nama rekening / akun *
          </label>
          <input
            type="text"
            required
            placeholder="Misal: BCA, SeaBank, GoPay, OVO"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full bg-obsidian-panel border border-luma-smokeline rounded-2xl px-3.5 py-2.5 text-xs sm:text-sm text-white focus:outline-none focus:border-luma-ember transition"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 relative z-30">
          <div>
            <label className="block text-xs font-semibold text-luma-smoke mb-1.5">
              Tipe rekening
            </label>
            <CustomSelect
              value={type}
              onChange={setType}
              options={TYPE_OPTIONS}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-luma-smoke mb-1.5">
              Warna
            </label>
            <CustomSelect
              value={color}
              onChange={setColor}
              options={COLOR_OPTIONS}
            />
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="block text-xs font-semibold text-luma-smoke mb-1.5">
              Label singkat
            </label>
            <input
              type="text"
              placeholder="Misal: Saku Tambahan, Tabungan Pribadi, Rekening Bisnis"
              value={tag}
              onChange={(e) => setTag(e.target.value)}
              className="w-full bg-obsidian-panel border border-luma-smokeline rounded-2xl px-3.5 py-2.5 text-xs sm:text-sm text-white focus:outline-none focus:border-luma-ember transition"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-luma-smoke mb-1.5">
              Saldo awal (opsional)
            </label>
            <CurrencyInput
              value={initialBalance}
              onChange={setInitialBalance}
              placeholder="0"
            />
            <p className="text-xs text-luma-smoke mt-1">
              Jika diisi lebih dari Rp 0, sistem otomatis mencatat transaksi pemasukan &ldquo;Saldo awal&rdquo; di riwayat Transaksi.
            </p>
          </div>
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
                <PlusCircle className="w-4 h-4" />
                <span>Simpan rekening</span>
              </>
            )}
          </button>
        </div>
      </form>
    </CustomModal>
  );
}
