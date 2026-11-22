"use client";

import { Wallet } from "lucide-react";
import { getAccountRoleBadge } from "./AccountGrid";
import { HiddenAmount } from "./ui/HiddenAmount";
import { Skeleton } from "./ui/Skeleton";

interface CashAccount {
  name: string;
  balance: number;
  type?: string;
}

interface LumaAccountStripProps {
  accounts: CashAccount[];
  formatRupiah: (val: number) => string;
  loading?: boolean;
  hideBalance?: boolean;
  onOpenAccounts: () => void;
}

export function LumaAccountStrip({ accounts, formatRupiah, loading, hideBalance, onOpenAccounts }: LumaAccountStripProps) {
  if (!loading && accounts.length === 0) return null;

  return (
    <section className="fold-wallet" aria-labelledby="fold-wallet-title" aria-busy={loading || undefined}>
      <header className="fold-section-header">
        <h2 id="fold-wallet-title">Rekening kas</h2>
        <button type="button" className="fold-link" onClick={onOpenAccounts}>Kelola rekening</button>
      </header>
      <ul className="fold-wallet-list">
        {loading ? [1, 2, 3].map((item) => (
          <li className="fold-pocket" key={item}>
            <Skeleton className="size-9 rounded-full" />
            <Skeleton className="h-4 w-20" />
          </li>
        )) : accounts.map((account) => (
          <li className="fold-pocket" key={account.name}>
            <span className="fold-pocket-icon"><Wallet size={17} aria-hidden="true" /></span>
            <div>
              <p className="fold-pocket-name">{account.name}</p>
              {account.type && <p className="fold-pocket-role">{getAccountRoleBadge(account.type).label}</p>}
            </div>
            <p className={`fold-pocket-amount ${account.balance < 0 && !hideBalance ? "fold-negative" : ""}`}>
              {hideBalance ? <HiddenAmount /> : formatRupiah(account.balance)}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
