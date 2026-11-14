import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeftRight,
  Bot,
  CreditCard,
  Dumbbell,
  Landmark,
  Link2,
  Pencil,
  Plus,
  Smartphone,
  Wallet,
} from "lucide-react";
import { Skeleton } from "./ui/Skeleton";
import {
  PocketItem,
  PocketsSummaryResponse,
  getPockets,
} from "@/lib/api";

export type JagoPocketItem = PocketItem;
export type JagoPocketsSummaryResponse = PocketsSummaryResponse;
export const getJagoPockets = getPockets;
import { EditPocketsModal } from "./EditPocketsModal";
import { getPocketStatus } from "@/lib/pocketStatus";
import { AddPocketModal } from "./AddPocketModal";
import { LinkPocketBillModal } from "./LinkPocketBillModal";
import { TransferPocketModal } from "./TransferPocketModal";
import type { AccountItem } from "./AccountGrid";

export interface PocketsProps {
  accountId?: number;
  accountName?: string;
  cycleStart?: string;
  cycleEnd?: string;
  formatRupiah: (val: number) => string;
  refreshSignal?: number;
  onToast?: (msg: string) => void;
  onDataLoaded?: (data: PocketsSummaryResponse) => void;
  showActions?: boolean;
}

export type JagoPocketsProps = PocketsProps;

export interface AccountPocketsProps extends PocketsProps {
  accounts?: AccountItem[];
}

const POCKET_ORDER = ["utama", "kuota", "visa", "claude", "gym"] as const;

const POCKET_META: Record<
  string,
  { icon: React.ComponentType<{ className?: string }>; accent: string }
> = {
  utama: { icon: Wallet, accent: "text-luma-ember bg-luma-ember/10 border-luma-ember/30" },
  kuota: { icon: Smartphone, accent: "text-luma-gold bg-luma-gold/10 border-luma-gold/30" },
  visa: { icon: CreditCard, accent: "text-luma-gold bg-luma-gold/10 border-luma-gold/30" },
  claude: { icon: Bot, accent: "text-luma-ember bg-luma-ember/10 border-luma-ember/30" },
  gym: { icon: Dumbbell, accent: "text-luma-sage bg-luma-sage/10 border-luma-sage/30" },
};

function sortPockets(pockets: PocketItem[]): PocketItem[] {
  const order = new Map<string, number>(POCKET_ORDER.map((slug, i) => [slug, i]));
  return [...pockets].sort((a, b) => {
    const ai = order.has(a.slug) ? (order.get(a.slug) as number) : 99;
    const bi = order.has(b.slug) ? (order.get(b.slug) as number) : 99;
    if (ai !== bi) return ai - bi;
    return a.name.localeCompare(b.name);
  });
}

function statusFor(tone: ReturnType<typeof getPocketStatus>["tone"]): {
  bar: string;
  badge: string;
} {
  if (tone === "danger") {
    return {
      bar: "bg-luma-coral",
      badge: "bg-luma-coral/10 border-luma-coral/30 text-luma-coral",
    };
  }
  if (tone === "warning") {
    return {
      bar: "bg-luma-gold",
      badge: "bg-luma-gold/10 border-luma-gold/30 text-luma-gold",
    };
  }
  if (tone === "neutral") {
    return {
      bar: "bg-luma-smoke",
      badge: "bg-white/[0.06] border-luma-smokeline text-luma-smoke",
    };
  }
  return {
    bar: "bg-luma-sage",
    badge: "bg-luma-sage/10 border-luma-sage/30 text-luma-sage",
  };
}

export function Pockets({
  accountId,
  accountName,
  cycleStart,
  cycleEnd,
  formatRupiah,
  refreshSignal = 0,
  onToast,
  onDataLoaded,
  showActions = true,
}: PocketsProps) {
  const onDataLoadedRef = useRef(onDataLoaded);
  useEffect(() => {
    onDataLoadedRef.current = onDataLoaded;
  }, [onDataLoaded]);

  const [data, setData] = useState<PocketsSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals state
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isTransferOpen, setIsTransferOpen] = useState(false);
  const [transferSourceId, setTransferSourceId] = useState<number | undefined>();
  const [transferTargetId, setTransferTargetId] = useState<number | undefined>();
  const [linkPocketId, setLinkPocketId] = useState<number | null>(null);

  const requestVersion = useRef(0);

  const fetchPockets = useCallback(async () => {
    const version = ++requestVersion.current;
    setLoading(true);
    setError(null);
    try {
      const res = await getPockets(accountId, cycleStart, cycleEnd);
      if (version !== requestVersion.current) return;
      setData(res);
      onDataLoadedRef.current?.(res);
    } catch (err) {
      if (version !== requestVersion.current) return;
      const msg = err instanceof Error ? err.message : "Gagal memuat kantong rekening";
      setError(msg);
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }, [accountId, cycleStart, cycleEnd]);

  useEffect(() => {
    fetchPockets();
    return () => {
      requestVersion.current += 1;
    };
  }, [fetchPockets, refreshSignal]);

  const handleEditSuccess = () => {
    void fetchPockets();
    onToast?.("Target komitmen kantong berhasil diperbarui");
  };

  const handleTransferSuccess = () => {
    void fetchPockets();
    onToast?.("Saldo kas berhasil dipindahkan antar-kantong");
  };

  const pockets = useMemo(
    () => (data ? sortPockets(data.pockets ?? data.items ?? []) : []),
    [data]
  );
  const parentName =
    accountName || data?.account_name || pockets[0]?.account_name || undefined;
  const title = parentName ? `Kantong ${parentName}` : "Kantong rekening";

  // Balance breakdown
  const totalAccountBalance =
    data?.total_balance ?? data?.total_pocket_balance ?? data?.total_jago_balance ?? 0;

  const utamaPocket = useMemo(
    () => pockets.find((p) => p.slug === "utama"),
    [pockets]
  );
  const utamaBalance =
    utamaPocket?.balance ?? utamaPocket?.remaining_amount ?? 0;

  const subPockets = useMemo(
    () => pockets.filter((p) => p.slug !== "utama"),
    [pockets]
  );

  const subPocketsBalance = useMemo(
    () =>
      subPockets.reduce(
        (sum, p) => sum + (p.balance ?? p.remaining_amount ?? 0),
        0
      ),
    [subPockets]
  );

  const openTransferModal = (fromId?: number, toId?: number) => {
    setTransferSourceId(fromId);
    setTransferTargetId(toId);
    setIsTransferOpen(true);
  };

  if (loading) {
    return (
      <section
        aria-label={title}
        className="luma-glass p-6 sm:p-7 space-y-5"
        aria-busy="true"
      >
        <div className="flex flex-col items-start gap-4">
          <div>
            <Skeleton className="w-56 h-5 rounded-full" />
            <Skeleton className="w-80 h-3.5 rounded-full mt-1.5" />
          </div>
          {showActions && (
            <div className="flex items-center gap-2">
              <Skeleton className="w-32 h-11 rounded-2xl" />
              <Skeleton className="w-28 h-11 rounded-2xl" />
            </div>
          )}
        </div>
        <div className="ai7-pocket-grid grid gap-3.5 sm:gap-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className="rounded-2xl bg-white/[0.04] border border-luma-smokeline p-4 sm:p-5 space-y-4"
            >
              <div className="flex justify-between items-center gap-2">
                <Skeleton className="w-24 h-4 rounded-full" />
                <Skeleton className="w-10 h-4 rounded-full" />
              </div>
              <div>
                <Skeleton className="w-28 h-6 rounded-full" />
                <Skeleton className="w-16 h-3 rounded-full mt-1.5" />
              </div>
              <Skeleton className="w-full h-1.5 rounded-full" />
              <div className="flex justify-between items-center pt-2 border-t border-luma-smokeline">
                <Skeleton className="w-16 h-3 rounded-full" />
                <Skeleton className="w-16 h-3 rounded-full" />
              </div>
            </div>
          ))}
        </div>
      </section>
    );
  }

  return (
    <section aria-label={title} className="luma-glass p-6 sm:p-7 space-y-5">
      {/* Header Section */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="ai7-type-section text-luma-ivory tracking-tight flex items-center gap-2">
            <Landmark className="w-5 h-5 text-luma-ember shrink-0" aria-hidden="true" />
            <span>{title}</span>
          </h2>
          <p className="text-xs text-luma-smoke mt-1">
            Partisi saldo kas riil per sub-akun. Total saldo kantong selalu setara dengan saldo rekening di ledger.
          </p>

          {/* Real Cash Metric Grid */}
          <dl className="mt-3.5 grid grid-cols-2 gap-x-5 gap-y-3 sm:grid-cols-3">
            <div className="min-w-0">
              <dt className="text-xs text-luma-smoke">Total Saldo Kas</dt>
              <dd className="text-sm font-semibold text-luma-ivory tabular-nums [overflow-wrap:anywhere]">
                {formatRupiah(totalAccountBalance)}
              </dd>
              <span className="text-[10px] text-zinc-500 block">Saldo kas rekening</span>
            </div>
            <div className="min-w-0">
              <dt className="text-xs text-luma-smoke">Kas Bebas (Utama)</dt>
              <dd className="text-sm font-semibold text-luma-gold tabular-nums [overflow-wrap:anywhere]">
                {formatRupiah(utamaBalance)}
              </dd>
              <span className="text-[10px] text-zinc-500 block">Unallocated cash pool</span>
            </div>
            <div className="min-w-0">
              <dt className="text-xs text-luma-smoke">Saldo Sub-Kantong</dt>
              <dd className="text-sm font-semibold text-luma-sage tabular-nums [overflow-wrap:anywhere]">
                {formatRupiah(subPocketsBalance)}
              </dd>
              <span className="text-[10px] text-zinc-500 block">
                {subPockets.length} kantong teralokasi
              </span>
            </div>
          </dl>
        </div>

        {/* Action Controls */}
        {showActions && (
          <div className="flex flex-wrap items-center gap-2 shrink-0 self-start sm:self-center">
            <button
              type="button"
              onClick={() => openTransferModal()}
              disabled={!!error || pockets.length < 2}
              title="Pindah saldo kas fisik antar-kantong"
              className="luma-action-primary cursor-pointer disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              <ArrowLeftRight className="w-4 h-4 shrink-0" aria-hidden="true" />
              <span>Pindah Saldo</span>
            </button>
            <button
              type="button"
              onClick={() => setIsEditOpen(true)}
              disabled={!!error || pockets.length === 0}
              title="Atur target komitmen sinking fund kantong"
              className="luma-action-secondary cursor-pointer disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              <Pencil className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
              <span>Atur Target</span>
            </button>
            <button
              type="button"
              onClick={() => {
                const targetPocket =
                  pockets.find((pocket) => pocket.role === "tagihan") || pockets[0];
                if (targetPocket) setLinkPocketId(targetPocket.id);
              }}
              disabled={!!error || !parentName || pockets.length === 0}
              title="Hubungkan kantong ke tagihan autodebet berkala"
              className="luma-action-secondary cursor-pointer disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              <Link2 className="w-4 h-4 shrink-0" aria-hidden="true" />
              <span>Tagihan</span>
            </button>
            {accountId !== undefined && (
              <button
                type="button"
                onClick={() => setIsAddOpen(true)}
                disabled={!!error}
                className="luma-action-secondary cursor-pointer disabled:cursor-not-allowed flex items-center gap-1.5"
              >
                <Plus className="w-4 h-4 shrink-0" aria-hidden="true" />
                <span>Tambah</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-2xl bg-luma-coral/10 border border-luma-coral/30 text-sm text-luma-coral flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <span>{error}</span>
          <button
            type="button"
            onClick={fetchPockets}
            className="luma-touch min-w-[44px] px-4 py-2 rounded-full text-xs font-semibold bg-luma-coral/15 border border-luma-coral/40 hover:bg-luma-coral/25 active:scale-95 transition shrink-0 cursor-pointer"
          >
            Coba Lagi
          </button>
        </div>
      )}

      {/* Pocket Cards Grid */}
      {pockets.length === 0 && !error ? (
        <div className="p-6 rounded-2xl bg-white/[0.04] border border-luma-smokeline text-center text-sm text-luma-smoke">
          Belum ada kantong aktif. Tambahkan kantong untuk mempartisi alokasi saldo kas rekening ini.
        </div>
      ) : (
        <div className="ai7-pocket-grid grid gap-3.5 sm:gap-4">
          {pockets.map((pocket) => {
            const balance = pocket.balance ?? pocket.remaining_amount ?? 0;
            const target = pocket.target_amount ?? 0;
            const isUtama = pocket.slug === "utama";
            const state = getPocketStatus(balance, target, isUtama);
            const status = statusFor(state.tone);
            const fillPct =
              target > 0
                ? Math.min(100, Math.max(0, Math.round((balance / target) * 100)))
                : null;

            const meta = POCKET_META[pocket.slug] ?? {
              icon: Wallet,
              accent: "text-luma-smoke bg-white/[0.06] border-luma-smokeline",
            };
            const Icon = meta.icon;

            return (
              <div
                key={pocket.slug}
                className="rounded-2xl bg-white/[0.04] border border-luma-smokeline hover:border-white/[0.18] p-4 sm:p-5 space-y-3.5 flex flex-col justify-between transition-all duration-200"
              >
                <div className="space-y-3">
                  {/* Card Header: Icon, Name, and Status Badge */}
                  <div className="flex justify-between items-center gap-2">
                    <div className="flex items-center gap-2.5 min-w-0 flex-1">
                      <span
                        className={`w-9 h-9 rounded-full border flex items-center justify-center shrink-0 ${meta.accent}`}
                      >
                        <Icon className="w-4 h-4" aria-hidden="true" />
                      </span>
                      <div className="min-w-0">
                        <span className="text-luma-ivory font-semibold text-sm block truncate leading-snug">
                          {pocket.name}
                        </span>
                        <span className="text-[10px] text-luma-smoke capitalize block">
                          {isUtama ? "Kas Utama Bebas" : pocket.role || "Sub-Akun"}
                        </span>
                      </div>
                    </div>
                    <span
                      className={`text-xs px-2.5 py-1 rounded-badge border shrink-0 font-medium ${status.badge}`}
                    >
                      {state.label}
                    </span>
                  </div>

                  {/* Primary Metric: Saldo Kas Riil */}
                  <div>
                    <div className="ai7-type-metric text-luma-ivory tracking-tight tabular-nums break-words font-semibold text-xl sm:text-2xl">
                      {formatRupiah(balance)}
                    </div>
                    <div className="text-xs text-luma-smoke mt-0.5">
                      {isUtama
                        ? "Kas bebas siap alokasi & belanja"
                        : "Saldo kas riil sub-kantong"}
                    </div>

                    {pocket.subscription_id && (
                      <p
                        className={`text-xs mt-2 ${
                          pocket.subscription_status === "active"
                            ? "text-luma-smoke"
                            : "text-luma-coral"
                        }`}
                      >
                        {pocket.subscription_name || "Tagihan terhubung"} ·{" "}
                        {pocket.subscription_status === "active"
                          ? "Autodebet sinkron"
                          : "Tagihan non-aktif"}
                      </p>
                    )}
                  </div>

                  {/* Target Commitment & Sinking Fund Progress */}
                  {!isUtama && target > 0 && fillPct !== null && (
                    <div className="space-y-1.5 pt-1">
                      <div className="flex justify-between items-center text-xs tabular-nums text-luma-smoke">
                        <span>Target: {formatRupiah(target)}</span>
                        <span className="font-semibold text-luma-ivory">{fillPct}%</span>
                      </div>
                      <div
                        className="h-1.5 bg-black/35 rounded-full overflow-hidden"
                        role="progressbar"
                        aria-valuenow={fillPct}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label={`Kecukupan target ${pocket.name} ${fillPct} persen`}
                      >
                        <div
                          style={{ width: `${fillPct}%` }}
                          className={`h-full transition-all duration-500 rounded-full ${status.bar}`}
                        />
                      </div>
                      <div className="text-[11px] text-zinc-400 tabular-nums">
                        {balance >= target ? (
                          <span className="text-luma-sage font-medium">
                            Target terpenuhi penuh
                          </span>
                        ) : (
                          <span>Kurang {formatRupiah(target - balance)} untuk capai target</span>
                        )}
                      </div>
                    </div>
                  )}

                  {!isUtama && target <= 0 && (
                    <p className="text-xs text-luma-smoke italic">
                      Kantong fleksibel tanpa target komitmen
                    </p>
                  )}
                </div>

                {/* Card Footer: Quick Actions */}
                <div className="pt-3 border-t border-luma-smokeline flex items-center justify-between gap-2 text-xs">
                  {isUtama ? (
                    <button
                      type="button"
                      onClick={() => openTransferModal(pocket.id, undefined)}
                      className="inline-flex items-center gap-1.5 text-luma-gold hover:text-amber-300 font-medium transition cursor-pointer"
                    >
                      <ArrowLeftRight className="w-3.5 h-3.5" aria-hidden="true" />
                      <span>Alokasikan ke Kantong Lain</span>
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        if (balance > 0) {
                          openTransferModal(pocket.id, utamaPocket?.id);
                        } else {
                          openTransferModal(utamaPocket?.id, pocket.id);
                        }
                      }}
                      className="inline-flex items-center gap-1.5 text-luma-smoke hover:text-luma-ivory transition cursor-pointer"
                    >
                      <ArrowLeftRight className="w-3.5 h-3.5" aria-hidden="true" />
                      <span>{balance > 0 ? "Pindah Dana" : "Isi dari Kas Utama"}</span>
                    </button>
                  )}

                  {!isUtama && parentName && (
                    <button
                      type="button"
                      onClick={() => setLinkPocketId(pocket.id)}
                      className="text-right text-zinc-500 hover:text-luma-ivory transition cursor-pointer"
                      aria-label={`Atur hubungan tagihan ${pocket.name}`}
                    >
                      {pocket.subscription_id ? "Atur tagihan" : "Hubungkan"}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Target Edit Modal */}
      <EditPocketsModal
        accountId={accountId}
        accountName={parentName}
        isOpen={isEditOpen}
        pockets={pockets}
        formatRupiah={formatRupiah}
        onClose={() => setIsEditOpen(false)}
        onSuccess={handleEditSuccess}
      />

      {/* Transfer / Allocation Modal */}
      <TransferPocketModal
        accountId={accountId}
        accountName={parentName}
        isOpen={isTransferOpen}
        pockets={pockets}
        initialSourcePocketId={transferSourceId}
        initialTargetPocketId={transferTargetId}
        formatRupiah={formatRupiah}
        onClose={() => setIsTransferOpen(false)}
        onSuccess={handleTransferSuccess}
      />

      {/* Add Pocket Modal */}
      {isAddOpen && accountId !== undefined && (
        <AddPocketModal
          accountId={accountId}
          accountName={parentName || "Rekening"}
          onClose={() => setIsAddOpen(false)}
          onCreated={() => {
            void fetchPockets();
            onToast?.("Kantong berhasil ditambahkan");
          }}
        />
      )}

      {/* Link Bill Modal */}
      {linkPocketId !== null && parentName && (
        <LinkPocketBillModal
          pockets={pockets}
          initialPocketId={linkPocketId}
          accountName={parentName}
          formatRupiah={formatRupiah}
          onClose={() => setLinkPocketId(null)}
          onSuccess={() => {
            void fetchPockets();
            onToast?.("Hubungan tagihan berhasil disimpan");
          }}
        />
      )}
    </section>
  );
}

export function AccountPockets({
  accounts,
  accountId,
  accountName,
  ...props
}: AccountPocketsProps) {
  // If accounts array is provided with items, render account selector tabs
  const available = useMemo(
    () => (accounts ? accounts.filter((account) => typeof account.id === "number") : []),
    [accounts]
  );

  const [selectedId, setSelectedId] = useState<number | undefined>(() => {
    if (accountId !== undefined) return accountId;
    return available[0]?.id;
  });

  useEffect(() => {
    if (accountId !== undefined) {
      setSelectedId(accountId);
    } else if (available.length > 0 && (selectedId === undefined || !available.some((a) => a.id === selectedId))) {
      setSelectedId(available[0]?.id);
    }
  }, [accountId, available, selectedId]);

  if (accounts && accounts.length > 0) {
    const selected = available.find((account) => account.id === selectedId) || available[0];

    if (!selected) {
      return (
        <p className="luma-data-state text-luma-smoke">
          Tambahkan rekening terlebih dahulu sebelum membuat kantong.
        </p>
      );
    }

    return (
      <div className="space-y-4">
        <fieldset className="min-w-0">
          <legend className="text-xs text-luma-smoke font-medium mb-2">
            Rekening induk
          </legend>
          <div className="flex flex-wrap gap-2">
            {available.map((account) => (
              <button
                key={account.id}
                type="button"
                aria-pressed={account.id === selected.id}
                onClick={() => setSelectedId(account.id)}
                className={`min-w-0 max-w-full px-4 py-2 text-left font-medium [overflow-wrap:anywhere] rounded-2xl border transition-colors cursor-pointer ${
                  account.id === selected.id
                    ? "bg-luma-ivory text-luma-charcoal border-transparent font-semibold"
                    : "bg-white/[0.04] text-luma-smoke border-luma-smokeline hover:bg-white/[0.08] hover:text-luma-ivory"
                }`}
              >
                {account.name}
              </button>
            ))}
          </div>
        </fieldset>
        <Pockets
          key={selected.id}
          {...props}
          accountId={selected.id}
          accountName={selected.name}
        />
      </div>
    );
  }

  // Single account mode
  return (
    <Pockets
      {...props}
      accountId={accountId}
      accountName={accountName}
    />
  );
}

// Aliases for backward compatibility
export const JagoPockets = AccountPockets;
export const OperationalPockets = AccountPockets;
export default AccountPockets;
