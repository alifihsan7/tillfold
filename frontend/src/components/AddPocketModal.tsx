import React, { useState } from "react";
import { Wallet } from "@/components/icons";
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
  const [targetAmount, setTargetAmount] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (saving) return;
    const allocation = Number(amount || 0);
    const target = Number(targetAmount || 0);
    if (!name.trim() || [allocation, target].some((value) => !Number.isSafeInteger(value) || value < 0 || value > 9_000_000_000_000_000)) {
      setError("Isi nama dan nominal kantong yang valid.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createAccountPocket({
        account_id: accountId, name: name.trim(), role, target_amount: target, allocation_amount: allocation,
      });
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
      title="Tambah kantong"
      subtitle={`Rekening induk: ${accountName}`}
      icon={<Wallet className="w-5 h-5 text-luma-smoke" />}
      accent="amber"
      maxWidth="form"
    >
      <form onSubmit={submit} className="space-y-4">
        {error && (
          <div role="alert" className="p-3 bg-luma-coral/10 border border-luma-coral/30 rounded-2xl text-luma-coral text-xs">
            {error}
          </div>
        )}
        <div className="space-y-1.5">
          <label htmlFor="pocket-name" className="text-xs font-semibold text-luma-secondary">
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
            className="w-full px-3.5 py-2.5 border border-luma-smokeline rounded-2xl bg-obsidian-panel text-luma-ivory text-xs sm:text-sm focus:outline-none focus:border-luma-ember transition"
          />
        </div>
        <fieldset disabled={saving} className="space-y-1.5">
          <legend className="text-xs font-semibold text-luma-secondary">Jenis kantong</legend>
          <CustomSelect
            value={role}
            onChange={setRole}
            disabled={saving}
            options={[
              { value: "operasional", label: "Operasional / umum" },
              { value: "tagihan", label: "Tagihan / langganan" },
              { value: "darurat", label: "Dana darurat" },
              { value: "tabungan", label: "Tabungan / impian" },
              { value: "investasi", label: "Investasi" },
            ]}
          />
        </fieldset>
        <fieldset disabled={saving} className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="pocket-allocation" className="text-xs font-semibold text-luma-secondary">Alokasi awal</label>
            <CurrencyInput id="pocket-allocation" value={amount} onChange={setAmount} placeholder="0" accent="amber" />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="pocket-target" className="text-xs font-semibold text-luma-secondary">Target (opsional)</label>
            <CurrencyInput id="pocket-target" value={targetAmount} onChange={setTargetAmount} placeholder="0" accent="amber" />
          </div>
        </fieldset>
        <div className="flex justify-end gap-2.5 pt-4 border-t border-luma-smokeline">
          <button
            type="button"
            disabled={saving}
            onClick={onClose}
            className="luma-action-secondary"
          >
            Batal
          </button>
          <button
            type="submit"
            disabled={saving}
            className="luma-action-primary"
          >
            {saving ? "Menyimpan..." : "Tambah kantong"}
          </button>
        </div>
      </form>
    </CustomModal>
  );
}
