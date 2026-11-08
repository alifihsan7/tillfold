import React, { useState } from "react";
import { CreditCard, Trash2, AlertTriangle, X, Edit2 } from "lucide-react";
import { Skeleton } from "./ui/Skeleton";
import { authFetch } from "@/lib/api";
import { CustomModal } from "./ui/CustomModal";
import { ReconcileAccountModal } from "./ReconcileAccountModal";

export interface AccountItem {
  id?: number;
  name: string;
  type?: string;
  tag?: string | null;
  color?: string;
  initial_balance?: number;
  current_balance?: number;
  is_archived?: boolean;
}

interface AccountGridProps {
  summary: {
    expense: number;
    accounts?: { account: string; balance: number; expense?: number }[];
    safe_to_spend?: {
      pocket_spent: number;
      pocket_remaining: number;
      cycle_days?: number;
      pocket_budget?: number;
      pocket_account?: string;
    };
  };
  customAccounts?: AccountItem[];
  formatRupiah: (val: number) => string;
  loading?: boolean;
  onAccountDeleted?: () => void;
  onEditAccount?: (acc: AccountItem) => void;
  onReconciled?: () => void;
  onArchiveChanged?: () => void;
}

const ACCOUNT_COLOR_DOTS: Record<string, string> = {
  amberGold: "bg-amber-500", cyanHub: "bg-cyan-500", teal: "bg-teal-500",
  purpleLock: "bg-purple-500", blue: "bg-blue-600", coralFall: "bg-rose-500",
  ember: "bg-luma-ember", sage: "bg-luma-sage", mintRise: "bg-emerald-500",
};

export function getAccountRoleBadge(type?: string): { label: string; className: string } {
  const t = (type || "").toLowerCase().trim();
  switch (t) {
    case "gajian":
      return {
        label: "Gajian",
        className: "bg-mintRise/15 text-mintRise border-mintRise/30",
      };
    case "operasional":
      return {
        label: "Operasional",
        className: "bg-luma-transfer/15 text-luma-transfer border-luma-transfer/30",
      };
    case "tagihan":
      return {
        label: "Tagihan",
        className: "bg-luma-gold/15 text-luma-gold border-luma-gold/30",
      };
    case "darurat":
      return {
        label: "Dana darurat",
        className: "bg-luma-transfer/15 text-luma-transfer border-luma-transfer/30",
      };
    case "tabungan":
      return {
        label: "Tabungan",
        className: "bg-luma-sage/15 text-luma-sage border-luma-sage/30",
      };
    case "investasi":
      return {
        label: "Investasi",
        className: "bg-luma-sage/15 text-luma-sage border-luma-sage/30",
      };
    case "ewallet":
      return {
        label: "E-wallet",
        className: "bg-luma-transfer/15 text-luma-transfer border-luma-transfer/30",
      };
    default:
      return {
        label: type || "Akun",
        className: "bg-white/[0.06] text-luma-smoke border-luma-smokeline",
      };
  }
}

export function getDefaultTagForType(type?: string): string {
  const t = (type || "").toLowerCase().trim();
  switch (t) {
    case "operasional":
      return "Pos Operasional & Saku Harian";
    case "tagihan":
      return "Pos Tagihan & Autodebet";
    case "gajian":
      return "Rekening Pemasukan Utama";
    case "tabungan":
      return "Pos Tabungan & Simpanan";
    case "investasi":
      return "Pos Investasi Portofolio";
    case "darurat":
      return "Cadangan Proteksi Darurat";
    case "ewallet":
      return "Dompet Digital / E-Wallet";
    default:
      return "Rekening Kas Aktif";
  }
}

export function AccountGrid({ summary, customAccounts = [], formatRupiah, loading, onAccountDeleted, onEditAccount, onReconciled, onArchiveChanged }: AccountGridProps) {
  const [showArchived, setShowArchived] = useState(false);
  const [archiveTarget, setArchiveTarget] = useState<AccountItem | null>(null);
  const [archivePending, setArchivePending] = useState(false);
  const [archiveError, setArchiveError] = useState("");
  const archiveAccount = async () => {
    if (!archiveTarget?.id || archivePending) return;
    setArchivePending(true);
    setArchiveError("");
    try {
      const response = await authFetch(`/api/v1/accounts/${archiveTarget.id}/archive`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_archived: !archiveTarget.is_archived }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(typeof data?.detail === "string" ? data.detail : "Status rekening gagal disimpan.");
      }
      setArchiveTarget(null);
      onArchiveChanged?.();
    } catch (error) {
      setArchiveError(error instanceof Error ? error.message : "Status rekening gagal disimpan.");
    } finally { setArchivePending(false); }
  };
  const [reconcileId, setReconcileId] = useState<number | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<{ id: number; name: string } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleDeleteAccount = async () => {
    if (!confirmDelete) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      const res = await authFetch(`/api/v1/accounts/${confirmDelete.id}`, { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json();
        setDeleteError(err.detail || "Gagal menghapus rekening");
        setIsDeleting(false);
        return;
      }
      setConfirmDelete(null);
      if (onAccountDeleted) onAccountDeleted();
    } catch {
      setDeleteError("Terjadi kesalahan jaringan saat menghapus rekening");
    } finally {
      setIsDeleting(false);
    }
  };

  // Map balance riil dari summary.accounts
  const balanceMap = (summary.accounts || []).reduce<Record<string, number>>((acc, item) => {
    acc[item.account] = item.balance;
    return acc;
  }, {});

  // Map expense riil dari summary.accounts
  const expenseMap = (summary.accounts || []).reduce<Record<string, number>>((acc, item) => {
    acc[item.account] = item.expense ?? 0;
    return acc;
  }, {});

  const pocketSpent = summary.safe_to_spend?.pocket_spent ?? 0;
  const cycleDays = summary.safe_to_spend?.cycle_days ?? 14;
  const cycleBadge = `${cycleDays} Hari`;
  const pocketBudget = summary.safe_to_spend?.pocket_budget && summary.safe_to_spend.pocket_budget > 0
    ? summary.safe_to_spend.pocket_budget
    : 0;

  // Akun default generic jika user belum memiliki rekening kustom
  const genericDefaultAccounts = [
    {
      id: undefined,
      name: "Rekening Utama",
      tag: "Pos Operasional & Saku Harian",
      balance: 0,
      spent: 0,
      allocated: 0,
      colorKey: "ember",
      type: "operasional",
      isPocket: true,
      cycleBadge,
      isCustom: false,
    },
    {
      id: undefined,
      name: "Tabungan",
      tag: "Pos Tabungan & Simpanan",
      balance: 0,
      spent: 0,
      allocated: 0,
      colorKey: "sage",
      type: "tabungan",
      isPocket: false,
      cycleBadge,
      isCustom: false,
    },
    {
      id: undefined,
      name: "Investasi",
      tag: "Pos Investasi Portofolio",
      balance: 0,
      spent: 0,
      allocated: 0,
      colorKey: "sage",
      type: "investasi",
      isPocket: false,
      cycleBadge,
      isCustom: false,
    },
    {
      id: undefined,
      name: "Dana Darurat",
      tag: "Cadangan Proteksi Darurat",
      balance: 0,
      spent: 0,
      allocated: 0,
      colorKey: "amberGold",
      type: "darurat",
      isPocket: false,
      cycleBadge,
      isCustom: false,
    },
  ];

  const pocketAccountName = (summary.safe_to_spend?.pocket_account || "").toLowerCase();
  const lumaKeyFor = (color?: string) => {
    if (color === "teal") return "sage";
    if (color === "purpleLock" || color === "coralFall") return "coralFall";
    if (color === "blue" || color === "cyanHub") return "blue";
    if (color === "amberGold") return "amberGold";
    return "ember";
  };

  const allDisplayAccounts = customAccounts.length > 0
    ? customAccounts.map((ca) => {
        const colorKey = lumaKeyFor(ca.color);
        const bal = ca.current_balance ?? balanceMap[ca.name] ?? 0;
        const isPocket = ca.name.toLowerCase() === pocketAccountName || (pocketAccountName === "" && ca.name.toLowerCase().includes("mandiri"));
        const roleBadge = getAccountRoleBadge(ca.type);
        return {
          id: ca.id,
          name: ca.name,
          type: ca.type,
          tag: ca.tag || getDefaultTagForType(ca.type),
          balance: bal,
          spent: isPocket ? pocketSpent : (expenseMap[ca.name] ?? 0),
          allocated: isPocket ? pocketBudget : 0,
          colorKey,
          roleBadge,
          isPocket,
          cycleBadge,
          isCustom: true,
          is_archived: !!ca.is_archived,
        };
      })
    : genericDefaultAccounts.map((acc) => ({
        ...acc,
        roleBadge: getAccountRoleBadge(acc.type),
        is_archived: false,
      }));

  if (loading) {
    return (
      <div className="ai7-account-grid">
        {[1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className="ai7-account-card luma-glass p-5 flex flex-col justify-between space-y-4"
          >
            <div>
              <div className="flex justify-between items-center gap-2">
                <div className="flex items-center gap-2">
                  <Skeleton className="w-9 h-9 rounded-full" />
                  <Skeleton className="w-20 h-4 rounded-full" />
                </div>
                <Skeleton className="w-12 h-4 rounded-full" />
              </div>
              <Skeleton className="w-32 h-3 rounded-full mt-2.5" />
              <div className="mt-4">
                <Skeleton className="w-28 h-6 rounded-full" />
                <Skeleton className="w-20 h-3 rounded-full mt-1.5" />
              </div>
            </div>
            <div className="pt-3 border-t border-luma-smokeline">
              <Skeleton className="w-full h-1.5 rounded-full" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2" role="group" aria-label="Status rekening">
        <button type="button" aria-pressed={!showArchived} onClick={() => setShowArchived(false)} className={showArchived ? "luma-action-secondary" : "luma-action-primary"}>Aktif ({allDisplayAccounts.filter((account) => !account.is_archived).length})</button>
        <button type="button" aria-pressed={showArchived} onClick={() => setShowArchived(true)} className={showArchived ? "luma-action-primary" : "luma-action-secondary"}>Arsip ({allDisplayAccounts.filter((account) => account.is_archived).length})</button>
      </div>
      {showArchived && <p className="text-sm text-luma-smoke">Saldo dan riwayat rekening arsip tetap tersimpan.</p>}
      {showArchived && !allDisplayAccounts.some((account) => account.is_archived) && <p className="luma-matte p-4 text-sm text-luma-smoke">Belum ada rekening yang diarsipkan.</p>}
      <div className="ai7-account-grid">
      {allDisplayAccounts.filter((account) => account.is_archived === showArchived).map((acc) => {
        const hasPlafon = acc.allocated > 0;
        const pctUsed = hasPlafon ? Math.min(100, Math.round((acc.spent / acc.allocated) * 100)) : 0;
        const isInvest = (acc.type || "").toLowerCase() === "investasi"
          || acc.name.toLowerCase().includes("invest")
          || acc.name.toLowerCase().includes("bibit");

        return (
          <div
            key={acc.name}
            className="ai7-account-card luma-glass p-5 flex flex-col justify-between"
          >
            <div className="min-w-0">
              <div className="ai7-account-header grid grid-cols-[minmax(0,1fr)_auto] items-start gap-2">
                <div className="flex items-center gap-2.5 min-w-0 flex-1">
                  <span
                    aria-hidden="true"
                    className="ai7-account-icon relative w-9 h-9 rounded-xl border flex items-center justify-center shrink-0"
                  >
                    <CreditCard className="w-4 h-4" />
                    <span className={`absolute bottom-1 right-1 h-1.5 w-1.5 rounded-full ${ACCOUNT_COLOR_DOTS[acc.colorKey] || "bg-luma-ember"}`} />
                  </span>
                  <span className="text-luma-ivory font-semibold text-sm sm:text-base min-w-0 [overflow-wrap:anywhere] leading-snug flex-1">
                    {acc.name}
                  </span>
                </div>

                <div className="flex items-center gap-1 shrink-0 justify-end">
                  {acc.id && onEditAccount && (
                    <button
                      type="button"
                      title={`Ubah rekening ${acc.name}`}
                      aria-label={`Ubah rekening ${acc.name}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        const found = customAccounts.find((c) => c.id === acc.id);
                        onEditAccount(
                          found || {
                            id: acc.id,
                            name: acc.name,
                            type: acc.type,
                            tag: acc.tag,
                            color: "amberGold",
                            current_balance: acc.balance,
                          }
                        );
                      }}
                      className="luma-touch min-w-[44px] inline-flex items-center justify-center text-luma-smoke hover:text-luma-ivory hover:bg-luma-coal transition-colors cursor-pointer"
                    >
                      <Edit2 size={16} aria-hidden="true" />
                    </button>
                  )}
                  {acc.id && onAccountDeleted && (
                    <button
                      type="button"
                      title={`Hapus rekening ${acc.name}`}
                      aria-label={`Hapus rekening ${acc.name}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        setConfirmDelete({ id: acc.id!, name: acc.name });
                      }}
                      className="luma-touch min-w-[44px] inline-flex items-center justify-center text-luma-coral hover:bg-luma-coral/10 transition-colors cursor-pointer"
                    >
                      <Trash2 size={16} aria-hidden="true" />
                    </button>
                  )}
                </div>
              </div>

              <div className="ai7-account-badges flex flex-wrap items-center gap-2 mt-3">
                <span className={`text-xs font-medium px-2.5 py-1 rounded-badge border ${acc.roleBadge.className}`}>
                  {acc.roleBadge.label}
                </span>
                {acc.isPocket && (
                  <span className="text-xs font-medium px-2 py-1 rounded-badge bg-white/[0.05] text-luma-smoke border border-luma-smokeline">
                    {acc.cycleBadge}
                  </span>
                )}
              </div>

              {/* Tag / Deskripsi — full wrap, never clipped */}
              <div className="text-xs text-luma-smoke mt-2 w-full break-words leading-relaxed">
                {acc.tag}
              </div>

              <div className="mt-4">
                <div className="text-xs text-luma-smoke font-semibold ">
                  Saldo rekening
                </div>
                <div className="ai7-type-metric text-luma-ivory mt-1 tracking-tight break-words tabular-nums">
                  {formatRupiah(acc.balance)}
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-luma-smokeline">
              {acc.is_archived ? <p className="text-xs text-luma-smoke">Diarsipkan · tersedia di riwayat</p> : isInvest ? (
                <div className="space-y-1.5">
                  <div className="flex flex-wrap justify-between items-center gap-x-2 gap-y-0.5 text-xs text-luma-sage font-sans">
                    <span className="whitespace-nowrap">Target Portofolio</span>
                    <span className="whitespace-nowrap font-semibold tabular-nums">+{formatRupiah(acc.allocated)}/siklus</span>
                  </div>
                  <div className="h-1.5 bg-black/25 rounded-full overflow-hidden">
                    <div style={{ width: "100%" }} className="h-full bg-luma-sage rounded-full"></div>
                  </div>
                </div>
              ) : hasPlafon ? (
                <div className="space-y-1.5">
                  <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5 text-xs font-sans">
                    <span className="text-luma-smoke whitespace-nowrap">
                      Terpakai{" "}
                      <strong
                        className={
                          pctUsed > 85
                            ? "text-luma-coral"
                            : pctUsed > 60
                            ? "text-luma-gold"
                            : "text-luma-ivory"
                        }
                      >
                        {pctUsed}%
                      </strong>
                    </span>
                    <span className="text-luma-smoke whitespace-nowrap text-right tabular-nums">
                      Plafon:{" "}
                      <strong className="text-luma-ivory font-medium">
                        {formatRupiah(acc.allocated)}
                      </strong>
                    </span>
                  </div>
                  <div
                    className="h-1.5 bg-black/25 rounded-full overflow-hidden"
                    role="progressbar"
                    aria-valuenow={pctUsed}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`Pemakaian ${acc.name} ${pctUsed} persen`}
                  >
                    <div
                      style={{ width: `${pctUsed}%` }}
                      className={`h-full rounded-full ${
                        pctUsed > 85 ? "bg-luma-coral" : pctUsed > 60 ? "bg-luma-gold" : "bg-luma-ember"
                      }`}
                    ></div>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between text-xs text-luma-smoke font-sans py-1">
                  <span>Status</span>
                  <span className={`shrink-0 font-semibold ${acc.balance < 0 ? "text-luma-coral" : "text-luma-smoke"}`}>
                    {acc.balance < 0 ? "Saldo negatif" : acc.balance === 0 ? "Saldo kosong" : "Aktif"}
                  </span>
                </div>
              )}
              {acc.id && !acc.is_archived && onReconciled && <button type="button" onClick={() => setReconcileId(acc.id!)}
                aria-label={"Cocokkan saldo " + acc.name} className="luma-action-secondary mt-3 w-full">Cocokkan saldo</button>}
              {acc.id && onArchiveChanged && <button type="button" className="luma-action-secondary mt-3 w-full"
                disabled={!acc.is_archived && allDisplayAccounts.filter((account) => !account.is_archived).length <= 1}
                aria-label={`${acc.is_archived ? "Aktifkan kembali" : "Arsipkan"} rekening ${acc.name}`}
                onClick={() => { setArchiveError(""); setArchiveTarget({ id: acc.id, name: acc.name, is_archived: acc.is_archived }); }}>
                {acc.is_archived ? "Aktifkan kembali" : "Arsipkan rekening"}
              </button>}

            </div>
          </div>
        );
      })}

      </div>
      <CustomModal isOpen={!!archiveTarget} onClose={() => { if (!archivePending) setArchiveTarget(null); }}
        title={archiveTarget?.is_archived ? "Aktifkan rekening?" : "Arsipkan rekening?"} maxWidth="md">
        <div className="space-y-4">
          <p className="text-sm"><strong>{archiveTarget?.name}</strong></p>
          <p className="text-sm text-luma-smoke">{archiveTarget?.is_archived ? "Rekening akan tersedia lagi untuk transaksi baru." : "Rekening disembunyikan dari pilihan transaksi baru. Saldo dan riwayat tetap tersimpan."}</p>
          {!archiveTarget?.is_archived && <p className="text-sm text-luma-smoke">Jika dipakai sebagai default gaji atau belanja, rekening aktif lain akan menggantikannya.</p>}
          {archiveError && <p role="alert" className="text-sm text-luma-coral">{archiveError}</p>}
          <div className="flex flex-wrap justify-end gap-2">
            <button type="button" disabled={archivePending} className="luma-action-secondary" onClick={() => setArchiveTarget(null)}>Batal</button>
            <button type="button" disabled={archivePending} className="luma-action-primary" onClick={() => void archiveAccount()}>{archivePending ? "Menyimpan…" : archiveTarget?.is_archived ? "Aktifkan kembali" : "Arsipkan"}</button>
          </div>
        </div>
      </CustomModal>
      {/* Modal Konfirmasi Hapus Rekening — Luma smoked glass */}
      {reconcileId !== null && <ReconcileAccountModal key={reconcileId} accountId={reconcileId}
        onClose={() => setReconcileId(null)} onSuccess={() => onReconciled?.()} />}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fadeIn" role="dialog" aria-modal="true" aria-label="Hapus rekening">
          <div className="luma-hero max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-luma-coral">
                <AlertTriangle className="w-5 h-5" />
                <h3 className="ai7-type-card text-luma-ivory">Hapus rekening?</h3>
              </div>
              <button
                type="button"
                aria-label="Tutup dialog"
                onClick={() => { setConfirmDelete(null); setDeleteError(null); }}
                className="luma-touch min-w-[44px] inline-flex items-center justify-center rounded-full text-luma-smoke hover:text-luma-ivory transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-luma-smoke leading-relaxed">
              Apakah Anda yakin ingin menghapus rekening <strong className="text-luma-gold font-sans">{confirmDelete.name}</strong>?
              Seluruh riwayat transaksi yang tercatat pada rekening ini akan ikut dihapus. Minimal Anda harus menyisakan 1 rekening aktif.
            </p>

            {deleteError && (
              <div className="p-3 rounded-2xl bg-luma-coral/10 border border-luma-coral/30 text-luma-coral text-xs">
                {deleteError}
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => { setConfirmDelete(null); setDeleteError(null); }}
                className="luma-touch px-4 py-2 rounded-full bg-white/[0.06] hover:bg-white/[0.1] text-luma-smoke hover:text-luma-ivory text-xs font-semibold border border-luma-smokeline transition"
              >
                Batal
              </button>
              <button
                type="button"
                disabled={isDeleting}
                onClick={handleDeleteAccount}
                className="luma-touch px-4 py-2 rounded-full bg-luma-coral hover:brightness-110 text-luma-charcoal text-xs font-semibold transition inline-flex items-center gap-1.5 disabled:opacity-50"
              >
                {isDeleting ? "Menghapus..." : "Ya, hapus rekening"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
