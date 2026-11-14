import React, { useState } from "react";
import { Wallet } from "lucide-react";
import { CustomModal } from "./ui/CustomModal";
import { CustomSelect } from "./ui/CustomSelect";
import { CurrencyInput } from "./ui/CurrencyInput";
import { createAccountPocket } from "@/lib/api";

interface AddPocketModalProps {
  accountId: number;
  accountName: string;
  onClose: () => void;
  onCreated: () => void;
}

export function AddPocketModal({ accountId, accountName, onClose, onCreated }: AddPocketModalProps) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("operasional");
  const [amount, setAmount] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (saving) return;
    const target = Number(amount || 0);
    if (!name.trim() || !Number.isSafeInteger(target) || target < 0 || target > 9000000000000000) {
      setError("Isi nama dan target komitmen yang valid.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createAccountPocket({ account_id: accountId, name: name.trim(), role, target_amount: target });
      onCreated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menambah kantong.");
      setSaving(false);
    }
  };

  return (
    <CustomModal
      isOpen
      onClose={() => {
        if (!saving) onClose();
      }}
      title="Tambah Kantong Sub-Akun"
      subtitle={`Rekening induk: ${accountName}`}
      icon={<Wallet className="w-5 h-5 text-luma-gold" />}
      accent="amber"
      maxWidth="md"
    >
      <form onSubmit={submit} className="space-y-4">
        {error && (
          <div role="alert" className="p-3 bg-luma-coral/10 border border-luma-coral/30 rounded-2xl text-luma-coral text-xs">
            {error}
          </div>
        )}
        <div className="space-y-1.5">
          <label htmlFor="pocket-name" className="text-xs font-semibold text-zinc-300">
            Nama kantong
          </label>
          <input
            id="pocket-name"
            required
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={saving}
            placeholder="Contoh: Tabungan Liburan, Biaya Sekolah"
            className="w-full px-3.5 py-2.5 border border-luma-smokeline rounded-2xl bg-obsidian-panel text-luma-ivory text-xs sm:text-sm focus:outline-none focus:border-luma-gold transition"
          />
        </div>
        <fieldset disabled={saving} className="space-y-1.5">
          <legend className="text-xs font-semibold text-zinc-300">Jenis kantong</legend>
          <CustomSelect
            value={role}
            onChange={setRole}
            disabled={saving}
            options={[
              { value: "operasional", label: "Operasional / Umum" },
              { value: "tagihan", label: "Tagihan / Langganan" },
              { value: "darurat", label: "Dana Darurat" },
              { value: "tabungan", label: "Tabungan / Impian" },
              { value: "investasi", label: "Investasi" },
            ]}
          />
        </fieldset>
        <fieldset disabled={saving} className="space-y-1.5">
          <legend className="text-xs font-semibold text-zinc-300">Target Komitmen (Sinking Fund)</legend>
          <CurrencyInput value={amount} onChange={setAmount} placeholder="0" accent="amber" />
          <p className="text-xs text-luma-smoke mt-1.5">
            Target komitmen untuk kantong ini. Saldo kas riil dapat dipindahkan dari Kantong Utama kapan saja melalui tombol Pindah Saldo.
          </p>
        </fieldset>
        <div className="flex justify-end gap-2.5 pt-4 border-t border-luma-smokeline">
          <button
            type="button"
            disabled={saving}
            onClick={onClose}
            className="min-h-[44px] px-5 py-2.5 rounded-full border border-luma-smokeline text-xs font-semibold text-luma-smoke hover:bg-white/[0.04] hover:text-luma-ivory transition cursor-pointer"
          >
            Batal
          </button>
          <button
            type="submit"
            disabled={saving}
            className="min-h-[44px] px-6 py-2.5 rounded-full bg-luma-ivory hover:bg-white text-luma-charcoal text-xs font-semibold transition active:scale-95 cursor-pointer disabled:opacity-50"
          >
            {saving ? "Menyimpan..." : "Tambah Kantong"}
          </button>
        </div>
      </form>
    </CustomModal>
  );
}
