"use client";

import { formatShortDate, formatSignedRupiah } from "@/lib/format";
import { ArrowRight, Receipt, ArrowUpRight, ArrowDownLeft, ArrowLeftRight, Pencil, Trash2 } from "@/components/icons";
import { Skeleton } from "./ui/Skeleton";

export interface LumaTransaction {
  id: number;
  type: "income" | "expense" | "transfer_in" | "transfer_out" | "adjustment_in" | "adjustment_out";
  amount: number;
  account: string;
  category: string;
  description: string;
  date: string;
  is_internal_loan_transfer?: boolean;
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

export function LumaRecentTransactions({
  newTransactionIds, transactions, totalCount, formatRupiah, loading,
  onOpenLedger, onAddTransaction, onEdit, onDelete,
}: LumaRecentTransactionsProps) {
  const hasNew = transactions.some((transaction) => newTransactionIds?.has(transaction.id));

  return (
    <section className="fold-transactions" aria-labelledby="fold-transactions-title" aria-busy={loading || undefined}>
      <header className="fold-section-header">
        <h2 id="fold-transactions-title">Transaksi terbaru</h2>
        <button type="button" className="fold-link" onClick={onOpenLedger}>
          Semua transaksi ({totalCount}) <ArrowRight size={14} aria-hidden="true" />
        </button>
      </header>
      <p className="sr-only" role="status">{hasNew ? "Transaksi baru ditampilkan." : ""}</p>

      <div className="fold-card fold-transactions-panel">
      {loading ? (
        <ul className="fold-transaction-list">
          {[1, 2, 3, 4, 5, 6].map((item) => (
            <li className="fold-transaction" key={item}>
              <Skeleton className="size-9 rounded-full" /><Skeleton className="h-4 w-24" /><Skeleton className="h-4 w-16" />
            </li>
          ))}
        </ul>
      ) : transactions.length === 0 ? (
        <div className="fold-message fold-transactions-empty">
          <Receipt size={24} aria-hidden="true" />
          <p>Belum ada transaksi pada periode ini.</p>
          {onAddTransaction && <button type="button" className="fold-link" onClick={onAddTransaction}>Catat transaksi pertama</button>}
        </div>
      ) : (
        <ul className="fold-transaction-list">
          {transactions.map((transaction, index) => {
            const { id, type, description, date, category, account, amount, is_internal_loan_transfer } = transaction;
            const adjustment = type === "adjustment_in" || type === "adjustment_out";
            const transfer = type === "transfer_in" || type === "transfer_out";
            const incoming = type === "income" || type === "transfer_in" || type === "adjustment_in";
            const tone = adjustment || transfer ? "fold-muted" : incoming ? "fold-positive" : "fold-negative";
            const Icon = adjustment || transfer ? ArrowLeftRight : incoming ? ArrowDownLeft : ArrowUpRight;
            return (
              <li key={id} className="fold-transaction" data-desktop-only={index >= 5 || undefined} data-new-transaction={newTransactionIds?.has(id) || undefined}>
                <span className={`fold-transaction-icon ${tone}`}><Icon size={16} aria-hidden="true" /></span>
                <div className="fold-transaction-copy">
                  <p>{description}</p>
                  <p>{formatShortDate(date)} · {category} · {account}{is_internal_loan_transfer ? " · Dana talangan" : ""}</p>
                </div>
                <p className={`fold-transaction-value ${tone}`}>{formatSignedRupiah(amount, incoming, formatRupiah)}</p>
                {!adjustment && !is_internal_loan_transfer && (onEdit || onDelete) && (
                  <div className="fold-row-actions">
                    {onEdit && <button type="button" className="fold-icon-button" title="Edit transaksi"
                      aria-label={`Edit transaksi ${description}`} onClick={() => onEdit(transaction)}>
                      <Pencil size={15} aria-hidden="true" />
                    </button>}
                    {onDelete && <button type="button" className="fold-icon-button" title="Hapus transaksi"
                      aria-label={`Hapus transaksi ${description}`} onClick={() => onDelete(transaction)}>
                      <Trash2 size={15} aria-hidden="true" />
                    </button>}
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
