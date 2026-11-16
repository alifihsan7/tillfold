"use client";

import { DateField } from "@/components/ui/DateField";
import { SegmentedControl } from "./ui/controls";
import React, { useState, useEffect } from "react";
import { CustomModal } from "./ui/CustomModal";
import { CurrencyInput } from "./ui/CurrencyInput";
import { CustomSelect, SelectOption } from "./ui/CustomSelect";
import { Transaction } from "./TransactionTable";
import { authFetch } from "@/lib/api";

interface EditTransactionModalProps {
  isOpen: boolean;
  onClose: () => void;
  transaction: Transaction | null;
  onSuccess: () => void;
  accountOptions: SelectOption[];
  categoryOptions: SelectOption[];
}

export function EditTransactionModal({
  isOpen,
  onClose,
  transaction,
  onSuccess,
  accountOptions,
  categoryOptions,
}: EditTransactionModalProps) {
  const [type, setType] = useState<Transaction["type"]>("expense");
  const isTransfer = type === "transfer_in" || type === "transfer_out";
  const [amount, setAmount] = useState<string>("");
  const [account, setAccount] = useState<string>("");
  const [category, setCategory] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [date, setDate] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  const effectiveCategoryOptions = React.useMemo(() => {
    if (category && !categoryOptions.some((opt) => opt.value === category)) {
      return [{ value: category, label: category }, ...categoryOptions];
    }
    return categoryOptions;
  }, [category, categoryOptions]);

  useEffect(() => {
    if (transaction) {
      setType(transaction.type);
      setAmount(transaction.amount.toString());
      setAccount(transaction.account);
      setCategory(transaction.category);
      setDescription(transaction.description);
      setDate(transaction.date);
      setError("");
    }
  }, [transaction]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!transaction) return;
    const numAmount = parseInt(amount.replace(/\D/g, ""), 10);
    if (!numAmount || !description.trim()) {
      setError("Nominal dan keterangan wajib diisi.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const res = await authFetch(`/api/v1/transactions/${transaction.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type,
          amount: numAmount,
          account,
          category,
          description: description.trim(),
          date,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(typeof data?.detail === "string" ? data.detail : "Gagal memperbarui transaksi");
      }

      onSuccess();
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Terjadi kesalahan";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (!transaction) return null;

  return (
    <CustomModal
      isOpen={isOpen}
      onClose={onClose}
      title="Ubah transaksi"
      subtitle={`Ubah data transaksi #${transaction.id}`}
      accent={type === "income" ? "mint" : "coral"}
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4 text-left">
        {error && (
          <div className="p-3 bg-coralFall/10 border border-coralFall/30 rounded-2xl text-coralFall text-xs">
            {error}
          </div>
        )}

        <div>
          <label className="block text-xs font-sans text-zinc-400 mb-2">
            Tipe transaksi
          </label>
          {isTransfer ? <p className="text-sm text-luma-smoke">{type === "transfer_in" ? "Transfer masuk" : "Transfer keluar"}. Nominal dan tanggal akan diperbarui pada kedua sisi transfer.</p> : <SegmentedControl fill label="Jenis transaksi" value={type === "income" ? "income" : "expense"} onChange={setType} options={[
            { value: "expense", label: "Pengeluaran", tone: "expense" },
            { value: "income", label: "Pemasukan", tone: "income" },
          ]} />}
        </div>

        <div>
          <label className="block text-xs font-sans text-zinc-400 mb-1.5">
            Nominal transaksi
          </label>
          <CurrencyInput
            value={amount}
            onChange={setAmount}
            placeholder="0"
            required
            accent={type === "income" ? "mint" : "coral"}
          />
        </div>

        <div>
          <label className="block text-xs font-sans text-zinc-400 mb-1.5">
            Tanggal transaksi
          </label>
          <DateField label="Tanggal transaksi"
            value={date}
            onChange={(dateValue) => setDate(dateValue)}
            required
          />
        </div>

        <div>
          <label className="block text-xs font-sans text-zinc-400 mb-1.5">
            Rekening
          </label>
          <CustomSelect
            value={account}
            onChange={setAccount}
            options={accountOptions}
          />
        </div>

        <div>
          <label className="block text-xs font-sans text-zinc-400 mb-1.5">
            Kategori
          </label>
          <CustomSelect
            value={category}
            onChange={setCategory}
            options={effectiveCategoryOptions}
            disabled={isTransfer}
          />
        </div>

        <div>
          <label className="block text-xs font-sans text-zinc-400 mb-1.5">
            Keterangan
          </label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Contoh: Makan siang, bayar wifi..."
            required
            className="w-full bg-obsidian-panel border border-luma-smokeline rounded-2xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-luma-ember transition"
          />
        </div>

        <div className="ui-dialog-actions">
          <button type="button" onClick={onClose} className="luma-action-secondary">
            Batal
          </button>
          <button type="submit" disabled={loading} className="luma-action-primary disabled:cursor-not-allowed">
            {loading ? "Menyimpan…" : "Simpan perubahan"}
          </button>
        </div>
      </form>
    </CustomModal>
  );
}
