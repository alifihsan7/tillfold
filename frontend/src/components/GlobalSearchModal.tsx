"use client";

import { useEffect, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { authFetch } from "@/lib/api";
import { CustomModal } from "./ui/CustomModal";
import type { Transaction } from "./TransactionTable";
import type { AccountItem } from "./AccountGrid";
import type { SubscriptionItem } from "./SubscriptionsView";
import type { GoalItem } from "./EditGoalModal";

export type SearchResult = { id: number; title: string; subtitle: string; amount: number } & (
  { kind: "transaction"; data: Transaction } | { kind: "account"; data: AccountItem } |
  { kind: "bill"; data: SubscriptionItem } | { kind: "goal"; data: GoalItem }
);
interface SearchGroup { kind: string; label: string; has_more: boolean; items: SearchResult[] }
interface Props { isOpen: boolean; onClose: () => void; onChoose: (result: SearchResult) => void }
const rupiah = new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 });

export function GlobalSearchModal({ isOpen, onClose, onChoose }: Props) {
  const [query, setQuery] = useState("");
  const [groups, setGroups] = useState<SearchGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!isOpen) return;
    setQuery(""); setGroups([]); setError("");
    const frame = requestAnimationFrame(() => input.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [isOpen]);
  useEffect(() => {
    if (!isOpen) return;
    setGroups([]); setError("");
    const value = query.trim();
    if (value.length < 2) { setLoading(false); return; }
    const controller = new AbortController();
    setLoading(true);
    const timer = window.setTimeout(async () => {
      try {
        const response = await authFetch(`/api/v1/search?q=${encodeURIComponent(value)}`, { signal: controller.signal, cache: "no-store" });
        if (!response.ok) throw new Error(response.status === 401 ? "Sesi berakhir. Masuk kembali untuk mencari." : "Pencarian gagal dimuat.");
        const data = await response.json();
        if (!controller.signal.aborted) setGroups(data.groups);
      } catch (err) {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Pencarian gagal dimuat.");
      } finally { if (!controller.signal.aborted) setLoading(false); }
    }, 250);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [isOpen, query, retry]);

  return <CustomModal isOpen={isOpen} onClose={onClose} title="Cari di Tillfold" maxWidth="xl">
    <div className="space-y-4">
      <div className="space-y-2">
        <label htmlFor="global-search-input" className="text-sm font-medium">Nama, catatan, rekening, atau nominal</label>
        <div className="relative">
          <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-luma-smoke" />
          <input ref={input} id="global-search-input" type="text" inputMode="search" autoComplete="off" maxLength={120}
            value={query} onChange={(event) => setQuery(event.target.value)}
            className="w-full min-h-11 rounded-xl border border-luma-smokeline bg-luma-charcoal py-2.5 pl-10 pr-12 text-base text-luma-ivory"
            placeholder="Contoh: makan, internet, 25.000" />
          {query && <button type="button" aria-label="Hapus pencarian" className="absolute right-0 top-0 flex h-11 w-11 items-center justify-center rounded-xl text-luma-smoke hover:bg-luma-coal hover:text-luma-ivory"
            onClick={() => { setQuery(""); input.current?.focus(); }}><X className="h-4 w-4" aria-hidden="true" /></button>}
        </div>
      </div>
      <div role="status" aria-live="polite" className="text-sm text-luma-smoke">
        {loading ? "Mencari…" : error ? "" : query.trim().length < 2 ? "Ketik minimal 2 karakter. Pencarian mencakup semua periode." : groups.length === 0 ? "Tidak ada hasil. Coba kata lain." : `${groups.reduce((total, group) => total + group.items.length, 0)} hasil ditemukan.`}
      </div>
      {error && <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-luma-coral">
        <p>{error}</p><button type="button" className="luma-action-secondary" onClick={() => setRetry((value) => value + 1)}>Coba lagi</button>
      </div>}
      {!loading && !error && groups.map((group) => <section key={group.kind} aria-label={group.label} className="space-y-2">
        <h4 className="text-sm font-semibold text-luma-smoke">{group.label}</h4>
        <ul className="divide-y divide-luma-smokeline rounded-xl border border-luma-smokeline">
          {group.items.map((result) => <li key={`${result.kind}-${result.id}`}>
            <button type="button" onClick={() => onChoose(result)}
              className="flex min-h-11 w-full flex-col gap-1 rounded-xl px-3 py-3 text-left text-luma-ivory transition-colors hover:bg-luma-coal focus-visible:outline focus-visible:outline-2 focus-visible:outline-luma-ember sm:flex-row sm:items-center sm:justify-between sm:gap-3">
              <span className="min-w-0"><span className="block break-words text-sm font-medium">{result.title}</span>
                <span className="mt-1 block break-words text-xs text-luma-smoke">{result.subtitle}</span></span>
              <span className="shrink-0 text-sm tabular-nums">{result.kind === "transaction" ? `${["income", "transfer_in", "adjustment_in"].includes(result.data.type) ? "+" : "−"} ${rupiah.format(result.amount)}` : result.kind === "goal" ? `Target ${rupiah.format(result.amount)}` : rupiah.format(result.amount)}</span>
            </button>
          </li>)}
        </ul>
        {group.has_more && <p className="text-xs text-luma-smoke">Ada hasil lain. Perjelas pencarian untuk menemukannya.</p>}
      </section>)}
    </div>
  </CustomModal>;
}
