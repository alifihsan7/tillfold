import React from "react";
import { Edit2, Trash2 } from "lucide-react";
import { Skeleton } from "./ui/Skeleton";
import { getCategoryBadgeClasses } from "@/lib/categoryColors";

export interface Transaction {
  id: number;
  type: "income" | "expense" | "transfer_in" | "transfer_out" | "adjustment_in" | "adjustment_out";
  amount: number;
  account: string;
  category: string;
  description: string;
  raw_text?: string;
  date: string;
}

interface TransactionTableProps {
  newTransactionIds?: ReadonlySet<number>;
  transactions: Transaction[];
  formatRupiah: (val: number) => string;
  onEdit?: (tx: Transaction) => void;
  onDelete?: (tx: Transaction) => void;
  loading?: boolean;
}

export function TransactionTable({
  newTransactionIds,
  transactions,
  formatRupiah,
  onEdit,
  onDelete,
  loading,
}: TransactionTableProps) {
  const showActions = Boolean(onEdit || onDelete);

  return (
    <div className="ai7-ledger-table luma-glass overflow-hidden">
      <p className="sr-only" role="status">{transactions.some((tx) => newTransactionIds?.has(tx.id)) ? "Transaksi baru ditampilkan." : ""}</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[700px] text-left text-sm border-collapse tabular-nums">
          <thead>
            <tr className="border-b border-luma-smokeline text-luma-smoke font-medium text-xs">
              <th className="py-4 px-4 sm:px-6 whitespace-nowrap w-28">Tanggal</th>
              <th className="py-4 px-4 sm:px-6 min-w-[200px]">Keterangan</th>
              <th className="py-4 px-4 sm:px-6 whitespace-nowrap w-44">Kategori</th>
              <th className="py-4 px-4 sm:px-6 whitespace-nowrap w-32">Akun</th>
              <th className="py-4 px-4 sm:px-6 text-right whitespace-nowrap w-36">Nominal</th>
              {showActions && <th className="py-4 px-4 sm:px-6 text-center whitespace-nowrap w-24">Aksi</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.06]">
            {loading ? (
              [1, 2, 3, 4, 5].map((i) => (
                <tr key={i} className="animate-pulse">
                  <td className="py-4 px-4 sm:px-6">
                    <Skeleton className="w-20 h-4 rounded-full" />
                  </td>
                  <td className="py-4 px-4 sm:px-6">
                    <Skeleton className="w-48 h-4 rounded-full" />
                  </td>
                  <td className="py-4 px-4 sm:px-6">
                    <Skeleton className="w-24 h-4 rounded-full" />
                  </td>
                  <td className="py-4 px-4 sm:px-6">
                    <Skeleton className="w-20 h-4 rounded-full" />
                  </td>
                  <td className="py-4 px-4 sm:px-6 text-right">
                    <Skeleton className="w-24 h-4 rounded-full ml-auto" />
                  </td>
                  {showActions && (
                    <td className="py-4 px-4 sm:px-6 text-center">
                      <Skeleton className="w-14 h-4 rounded-full mx-auto" />
                    </td>
                  )}
                </tr>
              ))
            ) : transactions.length === 0 ? (
              <tr>
                <td colSpan={showActions ? 6 : 5} className="py-12 text-center text-luma-smoke">
                  Tidak ada transaksi yang cocok dengan filter pencarian.
                </td>
              </tr>
            ) : (
              transactions.map((tx) => {
                const isIncome = tx.type === "income";
                const isTransferIn = tx.type === "transfer_in";
                const isTransferOut = tx.type === "transfer_out";
                const isAdjustment = tx.type === "adjustment_in" || tx.type === "adjustment_out";
                const isPositive = isIncome || isTransferIn || tx.type === "adjustment_in";
                const isTransfer = isTransferIn || isTransferOut;

                return (
                  <tr key={tx.id} data-new-transaction={newTransactionIds?.has(tx.id) || undefined} className="hover:bg-white/[0.04] transition group">
                    <td className="py-4 px-4 sm:px-6 text-luma-smoke font-sans whitespace-nowrap text-xs sm:text-sm">
                      {tx.date}
                    </td>
                    <td className="py-4 px-4 sm:px-6 text-luma-ivory font-medium min-w-[200px] leading-snug break-words">
                      {tx.description}
                    </td>
                    <td className="py-4 px-4 sm:px-6 whitespace-nowrap">
                      <span
                        className={`inline-block px-3 py-1 rounded-badge text-xs font-sans font-medium border whitespace-nowrap ${
                          isAdjustment ? "bg-white/[0.04] border-luma-smokeline text-luma-smoke" : isTransfer
                            ? "bg-luma-transfer/10 border-luma-transfer/30 text-luma-transfer"
                            : getCategoryBadgeClasses(tx.category)
                        }`}
                      >
                        {tx.category}
                      </span>
                    </td>
                    <td className="py-4 px-4 sm:px-6 text-luma-smoke font-sans text-xs sm:text-sm whitespace-nowrap">
                      {tx.account}
                    </td>
                    <td
                      className={`ai7-type-amount py-4 px-4 sm:px-6 text-right whitespace-nowrap ${
                        isAdjustment ? "text-luma-ivory" : isTransfer ? "text-luma-transfer" : isIncome ? "text-luma-sage" : "text-luma-coral"
                      }`}
                    >
                      {isPositive ? "+" : "-"} {formatRupiah(tx.amount)}
                    </td>
                    {showActions && (
                      <td className="py-4 px-4 sm:px-6 text-center whitespace-nowrap">
                        <div className="flex items-center justify-center gap-1 opacity-80 group-hover:opacity-100 transition">
                          {isAdjustment && <span className="text-xs text-luma-smoke">Rekonsiliasi</span>}
                          {onEdit && !isAdjustment && (
                            <button
                              type="button"
                              onClick={() => onEdit(tx)}
                              title="Ubah transaksi"
                              aria-label={`Ubah transaksi ${tx.description}`}
                              className="luma-touch min-w-[44px] inline-flex items-center justify-center text-luma-smoke hover:text-luma-ivory hover:bg-luma-coal transition cursor-pointer"
                            >
                              <Edit2 size={16} aria-hidden="true" />
                            </button>
                          )}
                          {onDelete && !isAdjustment && (
                            <button
                              type="button"
                              onClick={() => onDelete(tx)}
                              title="Hapus transaksi"
                              aria-label={`Hapus transaksi ${tx.description}`}
                              className="luma-touch min-w-[44px] inline-flex items-center justify-center text-luma-coral hover:bg-luma-coral/10 transition cursor-pointer"
                            >
                              <Trash2 size={16} aria-hidden="true" />
                            </button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
