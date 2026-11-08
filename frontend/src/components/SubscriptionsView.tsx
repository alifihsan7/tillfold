import React, { useState } from "react";
import { BillPaymentModal } from "./BillPaymentModal";
import { Trash2, Calendar, Edit2, Clock, Pause, Play } from "lucide-react";
import { Skeleton } from "./ui/Skeleton";

export interface SubscriptionItem {
  id: number;
  name: string;
  amount: number;
  category: string;
  account: string;
  billing_cycle: string;
  billing_day: number;
  billing_type?: "fixed_day" | "exact_date";
  exact_due_date?: string;
  is_active: boolean;
  notes?: string;
  days_until_due?: number;
  next_billing_date?: string;
  payment_period?: string | null;
  payment_due_date?: string | null;
  is_paid?: boolean;
  paid_date?: string | null;
  payment_transaction_id?: number | null;
  paid_amount?: number | null;
}

export interface SubscriptionsData {
  total_monthly_commitment: number;
  active_count: number;
  upcoming_this_week: number;
  items: SubscriptionItem[];
}

interface SubscriptionsViewProps {
  subsData: SubscriptionsData;
  formatRupiah: (val: number) => string;
  onToggleActive: (sub: SubscriptionItem) => void;
  onDelete: (id: number) => void;
  onEdit?: (sub: SubscriptionItem) => void;
  loading?: boolean;
  onPaymentChanged?: () => void;
}

export function SubscriptionsView({
  subsData,
  formatRupiah,
  onToggleActive,
  onDelete,
  onEdit,
  loading,
  onPaymentChanged,
}: SubscriptionsViewProps) {
  const [payId, setPayId] = useState<number | null>(null);
  const currentDate = new Date();
  const today = currentDate.getFullYear() + "-" + String(currentDate.getMonth() + 1).padStart(2, "0") + "-" + String(currentDate.getDate()).padStart(2, "0");
  return (
    <div className="ai7-subscriptions space-y-8">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4 border-y border-luma-smokeline py-5 sm:grid-cols-3" aria-label="Ringkasan tagihan" aria-busy={loading}>
        {[
          { label: "Komitmen bulanan", value: formatRupiah(subsData.total_monthly_commitment), color: "text-luma-ivory", className: "col-span-2 sm:col-span-1" },
          { label: "Tagihan aktif", value: String(subsData.active_count), color: "text-luma-ivory", className: "" },
          { label: "Jatuh tempo pekan ini", value: String(subsData.upcoming_this_week), color: subsData.upcoming_this_week > 0 ? "text-luma-gold" : "text-luma-ivory", className: "" },
        ].map((item) => <div key={item.label} className={`min-w-0 space-y-2 ${item.className}`}>
          <dt className="text-xs text-luma-smoke">{item.label}</dt>
          <dd className={`ai7-type-metric ${item.color}`}>{loading ? <Skeleton className="h-8 w-24" /> : item.value}</dd>
        </div>)}
      </dl>

      {/* Subscriptions Grid Cards */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
          <div>
            <h3 className="ai7-type-card text-white">
              Daftar tagihan
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              {subsData.items.length} tagihan terdaftar
            </p>
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="bg-obsidian-card border border-luma-smokeline rounded-2xl p-5 space-y-4 shadow-sm"
              >
                <div className="flex justify-between items-start">
                  <div className="space-y-1.5">
                    <Skeleton className="w-28 h-5 rounded-full" />
                    <Skeleton className="w-16 h-3 rounded-full" />
                  </div>
                  <Skeleton className="w-12 h-5 rounded-full" />
                </div>
                <Skeleton className="w-36 h-6 rounded-full" />
                <div className="pt-2 border-t border-luma-smokeline flex justify-between">
                  <Skeleton className="w-24 h-4 rounded-full" />
                  <Skeleton className="w-16 h-4 rounded-full" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {subsData.items.map((sub) => {
            const isExact = sub.billing_type === "exact_date";
            const isYearly = sub.billing_cycle === "yearly";
            const missingDate = isYearly && !sub.next_billing_date;
            const days = sub.days_until_due ?? 99;
            const paymentOverdue = !sub.is_paid && sub.is_active && Boolean(sub.payment_due_date && sub.payment_due_date < today);
            const isExpired = paymentOverdue || (!sub.is_paid && isExact && days < 0);
            const isToday = !sub.is_paid && days === 0;
            const isUpcoming = !sub.is_paid && days <= 3 && days >= 0;

            return (
              <div
                key={sub.id}
                className="bg-obsidian-card border border-luma-smokeline rounded-2xl p-5 space-y-4"
              >
                <div className="flex flex-wrap justify-between items-start gap-3">
                  <div className="min-w-[min(100%,180px)] flex-1">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-base font-semibold text-white break-words">
                        {sub.name}
                      </span>
                    </div>
                    <span className="text-xs text-zinc-400 font-sans truncate block mt-0.5">{sub.category}</span>
                  </div>
                  <span
                    className={`text-xs font-sans px-2.5 py-0.5 rounded-full border shrink-0 whitespace-nowrap ${
                      sub.is_paid ? "bg-mintRise/10 border-mintRise/30 text-mintRise" : !sub.is_active
                        ? "bg-white/[0.04] border-luma-smokeline text-zinc-400"
                        : isExpired
                        ? "bg-coralFall/20 border-coralFall/40 text-coralFall font-semibold"
                        : isToday
                        ? "bg-amberGold/20 border-amberGold/40 text-amberGold font-semibold"
                        : isUpcoming
                        ? "bg-amberGold/20 border-amberGold/40 text-amberGold font-semibold"
                        : "bg-white/[0.04] border-luma-smokeline text-luma-smoke font-semibold"
                    }`}
                  >
                    {sub.is_paid ? "Lunas periode ini" : paymentOverdue ? "Belum dicatat" : !sub.is_active
                      ? "Dijeda"
                      : missingDate
                      ? "Tanggal belum diatur"
                      : isExpired
                      ? `Lewat ${Math.abs(days)} hari`
                      : isToday
                      ? "Jatuh tempo hari ini"
                      : `${days} hari lagi`}
                  </span>
                </div>

                <div>
                  <div className="ai7-type-metric text-white tracking-tight truncate">
                    {formatRupiah(sub.amount)}
                    <span className="text-xs font-normal text-zinc-400 font-sans">
                      {isExact ? " / periode" : isYearly ? " / tahun" : " / bulan"}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-zinc-400 font-sans mt-1 truncate">
                    {isExact ? (
                      <>
                        <Clock className="w-3.5 h-3.5 text-amberGold shrink-0" />
                        <span className="truncate">
                          Jatuh tempo <strong>{sub.exact_due_date || sub.next_billing_date}</strong>
                        </span>
                      </>
                    ) : (
                      <>
                        <Calendar className="w-3.5 h-3.5 text-amberGold shrink-0" />
                      <span className="truncate">{isYearly
                        ? (missingDate ? "Atur tanggal tahunan lewat Ubah" : `Jatuh tempo ${sub.next_billing_date}`)
                        : `Setiap tanggal ${sub.billing_day} (${sub.next_billing_date})`}</span>
                      </>
                    )}
                  </div>
                </div>

                {sub.notes && (
                  <div className="text-xs text-zinc-400 bg-obsidian-panel p-2.5 rounded-xl border border-luma-smokeline font-sans">
                    {sub.notes}
                  </div>
                )}

                {sub.payment_due_date && <p className="text-xs text-luma-smoke">
                  Periode jatuh tempo {sub.payment_due_date}{sub.is_paid ? " · Dibayar " + formatRupiah(sub.paid_amount ?? sub.amount) + " pada " + sub.paid_date : " · Belum dicatat pembayarannya"}
                </p>}

                <div className="flex flex-wrap items-center gap-2 pt-3 border-t border-luma-smokeline">
                  {sub.is_active && sub.payment_period && !sub.is_paid && onPaymentChanged &&
                    <button type="button" onClick={() => setPayId(sub.id)} aria-label={"Catat pembayaran " + sub.name}
                      className="luma-action-primary">Catat pembayaran</button>}
                  {onEdit && (
                    <button
                      type="button"
                      onClick={() => onEdit(sub)}
                      aria-label={`Ubah tagihan ${sub.name}`}
                      className="inline-flex min-h-11 cursor-pointer items-center gap-1.5 px-2 text-luma-ivory hover:bg-luma-coal"
                    >
                      <Edit2 size={16} aria-hidden="true" />
                      <span>Ubah</span>
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => onToggleActive(sub)}
                    aria-label={`${sub.is_active ? "Jeda" : "Aktifkan"} tagihan ${sub.name}`}
                    className="inline-flex min-h-11 cursor-pointer items-center gap-1.5 px-2 text-luma-ivory hover:bg-luma-coal"
                  >
                    {sub.is_active ? <Pause size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
                    <span>{sub.is_active ? "Jeda" : "Aktifkan"}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(sub.id)}
                    aria-label={`Hapus tagihan ${sub.name}`}
                    className="ml-auto inline-flex min-h-11 cursor-pointer items-center gap-1.5 px-2 text-luma-coral hover:bg-luma-coal"
                  >
                    <Trash2 size={16} aria-hidden="true" />
                    <span>Hapus</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
        )}
      </div>
      {payId !== null && <BillPaymentModal key={payId} subscriptionId={payId}
        onClose={() => setPayId(null)} onChanged={() => onPaymentChanged?.()} />}
    </div>
  );
}
