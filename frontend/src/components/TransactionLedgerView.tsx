import { TransactionCalendar } from "./TransactionCalendar";
import { authFetch } from "@/lib/api";
import { useTransactionHighlights } from "@/lib/useTransactionHighlights";
import { DateField } from "@/components/ui/DateField";
import React, { useState, useMemo, useEffect } from "react";
import {
  Search,
  X,
  RotateCcw,
  ArrowDownRight,
  ArrowUpRight,
  ArrowLeftRight,
  Calendar,
  Filter,
  Plus,
  ChevronLeft,
  ChevronRight,
  Receipt,
} from "lucide-react";
import { CustomSelect, SelectOption } from "./ui/CustomSelect";
import { Skeleton } from "./ui/Skeleton";
import { TransactionTable, Transaction } from "./TransactionTable";
import { CategoryItem } from "./ManageCategoriesModal";

interface AccountTab {
  id: string;
  label: string;
}

interface TransactionLedgerViewProps {
  transactions: Transaction[];
  accounts: AccountTab[];
  categories?: CategoryItem[];
  currentCycle?: {
    start_date: string;
    end_date: string;
    label: string;
  };
  formatRupiah: (val: number) => string;
  onEdit: (tx: Transaction) => void;
  onDelete: (tx: Transaction) => void;
  onOpenAddModal: () => void;
  loading?: boolean;
}

export function TransactionLedgerView({
  transactions,
  accounts,
  categories,
  currentCycle,
  formatRupiah,
  onEdit,
  onDelete,
  onOpenAddModal,
}: TransactionLedgerViewProps) {
  // Filter States
  const [viewMode, setViewMode] = useState<"list" | "calendar">("list");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeAccount, setActiveAccount] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [dateFilter, setDateFilter] = useState("all");
  const [customStartDate, setCustomStartDate] = useState("");
  const [customEndDate, setCustomEndDate] = useState("");
  const [sortBy, setSortBy] = useState("date-desc");

  // Pagination State
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 25;
  const [history, setHistory] = useState<{ items: Transaction[]; total: number; income: number; expense: number; net: number }>({ items: [], total: 0, income: 0, expense: 0, net: 0 });
  const [loading, setLoading] = useState(true);
  const [historyError, setHistoryError] = useState("");
  const [retry, setRetry] = useState(0);
  const { newIds: newTransactionIds, observe: observeTransactions } = useTransactionHighlights();

  // Dynamic Categories from API categories + available transactions
  const categoryOptions: SelectOption[] = useMemo(() => {
    const apiCats = categories ? categories.map((c) => c.name) : [];
    const txCats = [...transactions, ...history.items].map((tx) => tx.category).filter(Boolean);
    const uniqueCats = Array.from(new Set([...apiCats, ...txCats])).sort();

    return [
      { value: "all", label: "Semua kategori" },
      ...uniqueCats.map((cat) => ({ value: cat, label: cat })),
    ];
  }, [categories, transactions, history.items]);

  // Type filter options
  const typeOptions: SelectOption[] = [
    { value: "all", label: "Semua tipe transaksi" },
    { value: "adjustment", label: "Penyesuaian saldo" },
    { value: "expense", label: "Pengeluaran Saja (-)" },
    { value: "income", label: "Pemasukan Saja (+)" },
    { value: "transfer", label: "Transfer antar rekening (⇄)" },
  ];

  // Date preset options
  const dateOptions: SelectOption[] = useMemo(() => {
    const opts: SelectOption[] = [
      { value: "all", label: "Semua waktu" },
    ];
    if (currentCycle?.start_date && currentCycle?.end_date) {
      opts.push({
        value: "cycle",
        label: `Siklus Aktif (${currentCycle.label || "Saat Ini"})`,
      });
    }
    opts.push(
      { value: "this_month", label: "Bulan Ini" },
      { value: "last_7_days", label: "7 Hari Terakhir" },
      { value: "last_30_days", label: "30 Hari Terakhir" },
      { value: "custom", label: "Rentang Tanggal Kustom..." }
    );
    return opts;
  }, [currentCycle]);

  // Sort options
  const sortOptions: SelectOption[] = [
    { value: "date-desc", label: "Tanggal: terbaru → terlama" },
    { value: "date-asc", label: "Tanggal: terlama → terbaru" },
    { value: "amount-desc", label: "Nominal: Terbesar → Terkecil" },
    { value: "amount-asc", label: "Nominal: Terkecil → Terbesar" },
  ];

  const todayStr = new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Jakarta" });
  const daysAgo = (days: number) => {
    const day = new Date(`${todayStr}T12:00:00Z`);
    day.setUTCDate(day.getUTCDate() - days);
    return day.toISOString().slice(0, 10);
  };
  const sevenDaysAgoStr = daysAgo(6);
  const thirtyDaysAgoStr = daysAgo(29);
  const currentYearMonth = todayStr.slice(0, 7);
  const cycleStart = currentCycle?.start_date;
  const cycleEnd = currentCycle?.end_date;

  useEffect(() => {
    if (viewMode !== "list") return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setHistoryError("");
      try {
        const params = new URLSearchParams({ skip: String((currentPage - 1) * pageSize), limit: String(pageSize), sort: sortBy });
        if (activeAccount !== "all") params.set("account", activeAccount);
        if (typeFilter !== "all") params.set("type", typeFilter);
        if (categoryFilter !== "all") params.set("category", categoryFilter);
        if (searchQuery.trim()) params.set("search", searchQuery.trim());
        if (dateFilter === "cycle" && cycleStart && cycleEnd) {
          params.set("start_date", cycleStart);
          params.set("end_date", cycleEnd);
        } else if (dateFilter === "this_month") {
          params.set("start_date", `${currentYearMonth}-01`);
          params.set("end_date", todayStr);
        } else if (dateFilter === "last_7_days" || dateFilter === "last_30_days") {
          params.set("start_date", dateFilter === "last_7_days" ? sevenDaysAgoStr : thirtyDaysAgoStr);
          params.set("end_date", todayStr);
        } else if (dateFilter === "custom") {
          if (customStartDate) params.set("start_date", customStartDate);
          if (customEndDate) params.set("end_date", customEndDate);
        }
        const response = await authFetch(`/api/v1/transactions/history?${params}`, { signal: controller.signal, cache: "no-store" });
        if (!response.ok) throw new Error("Riwayat gagal dimuat. Coba lagi.");
        const data = await response.json();
        if (controller.signal.aborted) return;
        const lastPage = Math.max(1, Math.ceil(data.total / pageSize));
        if (currentPage > lastPage) { setCurrentPage(lastPage); return; }
        observeTransactions(data.items, JSON.stringify([viewMode, params.toString()]));
        setHistory(data);
      } catch (error) {
        if (!controller.signal.aborted) setHistoryError(error instanceof Error ? error.message : "Riwayat gagal dimuat.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, searchQuery.trim() ? 250 : 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [viewMode, transactions, retry, currentPage, sortBy, activeAccount, typeFilter, categoryFilter, searchQuery,
      dateFilter, customStartDate, customEndDate, cycleStart, cycleEnd,
      currentYearMonth, todayStr, sevenDaysAgoStr, thirtyDaysAgoStr, observeTransactions]);

  const totalPages = Math.max(1, Math.ceil(history.total / pageSize));
  const paginatedTransactions = history.items;
  const stats = { count: history.total, income: history.income, expense: history.expense, net: history.net };

  // Active filters count
  const activeFiltersCount = useMemo(() => {
    let count = 0;
    if (searchQuery.trim()) count++;
    if (activeAccount !== "all") count++;
    if (typeFilter !== "all") count++;
    if (categoryFilter !== "all") count++;
    if (dateFilter !== "all") count++;
    if (sortBy !== "date-desc") count++;
    return count;
  }, [searchQuery, activeAccount, typeFilter, categoryFilter, dateFilter, sortBy]);

  // Reset all filters
  const handleResetFilters = () => {
    setSearchQuery("");
    setActiveAccount("all");
    setTypeFilter("all");
    setCategoryFilter("all");
    setDateFilter("all");
    setCustomStartDate("");
    setCustomEndDate("");
    setSortBy("date-desc");
    setCurrentPage(1);
  };

  return (
    <div className="space-y-5">
      <div className="ai7-view-selection flex flex-wrap gap-2" role="group" aria-label="Tampilan transaksi">
        <button type="button" aria-pressed={viewMode === "list"} className={viewMode === "list" ? "luma-action-primary" : "luma-action-secondary"} onClick={() => setViewMode("list")}><Receipt className="h-4 w-4" aria-hidden="true" /> Daftar</button>
        <button type="button" aria-pressed={viewMode === "calendar"} className={viewMode === "calendar" ? "luma-action-primary" : "luma-action-secondary"} onClick={() => setViewMode("calendar")}><Calendar className="h-4 w-4" aria-hidden="true" /> Kalender</button>
      </div>
      {viewMode === "calendar" ? <TransactionCalendar accounts={accounts} account={activeAccount} onAccountChange={(value) => { setActiveAccount(value); setCurrentPage(1); }}
        refreshSignal={transactions} formatRupiah={formatRupiah} onEdit={onEdit} onDelete={onDelete} /> : <>
      <p className="text-sm text-luma-smoke">“Semua waktu” mencakup seluruh riwayat, di luar periode dashboard.</p>
      {historyError && <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-luma-coral">
        <span>{historyError}</span><button type="button" className="luma-action-secondary" onClick={() => setRetry((value) => value + 1)}>Coba lagi</button>
      </div>}
      {/* 1. QUICK-STATS KPI BAR (REAL-TIME AGGREGATES) */}
      <div className="ai7-metric-grid grid gap-4">
        {/* Total Transaksi */}
        <div className="bg-obsidian-card border border-luma-smokeline rounded-2xl p-4 sm:p-5 flex flex-col justify-between shadow-sm">
          <div className="flex items-center justify-between gap-2 text-zinc-400">
            <span className="text-xs font-medium truncate">Total transaksi</span>
            <Receipt className="w-4 h-4 text-luma-smoke shrink-0" />
          </div>
          <div className="mt-2.5">
            {loading ? (
              <Skeleton className="h-7 w-20 rounded-full" />
            ) : (
              <div className="ai7-type-metric text-white tracking-tight">
                {stats.count}{" "}
                <span className="text-xs font-normal text-zinc-400">item</span>
              </div>
            )}
            <p className="text-xs text-zinc-400 mt-0.5 truncate">
              {activeFiltersCount > 0 ? "Berdasarkan filter aktif" : "Seluruh catatan kas"}
            </p>
          </div>
        </div>

        {/* Total Pemasukan */}
        <div className="bg-obsidian-card border border-luma-smokeline rounded-2xl p-4 sm:p-5 flex flex-col justify-between shadow-sm">
          <div className="flex items-center justify-between gap-2 text-zinc-400">
            <span className="text-xs font-medium truncate">Total pemasukan</span>
            <div className="w-6 h-6 rounded-full bg-mintRise/15 border border-mintRise/30 flex items-center justify-center text-mintRise shrink-0">
              <ArrowDownRight className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="mt-2.5">
            {loading ? (
              <Skeleton className="h-7 w-28 rounded-full" />
            ) : (
              <div className="ai7-type-metric text-mintRise tracking-tight truncate">
                +{formatRupiah(stats.income)}
              </div>
            )}
            <p className="text-xs text-zinc-400 mt-0.5 truncate">
              Pemasukan sesuai filter
            </p>
          </div>
        </div>

        {/* Total Pengeluaran */}
        <div className="bg-obsidian-card border border-luma-smokeline rounded-2xl p-4 sm:p-5 flex flex-col justify-between shadow-sm">
          <div className="flex items-center justify-between gap-2 text-zinc-400">
            <span className="text-xs font-medium truncate">Total pengeluaran</span>
            <div className="w-6 h-6 rounded-full bg-coralFall/15 border border-coralFall/30 flex items-center justify-center text-coralFall shrink-0">
              <ArrowUpRight className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="mt-2.5">
            {loading ? (
              <Skeleton className="h-7 w-28 rounded-full" />
            ) : (
              <div className="ai7-type-metric text-coralFall tracking-tight truncate">
                -{formatRupiah(stats.expense)}
              </div>
            )}
            <p className="text-xs text-zinc-400 mt-0.5 truncate">
              Pengeluaran sesuai filter
            </p>
          </div>
        </div>

        {/* Arus Kas Bersih (Net Flow) */}
        <div className="bg-obsidian-card border border-luma-smokeline rounded-2xl p-4 sm:p-5 flex flex-col justify-between shadow-sm">
          <div className="flex items-center justify-between gap-2 text-zinc-400">
            <span className="text-xs font-medium truncate">Arus kas bersih</span>
            <div className="w-6 h-6 rounded-full bg-cyanHub/15 border border-cyanHub/30 flex items-center justify-center text-cyanHub shrink-0">
              <ArrowLeftRight className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="mt-2.5">
            {loading ? (
              <Skeleton className="h-7 w-28 rounded-full" />
            ) : (
              <div
                className={`ai7-type-metric tracking-tight truncate ${
                  stats.net >= 0 ? "text-mintRise" : "text-coralFall"
                }`}
              >
                {stats.net >= 0 ? "+" : "-"}
                {formatRupiah(Math.abs(stats.net))}
              </div>
            )}
            <p className="text-xs text-zinc-400 mt-0.5 truncate">
              {stats.net >= 0 ? "Surplus kas terfilter" : "Defisit kas terfilter"}
            </p>
          </div>
        </div>
      </div>

      {/* 2. FILTER & CONTROL PANEL */}
      <div className="bg-obsidian-panel border border-luma-smokeline rounded-3xl p-5 sm:p-6 space-y-4 shadow-sm">
        {/* Top Control Bar: Search & Account Pills */}
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-3">
          {/* Account Tabs */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 lg:pb-0 w-full lg:w-auto max-w-full">
            {accounts.map((tab) => (
              <button
                key={tab.id}
                type="button"
                aria-pressed={activeAccount === tab.id}
                onClick={() => {
                  setActiveAccount(tab.id);
                  setCurrentPage(1);
                }}
                className={`ai7-account-selection text-xs px-3.5 py-1.5 rounded-full font-medium transition-all whitespace-nowrap shrink-0 cursor-pointer ${
                  activeAccount === tab.id
                    ? "text-slate-950 bg-amberGold font-semibold shadow-sm"
                    : "text-zinc-400 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-luma-smokeline"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Search Bar & Quick Add */}
          <div className="flex items-center gap-2 w-full lg:w-auto shrink-0 justify-end">
            <div className="relative flex-1 lg:w-64">
              <Search className="w-4 h-4 text-zinc-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setCurrentPage(1);
                }}
                placeholder="Cari transaksi, ket, atau akun..."
                className="w-full bg-obsidian-card border border-luma-smokeline rounded-2xl pl-10 pr-8 py-2 text-xs sm:text-sm text-white placeholder-zinc-400 focus:outline-none focus:border-amberGold transition font-sans"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-white p-0.5 rounded cursor-pointer"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            <button
              type="button"
              onClick={onOpenAddModal}
              className="px-4 py-2 bg-amberGold text-slate-950 hover:bg-amber-300 font-semibold text-xs sm:text-sm rounded-2xl transition shadow-sm flex items-center gap-1.5 shrink-0 cursor-pointer active:scale-95"
            >
              <Plus className="w-4 h-4 stroke-[2.5]" />
              <span className="hidden sm:inline">Catat transaksi</span>
            </button>
          </div>
        </div>

        {/* Bottom Filter Controls: Type, Category, Date, Sort */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-3 border-t border-luma-smokeline">
          {/* Filter Tipe Transaksi */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1">
              Tipe transaksi
            </label>
            <CustomSelect
              value={typeFilter}
              onChange={(val) => {
                setTypeFilter(val);
                setCurrentPage(1);
              }}
              options={typeOptions}
              accent="amber"
              className="text-xs"
            />
          </div>

          {/* Filter Kategori */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1">
              Kategori
            </label>
            <CustomSelect
              value={categoryFilter}
              onChange={(val) => {
                setCategoryFilter(val);
                setCurrentPage(1);
              }}
              options={categoryOptions}
              accent="amber"
              className="text-xs"
            />
          </div>

          {/* Filter Rentang Tanggal */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1">
              Rentang waktu
            </label>
            <CustomSelect
              value={dateFilter}
              onChange={(val) => {
                setDateFilter(val);
                setCurrentPage(1);
              }}
              options={dateOptions}
              accent="amber"
              className="text-xs"
            />
          </div>

          {/* Pengurutan (Sort By) */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1">
              Urutkan berdasarkan
            </label>
            <CustomSelect
              value={sortBy}
              onChange={(val) => {
                setSortBy(val);
                setCurrentPage(1);
              }}
              options={sortOptions}
              accent="amber"
              className="text-xs"
            />
          </div>
        </div>

        {/* Conditional Custom Date Range Picker */}
        {dateFilter === "custom" && (
          <div className="p-3.5 rounded-2xl bg-obsidian-card border border-luma-smokeline flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 text-xs text-zinc-300">
              <Calendar className="w-4 h-4 text-amberGold shrink-0" />
              <span className="font-medium">Rentang Tanggal Kustom:</span>
            </div>
            <div className="grid min-w-0 flex-1 gap-2 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] sm:items-start">
              <DateField label="Tanggal mulai"
                value={customStartDate}
                onChange={(dateValue) => {
                  setCustomStartDate(dateValue);
                  setCurrentPage(1);
                }}
              />
              <span className="text-zinc-400 text-xs">s/d</span>
              <DateField label="Tanggal selesai"
                value={customEndDate}
                onChange={(dateValue) => {
                  setCustomEndDate(dateValue);
                  setCurrentPage(1);
                }}
              />
            </div>
          </div>
        )}

        {/* Active Filters Bar & Reset Action */}
        {activeFiltersCount > 0 && (
          <div className="flex items-center justify-between pt-1 text-xs">
            <div className="flex items-center gap-2 text-zinc-400 font-medium">
              <Filter className="w-3.5 h-3.5 text-amberGold" />
              <span>
                Menampilkan hasil dengan{" "}
                <strong className="text-amberGold font-sans">{activeFiltersCount}</strong> filter aktif
              </span>
            </div>
            <button
              type="button"
              onClick={handleResetFilters}
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium text-zinc-300 hover:text-coralFall hover:bg-coralFall/10 border border-luma-smokeline hover:border-coralFall/30 transition cursor-pointer"
            >
              <RotateCcw className="w-3 h-3" />
              Reset semua filter
            </button>
          </div>
        )}
      </div>

      {/* 3. TRANSACTION TABLE */}
      <div className="space-y-3">
        <TransactionTable
          transactions={paginatedTransactions}
          newTransactionIds={newTransactionIds}
          formatRupiah={formatRupiah}
          onEdit={onEdit}
          onDelete={onDelete}
          loading={loading}
        />

        {/* 4. PAGINATION FOOTER */}
        {history.total > pageSize && (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-2 pt-1 text-xs text-zinc-400 font-sans">
            <div>
              Menampilkan{" "}
              <strong className="text-white">
                {(currentPage - 1) * pageSize + 1}
              </strong>{" "}
              -{" "}
              <strong className="text-white">
                {Math.min(currentPage * pageSize, history.total)}
              </strong>{" "}
              dari{" "}
              <strong className="text-white">
                {history.total}
              </strong>{" "}
              transaksi terfilter
            </div>

            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={loading || currentPage === 1}
                className="p-2 rounded-xl border border-luma-smokeline bg-obsidian-card hover:bg-white/[0.06] text-white disabled:opacity-40 disabled:cursor-not-allowed transition cursor-pointer"
                title="Halaman sebelumnya" aria-label="Halaman sebelumnya"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>

              <div className="px-3.5 py-1.5 rounded-xl bg-obsidian-card border border-luma-smokeline text-white font-semibold">
                {currentPage} / {totalPages}
              </div>

              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={loading || currentPage === totalPages}
                className="p-2 rounded-xl border border-luma-smokeline bg-obsidian-card hover:bg-white/[0.06] text-white disabled:opacity-40 disabled:cursor-not-allowed transition cursor-pointer"
                title="Halaman berikutnya" aria-label="Halaman berikutnya"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
      </>}
    </div>
  );
}
