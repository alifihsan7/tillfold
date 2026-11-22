"use client";

import React from "react";
import { Wallet } from "lucide-react";
import { Skeleton } from "./ui/Skeleton";
import { HiddenAmount } from "./ui/HiddenAmount";
import { getAccountRoleBadge } from "./AccountGrid";

export interface LumaAccountSummary {
  name: string;
  balance: number;
  type?: string;
}

interface LumaAccountStripProps {
  accounts: LumaAccountSummary[];
  formatRupiah: (val: number) => string;
  loading?: boolean;
  hideBalance?: boolean;
  onOpenAccounts: () => void;
}

/**
 * LumaAccountStrip — airy horizontal cash-account summary for Ringkasan.
 * Names never clip to "Reke..." — full wrap with tabular balances.
 */
export function LumaAccountStrip({ accounts, formatRupiah, loading, hideBalance, onOpenAccounts }: LumaAccountStripProps) {
  if (loading) {
    return (
      <section aria-label="Ringkasan rekening kas" className="luma-accounts space-y-4">
        <Skeleton className="h-5 w-48 rounded-full" />
        <div className="luma-accounts-grid">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="luma-account-item space-y-2">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-6 w-4/5" />
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (accounts.length === 0) return null;

  return (
    <section aria-label="Ringkasan rekening kas" className="luma-accounts space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="ai7-type-section text-luma-ivory tracking-tight">
          Rekening kas
        </h2>
        <button
          type="button"
          onClick={onOpenAccounts}
          className="luma-touch inline-flex items-center px-2 text-xs text-luma-ember hover:underline font-semibold shrink-0 whitespace-nowrap cursor-pointer"
        >
          Kelola rekening
        </button>
      </div>
      <div className="luma-accounts-grid">
        {accounts.map((acc) => (
          <div
            key={acc.name}
            className="luma-account-item"
          >
            <span className="fold-account-icon"><Wallet size={17} aria-hidden="true" /></span>
            <div className="min-w-0">
              <p className="text-sm font-semibold leading-snug [overflow-wrap:anywhere]">{acc.name}</p>
              {acc.type && <p className="text-xs text-luma-smoke mt-1">{getAccountRoleBadge(acc.type).label}</p>}
            </div>
            <p className={`fold-account-amount tabular-nums [overflow-wrap:anywhere] ${acc.balance < 0 && !hideBalance ? "text-luma-coral" : "text-luma-ivory"}`}>
              {hideBalance ? <HiddenAmount /> : formatRupiah(acc.balance)}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
