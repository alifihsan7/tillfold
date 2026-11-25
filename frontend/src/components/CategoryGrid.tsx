"use client";

import React, { useState, useMemo, useId } from "react";
import { CategoryIcon } from "./CategoryIcon";
import { Badge, SegmentedControl } from "./ui/controls";
import {
  Tag,
  Plus,
  Edit2,
  Trash2,
  Loader2,
  AlertCircle,
  AlertTriangle,
} from "@/components/icons";
import { CategoryItem } from "./ManageCategoriesModal";
import { CATEGORY_COLORS, getCategoryColorDef } from "@/lib/categoryColors";
import { Skeleton } from "./ui/Skeleton";
import { CustomModal } from "./ui/CustomModal";
import { CustomSelect, SelectOption } from "./ui/CustomSelect";
import { authFetch } from "@/lib/api";

interface SummaryCategoryItem {
  category: string;
  total: number;
  count: number;
  percentage: number;
}

interface CategoryGridProps {
  categories: CategoryItem[];
  summaryCategories?: SummaryCategoryItem[];
  incomeSummaryCategories?: SummaryCategoryItem[];
  formatRupiah: (val: number) => string;
  loading?: boolean;
  onCategoriesUpdated?: () => void;
  transactions?: { category?: string }[];
  onOpenManageCategories?: () => void;
}

export function CategoryGrid({
  categories,
  summaryCategories = [],
  incomeSummaryCategories = [],
  formatRupiah,
  loading = false,
  onCategoriesUpdated,
  transactions = [],
}: CategoryGridProps) {
  const formId = useId();
  const [filterTab, setFilterTab] = useState<"all" | "expense" | "income">("all");

  // Modal Add state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [addName, setAddName] = useState("");
  const [addType, setAddType] = useState<"expense" | "income">("expense");
  const [addColor, setAddColor] = useState("amberGold");
  const [addLoading, setAddLoading] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  // Modal Edit state
  const [editingCat, setEditingCat] = useState<{
    id: number;
    name: string;
    type: "expense" | "income";
    color: string;
  } | null>(null);
  const [editName, setEditName] = useState("");
  const [editType, setEditType] = useState<"expense" | "income">("expense");
  const [editColor, setEditColor] = useState("amberGold");
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  // Modal Delete state
  const [deletingCat, setDeletingCat] = useState<{
    id: number;
    name: string;
    type: "expense" | "income";
    count?: number;
  } | null>(null);
  const [fallbackCategory, setFallbackCategory] = useState("Lainnya");
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Combine categories with spending data from summary
  const combinedCards = useMemo(() => {
    const list: {
      id: string | number;
      name: string;
      type: "expense" | "income";
      color: string;
      total: number;
      count: number;
      percentage: number;
    }[] = [];

    const seenNames = new Set<string>();

    // 1. Defined categories from API
    (categories || []).forEach((c) => {
      const type = (c.type as "expense" | "income") || "expense";
      seenNames.add(`${type}:${c.name.toLowerCase()}`);
      const stats = (type === "income" ? incomeSummaryCategories : summaryCategories).find(
        (sc) => sc.category.toLowerCase() === c.name.toLowerCase()
      );
      list.push({
        id: c.id,
        name: c.name,
        type,
        color: c.color,
        total: stats ? stats.total : 0,
        count: stats ? stats.count : 0,
        percentage: stats ? stats.percentage : 0,
      });
    });

    // 2. Summary categories not yet explicitly in categories table
    const summaries = [
      ...summaryCategories.map((sc) => ({ ...sc, type: "expense" as const })),
      ...incomeSummaryCategories.map((sc) => ({ ...sc, type: "income" as const })),
    ];
    summaries.forEach((sc, idx) => {
      const key = `${sc.type}:${sc.category.toLowerCase()}`;
      if (!seenNames.has(key)) {
        seenNames.add(key);
        list.push({
          id: `legacy-${idx}-${sc.category}`,
          name: sc.category,
          type: sc.type,
          color: "amberGold",
          total: sc.total,
          count: sc.count,
          percentage: sc.percentage,
        });
      }
    });

    // Sort: categories with spend/count first (descending by total), then alphabetically
    return list.sort((a, b) => {
      if (b.total !== a.total) {
        return b.total - a.total;
      }
      return a.name.localeCompare(b.name);
    });
  }, [categories, summaryCategories, incomeSummaryCategories]);

  // Filtered by tab
  const filteredList = useMemo(() => {
    if (filterTab === "all") return combinedCards;
    return combinedCards.filter((c) => c.type === filterTab);
  }, [combinedCards, filterTab]);

  const expenseCount = combinedCards.filter((c) => c.type === "expense").length;
  const incomeCount = combinedCards.filter((c) => c.type === "income").length;

  // Resolve category ID helper
  const resolveCategoryId = (c: (typeof combinedCards)[0]): number | null => {
    if (typeof c.id === "number") return c.id;
    const match = (categories || []).find(
      (cat) => cat.name.toLowerCase() === c.name.toLowerCase()
    );
    return match ? match.id : null;
  };

  // Open Edit Modal
  const handleOpenEdit = (c: (typeof combinedCards)[0]) => {
    const catId = resolveCategoryId(c);
    if (catId === null) return;
    setEditingCat({
      id: catId,
      name: c.name,
      type: c.type,
      color: c.color || "amberGold",
    });
    setEditName(c.name);
    setEditType(c.type);
    setEditColor(c.color || "amberGold");
    setEditError(null);
  };

  // Open Delete Modal
  const handleOpenDelete = (c: (typeof combinedCards)[0]) => {
    const catId = resolveCategoryId(c);
    if (catId === null) return;

    const sameTypeCats = (categories || [])
      .filter((cat) => cat.type === c.type && cat.id !== catId)
      .map((cat) => cat.name);
    const defaultFallback = c.type === "expense" ? "Lainnya" : "Pemasukan Lain";
    const initialFallback = sameTypeCats.includes(defaultFallback)
      ? defaultFallback
      : sameTypeCats[0] || defaultFallback;

    setFallbackCategory(initialFallback);
    setDeletingCat({
      id: catId,
      name: c.name,
      type: c.type,
      count: c.count,
    });
    setDeleteError(null);
  };

  // Handle Add Category Submit
  const handleAddCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanName = addName.trim();
    if (!cleanName) {
      setAddError("Nama kategori tidak boleh kosong.");
      return;
    }

    setAddLoading(true);
    setAddError(null);
    try {
      const res = await authFetch("/api/v1/categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: cleanName,
          type: addType,
          color: addColor,
        }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail || `Gagal menambahkan kategori (${res.status})`);
      }
      setAddName("");
      setAddColor("amberGold");
      setIsAddModalOpen(false);
      onCategoriesUpdated?.();
    } catch (err: unknown) {
      setAddError(err instanceof Error ? err.message : "Terjadi kesalahan saat menambahkan kategori.");
    } finally {
      setAddLoading(false);
    }
  };

  // Handle Update Category Submit
  const handleUpdateCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingCat) return;
    const cleanName = editName.trim();
    if (!cleanName) {
      setEditError("Nama kategori tidak boleh kosong.");
      return;
    }

    setEditLoading(true);
    setEditError(null);
    try {
      const res = await authFetch(`/api/v1/categories/${editingCat.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: cleanName,
          type: editType,
          color: editColor,
        }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail || `Gagal memperbarui kategori (${res.status})`);
      }
      setEditingCat(null);
      onCategoriesUpdated?.();
    } catch (err: unknown) {
      setEditError(err instanceof Error ? err.message : "Terjadi kesalahan saat memperbarui kategori.");
    } finally {
      setEditLoading(false);
    }
  };

  // Handle Confirm Delete
  const handleConfirmDelete = async () => {
    if (!deletingCat) return;
    setDeleteLoading(true);
    setDeleteError(null);

    let count = deletingCat.count || 0;
    if (transactions && transactions.length > 0) {
      const targetName = deletingCat.name.trim().toLowerCase();
      count = transactions.filter(
        (tx) => (tx.category || "").trim().toLowerCase() === targetName
      ).length;
    }

    let deleteUrl = `/api/v1/categories/${deletingCat.id}`;
    if (count > 0 || fallbackCategory) {
      deleteUrl += `?fallback_to=${encodeURIComponent(fallbackCategory.trim())}`;
    }

    try {
      const res = await authFetch(deleteUrl, { method: "DELETE" });
      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail || `Gagal menghapus kategori (${res.status})`);
      }
      setDeletingCat(null);
      onCategoriesUpdated?.();
    } catch (err: unknown) {
      setDeleteError(err instanceof Error ? err.message : "Terjadi kesalahan saat menghapus kategori.");
    } finally {
      setDeleteLoading(false);
    }
  };

  // Active tx count for delete modal
  const activeDeleteTxCount = useMemo(() => {
    if (!deletingCat) return 0;
    if (transactions && transactions.length > 0) {
      const targetName = deletingCat.name.trim().toLowerCase();
      const count = transactions.filter(
        (tx) => (tx.category || "").trim().toLowerCase() === targetName
      ).length;
      if (count > 0) return count;
    }
    return deletingCat.count || 0;
  }, [deletingCat, transactions]);

  // Fallback select options for delete modal
  const fallbackSelectOptions: SelectOption[] = useMemo(() => {
    if (!deletingCat) return [];
    const sameTypeCats = (categories || [])
      .filter((c) => c.type === deletingCat.type && c.id !== deletingCat.id)
      .map((c) => c.name);

    const defaultFallback = deletingCat.type === "expense" ? "Lainnya" : "Pemasukan Lain";
    if (!sameTypeCats.includes(defaultFallback)) {
      sameTypeCats.push(defaultFallback);
    }
    return sameTypeCats.map((name) => ({ value: name, label: name }));
  }, [deletingCat, categories]);

  return (
    <section className="ai7-section bg-obsidian-panel border border-luma-smokeline rounded-3xl p-5 sm:p-7 space-y-5">
      {/* Header Flex Row */}
      <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Tag className="w-5 h-5 text-luma-secondary" />
            <h2 className="ai7-type-section text-white tracking-tight">
              Kategori pengeluaran & pemasukan
            </h2>
          </div>
          <p className="text-xs sm:text-sm text-luma-smoke mt-0.5">
            Kelompok pengeluaran dan pemasukan beserta total transaksi periode ini.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 w-full xl:w-auto xl:justify-end">
          <SegmentedControl<"all" | "expense" | "income">
            label="Jenis kategori"
            className="fold-category-filters"
            value={filterTab}
            onChange={setFilterTab}
            options={[
              { value: "all", label: <>Semua <span>({combinedCards.length})</span></> },
              { value: "expense", label: <>Pengeluaran <span>({expenseCount})</span></> },
              { value: "income", label: <>Pemasukan <span>({incomeCount})</span></> },
            ]}
          />

          {/* + Tambah Kategori Button */}
          <button
            type="button"
            onClick={() => {
              setAddType(filterTab === "income" ? "income" : "expense");
              setIsAddModalOpen(true);
            }}
            className="luma-action-primary shrink-0"
            title="Tambah kategori transaksi baru"
          >
            <Plus className="w-3.5 h-3.5 shrink-0" />
            <span className="whitespace-nowrap">Tambah kategori</span>
          </button>
        </div>
      </div>

      {/* Loading Skeletons */}
      {loading ? (
        <div className="ai7-category-grid">
          {[...Array(8)].map((_, i) => (
            <div
              key={i}
              className="bg-obsidian-card border border-luma-smokeline rounded-2xl p-4 sm:p-5 space-y-3"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2.5">
                  <Skeleton className="w-8 h-8 rounded-xl" />
                  <div className="space-y-1.5">
                    <Skeleton className="w-24 h-4 rounded-full" />
                    <Skeleton className="w-16 h-3 rounded-full" />
                  </div>
                </div>
                <Skeleton className="w-16 h-4 rounded-full" />
              </div>
              <Skeleton className="w-full h-1.5 rounded-full" />
            </div>
          ))}
        </div>
      ) : filteredList.length === 0 ? (
        <div className="p-8 sm:p-10 text-center bg-obsidian-card/40 rounded-2xl border border-luma-smokeline text-luma-smoke text-xs sm:text-sm space-y-3">
          <p>Belum ada kategori yang sesuai dengan filter ini.</p>
          <button
            type="button"
            onClick={() => {
              setAddType(filterTab === "income" ? "income" : "expense");
              setIsAddModalOpen(true);
            }}
            className="luma-action-primary"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Tambah kategori baru</span>
          </button>
        </div>
      ) : (
        <div key={filterTab} className="ai7-category-grid fold-stagger">
          {filteredList.map((c) => {
            const colorDef = getCategoryColorDef(c.color);
            const isExpense = c.type === "expense";
            const avgSpend = c.count > 0 ? Math.round(c.total / c.count) : 0;

            return (
              <div
                key={c.id}
                className="ai7-category-card bg-obsidian-card border border-luma-smokeline rounded-2xl p-4 sm:p-5 space-y-3 flex flex-col justify-between group"
              >
                <div className="space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div
                        className="fold-category-mark flex size-8 items-center justify-center shrink-0"
                      >
                        <CategoryIcon name={c.name} type={c.type} />
                      </div>
                      <div className="min-w-0">
                        <span className="font-semibold text-sm text-white block truncate" title={c.name}>
                          {c.name}
                        </span>
                        <div className="flex items-center gap-1.5 text-xs font-sans text-luma-smoke mt-0.5">
                          <Badge tone={isExpense ? "neutral" : "positive"}>
                            {isExpense ? "Pengeluaran" : "Pemasukan"}
                          </Badge>
                          <span>•</span>
                          <span className="whitespace-nowrap">{c.count} tx</span>
                        </div>
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <div className="font-sans font-semibold text-sm text-white">
                        {formatRupiah(c.total)}
                      </div>
                      <span
                        className={`text-xs font-sans font-semibold ${
                          c.percentage > 0 ? colorDef.badgeText : "text-luma-smoke"
                        }`}
                      >
                        {c.percentage > 0 ? `${c.percentage.toFixed(1)}%` : "0% total"}
                      </span>
                    </div>
                  </div>

                  {/* Transaction metadata or subtitle + Tactile In-Card Action Buttons */}
                  <div className="text-xs font-sans text-luma-smoke flex items-center justify-between pt-1">
                    <span className="truncate pr-2">
                      {c.count > 0
                        ? `Rata-rata ${formatRupiah(avgSpend)}/tx`
                        : "Belum ada transaksi"}
                    </span>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenEdit(c);
                        }}
                        title={`Edit kategori ${c.name}`}
                        aria-label={`Edit kategori ${c.name}`}
                        className="p-1.5 text-luma-smoke hover:text-luma-ivory hover:bg-luma-coal transition-colors cursor-pointer"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenDelete(c);
                        }}
                        title={`Hapus kategori ${c.name}`}
                        aria-label={`Hapus kategori ${c.name}`}
                        className="p-1.5 text-luma-smoke hover:text-luma-coral hover:bg-luma-coral/10 transition-colors cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Progress Bar */}
                <div className="pt-2">
                  <div className="fold-category-track h-1.5 rounded-full overflow-hidden">
                    <div
                      style={{
                        width: `${c.percentage > 0 ? Math.min(100, Math.max(4, c.percentage)) : 0}%`,
                      }}
                      className={`h-full ${colorDef.dotClass} transition-all duration-500 rounded-full`}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* MODAL TAMBAH KATEGORI */}
      <CustomModal
        isOpen={isAddModalOpen}
        onClose={() => {
          if (!addLoading) {
            setIsAddModalOpen(false);
            setAddError(null);
          }
        }}
        title="Tambah kategori baru"
        subtitle="Buat pos alokasi transaksi baru untuk pengeluaran atau pemasukan."
        icon={<Plus className="w-5 h-5 text-luma-secondary" />}
        accent="amber"
        maxWidth="form"
      >
        <form onSubmit={handleAddCategory} className="grid gap-4 md:grid-cols-2">
          {/* Tipe Selector: Expense vs Income */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-luma-secondary">Tipe kategori</label>
            <SegmentedControl fill label="Tipe kategori" value={addType} onChange={setAddType} options={[
              { value: "expense", label: "Pengeluaran", tone: "expense" },
              { value: "income", label: "Pemasukan", tone: "income" },
            ]} />
          </div>

          {/* Nama Kategori */}
          <div className="space-y-1.5">
            <label htmlFor={`${formId}-add-name`} className="text-xs font-semibold text-luma-secondary">Nama kategori</label>
            <input
              id={`${formId}-add-name`}
              type="text"
              value={addName}
              onChange={(e) => setAddName(e.target.value)}
              placeholder="Contoh: Makan Harian, Langganan AI, Hiburan"
              className="w-full bg-obsidian-card border border-luma-smokeline focus:border-luma-ember/60 rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-luma-smoke outline-none transition"
              autoFocus
            />
          </div>

          {/* Pilihan Warna */}
          <div className="md:col-span-2 space-y-1.5">
            <label className="text-xs font-semibold text-luma-secondary">Warna aksen</label>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
              {CATEGORY_COLORS.map((col) => {
                const isSelected = addColor === col.id;
                return (
                  <button
                    key={col.id}
                    type="button"
                    onClick={() => setAddColor(col.id)}
                    aria-pressed={isSelected}
                    className={`flex items-center gap-1.5 p-2 rounded-xl border text-xs font-medium transition cursor-pointer ${
                      isSelected
                        ? "ui-selected"
                        : "border-luma-smokeline bg-obsidian-card text-luma-smoke hover:text-white hover:border-white/[0.2]"
                    }`}
                  >
                    <span className={`w-3 h-3 rounded-full shrink-0 ${col.dotClass}`} />
                    <span className="truncate">{col.name}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {addError && (
            <div className="md:col-span-2 flex items-center gap-2 p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{addError}</span>
            </div>
          )}

          <div className="md:col-span-2 ui-dialog-actions">
            <button
              type="button"
              onClick={() => setIsAddModalOpen(false)}
              disabled={addLoading}
              className="luma-action-secondary"
            >
              Batal
            </button>
            <button
              type="submit"
              disabled={addLoading || !addName.trim()}
              className="luma-action-primary disabled:cursor-not-allowed"
            >
              {addLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Simpan kategori</span>
            </button>
          </div>
        </form>
      </CustomModal>

      {/* MODAL EDIT KATEGORI */}
      <CustomModal
        isOpen={!!editingCat}
        onClose={() => {
          if (!editLoading) {
            setEditingCat(null);
            setEditError(null);
          }
        }}
        title="Edit kategori"
        subtitle="Perubahan nama otomatis diperbarui ke seluruh riwayat transaksi terkait."
        icon={<Edit2 className="w-5 h-5 text-luma-secondary" />}
        accent="amber"
        maxWidth="form"
      >
        <form onSubmit={handleUpdateCategory} className="grid gap-4 md:grid-cols-2">
          {/* Tipe Selector */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-luma-secondary">Tipe kategori</label>
            <SegmentedControl fill label="Tipe kategori" value={editType} onChange={setEditType} options={[
              { value: "expense", label: "Pengeluaran", tone: "expense" },
              { value: "income", label: "Pemasukan", tone: "income" },
            ]} />
          </div>

          {/* Nama Kategori */}
          <div className="space-y-1.5">
            <label htmlFor={`${formId}-edit-name`} className="text-xs font-semibold text-luma-secondary">Nama kategori</label>
            <input
              id={`${formId}-edit-name`}
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              placeholder="Nama kategori"
              className="w-full bg-obsidian-card border border-luma-smokeline focus:border-luma-ember/60 rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-luma-smoke outline-none transition"
            />
          </div>

          {/* Pilihan Warna */}
          <div className="md:col-span-2 space-y-1.5">
            <label className="text-xs font-semibold text-luma-secondary">Warna aksen</label>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
              {CATEGORY_COLORS.map((col) => {
                const isSelected = editColor === col.id;
                return (
                  <button
                    key={col.id}
                    type="button"
                    onClick={() => setEditColor(col.id)}
                    aria-pressed={isSelected}
                    className={`flex items-center gap-1.5 p-2 rounded-xl border text-xs font-medium transition cursor-pointer ${
                      isSelected
                        ? "ui-selected"
                        : "border-luma-smokeline bg-obsidian-card text-luma-smoke hover:text-white hover:border-white/[0.2]"
                    }`}
                  >
                    <span className={`w-3 h-3 rounded-full shrink-0 ${col.dotClass}`} />
                    <span className="truncate">{col.name}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {editError && (
            <div className="md:col-span-2 flex items-center gap-2 p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{editError}</span>
            </div>
          )}

          <div className="md:col-span-2 ui-dialog-actions">
            <button
              type="button"
              onClick={() => setEditingCat(null)}
              disabled={editLoading}
              className="luma-action-secondary"
            >
              Batal
            </button>
            <button
              type="submit"
              disabled={editLoading || !editName.trim()}
              className="luma-action-primary disabled:cursor-not-allowed"
            >
              {editLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Simpan perubahan</span>
            </button>
          </div>
        </form>
      </CustomModal>

      {/* MODAL HAPUS KATEGORI */}
      <CustomModal
        isOpen={!!deletingCat}
        onClose={() => {
          if (!deleteLoading) {
            setDeletingCat(null);
            setDeleteError(null);
          }
        }}
        title="Hapus kategori"
        subtitle="Konfirmasi penghapusan pos alokasi kategori transaksi."
        icon={<Trash2 className="w-5 h-5 text-coralFall" />}
        accent="coral"
        maxWidth="md"
      >
        <div className="space-y-4">
          <div className="p-3.5 rounded-2xl bg-obsidian-card border border-luma-smokeline flex items-center justify-between">
            <div>
              <div className="text-xs text-luma-smoke">Kategori tujuan</div>
              <div className="text-sm font-semibold text-white mt-0.5">{deletingCat?.name}</div>
            </div>
            <span
              className={`px-2 py-0.5 rounded-md text-xs font-semibold ${
                deletingCat?.type === "expense"
                  ? "bg-rose-500/15 text-rose-300"
                  : "bg-emerald-500/15 text-emerald-300"
              }`}
            >
              {deletingCat?.type === "expense" ? "Pengeluaran" : "Pemasukan"}
            </span>
          </div>

          <div className="space-y-3">
            <div className="flex items-start gap-2.5 p-3 rounded-xl bg-amberGold/10 text-amberGold text-xs leading-relaxed">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>
                {activeDeleteTxCount > 0 && <>{activeDeleteTxCount} transaksi terlihat pada periode ini. </>}
                Riwayat transaksi, tagihan, dan target yang masih memakai kategori ini akan dipindahkan ke kategori tujuan dengan tipe yang sama.
              </span>
            </div>
            <CustomSelect
              label="Kategori tujuan"
              value={fallbackCategory}
              onChange={setFallbackCategory}
              options={fallbackSelectOptions}
              placeholder="Pilih kategori tujuan"
            />
          </div>

          {deleteError && (
            <div className="flex items-center gap-2 p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{deleteError}</span>
            </div>
          )}

          <div className="ui-dialog-actions">
            <button
              type="button"
              onClick={() => setDeletingCat(null)}
              disabled={deleteLoading}
              className="luma-action-secondary"
            >
              Batal
            </button>
            <button
              type="button"
              onClick={handleConfirmDelete}
              disabled={deleteLoading}
              className="ui-btn ui-btn--danger"
            >
              {deleteLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Hapus kategori</span>
            </button>
          </div>
        </div>
      </CustomModal>
    </section>
  );
}
