"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  Tag,
  Plus,
  Edit2,
  Trash2,
  Check,
  AlertCircle,
  Loader2,
  AlertTriangle,
  ArrowRight,
  Layers,
} from "lucide-react";
import { CustomModal } from "./ui/CustomModal";
import { CustomSelect } from "./ui/CustomSelect";
import { authFetch } from "@/lib/api";
import { CATEGORY_COLORS, getCategoryColorDef } from "@/lib/categoryColors";

export interface CategoryItem {
  id: number;
  name: string;
  type: string; // "expense" | "income"
  color: string;
  icon?: string | null;
  created_at?: string;
}

interface TransactionCountSource {
  category: string;
}

interface ManageCategoriesModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCategoriesUpdated: () => void;
  transactions?: TransactionCountSource[];
  initialTab?: "expense" | "income";
}

export function ManageCategoriesModal({
  isOpen,
  onClose,
  onCategoriesUpdated,
  transactions = [],
  initialTab = "expense",
}: ManageCategoriesModalProps) {
  // Navigation tab
  const [activeTab, setActiveTab] = useState<"expense" | "income">(initialTab);

  // Categories list
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Create form state
  const [newName, setNewName] = useState("");
  const [newColor, setNewColor] = useState("amberGold");
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Edit state (inline per category)
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editColor, setEditColor] = useState("amberGold");
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  // Delete & Fallback Modal State
  const [deletingCat, setDeletingCat] = useState<CategoryItem | null>(null);
  const [fallbackCategory, setFallbackCategory] = useState<string>("Lainnya");
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Reset tab when reopened or prop changes
  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab);
    }
  }, [isOpen, initialTab]);

  // Fetch categories from API
  const fetchCategories = useCallback(async () => {
    try {
      setLoading(true);
      setFetchError(null);
      const res = await authFetch("/api/v1/categories");
      if (!res.ok) {
        throw new Error(`Gagal memuat kategori (${res.status})`);
      }
      const data: CategoryItem[] = await res.json();
      if (Array.isArray(data)) {
        setCategories(data);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Terjadi kesalahan saat memuat data";
      setFetchError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      fetchCategories();
      setCreateError(null);
      setEditError(null);
      setEditingId(null);
      setDeletingCat(null);
    }
  }, [isOpen, fetchCategories]);

  // Transaction count lookup by category name (case-insensitive)
  const transactionCounts = useMemo(() => {
    const map = new Map<string, number>();
    for (const tx of transactions) {
      if (!tx.category) continue;
      const key = tx.category.trim().toLowerCase();
      map.set(key, (map.get(key) || 0) + 1);
    }
    return map;
  }, [transactions]);

  const getTxCount = (catName: string): number => {
    return transactionCounts.get(catName.trim().toLowerCase()) || 0;
  };

  // Filter categories by active tab
  const expenseCategories = useMemo(
    () => categories.filter((c) => c.type === "expense"),
    [categories]
  );
  const incomeCategories = useMemo(
    () => categories.filter((c) => c.type === "income"),
    [categories]
  );
  const currentList = activeTab === "expense" ? expenseCategories : incomeCategories;

  // Handle Add Category
  const handleCreateCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanName = newName.trim();
    if (!cleanName) {
      setCreateError("Nama kategori tidak boleh kosong");
      return;
    }

    setCreateLoading(true);
    setCreateError(null);

    try {
      const res = await authFetch("/api/v1/categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: cleanName,
          type: activeTab,
          color: newColor,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        const errMsg = errJson?.detail || `Gagal menambahkan kategori (${res.status})`;
        throw new Error(errMsg);
      }

      setNewName("");
      // Keep selected color or cycle, clear errors
      await fetchCategories();
      onCategoriesUpdated();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal menambahkan kategori";
      setCreateError(msg);
    } finally {
      setCreateLoading(false);
    }
  };

  // Start inline editing
  const startEdit = (cat: CategoryItem) => {
    setEditingId(cat.id);
    setEditName(cat.name);
    setEditColor(cat.color || "amberGold");
    setEditError(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditName("");
    setEditError(null);
  };

  // Submit Edit Category
  const handleUpdateCategory = async (catId: number) => {
    const cleanName = editName.trim();
    if (!cleanName) {
      setEditError("Nama kategori tidak boleh kosong");
      return;
    }

    setEditLoading(true);
    setEditError(null);

    try {
      const res = await authFetch(`/api/v1/categories/${catId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: cleanName,
          type: activeTab,
          color: editColor,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        const errMsg = errJson?.detail || `Gagal memperbarui kategori (${res.status})`;
        throw new Error(errMsg);
      }

      setEditingId(null);
      await fetchCategories();
      onCategoriesUpdated();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal memperbarui kategori";
      setEditError(msg);
    } finally {
      setEditLoading(false);
    }
  };

  // Trigger Delete confirmation / fallback flow
  const initiateDelete = (cat: CategoryItem) => {
    setDeletingCat(cat);
    setDeleteError(null);

    // Default fallback category suggestion
    const sameTypeCats = categories
      .filter((c) => c.type === cat.type && c.id !== cat.id)
      .map((c) => c.name);

    if (cat.type === "expense") {
      const hasLainnya = sameTypeCats.includes("Lainnya");
      setFallbackCategory(hasLainnya ? "Lainnya" : sameTypeCats[0] || "Lainnya");
    } else {
      const hasPemasukanLain = sameTypeCats.includes("Pemasukan Lain");
      setFallbackCategory(hasPemasukanLain ? "Pemasukan Lain" : sameTypeCats[0] || "Pemasukan Lain");
    }
  };

  // Execute Delete
  const handleConfirmDelete = async () => {
    if (!deletingCat) return;

    setIsDeleting(true);
    setDeleteError(null);

    const txCount = getTxCount(deletingCat.name);
    const hasTransactions = txCount > 0;

    let deleteUrl = `/api/v1/categories/${deletingCat.id}`;
    if (hasTransactions || fallbackCategory) {
      deleteUrl += `?fallback_to=${encodeURIComponent(fallbackCategory.trim())}`;
    }

    try {
      const res = await authFetch(deleteUrl, {
        method: "DELETE",
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        const errMsg = errJson?.detail || `Gagal menghapus kategori (${res.status})`;
        throw new Error(errMsg);
      }

      setDeletingCat(null);
      await fetchCategories();
      onCategoriesUpdated();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal menghapus kategori";
      setDeleteError(msg);
    } finally {
      setIsDeleting(false);
    }
  };

  // Fallback options available for the deleting category
  const fallbackOptions = useMemo(() => {
    if (!deletingCat) return [];
    const list = categories
      .filter((c) => c.type === deletingCat.type && c.id !== deletingCat.id)
      .map((c) => c.name);

    const defaultFallback = deletingCat.type === "expense" ? "Lainnya" : "Pemasukan Lain";
    if (!list.includes(defaultFallback)) {
      list.push(defaultFallback);
    }
    return list;
  }, [deletingCat, categories]);

  return (
    <CustomModal
      isOpen={isOpen}
      onClose={onClose}
      title="Kelola kategori transaksi"
      subtitle="Atur kategori pengeluaran dan pemasukan. Nama kategori yang diubah ikut diperbarui di semua transaksinya."
      icon={<Tag className="w-5 h-5" />}
      accent={activeTab === "expense" ? "coral" : "mint"}
      maxWidth="lg"
    >
      <div className="space-y-5">
        {/* TAB SWITCHER: Pengeluaran vs Pemasukan */}
        <div className="grid grid-cols-2 gap-2 bg-obsidian-panel p-1.5 rounded-2xl border border-luma-smokeline">
          <button
            type="button"
            onClick={() => {
              setActiveTab("expense");
              setEditingId(null);
              setCreateError(null);
            }}
            className={`py-2 px-3 text-xs sm:text-sm font-semibold rounded-xl transition flex items-center justify-center gap-2 cursor-pointer ${
              activeTab === "expense"
                ? "bg-coralFall text-slate-950 font-semibold shadow-sm"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <span>Pengeluaran</span>
            <span
              className={`text-xs font-sans px-2 py-0.5 rounded-full ${
                activeTab === "expense"
                  ? "bg-slate-950/25 text-slate-950 font-semibold"
                  : "bg-white/[0.06] text-zinc-400"
              }`}
            >
              {expenseCategories.length}
            </span>
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab("income");
              setEditingId(null);
              setCreateError(null);
            }}
            className={`py-2 px-3 text-xs sm:text-sm font-semibold rounded-xl transition flex items-center justify-center gap-2 cursor-pointer ${
              activeTab === "income"
                ? "bg-mintRise text-slate-950 font-semibold shadow-sm"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <span>Pemasukan</span>
            <span
              className={`text-xs font-sans px-2 py-0.5 rounded-full ${
                activeTab === "income"
                  ? "bg-slate-950/25 text-slate-950 font-semibold"
                  : "bg-white/[0.06] text-zinc-400"
              }`}
            >
              {incomeCategories.length}
            </span>
          </button>
        </div>

        {/* FORM TAMBAH KATEGORI BARU */}
        <form
          onSubmit={handleCreateCategory}
          className="bg-obsidian-panel/90 border border-luma-smokeline rounded-2xl p-4 sm:p-5 space-y-3.5 shadow-xs"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5">
              <Plus className="w-3.5 h-3.5 text-luma-smoke" aria-hidden="true" />
              Tambah kategori {activeTab === "expense" ? "Pengeluaran" : "Pemasukan"}
            </span>
            <span className="text-xs text-zinc-400 font-sans">
              Badge: <span className="text-zinc-300">{getCategoryColorDef(newColor).name}</span>
            </span>
          </div>

          {/* Name input */}
          <div>
            <input
              type="text"
              value={newName}
              onChange={(e) => {
                setNewName(e.target.value);
                if (createError) setCreateError(null);
              }}
              placeholder={
                activeTab === "expense"
                  ? "Contoh: Jajanan Sore, Skincare, Alat Kantor..."
                  : "Contoh: Gaji Tambahan, Dividen, Freelance..."
              }
              className="w-full bg-obsidian-card border border-luma-smokeline rounded-2xl px-3.5 py-2.5 text-xs sm:text-sm text-white placeholder-zinc-400 focus:outline-none focus:border-luma-ember transition"
            />
          </div>

          {/* Color Badge Picker */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">
              Warna label
            </label>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
              {CATEGORY_COLORS.map((c) => {
                const isSelected = newColor === c.id;
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setNewColor(c.id)}
                    className={`py-1.5 px-2 rounded-xl text-xs font-medium border flex items-center justify-center gap-1.5 transition cursor-pointer ${
                      isSelected
                        ? `${c.badgeBg} ${c.badgeBorder} ${c.badgeText} ring-2 ring-luma-ember/60 font-semibold shadow-xs`
                        : "bg-obsidian-card/60 border-luma-smokeline text-zinc-400 hover:text-white hover:border-white/[0.12]"
                    }`}
                  >
                    <span className={`w-2 h-2 rounded-full ${c.dotClass} shrink-0`} />
                    <span className="truncate text-xs">{c.name.split(" ")[0]}</span>
                    {isSelected && <Check className="w-3 h-3 ml-0.5 shrink-0" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Error Message */}
          {createError && (
            <div className="p-2.5 rounded-xl bg-coralFall/10 border border-coralFall/20 text-coralFall text-xs flex items-center gap-2 animate-fadeIn">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{createError}</span>
            </div>
          )}

          {/* Submit button */}
          <div className="flex justify-end pt-1">
            <button
              type="submit"
              disabled={createLoading || !newName.trim()}
              className="luma-action-primary disabled:cursor-not-allowed"
            >
              {createLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Menyimpan...</span>
                </>
              ) : (
                <>
                  <Plus className="w-4 h-4 stroke-[2.5]" />
                  <span>Tambah kategori</span>
                </>
              )}
            </button>
          </div>
        </form>

        {/* DAFTAR KATEGORI AKTIF */}
        <div className="space-y-2.5">
          <div className="flex items-center justify-between px-1">
            <h4 className="text-xs font-semibold text-zinc-400 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-zinc-400" />
              Daftar Kategori {activeTab === "expense" ? "Pengeluaran" : "Pemasukan"} ({currentList.length})
            </h4>
            {loading && (
              <span className="text-xs text-zinc-400 font-sans flex items-center gap-1">
                <Loader2 className="w-3 h-3 animate-spin text-luma-smoke" /> Memuat...
              </span>
            )}
          </div>

          {fetchError && (
            <div className="p-3 rounded-2xl bg-coralFall/10 border border-coralFall/20 text-coralFall text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{fetchError}</span>
            </div>
          )}

          {/* Category List Scrollable Container */}
          <div className="max-h-[320px] overflow-y-auto space-y-2 pr-1 custom-scrollbar">
            {currentList.length === 0 && !loading ? (
              <div className="p-8 text-center bg-obsidian-panel/50 rounded-2xl border border-luma-smokeline text-zinc-400 text-xs">
                Belum ada kategori {activeTab === "expense" ? "pengeluaran" : "pemasukan"}. Buat kategori baru di atas.
              </div>
            ) : (
              currentList.map((cat) => {
                const isEditing = editingId === cat.id;
                const txCount = getTxCount(cat.name);
                const colorDef = getCategoryColorDef(cat.color);

                if (isEditing) {
                  return (
                    <div
                      key={cat.id}
                      className="p-3 bg-obsidian-panel border border-luma-smokeline rounded-2xl space-y-3 animate-fadeIn"
                    >
                      <div className="text-xs font-semibold text-luma-ivory flex items-center gap-1">
                        <Edit2 className="w-3 h-3" /> Edit kategori
                      </div>

                      {/* Edit Name input */}
                      <input
                        type="text"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        className="w-full bg-obsidian-card border border-luma-smokeline rounded-xl px-3 py-2 text-xs sm:text-sm text-white focus:outline-none focus:border-luma-ember transition"
                        placeholder="Nama kategori"
                        autoFocus
                      />

                      {/* Edit Color chips */}
                      <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
                        {CATEGORY_COLORS.map((c) => {
                          const isSel = editColor === c.id;
                          return (
                            <button
                              key={c.id}
                              type="button"
                              onClick={() => setEditColor(c.id)}
                              className={`py-1 px-1.5 rounded-lg text-xs font-medium border flex items-center justify-center gap-1 transition cursor-pointer ${
                                isSel
                                  ? `${c.badgeBg} ${c.badgeBorder} ${c.badgeText} ring-2 ring-luma-ember/60 font-semibold`
                                  : "bg-obsidian-card/70 border-luma-smokeline text-zinc-400 hover:text-white"
                              }`}
                            >
                              <span className={`w-1.5 h-1.5 rounded-full ${c.dotClass}`} />
                              <span className="truncate">{c.name.split(" ")[0]}</span>
                            </button>
                          );
                        })}
                      </div>

                      {editError && (
                        <div className="p-2 rounded-xl bg-coralFall/10 border border-coralFall/20 text-coralFall text-xs">
                          {editError}
                        </div>
                      )}

                      <div className="flex justify-end gap-2 pt-1">
                        <button
                          type="button"
                          onClick={cancelEdit}
                          disabled={editLoading}
                          className="luma-action-secondary"
                        >
                          Batal
                        </button>
                        <button
                          type="button"
                          onClick={() => handleUpdateCategory(cat.id)}
                          disabled={editLoading || !editName.trim()}
                          className="luma-action-primary"
                        >
                          {editLoading ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Check className="w-3.5 h-3.5" />
                          )}
                          <span>Simpan</span>
                        </button>
                      </div>
                    </div>
                  );
                }

                return (
                  <div
                    key={cat.id}
                    className="flex items-center justify-between p-3 rounded-2xl bg-obsidian-panel/80 hover:bg-obsidian-panel border border-luma-smokeline hover:border-white/[0.12] transition group"
                  >
                    {/* Left: Badge, Name, Tx Count */}
                    <div className="flex items-center gap-2.5 min-w-0 pr-2">
                      <span
                        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border whitespace-nowrap ${colorDef.badgeBg} ${colorDef.badgeBorder} ${colorDef.badgeText}`}
                      >
                        <span className={`w-1.5 h-1.5 rounded-full ${colorDef.dotClass} shrink-0`} />
                        <span className="font-semibold">{cat.name}</span>
                      </span>

                      <span
                        className="text-xs font-sans text-zinc-400 bg-white/[0.03] px-2 py-0.5 rounded-md border border-luma-smokeline shrink-0"
                        title={`${txCount} transaksi tercatat dengan kategori ini`}
                      >
                        {txCount} tx
                      </span>
                    </div>

                    {/* Right: Actions (Edit & Delete) */}
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        type="button"
                        onClick={() => startEdit(cat)}
                        title="Edit kategori"
                        className="p-1.5 rounded-xl text-zinc-400 hover:text-luma-ivory hover:bg-luma-coal border border-transparent transition cursor-pointer"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>

                      <button
                        type="button"
                        onClick={() => initiateDelete(cat)}
                        title="Hapus kategori"
                        className="p-1.5 rounded-xl text-zinc-400 hover:text-coralFall hover:bg-coralFall/10 border border-transparent hover:border-coralFall/20 transition cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* FOOTER ACTION */}
        <div className="pt-3 border-t border-luma-smokeline flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2.5 text-xs sm:text-sm font-semibold text-zinc-300 hover:text-white bg-obsidian-card hover:bg-obsidian-hover border border-luma-smokeline rounded-2xl transition cursor-pointer"
          >
            Selesai
          </button>
        </div>
      </div>

      {/* CONFIRMATION & FALLBACK REASSIGNMENT SUB-MODAL */}
      {deletingCat && (
        <div className="fixed inset-0 z-60 bg-black/85 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150">
          <div className="bg-obsidian-card border border-luma-smokeline rounded-3xl p-5 sm:p-6 w-full max-w-md shadow-2xl space-y-4 animate-in zoom-in-95 duration-150">
            <div className="flex items-start gap-3">
              <div className="p-2.5 rounded-2xl bg-coralFall/15 text-coralFall border border-coralFall/30 shrink-0">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="ai7-type-card text-white">
                  Hapus kategori &quot;{deletingCat.name}&quot;?
                </h3>
                <p className="text-xs text-zinc-400 mt-0.5">
                  {getTxCount(deletingCat.name) > 0 ? (
                    <span>
                      Kategori ini digunakan oleh{" "}
                      <strong className="text-luma-ivory font-sans">
                        {getTxCount(deletingCat.name)} transaksi
                      </strong>
                      . Tentukan kategori tujuan untuk memindahkan transaksi terkait.
                    </span>
                  ) : (
                    <span>Kategori ini belum memiliki transaksi terkait dan aman untuk dihapus.</span>
                  )}
                </p>
              </div>
            </div>

            {/* If transactions exist, show fallback target selector */}
            {getTxCount(deletingCat.name) > 0 && (
              <div className="space-y-2 bg-obsidian-panel p-3.5 rounded-2xl border border-luma-smokeline">
                <label className="block text-xs font-semibold text-zinc-300 flex items-center gap-1.5">
                  <ArrowRight className="w-3.5 h-3.5 text-luma-smoke" aria-hidden="true" />
                  Pindahkan transaksi ke kategori
                </label>
                <CustomSelect
                  value={fallbackCategory}
                  onChange={(val) => setFallbackCategory(val)}
                  options={fallbackOptions.map((opt) => ({
                    value: opt,
                    label: opt,
                  }))}
                  accent="amber"
                  placeholder="Pilih kategori tujuan..."
                />
                <p className="text-xs text-zinc-400">
                  Transaksi, tagihan rutin, atau target tabungan yang memakai &quot;{deletingCat.name}&quot; akan dialihkan ke &quot;{fallbackCategory}&quot;.
                </p>
              </div>
            )}

            {deleteError && (
              <div className="p-3 rounded-2xl bg-coralFall/10 border border-coralFall/20 text-coralFall text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{deleteError}</span>
              </div>
            )}

            <div className="flex justify-end gap-2.5 pt-2 border-t border-luma-smokeline">
              <button
                type="button"
                onClick={() => setDeletingCat(null)}
                disabled={isDeleting}
                className="luma-action-secondary"
              >
                Batal
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                className="px-4 py-2 text-xs font-semibold text-slate-950 bg-coralFall hover:brightness-110 rounded-xl transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Menghapus...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>
                      {getTxCount(deletingCat.name) > 0 ? "Pindahkan & hapus" : "Hapus kategori"}
                    </span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </CustomModal>
  );
}
