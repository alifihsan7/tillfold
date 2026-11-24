import { todayWib } from "@/lib/transactionCalendar";
import { DateField } from "@/components/ui/DateField";
import React, { useState } from "react";
import { ArrowLeftRight, CheckCircle2 } from "@/components/icons";
import { CustomModal } from "@/components/ui/CustomModal";
import { CustomSelect } from "@/components/ui/CustomSelect";
import { CurrencyInput } from "@/components/ui/CurrencyInput";
import { authFetch } from "@/lib/api";

interface TransferModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  initialFromAccount?: string;
  accountOptions?: { value: string; label: string; color?: string; description?: string }[];
}

const ACCOUNT_OPTIONS = [
  { value: "Rekening Utama", label: "Rekening Utama (Operasional)", color: "bg-blue-500", description: "Pos belanja harian & saku" },
  { value: "Tabungan", label: "Tabungan (Simpanan)", color: "bg-emerald-500", description: "Pos tabungan & simpanan" },
  { value: "Investasi", label: "Investasi (Portofolio)", color: "bg-teal-500", description: "Portofolio tabungan investasi" },
  { value: "Uang Tunai (Cash)", label: "Uang Tunai (Cash)", color: "bg-amber-500", description: "Uang tunai fisik" },
];

export function TransferModal({ isOpen, onClose, onSuccess, accountOptions, initialFromAccount }: TransferModalProps) {
  const options = accountOptions && accountOptions.length > 0 ? accountOptions : ACCOUNT_OPTIONS;
  const initialFrom = options.find(({ value }) => value === initialFromAccount)?.value;
  const [fromAccount, setFromAccount] = useState(() => initialFrom ?? options[0]?.value ?? "");
  const [toAccount, setToAccount] = useState(() => initialFrom
    ? options.find(({ value }) => value !== initialFrom)?.value ?? ""
    : options[1]?.value ?? options[0]?.value ?? "");
  const [amount, setAmount] = useState<string>("");
  const [description, setDescription] = useState("");
  const [date, setDate] = useState(todayWib());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => { if (isOpen) setDate(todayWib()); }, [isOpen]);

  // Auto-sync initial accounts if options change
  React.useEffect(() => {
    if (options.length > 0) {
      if (!fromAccount || !options.some((o) => o.value === fromAccount)) {
        setFromAccount(options[0].value);
      }
      if (!toAccount || !options.some((o) => o.value === toAccount)) {
        setToAccount(options[1]?.value || options[0].value);
      }
    }
  }, [options, fromAccount, toAccount]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const numAmount = parseInt(amount.replace(/[^\d]/g, ""), 10);
    if (!numAmount || numAmount <= 0) {
      setError("Nominal transfer harus lebih besar dari Rp 0");
      return;
    }

    if (fromAccount === toAccount) {
      setError("Rekening asal dan tujuan tidak boleh sama");
      return;
    }

    setLoading(true);
    try {
      const res = await authFetch("/api/v1/transactions/transfer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          from_account: fromAccount,
          to_account: toAccount,
          amount: numAmount,
          description: description.trim() || `Transfer ${fromAccount} -> ${toAccount}`,
          date,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Gagal melakukan transfer");
      }

      onSuccess();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Terjadi kesalahan saat transfer");
    } finally {
      setLoading(false);
    }
  };

  return (
    <CustomModal
      isOpen={isOpen}
      onClose={onClose}
      title="Transfer antar rekening"
      subtitle="Pindahkan saldo antar-rekening Anda sendiri."
      icon={<ArrowLeftRight className="w-5 h-5" />}
      accent="cyan"
      maxWidth="md"
    >
      {error && (
        <div className="mb-4 p-3 rounded-2xl bg-coralFall/10 border border-coralFall/30 text-coralFall text-xs font-sans">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Rekening Asal & Tujuan */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 relative z-20">
          <div>
            <label className="block text-xs font-semibold text-luma-smoke mb-1.5">
              Dari rekening
            </label>
            <CustomSelect
              value={fromAccount}
              onChange={setFromAccount}
              options={options}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-luma-smoke mb-1.5">
              Ke rekening
            </label>
            <CustomSelect
              value={toAccount}
              onChange={setToAccount}
              options={options}
            />
          </div>
        </div>

        {/* Nominal with CurrencyInput */}
        <div>
          <label className="block text-xs font-semibold text-luma-smoke mb-1.5">
            Nominal
          </label>
          <CurrencyInput
            value={amount}
            onChange={setAmount}
            placeholder="0"
            required
            accent="cyan"
            quickAmounts={[50000, 100000, 200000, 500000]}
          />
        </div>

        {/* Catatan / Keterangan */}
        <div>
          <label className="block text-xs font-semibold text-luma-smoke mb-1.5">
            Catatan (opsional)
          </label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Contoh: Top up tabungan dingin"
            className="w-full bg-obsidian-panel border border-luma-smokeline rounded-2xl px-3.5 py-2.5 text-xs sm:text-sm text-white placeholder-luma-smoke focus:outline-none focus:border-cyanHub transition"
          />
        </div>

        {/* Tanggal */}
        <div>
          <label className="block text-xs font-semibold text-luma-smoke mb-1.5">
            Tanggal transaksi
          </label>
          <DateField label="Tanggal transaksi"
            value={date}
            onChange={(dateValue) => setDate(dateValue)}
          />
        </div>

        {/* Actions Footer */}
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
            <CheckCircle2 className="w-4 h-4" />
            <span>{loading ? "Memproses..." : "Transfer"}</span>
          </button>
        </div>
      </form>
    </CustomModal>
  );
}
