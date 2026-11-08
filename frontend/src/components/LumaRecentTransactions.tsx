"use client";

import React from "react";
import { ArrowRight, Receipt, ArrowUpRight, ArrowDownRight, ArrowLeftRight } from "lucide-react";
import { Skeleton } from "./ui/Skeleton";

export interface LumaTransaction {
  id: number;
  type: "income" | "expense" | "transfer_in" | "transfer_out" | "adjustment_in" | "adjustment_out";
  amount: number;
  account: string;
  category: string;
  description: string;
  date: string;
}

interface LumaRecentTransactionsProps {
  newTransactionIds?: ReadonlySet<number>;
  transactions: LumaTransaction[];
  totalCount: number;
  formatRupiah: (val: number) => string;
  loading?: boolean;
  onOpenLedger: () => void;
  onAddTransaction?: () => void;
  onEdit?: (tx: LumaTransaction) => void;
  onDelete?: (tx: LumaTransaction) => void;
}

function TxIcon({ type }: { type: LumaTransaction["type"] }) {
  if (type === "adjustment_in" || type === "adjustment_out") {
    return <ArrowLeftRight className="h-4 w-4 text-luma-smoke" aria-hidden="true" />;
  }
  if (type === "income") {
    return <ArrowUpRight className="w-4 h-4 text-luma-sage shrink-0" aria-hidden="true" />;
  }
  if (type === "transfer_in" || type === "transfer_out") {
    return <ArrowLeftRight className="w-4 h-4 text-luma-transfer shrink-0" aria-hidden="true" />;
  }
  return <ArrowDownRight className="w-4 h-4 text-luma-coral shrink-0" aria-hidden="true" />;
}

/**
 * LumaRecentTransactions — calm Luma list style for the Ringkasan tab.
 * Round icon wells, clear labels, tidy tabular amounts. Edit/delete
 * affordances are always visible (thumb-friendly, no hover-only traps).
 */
export function LumaRecentTransactions({
  newTransactionIds,
  transactions,
  totalCount,
  formatRupiah,
  loading,
  onOpenLedger,
  onAddTransaction,
  onEdit,
  onDelete,
}: LumaRecentTransactionsProps) {
  return (
    <section aria-label="Transaksi terbaru" className="luma-recent space-y-4">
      <p className="sr-only" role="status">{transactions.some((tx) => newTransactionIds?.has(tx.id)) ? "Transaksi baru ditampilkan." : ""}</p>
      <div className="flex items-center justify-between gap-2">
        <h2 className="ai7-type-card text-luma-ivory tracking-tight">
          Transaksi terbaru
        </h2>
        <button
          type="button"
          onClick={onOpenLedger}
          className="luma-touch inline-flex items-center gap-1 px-2 text-xs text-luma-ember hover:underline font-semibold shrink-0 whitespace-nowrap cursor-pointer"
        >
          <span>Semua transaksi ({totalCount})</span>
          <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
        </button>
      </div>

      <div className="luma-glass !rounded-3xl overflow-hidden">
        {loading ? (
          <ul className="divide-y divide-white/[0.06]">
            {[1, 2, 3, 4, 5].map((i) => (
              <li key={i} className="flex items-center gap-3.5 px-5 py-4">
                <Skeleton className="w-11 h-11 rounded-full shrink-0" />
                <div className="flex-1 space-y-2 min-w-0">
                  <Skeleton className="h-4 w-2/3 rounded-full" />
                  <Skeleton className="h-3 w-1/3 rounded-full" />
                </div>
                <Skeleton className="h-5 w-24 rounded-full shrink-0" />
              </li>
            ))}
          </ul>
        ) : transactions.length === 0 ? (
          <div className="flex flex-col items-center gap-3 px-5 py-12 text-center">
            <div className="w-12 h-12 rounded-full bg-white/[0.05] border border-luma-smokeline flex items-center justify-center">
              <Receipt className="w-5 h-5 text-luma-smoke" aria-hidden="true" />
            </div>
            <p className="text-sm text-luma-smoke">Belum ada transaksi pada periode ini.</p>
            {onAddTransaction && <button type="button" onClick={onAddTransaction} className="luma-text-action">Catat transaksi pertama</button>}
          </div>
        ) : (
          <ul className="divide-y divide-white/[0.06]">
            {transactions.map((tx) => {
              const isAdjustment = tx.type === "adjustment_in" || tx.type === "adjustment_out";
              const isPositive = tx.type === "income" || tx.type === "transfer_in" || tx.type === "adjustment_in";
              const isTransfer = tx.type === "transfer_in" || tx.type === "transfer_out";
              const amountClass = isAdjustment ? "text-luma-ivory" : isTransfer
                ? "text-luma-transfer"
                : isPositive ? "text-luma-sage" : "text-luma-coral";
              return (
                <li
                  key={tx.id}
                  data-new-transaction={newTransactionIds?.has(tx.id) || undefined}
                  className="flex items-center gap-3.5 px-5 py-4 hover:bg-white/[0.03] transition-colors"
                >
                  <div
                    aria-hidden="true"
                    className="w-11 h-11 rounded-[var(--ai7-radius-control)] bg-luma-coal border border-luma-smokeline flex items-center justify-center shrink-0"
                  >
                    <TxIcon type={tx.type} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-luma-ivory truncate leading-snug">
                      {tx.description}
                    </p>
                    <p className="text-xs font-sans text-luma-smoke truncate mt-0.5">
                      {tx.date} · {tx.category} · {tx.account}
                    </p>
                  </div>
                  <div
                    className={`text-sm sm:text-base font-semibold font-sans tabular-nums whitespace-nowrap shrink-0 ${amountClass}`}
                  >
                    {isPositive ? "+" : "-"} {formatRupiah(tx.amount)}
                  </div>
                  {(onEdit || onDelete) && !isAdjustment && (
                    <div className="flex items-center gap-1 shrink-0 ml-auto">
                      {onEdit && (
                        <button
                          type="button"
                          onClick={() => onEdit(tx)}
                          title="Edit transaksi"
                          aria-label={`Edit transaksi ${tx.description}`}
                          className="luma-touch min-w-[44px] inline-flex items-center justify-center rounded-full text-luma-smoke hover:text-luma-gold hover:bg-luma-gold/10 border border-transparent hover:border-luma-gold/25 transition cursor-pointer"
                        >
                          <span className="text-xs font-semibold">Ubah</span>
                        </button>
                      )}
                      {onDelete && (
                        <button
                          type="button"
                          onClick={() => onDelete(tx)}
                          title="Hapus transaksi"
                          aria-label={`Hapus transaksi ${tx.description}`}
                          className="luma-touch min-w-[44px] inline-flex items-center justify-center rounded-full text-luma-smoke hover:text-luma-coral hover:bg-luma-coral/10 border border-transparent hover:border-luma-coral/25 transition cursor-pointer"
                        >
                          <span className="text-xs font-semibold">Hapus</span>
                        </button>
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
