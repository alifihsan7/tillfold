"use client";

import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { ArrowLeftRight, Check, Landmark, Smartphone, Wallet } from "lucide-react";
import { getPockets, type PocketItem } from "@/lib/api";
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
  cycleStart?: string;
  cycleEnd?: string;
  refreshSignal?: number;
  onOpenAccounts: () => void;
  onReconcile: (id: number) => void;
  onTransfer?: (name: string) => void;
}

const compactCurrency = new Intl.NumberFormat("id-ID", {
  style: "currency", currency: "IDR", notation: "compact", maximumFractionDigits: 1,
});

export function LumaAccountStrip({
  accounts, formatRupiah, loading, hideBalance, featuredName, featuredPockets = [],
  cycleStart, cycleEnd, refreshSignal,
  onOpenAccounts, onReconcile, onTransfer,
}: LumaAccountStripProps) {
  const [selectedName, setSelectedName] = useState<string>();
  const [preview, setPreview] = useState<{ key: string; pockets: PocketItem[] | null }>();
  const front = useRef<HTMLLIElement>(null);
  const move = useRef<{ name: string; offset: number }>();

  const featured = accounts.find((account) => account.name === selectedName)
    ?? accounts.find((account) => account.name === featuredName) ?? accounts[0];
  const otherAccounts = accounts.filter((account) => account !== featured);
  const isDefault = featured?.name === featuredName;
  const previewId = !loading && !isDefault ? featured?.id : undefined;
  const previewKey = previewId === undefined ? undefined : JSON.stringify([previewId, cycleStart, cycleEnd, refreshSignal]);
  const previewPockets = previewKey && preview?.key === previewKey ? preview.pockets : undefined;
  const pockets = isDefault ? featuredPockets : previewPockets ?? [];
  const reconcileId = featured?.id;
  const transfer = reconcileId !== undefined ? onTransfer : undefined;

  useEffect(() => {
    if (previewId === undefined || previewKey === undefined) return;
    const request = new AbortController();
    void getPockets(previewId, cycleStart, cycleEnd, request.signal).then((data) => {
      if (request.signal.aborted) return;
      const pockets = (data.pockets ?? data.items ?? []).filter((pocket) =>
        pocket.is_active && (pocket.account_id ?? data.account_id ?? previewId) === previewId);
      setPreview({ key: previewKey, pockets });
    }).catch(() => {
      if (!request.signal.aborted) setPreview({ key: previewKey, pockets: null });
    });
    return () => request.abort();
  }, [cycleStart, cycleEnd, previewId, previewKey]);

  useLayoutEffect(() => {
    const card = front.current;
    const selection = move.current;
    if (!card || !selection || selection.name !== featured?.name) return;
    move.current = undefined;
    card.focus({ preventScroll: true });
    card.scrollIntoView({ block: "nearest" });
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const distance = Math.min(120, Math.max(16, selection.offset));
    const animation = card.animate([
      { transform: `translateY(${distance}px)`, opacity: .72 },
      { transform: "translateY(0)", opacity: 1 },
    ], { duration: 250, easing: "cubic-bezier(.22, 1, .36, 1)" });
    return () => animation.cancel();
  }, [featured?.name]);

  if (!loading && accounts.length === 0) return null;

  const accountAmount = (account: CashAccount, Element: "p" | "span" = "p") => (
    <Element className={`fold-pocket-amount ${account.balance < 0 && !hideBalance ? "fold-negative" : ""}`}>
      {hideBalance ? <HiddenAmount /> : formatRupiah(account.balance)}
    </Element>
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
          <li className="fold-pocket fold-pocket-skeleton" key={item}>
            <Skeleton className="size-9 rounded-full" />
            <Skeleton className="h-4 w-20" />
          </li>
        )) : featured && (
          <>
            <li className="fold-pocket-front" key={featured.name} ref={front} tabIndex={-1} style={{ zIndex: accounts.length }}>
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
              {previewPockets === null && <p className="fold-pocket-preview-error" role="status">Kantong belum bisa dimuat.</p>}
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
                  <button type="button" className="fold-pocket-button" onClick={(event) => {
                    const start = event.currentTarget.getBoundingClientRect().top;
                    move.current = { name: account.name, offset: start - (front.current?.getBoundingClientRect().top ?? start) };
                    setSelectedName(account.name);
                  }}>
                    <span className="sr-only">Tampilkan rekening</span>
                    <span className="fold-pocket-icon"><Icon size={17} aria-hidden="true" /></span>
                    <span>
                      <span className="fold-pocket-name">{account.name}</span>
                      {account.type && <span className="fold-pocket-role">{getAccountRoleBadge(account.type).label}</span>}
                    </span>
                    {accountAmount(account, "span")}
                  </button>
                </li>
              );
            })}
          </>
        )}
      </ul>
    </section>
  );
}
