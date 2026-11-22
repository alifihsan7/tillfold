"use client";

import { DateField } from "@/components/ui/DateField";
import React, { useState, useEffect } from "react";
import { Calendar, Clock, Sparkles } from "lucide-react";
import { CustomModal } from "./ui/CustomModal";
import { CurrencyInput } from "./ui/CurrencyInput";
import { CustomSelect, SelectOption } from "./ui/CustomSelect";
import { SubscriptionItem } from "./SubscriptionsView";
import { authFetch } from "@/lib/api";

interface EditSubscriptionModalProps {
  isOpen: boolean;
  onClose: () => void;
  subscription: SubscriptionItem | null;
  onSuccess: () => void;
  accountOptions: SelectOption[];
  categoryOptions: SelectOption[];
}

export function EditSubscriptionModal({
  isOpen,
  onClose,
  subscription,
  onSuccess,
  accountOptions,
  categoryOptions,
}: EditSubscriptionModalProps) {
  const [name, setName] = useState("");
  const [amount, setAmount] = useState<string>("");
  const [category, setCategory] = useState("Layanan Digital");
  const [account, setAccount] = useState("");
  const [billingType, setBillingType] = useState<"fixed_day" | "exact_date" | "yearly">("fixed_day");
  const [billingDay, setBillingDay] = useState("1");
  const [exactDueDate, setExactDueDate] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (subscription) {
      setName(subscription.name);
      setAmount(subscription.amount.toString());
      setCategory(subscription.category);
      setAccount(subscription.account || "");
      setBillingType(subscription.billing_type === "exact_date" ? "exact_date" : subscription.billing_cycle === "yearly" ? "yearly" : "fixed_day");
      setBillingDay(subscription.billing_day ? subscription.billing_day.toString() : "1");
      setExactDueDate(subscription.exact_due_date || subscription.next_billing_date || "");
      setNotes(subscription.notes || "");
      setError("");
    }
  }, [subscription]);

  const handleAddDays = (days: number) => {
    const base = exactDueDate ? new Date(exactDueDate) : new Date();
    base.setDate(base.getDate() + days);
    setExactDueDate(base.toISOString().split("T")[0]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!subscription) return;

    const numAmount = parseInt(amount.replace(/\D/g, ""), 10);
    if (!numAmount || !name.trim()) {
      setError("Nama layanan dan nominal wajib diisi.");
      return;
    }

    if (billingType !== "fixed_day" && !exactDueDate) {
      setError("Pilih tanggal jatuh tempo.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const payload: Record<string, unknown> = {
        name: name.trim(),
        amount: numAmount,
        category,
        account,
        billing_type: billingType === "yearly" ? "fixed_day" : billingType,
        billing_cycle: billingType === "yearly" || (billingType === "exact_date" && subscription.billing_type === "exact_date" && subscription.billing_cycle === "yearly") ? "yearly" : "monthly",
        notes: notes.trim() || null,
      };

      if (billingType !== "fixed_day") {
        payload.exact_due_date = exactDueDate;
        // Also sync billing_day to match day of month
        const parsed = new Date(exactDueDate);
        if (!isNaN(parsed.getDate())) {
          payload.billing_day = parsed.getDate();
        }
      } else {
        payload.billing_day = parseInt(billingDay, 10) || 1;
        payload.exact_due_date = null;
      }

      const res = await authFetch(`/api/v1/subscriptions/${subscription.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Gagal memperbarui tagihan");
      }

      onSuccess();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Terjadi kesalahan saat menyimpan");
    } finally {
      setLoading(false);
    }
  };

  if (!subscription) return null;

  return (
    <CustomModal
      isOpen={isOpen}
      onClose={onClose}
      title="Ubah tagihan"
      subtitle={`Perbarui parameter siklus dan tanggal jatuh tempo untuk ${subscription.name}`}
      accent="amber"
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4 text-left">
        {error && (
          <div className="p-3 bg-coralFall/10 border border-coralFall/30 rounded-2xl text-coralFall text-xs font-sans">
            {error}
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-luma-smoke mb-1.5">
            Nama tagihan / layanan
          </label>
          <input
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full bg-obsidian-panel border border-luma-smokeline rounded-2xl px-3.5 py-2.5 text-xs sm:text-sm text-white focus:outline-none focus:border-luma-ember transition"
          />
        </div>

        {/* Pilihan Mode Siklus */}
        <div>
          <label className="block text-xs font-semibold text-luma-smoke mb-2">
            Metode perhitungan jatuh tempo
          </label>
          <div className="grid grid-cols-2 gap-2 p-1 bg-obsidian-panel rounded-2xl border border-luma-smokeline">
            <button
              type="button"
              aria-pressed={billingType === "fixed_day"}
              onClick={() => setBillingType("fixed_day")}
              className={`py-2 px-2 text-xs font-semibold rounded-xl transition flex items-center justify-center gap-1.5 cursor-pointer ${
                billingType === "fixed_day"
                  ? "ui-selected"
                  : "text-luma-smoke hover:text-white"
              }`}
            >
              <Clock className="w-3.5 h-3.5 shrink-0" />
              <span>Tanggal rutin</span>
            </button>
            <button
              type="button"
              aria-pressed={billingType === "exact_date"}
              onClick={() => {
                setBillingType("exact_date");
                if (!exactDueDate) {
                  const d = new Date();
                  d.setDate(d.getDate() + 30);
                  setExactDueDate(d.toISOString().split("T")[0]);
                }
              }}
              className={`py-2 px-2 text-xs font-semibold rounded-xl transition flex items-center justify-center gap-1.5 cursor-pointer ${
                billingType === "exact_date"
                  ? "ui-selected"
                  : "text-luma-smoke hover:text-white"
              }`}
            >
              <Calendar className="w-3.5 h-3.5 shrink-0" />
              <span>Tanggal tertentu</span>
            </button>
            <button
              type="button"
              aria-pressed={billingType === "yearly"}
              onClick={() => setBillingType("yearly")}
              className={`col-span-2 rounded-xl px-2 py-2 text-xs font-semibold ${billingType === "yearly" ? "ui-selected" : "text-luma-smoke hover:text-luma-ivory"}`}
            >
              Tahunan
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-luma-smoke mb-1.5">
              Nominal / periode
            </label>
            <CurrencyInput
              value={amount}
              onChange={setAmount}
              placeholder="0"
              required
              accent="amber"
              quickAmounts={[50000, 100000, 150000, 225000]}
            />
          </div>

          {billingType === "fixed_day" ? (
            <div>
              <label className="block text-xs font-semibold text-luma-smoke mb-1.5">
                Jatuh tempo (tgl 1-31)
              </label>
              <input
                type="number"
                required
                min={1}
                max={31}
                value={billingDay}
                onChange={(e) => setBillingDay(e.target.value)}
                className="w-full bg-obsidian-panel border border-luma-smokeline rounded-2xl px-3.5 py-2.5 text-xs sm:text-sm text-white font-sans focus:outline-none focus:border-luma-ember transition"
              />
            </div>
          ) : (
            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="block text-xs font-semibold text-luma-smoke ">
                  {billingType === "yearly" ? "Tanggal tagihan tahunan" : "Tanggal jatuh tempo"}
                </label>
                <div className="flex gap-1">
                  <button
                    type="button"
                    onClick={() => handleAddDays(30)}
                    className="ai7-amount-preset"
                  >
                    <Sparkles className="w-2.5 h-2.5" />
                    +30 Hari
                  </button>
                </div>
              </div>
              <DateField label="Tanggal jatuh tempo"
                required
                value={exactDueDate}
                onChange={(dateValue) => setExactDueDate(dateValue)}
              />
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 relative z-20">
          <div>
            <label className="block text-xs font-semibold text-luma-smoke mb-1.5">
              Kategori
            </label>
            <CustomSelect
              value={category}
              onChange={setCategory}
              options={categoryOptions}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-luma-smoke mb-1.5">
              Rekening pembayaran
            </label>
            <CustomSelect
              value={account}
              onChange={setAccount}
              options={account && !accountOptions.some((option) => option.value === account)
                ? [...accountOptions, { value: account, label: account }]
                : accountOptions}
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-luma-smoke mb-1.5">
            Catatan tambahan (opsional)
          </label>
          <input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Contoh: Paket bulanan"
            className="w-full bg-obsidian-panel border border-luma-smokeline rounded-2xl px-3.5 py-2.5 text-xs sm:text-sm text-white focus:outline-none focus:border-luma-ember transition"
          />
        </div>

        <div className="pt-3 flex gap-3 border-t border-luma-smokeline">
          <button
            type="button"
            onClick={onClose}
            className="luma-action-secondary flex-1"
          >
            Batal
          </button>
          <button
            type="submit"
            disabled={loading}
            className="luma-action-primary flex-1"
          >
            {loading ? "Menyimpan..." : "Simpan perubahan"}
          </button>
        </div>
      </form>
    </CustomModal>
  );
}
