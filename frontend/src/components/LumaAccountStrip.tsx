"use client";

import type { CSSProperties } from "react";
import { ArrowLeftRight, Check, Landmark, Smartphone, Wallet } from "lucide-react";
import type { PocketItem } from "@/lib/api";
import { getAccountRoleBadge } from "./AccountGrid";
import { HiddenAmount } from "./ui/HiddenAmount";
import { Skeleton } from "./ui/Skeleton";

interface CashAccount {
  id?: number;
  name: string;
  balance: number;
  type?: string;
}

interface LumaAccountStripProps {
  accounts: CashAccount[];
  formatRupiah: (val: number) => string;
  loading?: boolean;
  hideBalance?: boolean;
  featuredName?: string;
  featuredPockets?: PocketItem[];
  onOpenAccounts: () => void;
  onReconcile: (id: number) => void;
  onTransfer?: (name: string) => void;
}

const compactCurrency = new Intl.NumberFormat("id-ID", {
  style: "currency", currency: "IDR", notation: "compact", maximumFractionDigits: 1,
});

export function LumaAccountStrip({
  accounts, formatRupiah, loading, hideBalance, featuredName, featuredPockets = [],
  onOpenAccounts, onReconcile, onTransfer,
}: LumaAccountStripProps) {
  if (!loading && accounts.length === 0) return null;

  const featured = accounts.find((account) => account.name === featuredName) ?? accounts[0];
  const otherAccounts = accounts.filter((account) => account !== featured);
  const pockets = featured?.name === featuredName ? featuredPockets : [];
  const reconcileId = featured?.id;
  const transfer = reconcileId !== undefined ? onTransfer : undefined;
  const accountAmount = (account: CashAccount) => (
    <p className={`fold-pocket-amount ${account.balance < 0 && !hideBalance ? "fold-negative" : ""}`}>
      {hideBalance ? <HiddenAmount /> : formatRupiah(account.balance)}
    </p>
  );

  return (
    <section className="fold-wallet" aria-labelledby="fold-wallet-title" aria-busy={loading || undefined}>
      <header className="fold-section-header">
        <div className="fold-wallet-heading">
          <h2 id="fold-wallet-title">Rekening kas</h2>
          {!loading && <span>{accounts.length} rekening</span>}
        </div>
        <button type="button" className="fold-link" aria-label="Kelola rekening" onClick={onOpenAccounts}>Kelola</button>
      </header>
      <ul className="fold-wallet-list">
        {loading ? [1, 2, 3].map((item) => (
          <li className="fold-pocket" key={item}>
            <Skeleton className="size-9 rounded-full" />
            <Skeleton className="h-4 w-20" />
          </li>
        )) : featured && (
          <>
            <li className="fold-pocket-front" key={featured.name} style={{ zIndex: accounts.length }}>
              <div className="fold-pocket-top">
                <span className="fold-pocket-icon"><Landmark size={17} aria-hidden="true" /></span>
                <div>
                  <p className="fold-pocket-name">{featured.name}</p>
                  <p className="fold-pocket-role">{pockets.length ? `Rekening induk · ${pockets.length} kantong` : getAccountRoleBadge(featured.type).label}</p>
                </div>
                {accountAmount(featured)}
              </div>
              {pockets.length > 0 && (
                <ul className="fold-pocket-chips" aria-label={`Kantong ${featured.name}`}>
                  {pockets.slice(0, 3).map((pocket) => {
                    const balance = pocket.balance ?? pocket.remaining_amount;
                    return <li key={pocket.id} title={hideBalance ? undefined : formatRupiah(balance)}>
                      {pocket.name}{!hideBalance && ` · ${compactCurrency.format(balance)}`}
                    </li>;
                  })}
                  {pockets.length > 3 && <li>+{pockets.length - 3}</li>}
                </ul>
              )}
              {reconcileId !== undefined && (
                <div className="fold-pocket-actions">
                  <button type="button" className="fold-action fold-wallet-reconcile"
                    onClick={() => onReconcile(reconcileId)}><Check size={15} aria-hidden="true" /> Cocokkan saldo</button>
                  {transfer && <button type="button" className="fold-link" onClick={() => transfer(featured.name)}>
                    <ArrowLeftRight size={15} aria-hidden="true" /> Transfer
                  </button>}
                </div>
              )}
            </li>
            {otherAccounts.map((account, index) => {
              const Icon = account.type === "ewallet" ? Smartphone : account.type === "cash" ? Wallet : Landmark;
              return (
                <li className="fold-pocket" key={account.name}
                  style={{ zIndex: otherAccounts.length - index, "--pocket-depth": `${(index + 1) * 100 / otherAccounts.length}%` } as CSSProperties}>
                  <span className="fold-pocket-icon"><Icon size={17} aria-hidden="true" /></span>
                  <div>
                    <p className="fold-pocket-name">{account.name}</p>
                    {account.type && <p className="fold-pocket-role">{getAccountRoleBadge(account.type).label}</p>}
                  </div>
                  {accountAmount(account)}
                </li>
              );
            })}
          </>
        )}
      </ul>
    </section>
  );
}
