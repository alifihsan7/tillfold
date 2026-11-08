import React, { useState } from "react";
import { BillPaymentModal } from "./BillPaymentModal";
import { Plus, Trash2, Calendar, Edit2, Clock, Pause, Play } from "lucide-react";
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
  onOpenModal: () => void;
  onToggleActive: (sub: SubscriptionItem) => void;
  onDelete: (id: number) => void;
  onEdit?: (sub: SubscriptionItem) => void;
  loading?: boolean;
  onPaymentChanged?: () => void;
}

export function SubscriptionsView({
  subsData,
  formatRupiah,
  onOpenModal,
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
      {/* Top Metrics Cards */}
      <div className="ai7-metric-grid grid gap-4">
        <div className="bg-obsidian-card border border-luma-smokeline rounded-2xl p-5 sm:p-6 space-y-2 shadow-sm">
          <div className="text-xs font-semibold text-zinc-400 truncate">
            Total komitmen bulanan
          </div>
          {loading ? (
            <Skeleton className="h-8 w-36 rounded-full" />
          ) : (
            <div className="ai7-type-metric text-amberGold tracking-tight truncate">
              {formatRupiah(subsData.total_monthly_commitment)}
            </div>
          )}
          <div className="text-xs text-zinc-400 font-sans">
            Alokasi pos tagihan & autodebet
          </div>
        </div>

        <div className="bg-obsidian-card border border-luma-smokeline rounded-2xl p-5 sm:p-6 space-y-2 shadow-sm">
          <div className="text-xs font-semibold text-zinc-400 truncate">
            Tagihan aktif
          </div>
          {loading ? (
            <Skeleton className="h-8 w-24 rounded-full" />
          ) : (
            <div className="ai7-type-metric text-mintRise tracking-tight truncate">
              {subsData.active_count} Layanan
            </div>
          )}
          <div className="text-xs text-zinc-400 font-sans">
            Autodebet aktif bulanan
          </div>
        </div>

        <div className="bg-obsidian-card border border-luma-smokeline rounded-2xl p-5 sm:p-6 space-y-2 shadow-sm">
          <div className="text-xs font-semibold text-zinc-400 truncate">
            Jatuh tempo pekan ini
          </div>
          {loading ? (
            <Skeleton className="h-8 w-24 rounded-full" />
          ) : (
            <div className="ai7-type-metric text-coralFall tracking-tight truncate">
              {subsData.upcoming_this_week} Tagihan
            </div>
          )}
          <div className="text-xs text-zinc-400 font-sans">
            Siapkan saldo sebelum autodebet
          </div>
        </div>

        <div className="bg-obsidian-card border border-luma-smokeline rounded-2xl p-5 sm:p-6 flex flex-col justify-between shadow-sm">
          <div>
            <div className="text-xs font-semibold text-zinc-400 truncate">
              Perintah bot Telegram
            </div>
            <div className="text-sm font-sans text-white mt-1 font-semibold truncate">
              /subs atau /tagihan
            </div>
          </div>
          <button
            onClick={onOpenModal}
            className="mt-3 px-4 py-2 text-xs font-semibold bg-amberGold text-slate-950 hover:bg-yellow-300 rounded-xl transition flex items-center justify-center gap-1.5 shrink-0 whitespace-nowrap cursor-pointer active:scale-95"
          >
            <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
            <span>Tambah tagihan</span>
          </button>
        </div>
      </div>

      {/* Subscriptions Grid Cards */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
          <div>
            <h3 className="ai7-type-card text-white">
              Daftar tagihan & layanan terjadwal
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              Total {subsData.items.length} tagihan dan layanan rutin terdaftar
            </p>
          </div>
          <button
            type="button"
            onClick={onOpenModal}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-amberGold text-slate-950 font-semibold rounded-xl hover:bg-yellow-300 transition shadow-sm text-xs shrink-0 whitespace-nowrap cursor-pointer active:scale-95"
          >
            <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
            <span>Tambah tagihan</span>
          </button>
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
                className={`bg-obsidian-card border rounded-2xl p-5 space-y-4 transition-all shadow-sm ${
                  isExpired
                    ? "border-coralFall/50 bg-coralFall/5"
                    : isUpcoming || isToday
                    ? "border-amberGold/40 bg-amberGold/5"
                    : "border-luma-smokeline hover:border-white/[0.16]"
                }`}
              >
                <div className="flex justify-between items-start gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-base font-semibold text-white truncate">
                        {sub.name}
                      </span>
                      {isExact && (
                        <span className="text-xs font-sans px-2 py-0.5 rounded-full bg-amberGold/15 border border-amberGold/30 text-amberGold font-semibold shrink-0">
                          Berakhir spesifik
                        </span>
                      )}
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
                      ? `❌ Expired (${Math.abs(days)} hr lalu)`
                      : isToday
                      ? "🚨 Hari Ini!"
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
                          Berakhir pada tgl <strong>{sub.exact_due_date || sub.next_billing_date}</strong>
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
