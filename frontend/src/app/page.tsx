"use client";

import { DateField } from "@/components/ui/DateField";
import { useTransactionHighlights } from "@/lib/useTransactionHighlights";
import { todayWib } from "@/lib/transactionCalendar";
import React, { useState, useEffect, useMemo, useRef, useCallback } from "react";
import {
  Plus,
  Search,
  Download,
  RefreshCw,
  ChevronDown,
  CreditCard,
  ArrowDownLeft,
  CheckCircle2,
  Layers,
  Bell,
  BarChart2,
  LayoutDashboard,
  ArrowLeftRight,
  ArrowRight,
  Clock,
  Calendar,
  Menu,
  X,
  FileSpreadsheet,
  ExternalLink,
  Copy,
  Check,
  Target,
  AlertCircle,
  Receipt,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
  WalletCards,
} from "lucide-react";
import { StrataAllocationBar } from "@/components/StrataAllocation";
import { LumaOverview } from "@/components/LumaOverview";
import { LumaAccountStrip } from "@/components/LumaAccountStrip";
import { LumaRecentTransactions } from "@/components/LumaRecentTransactions";
import { AccountGrid } from "@/components/AccountGrid";
import { CategoryGrid } from "@/components/CategoryGrid";
import { SmartBudgetEnvelopes } from "@/components/MandiriEnvelopes";
import { AccountPockets } from "@/components/AccountPockets";
import { InternalLoansWidget } from "@/components/InternalLoansWidget";
import { Transaction } from "@/components/TransactionTable";
import { BurnRateChart } from "@/components/BurnRateChart";
import { TransactionLedgerView } from "@/components/TransactionLedgerView";
import { SubscriptionsView, SubscriptionItem, SubscriptionsData } from "@/components/SubscriptionsView";
import { GoalsView } from "@/components/GoalsView";
import { AddGoalModal } from "@/components/AddGoalModal";
import { EditGoalModal, GoalItem } from "@/components/EditGoalModal";
import { TransferModal } from "@/components/TransferModal";
import { AddAccountModal } from "@/components/AddAccountModal";
import { EditAccountModal } from "@/components/EditAccountModal";
import { EditTransactionModal } from "@/components/EditTransactionModal";
import { EditSubscriptionModal } from "@/components/EditSubscriptionModal";
import { ManageCategoriesModal, CategoryItem } from "@/components/ManageCategoriesModal";
import { AddTransactionModal } from "@/components/AddTransactionModal";
import PaycheckModal from "@/components/PaycheckModal";
import { RecordPaycheckModal } from "@/components/RecordPaycheckModal";
import { AccountItem } from "@/components/AccountGrid";
import { CustomModal } from "@/components/ui/CustomModal";
import { CustomSelect, SelectOption } from "@/components/ui/CustomSelect";
import { CurrencyInput } from "@/components/ui/CurrencyInput";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { Skeleton } from "@/components/ui/Skeleton";

import { PeriodSelector, PeriodOption } from "@/components/PeriodSelector";
import { AnalyticsView } from "@/components/AnalyticsView";
import { AuthModal } from "@/components/AuthModal";
import { OnboardingWizardModal } from "@/components/OnboardingWizardModal";
import { ThemeToggle } from "@/components/ThemeToggle";
import { UserProfileModal } from "@/components/UserProfileModal";
import { GlobalSearchModal, SearchResult } from "@/components/GlobalSearchModal";
import { BackupModal } from "@/components/BackupModal";
import {
  authFetch,
  getAuthToken,
  setStoredUser,
  setAuthToken,
  UserProfile,
  PocketsSummaryResponse,
  syncGoogleSheets,
} from "@/lib/api";
import { DashboardLoadError, loadDashboardData } from "@/lib/dashboardData";
import { getCategoryColorDef } from "@/lib/categoryColors";

interface MonthlySummary {
  period_type?: string;
  period_label?: string;
  start_date?: string;
  end_date?: string;
  month: string;
  income: number;
  expense: number;
  net: number;
  savings_rate: number;
  total_balance: number;
  accounts: { account: string; balance: number; expense?: number }[];
  categories: { category: string; total: number; count: number; percentage: number }[];
  income_categories?: { category: string; total: number; count: number; percentage: number }[];
  daily_trend?: { date: string; income: number; expense: number }[];
  safe_to_spend?: {
    cycle_start: string;
    cycle_end: string;
    cycle_type?: string;
    cycle_days?: number;
    pocket_account?: string;
    day_of_cycle: number;
    days_remaining: number;
    pocket_budget: number;
    pocket_spent: number;
    pocket_remaining: number;
    safe_daily: number;
    pace_status: "ahead" | "on_track" | "warning";
    ideal_pace_today: number;
    burn_chart: {
      day: number;
      date: string;
      spent: number;
      cumulative_spent: number;
      ideal_pace: number;
    }[];
  };
}

const TX_ACCOUNT_OPTIONS = [
  { value: "Rekening Utama", label: "Rekening Utama (Operasional)", color: "bg-blue-500", description: "Pos belanja harian & saku" },
  { value: "Rekening Tagihan", label: "Rekening Tagihan (Subs & Bills)", color: "bg-purple-500", description: "Pos langganan rutin" },
  { value: "Investasi", label: "Investasi (Portofolio)", color: "bg-teal-500", description: "Portofolio tabungan investasi" },
  { value: "Dana Darurat", label: "Dana darurat (Cadangan Likuid)", color: "bg-cyan-500", description: "Pos cadangan dana darurat" },
  { value: "Cash", label: "Cash (Uang Tunai)", color: "bg-amber-500", description: "Uang tunai fisik" },
];

const TX_CATEGORY_OPTIONS = [
  { value: "Makanan & Minuman", label: "Makanan & Minuman" },
  { value: "Jajan / Ngopi", label: "Jajan / Ngopi" },
  { value: "Laundry", label: "Laundry" },
  { value: "Galon / Air", label: "Galon / Air" },
  { value: "Pendidikan & Tools", label: "Pendidikan & Tools" },
  { value: "Perawatan Diri", label: "Perawatan Diri" },
  { value: "Social & Hiburan", label: "Social & Hiburan" },
  { value: "Kesehatan & Gym", label: "Kesehatan & Gym" },
  { value: "Langganan & Servis", label: "Langganan & Servis" },
  { value: "Keluarga & Sosial", label: "Keluarga & Sosial" },
  { value: "Dana Darurat", label: "Dana darurat" },
  { value: "Lainnya", label: "Lainnya" },
];

const SUB_CATEGORY_OPTIONS = [
  { value: "Produktivitas & AI", label: "Produktivitas & AI" },
  { value: "Hiburan / Streaming", label: "Hiburan / Streaming" },
  { value: "Cloud Backup", label: "Cloud Backup" },
  { value: "Gym & Fitness", label: "Gym & Fitness" },
  { value: "Tagihan Utilitas", label: "Tagihan Utilitas" },
  { value: "Lainnya", label: "Lainnya" },
];

const NAV_SLUGS: Record<string, string> = {
  "Ringkasan": "#/overview",
  "Transaksi": "#/transactions",
  "Anggaran": "#/budget",
  "Rencana": "#/plan",
  "Laporan": "#/reports",
  "Pengaturan": "#/settings",
};

const SLUG_TO_NAV: Record<string, string> = {
  // Ringkasan
  "#/overview": "Ringkasan",
  "/overview": "Ringkasan",
  "overview": "Ringkasan",
  "#/ringkasan": "Ringkasan",
  "/ringkasan": "Ringkasan",
  "ringkasan": "Ringkasan",

  // Transaksi (sebelumnya Buku Transaksi / Ledger)
  "#/transactions": "Transaksi",
  "/transactions": "Transaksi",
  "transactions": "Transaksi",
  "#/transaksi": "Transaksi",
  "/transaksi": "Transaksi",
  "transaksi": "Transaksi",
  "#/ledger": "Transaksi",
  "/ledger": "Transaksi",
  "ledger": "Transaksi",
  "#/buku-transaksi": "Transaksi",
  "/buku-transaksi": "Transaksi",
  "buku-transaksi": "Transaksi",

  // Anggaran (Pos Amplop Belanja & Alokasi Peran Finansial)
  "#/budget": "Anggaran",
  "/budget": "Anggaran",
  "budget": "Anggaran",
  "#/anggaran": "Anggaran",
  "/anggaran": "Anggaran",
  "anggaran": "Anggaran",
  "#/envelopes": "Anggaran",
  "/envelopes": "Anggaran",
  "envelopes": "Anggaran",
  "#/alokasi-amplop": "Anggaran",
  "/alokasi-amplop": "Anggaran",
  "alokasi-amplop": "Anggaran",
  "#/amplop": "Anggaran",
  "/amplop": "Anggaran",
  "amplop": "Anggaran",

  // Rencana (Target Tabungan + Tagihan)
  "#/plan": "Rencana",
  "/plan": "Rencana",
  "plan": "Rencana",
  "#/rencana": "Rencana",
  "/rencana": "Rencana",
  "rencana": "Rencana",
  "#/goals": "Rencana",
  "/goals": "Rencana",
  "goals": "Rencana",
  "#/target-finansial": "Rencana",
  "/target-finansial": "Rencana",
  "target-finansial": "Rencana",
  "#/target-tabungan": "Rencana",
  "/target-tabungan": "Rencana",
  "target-tabungan": "Rencana",
  "#/target": "Rencana",
  "/target": "Rencana",
  "target": "Rencana",
  "#/subscriptions": "Rencana",
  "/subscriptions": "Rencana",
  "subscriptions": "Rencana",
  "#/langganan": "Rencana",
  "/langganan": "Rencana",
  "langganan": "Rencana",
  "#/tagihan": "Rencana",
  "/tagihan": "Rencana",
  "tagihan": "Rencana",
  "#/plan/target": "Rencana",
  "/plan/target": "Rencana",
  "plan/target": "Rencana",
  "#/plan/tagihan": "Rencana",
  "/plan/tagihan": "Rencana",
  "plan/tagihan": "Rencana",
  "#/rencana/target": "Rencana",
  "/rencana/target": "Rencana",
  "rencana/target": "Rencana",
  "#/rencana/tagihan": "Rencana",
  "/rencana/tagihan": "Rencana",
  "rencana/tagihan": "Rencana",

  // Laporan (sebelumnya Analisis & Tren / Analytics)
  "#/reports": "Laporan",
  "/reports": "Laporan",
  "reports": "Laporan",
  "#/laporan": "Laporan",
  "/laporan": "Laporan",
  "laporan": "Laporan",
  "#/analytics": "Laporan",
  "/analytics": "Laporan",
  "analytics": "Laporan",
  "#/analisis": "Laporan",
  "/analisis": "Laporan",
  "analisis": "Laporan",

  // Pengaturan (sebelumnya Akun & Kategori / Settings)
  "#/settings": "Pengaturan",
  "/settings": "Pengaturan",
  "settings": "Pengaturan",
  "#/pengaturan": "Pengaturan",
  "/pengaturan": "Pengaturan",
  "pengaturan": "Pengaturan",
  "#/accounts": "Pengaturan",
  "/accounts": "Pengaturan",
  "accounts": "Pengaturan",
  "#/rekening": "Pengaturan",
  "/rekening": "Pengaturan",
  "rekening": "Pengaturan",
  "#/akun": "Pengaturan",
  "/akun": "Pengaturan",
  "akun": "Pengaturan",
  "#/categories": "Pengaturan",
  "/categories": "Pengaturan",
  "categories": "Pengaturan",
  "#/kategori": "Pengaturan",
  "/kategori": "Pengaturan",
  "kategori": "Pengaturan",
  "#/pockets": "Pengaturan",
  "/pockets": "Pengaturan",
  "pockets": "Pengaturan",
  "#/kantong": "Pengaturan",
  "/kantong": "Pengaturan",
  "kantong": "Pengaturan",
  "#/settings/pockets": "Pengaturan",
  "/settings/pockets": "Pengaturan",
  "settings/pockets": "Pengaturan",
  "#/pengaturan/kantong": "Pengaturan",
  "/pengaturan/kantong": "Pengaturan",
  "pengaturan/kantong": "Pengaturan",
  "#/settings/rekening": "Pengaturan",
  "/settings/rekening": "Pengaturan",
  "settings/rekening": "Pengaturan",
  "#/pengaturan/rekening": "Pengaturan",
  "/pengaturan/rekening": "Pengaturan",
  "pengaturan/rekening": "Pengaturan",
  "#/settings/kategori": "Pengaturan",
  "/settings/kategori": "Pengaturan",
  "settings/kategori": "Pengaturan",
  "#/pengaturan/kategori": "Pengaturan",
  "/pengaturan/kategori": "Pengaturan",
  "pengaturan/kategori": "Pengaturan",
  "#/settings/categories": "Pengaturan",
  "/settings/categories": "Pengaturan",
  "settings/categories": "Pengaturan",
  "#/settings/profile": "Pengaturan",
  "/settings/profile": "Pengaturan",
  "settings/profile": "Pengaturan",
  "#/pengaturan/profil": "Pengaturan",
  "/pengaturan/profil": "Pengaturan",
  "pengaturan/profil": "Pengaturan",
  "#/profile": "Pengaturan",
  "/profile": "Pengaturan",
  "profile": "Pengaturan",
  "#/profil": "Pengaturan",
  "/profil": "Pengaturan",
  "profil": "Pengaturan",
  "#/preferences": "Pengaturan",
  "/preferences": "Pengaturan",
  "preferences": "Pengaturan",
  "#/preferensi": "Pengaturan",
  "/preferensi": "Pengaturan",
  "preferensi": "Pengaturan",
};

function handleTabArrowKeys(event: React.KeyboardEvent<HTMLDivElement>) {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button[role="tab"]'));
  const current = tabs.findIndex((tab) => tab === event.target);
  if (current < 0) return;

  event.preventDefault();
  const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 :
    (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
  tabs[next].focus();
  tabs[next].click();
}

export default function FinanceDashboard() {
  const [activeNav, setActiveNav] = useState<string>("Ringkasan");
  const [planSubTab, setPlanSubTab] = useState<"target" | "tagihan">("target");
  const [settingsSubTab, setSettingsSubTab] = useState<"rekening" | "kantong" | "kategori" | "profil">("rekening");
  const [profileModalTab, setProfileModalTab] = useState<"profile" | "telegram" | "sheets">("profile");
  const [isSyncingSheets, setIsSyncingSheets] = useState(false);
  const [copiedSettingsEmail, setCopiedSettingsEmail] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [hideOverviewBalances, setHideOverviewBalances] = useState(false);
  const [sidebarMotion, setSidebarMotion] = useState(false);
  useEffect(() => {
    setSidebarCollapsed(localStorage.getItem("ai7_sidebar_collapsed") === "true");
  }, []);
  const toggleSidebar = () => {
    setSidebarMotion(true);
    setSidebarCollapsed((collapsed) => {
      const next = !collapsed;
      localStorage.setItem("ai7_sidebar_collapsed", String(next));
      return next;
    });
  };
  const mainContentRef = useRef<HTMLElement>(null);
  const dashboardRequestRef = useRef(0);
  const dashboardBusyRef = useRef(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isGlobalSearchOpen, setIsGlobalSearchOpen] = useState(false);
  const [isPaycheckModalOpen, setIsPaycheckModalOpen] = useState(false);
  const [isPayrollSettingsOpen, setIsPayrollSettingsOpen] = useState(false);
  const [isSubModalOpen, setIsSubModalOpen] = useState(false);
  const [isTransferModalOpen, setIsTransferModalOpen] = useState(false);
  const [isAddAccountModalOpen, setIsAddAccountModalOpen] = useState(false);
  const [accountToEdit, setAccountToEdit] = useState<AccountItem | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const toastTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const showToast = useCallback((msg: string) => {
    if (toastTimeoutRef.current) {
      clearTimeout(toastTimeoutRef.current);
    }
    setToastMessage(msg);
    toastTimeoutRef.current = setTimeout(() => {
      setToastMessage(null);
    }, 3500);
  }, []);

  const handleSyncSheets = useCallback(async () => {
    if (isSyncingSheets) return;
    setIsSyncingSheets(true);
    try {
      const res = await syncGoogleSheets();
      showToast(`Google Sheets berhasil disinkronkan (${res.sheet_title || "Snapshot"}).`);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Gagal menyinkronkan data ke Google Sheets.");
    } finally {
      setIsSyncingSheets(false);
    }
  }, [isSyncingSheets, showToast]);

  const handleCopySettingsEmail = useCallback(async () => {
    try {
      await navigator.clipboard.writeText("tillfold@tillfold.iam.gserviceaccount.com");
      setCopiedSettingsEmail(true);
      setTimeout(() => setCopiedSettingsEmail(false), 2000);
    } catch {
      showToast("Salin manual: tillfold@tillfold.iam.gserviceaccount.com");
    }
  }, [showToast]);

  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
  const [isExportMenuOpen, setIsExportMenuOpen] = useState(false);
  const [isExportingCSV, setIsExportingCSV] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);
  const [customAccounts, setCustomAccounts] = useState<AccountItem[]>([]);
  const activeAccounts = useMemo(() => customAccounts.filter((account) => !account.is_archived), [customAccounts]);
  const availableAccountNames = useMemo(() => {
    if (customAccounts.length > 0) {
      return customAccounts.filter((account) => !account.is_archived).map((a) => a.name);
    }
    return ["Rekening Utama", "Uang Tunai (Cash)", "Tabungan"];
  }, [customAccounts]);
  const [loading, setLoading] = useState(true);

  // Period filter state
  const [isBackupModalOpen, setIsBackupModalOpen] = useState(false);
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodOption>({
    id: "cycle_current",
    type: "cycle",
    label: "Memuat Siklus...",
    start: "",
    end: "",
    is_current: true,
  });
  const [activePaycheckSession, setActivePaycheckSession] = useState<{
    id: number;
    total_amount: number;
    date: string;
    status: string;
    completed_steps: number;
    total_steps: number;
    progress_percentage: number;
  } | null>(null);
  const [subToDelete, setSubToDelete] = useState<number | null>(null);
  const [txToDelete, setTxToDelete] = useState<Transaction | null>(null);
  const [deleteTxError, setDeleteTxError] = useState("");
  const [txToEdit, setTxToEdit] = useState<Transaction | null>(null);
  const [goals, setGoals] = useState<GoalItem[]>([]);
  const [isAddGoalModalOpen, setIsAddGoalModalOpen] = useState(false);
  const [goalToEdit, setGoalToEdit] = useState<GoalItem | null>(null);
  const [goalToDelete, setGoalToDelete] = useState<number | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Dynamic Categories & Manage Categories Modal state
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [isManageCategoriesOpen, setIsManageCategoriesOpen] = useState(false);

  // Dynamic category options derived from API categories
  const dynamicTxCategoryOptions: SelectOption[] = useMemo(() => {
    if (categories.length > 0) {
      return categories.map((c) => {
        const colorDef = getCategoryColorDef(c.color);
        return {
          value: c.name,
          label: `${c.name} (${c.type === "expense" ? "Pengeluaran" : "Pemasukan"})`,
          color: colorDef.dotClass,
        };
      });
    }
    return TX_CATEGORY_OPTIONS;
  }, [categories]);

  // Form state for new subscription
  const [subName, setSubName] = useState("");
  const [subAmount, setSubAmount] = useState("");
  const [subCategory, setSubCategory] = useState("Lainnya");
  const [subAccount, setSubAccount] = useState("");
  const [subBillingType, setSubBillingType] = useState<"fixed_day" | "exact_date" | "yearly">("fixed_day");
  const [subBillingDay, setSubBillingDay] = useState("1");
  const [subExactDueDate, setSubExactDueDate] = useState("");
  const [subNotes, setSubNotes] = useState("");
  const [subToEdit, setSubToEdit] = useState<SubscriptionItem | null>(null);

  // Paycheck configuration & buckets state
  const [paycheckConfig, setPaycheckConfig] = useState<{ id?: number; total_salary?: number; pocket_account?: string; source_account?: string; cycle_days?: number; cycle_type?: string } | null>(null);
  const [paycheckBuckets, setPaycheckBuckets] = useState<{ account: string; percentage: number; purpose?: string }[]>([]);

  const billAccountOptions = useMemo(() => {
    const options = activeAccounts.map(({ name }) => ({ value: name, label: name }));
    if (subToEdit?.account && !options.some((option) => option.value === subToEdit.account)) {
      options.push({ value: subToEdit.account, label: `${subToEdit.account} (arsip)` });
    }
    return options;
  }, [activeAccounts, subToEdit?.account]);

  // Auto-sync subAccount to available accounts
  useEffect(() => {
    setSubAccount((previous) =>
      billAccountOptions.some((account) => account.value === previous) ? previous : activeAccounts[0]?.name || ""
    );
  }, [activeAccounts, billAccountOptions]);

  // SPA Hash Routing sync & browser Back/Forward navigation listener
  useEffect(() => {
    const handleHashSync = () => {
      const rawHash = window.location.hash;
      const cleanHash = rawHash.replace(/^#\/?/, "").replace(/\/+$/, "").toLowerCase();

      // Backward-compatible & deep-linking sub-tab detection
      if (
        cleanHash === "subscriptions" ||
        cleanHash === "langganan" ||
        cleanHash === "tagihan" ||
        cleanHash === "plan/tagihan" ||
        cleanHash === "rencana/tagihan" ||
        cleanHash === "plan/subscriptions"
      ) {
        setActiveNav("Rencana");
        setPlanSubTab("tagihan");
        return;
      }
      if (
        cleanHash === "goals" ||
        cleanHash === "target-finansial" ||
        cleanHash === "target-tabungan" ||
        cleanHash === "target" ||
        cleanHash === "plan/target" ||
        cleanHash === "rencana/target" ||
        cleanHash === "plan/goals"
      ) {
        setActiveNav("Rencana");
        setPlanSubTab("target");
        return;
      }
      if (
        cleanHash === "categories" ||
        cleanHash === "kategori" ||
        cleanHash === "settings/categories" ||
        cleanHash === "pengaturan/kategori" ||
        cleanHash === "settings/kategori" ||
        cleanHash === "pengaturan/categories"
      ) {
        setActiveNav("Pengaturan");
        setSettingsSubTab("kategori");
        return;
      }
      if (
        cleanHash === "accounts" ||
        cleanHash === "rekening" ||
        cleanHash === "akun" ||
        cleanHash === "settings/accounts" ||
        cleanHash === "pengaturan/rekening" ||
        cleanHash === "settings/rekening" ||
        cleanHash === "pengaturan/accounts"
      ) {
        setActiveNav("Pengaturan");
        setSettingsSubTab("rekening");
        return;
      }
      if (
        cleanHash === "pockets" ||
        cleanHash === "kantong" ||
        cleanHash === "settings/pockets" ||
        cleanHash === "pengaturan/kantong" ||
        cleanHash === "settings/kantong" ||
        cleanHash === "pengaturan/pockets"
      ) {
        setActiveNav("Pengaturan");
        setSettingsSubTab("kantong");
        return;
      }
      if (
        cleanHash === "profile" ||
        cleanHash === "profil" ||
        cleanHash === "preferences" ||
        cleanHash === "preferensi" ||
        cleanHash === "settings/profile" ||
        cleanHash === "pengaturan/profil" ||
        cleanHash === "settings/preferences" ||
        cleanHash === "pengaturan/preferensi"
      ) {
        setActiveNav("Pengaturan");
        setSettingsSubTab("profil");
        return;
      }
      if (cleanHash === "settings" || cleanHash === "pengaturan") {
        setActiveNav("Pengaturan");
        setSettingsSubTab("rekening");
        return;
      }
      if (cleanHash === "plan" || cleanHash === "rencana") {
        setActiveNav("Rencana");
        setPlanSubTab("target");
        return;
      }

      const matched = SLUG_TO_NAV[rawHash] || SLUG_TO_NAV[cleanHash] || SLUG_TO_NAV["#" + cleanHash] || SLUG_TO_NAV["#/" + cleanHash];
      if (matched) {
        setActiveNav(matched);
      } else if (!rawHash || rawHash === "#" || rawHash === "#/") {
        window.location.hash = "#/overview";
      }
    };

    handleHashSync();
    window.addEventListener("hashchange", handleHashSync);
    return () => window.removeEventListener("hashchange", handleHashSync);
  }, []);

  // Update URL hash and auto-scroll viewport when activeNav changes
  useEffect(() => {
    const rawHash = window.location.hash;
    const cleanHash = rawHash.replace(/^#\/?/, "").replace(/\/+$/, "").toLowerCase();
    const currentNav = SLUG_TO_NAV[rawHash] || SLUG_TO_NAV[cleanHash] || SLUG_TO_NAV["#" + cleanHash] || SLUG_TO_NAV["#/" + cleanHash];

    // Only overwrite hash if navigating to a different main section, so subtab URLs are retained
    if (currentNav !== activeNav) {
      const targetHash = NAV_SLUGS[activeNav];
      if (targetHash && window.location.hash !== targetHash) {
        window.location.hash = targetHash;
      }
    }
    if (mainContentRef.current) {
      mainContentRef.current.scrollTop = 0;
    }
  }, [activeNav]);

  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const { newIds: newTransactionIds, observe: observeTransactions } = useTransactionHighlights();
  const [overviewError, setOverviewError] = useState<string | null>(null);

  const [summary, setSummary] = useState<MonthlySummary>({
    month: "",
    income: 0,
    expense: 0,
    net: 0,
    savings_rate: 0,
    total_balance: 0,
    accounts: [],
    categories: [],
  });

  const [subsData, setSubsData] = useState<SubscriptionsData>({
    total_monthly_commitment: 0,
    active_count: 0,
    upcoming_this_week: 0,
    items: [],
  });

  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [isOnboardingModalOpen, setIsOnboardingModalOpen] = useState(false);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [pocketsRefreshSignal, setPocketsRefreshSignal] = useState(0);
  const [loansRefreshSignal, setLoansRefreshSignal] = useState(0);
  const [pocketsData, setPocketsData] = useState<PocketsSummaryResponse | null>(null);

  const pocketsCount = (pocketsData?.pockets ?? pocketsData?.items)?.length ?? 0;

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(event.target as Node)) {
        setIsExportMenuOpen(false);
      }
    };
    if (isExportMenuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isExportMenuOpen]);

  // Mobile drawer keyboard accessibility & scroll lock
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isMobileDrawerOpen) {
        setIsMobileDrawerOpen(false);
      }
    };
    if (isMobileDrawerOpen) {
      document.body.style.overflow = "hidden";
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.body.style.overflow = "unset";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isMobileDrawerOpen]);

  useEffect(() => {
    const initUser = async () => {
      try {
        // Cek integrasi Telegram Mini App (TWA)
        if (typeof window !== "undefined" && window.Telegram?.WebApp) {
          const tg = window.Telegram.WebApp;
          try {
            tg.ready();
            tg.expand();
            if (typeof tg.setHeaderColor === "function") tg.setHeaderColor("#090A0D");
            if (typeof tg.setBackgroundColor === "function") tg.setBackgroundColor("#090A0D");
          } catch (e) {
            console.warn("Telegram WebApp init warning:", e);
          }

          // Jika ada initData valid dari Telegram WebApp, autentikasi otomatis
          if (tg.initData && tg.initData.length > 0) {
            try {
              const tgRes = await fetch("/api/v1/auth/telegram-webapp", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ init_data: tg.initData }),
              });
              if (tgRes.ok) {
                const authData = await tgRes.json();
                setAuthToken(authData.access_token);
                setStoredUser(authData.user);
                setCurrentUser(authData.user);
                setIsAuthModalOpen(false);
                if (!authData.user.is_onboarded) {
                  setIsOnboardingModalOpen(true);
                }
                setLoading(false);
                return;
              }
            } catch (err) {
              console.error("Gagal auto-login Telegram WebApp:", err);
            }
          }
        }

        const token = getAuthToken();
        if (!token) {
          setCurrentUser(null);
          setStoredUser(null);
          setIsAuthModalOpen(true);
          setLoading(false);
          return;
        }

        const res = await authFetch("/api/v1/auth/me");
        if (res.ok) {
          const u = await res.json();
          setCurrentUser(u);
          setStoredUser(u);
          if (!u.is_onboarded) {
            setIsOnboardingModalOpen(true);
          }
        } else {
          // Token tidak valid atau kedaluwarsa
          setAuthToken(null);
          setStoredUser(null);
          setCurrentUser(null);
          setIsAuthModalOpen(true);
        }
      } catch {
        setAuthToken(null);
        setStoredUser(null);
        setCurrentUser(null);
        setIsAuthModalOpen(true);
      } finally {
        setLoading(false);
      }
    };
    initUser();
  }, []);

  const fetchDashboard = async (background = false) => {
    if (background && dashboardBusyRef.current) return;
    dashboardBusyRef.current = true;
    const requestId = ++dashboardRequestRef.current;
    if (!background) setOverviewError(null);
    const token = getAuthToken();
    if (!token) {
      setTransactions([]);
      setCategories([]);
      setSummary({
        month: "",
        income: 0,
        expense: 0,
        net: 0,
        savings_rate: 0,
        total_balance: 0,
        accounts: [],
        categories: [],
      });
      setSubsData({
        total_monthly_commitment: 0,
        active_count: 0,
        upcoming_this_week: 0,
        items: [],
      });
      setCustomAccounts([]);
      setGoals([]);
      setActivePaycheckSession(null);
      setLoading(false);
      dashboardBusyRef.current = false;
      return;
    }

    try {
      if (!background) setLoading(true);

      const data = await loadDashboardData(authFetch, selectedPeriod);
      if (requestId !== dashboardRequestRef.current) return;
      setOverviewError(null);
      if (Array.isArray(data.transactions)) {
        observeTransactions(data.transactions, JSON.stringify([currentUser?.id, selectedPeriod.id, selectedPeriod.start, selectedPeriod.end]));
        setTransactions(data.transactions);
      }
      if (data.summary) {
        setSummary(data.summary);
        if (!selectedPeriod.start && data.summary.start_date) {
          setSelectedPeriod({
            id: `cycle_${data.summary.start_date}`,
            type: data.summary.period_type || "cycle",
            label: data.summary.period_label || "Siklus Aktif",
            start: data.summary.start_date,
            end: data.summary.end_date,
            is_current: true,
          });
        }
      }

      if (data.subscriptions) setSubsData(data.subscriptions);
      if (Array.isArray(data.accounts)) setCustomAccounts(data.accounts);
      if (Array.isArray(data.goals)) setGoals(data.goals);
      setActivePaycheckSession(data.session?.id && data.session.status === "in_progress" ? data.session : null);
      if (data.paycheck?.config) setPaycheckConfig(data.paycheck.config);
      if (Array.isArray(data.paycheck?.buckets)) setPaycheckBuckets(data.paycheck.buckets);
      if (Array.isArray(data.categories)) setCategories(data.categories);

      // Refresh account pockets after any ledger-affecting fetch.
      setPocketsRefreshSignal((prev) => prev + 1);
    } catch (err) {
      if (requestId !== dashboardRequestRef.current) return;
      if (err instanceof DashboardLoadError && err.status === 401) setIsAuthModalOpen(true);
      setOverviewError(err instanceof Error ? err.message : "Koneksi terputus. Coba muat ulang ringkasan.");
      console.error("Fetch error:", err);
    } finally {
      if (requestId === dashboardRequestRef.current) { setLoading(false); dashboardBusyRef.current = false; }
    }
  };

  const fetchData = () => {
    fetchDashboard();
    setLoansRefreshSignal((s) => s + 1);
  };

  useEffect(() => {
    if (currentUser) {
      fetchData();
    }
  }, [selectedPeriod, currentUser]);

  const externalRefreshRef = useRef(() => {});
  externalRefreshRef.current = () => { if (currentUser) void fetchDashboard(true); };
  useEffect(() => {
    if (!currentUser) return;
    const refresh = () => { if (document.visibilityState === "visible") externalRefreshRef.current(); };
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    const interval = window.setInterval(refresh, 30000);
    return () => {
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
      window.clearInterval(interval);
    };
  }, [currentUser]);

  useEffect(() => {
    if (!currentUser) return;
    const openSearch = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "k" || event.repeat ||
        target?.closest("input, textarea, select, [contenteditable=true]") || document.querySelector('[role="dialog"]')) return;
      event.preventDefault();
      setIsExportMenuOpen(false);
      setIsGlobalSearchOpen(true);
    };
    window.addEventListener("keydown", openSearch);
    return () => window.removeEventListener("keydown", openSearch);
  }, [currentUser]);

  const chooseSearchResult = (result: SearchResult) => {
    setIsGlobalSearchOpen(false);
    if (result.kind === "transaction") {
      setActiveNav("Transaksi"); window.location.hash = "#/transactions"; setTxToEdit(result.data);
    } else if (result.kind === "account") {
      setActiveNav("Pengaturan"); setSettingsSubTab("rekening"); window.location.hash = "#/accounts"; setAccountToEdit(result.data);
    } else if (result.kind === "bill") {
      setActiveNav("Rencana"); setPlanSubTab("tagihan"); window.location.hash = "#/tagihan"; setSubToEdit(result.data);
    } else {
      setActiveNav("Rencana"); setPlanSubTab("target"); window.location.hash = "#/plan"; setGoalToEdit(result.data);
    }
  };

  const formatRupiah = (val: number) => {
    return new Intl.NumberFormat("id-ID", {
      style: "currency",
      currency: "IDR",
      maximumFractionDigits: 0,
    }).format(val);
  };

  // Dynamic account options for modals
  const availableAccountOptions = useMemo(() => {
    if (activeAccounts.length > 0) {
      return activeAccounts.map((ca) => ({
        value: ca.name,
        label: ca.name,
      }));
    }
    return TX_ACCOUNT_OPTIONS.map(({ value }) => ({ value, label: value }));
  }, [activeAccounts]);

  // Dynamic tab list for transaction filtering
  const allAccountTabs = useMemo(() => {
    const tabs = [{ id: "all", label: "Semua" }];
    if (customAccounts.length > 0) {
      customAccounts.forEach((ca) => {
        tabs.push({ id: ca.name, label: ca.is_archived ? `${ca.name} (arsip)` : ca.name });
      });
    } else {
      TX_ACCOUNT_OPTIONS.forEach((opt) => {
        tabs.push({ id: opt.value, label: opt.value });
      });
    }
    return tabs;
  }, [customAccounts]);

  // Dynamic strata allocation buckets mapped from paycheck config or custom accounts
  const dynamicStrataBuckets = useMemo(() => {
    if (paycheckBuckets && paycheckBuckets.length > 0) {
      return paycheckBuckets.map((b) => ({
        account: b.account,
        percentage: Number(b.percentage) || 0,
        purpose: b.purpose || "Pos Rekening",
      }));
    }
    if (customAccounts.length > 0) {
      const defaultPct = Math.round((100 / customAccounts.length) * 10) / 10;
      return customAccounts.map((a, i) => ({
        account: a.name,
        percentage: i === customAccounts.length - 1 ? Math.max(0, 100 - defaultPct * (customAccounts.length - 1)) : defaultPct,
        purpose: a.tag || a.type || "Alokasi Rekening",
      }));
    }
    return [];
  }, [paycheckBuckets, customAccounts]);

  const pocketAccountName = (summary.safe_to_spend?.pocket_account || "").toLowerCase();

  const mandiriExpenses = useMemo(() => {
    const expenses = { makan: 0, jajan: 0, laundry: 0, galon: 0 };
    transactions.forEach((tx) => {
      const acc = (tx.account || "").toLowerCase();
      const isTargetPocket = pocketAccountName
        ? acc === pocketAccountName || acc.includes(pocketAccountName)
        : acc.includes("mandiri") || acc.includes("utama");

      if (tx.type === "expense" && isTargetPocket) {
        const cat = tx.category.toLowerCase();
        if (cat.includes("makan")) expenses.makan += tx.amount;
        else if (cat.includes("jajan") || cat.includes("ngopi")) expenses.jajan += tx.amount;
        else if (cat.includes("laundry")) expenses.laundry += tx.amount;
        else if (cat.includes("galon") || cat.includes("air")) expenses.galon += tx.amount;
      }
    });
    return expenses;
  }, [transactions, pocketAccountName]);

  // Real account balances mapped by type
  const { totalInvestasiReal, investasiLabels, totalDaruratReal, daruratLabels, totalTabunganReal, tabunganLabels } = useMemo(() => {
    const balanceMap: Record<string, number> = {};
    (summary.accounts || []).forEach((acc) => {
      balanceMap[acc.account.toLowerCase()] = acc.balance;
    });

    const getBalance = (ca: AccountItem) => {
      const key = ca.name.toLowerCase();
      if (key in balanceMap) return balanceMap[key];
      return ca.current_balance ?? ca.initial_balance ?? 0;
    };

    const inv = customAccounts.filter((a) => (a.type || "").toLowerCase() === "investasi");
    const dar = customAccounts.filter((a) => (a.type || "").toLowerCase() === "darurat");
    const tab = customAccounts.filter((a) => (a.type || "").toLowerCase() === "tabungan");

    return {
      totalInvestasiReal: inv.reduce((sum, a) => sum + getBalance(a), 0),
      investasiLabels: inv.map((a) => a.name).join(", "),
      totalDaruratReal: dar.reduce((sum, a) => sum + getBalance(a), 0),
      daruratLabels: dar.map((a) => a.name).join(", "),
      totalTabunganReal: tab.reduce((sum, a) => sum + getBalance(a), 0),
      tabunganLabels: tab.map((a) => a.name).join(", "),
    };
  }, [summary.accounts, customAccounts]);

  const handleCreateSubscription = async (e: React.FormEvent) => {
    e.preventDefault();
    const numAmount = parseInt(subAmount.replace(/\D/g, ""), 10);
    const day = parseInt(subBillingDay, 10);
    if (!numAmount || !subName.trim() || !billAccountOptions.some(({ value }) => value === subAccount)) return;
    if (subBillingType === "fixed_day" && !day) return;
    if (subBillingType !== "fixed_day" && !subExactDueDate) return;

    setIsSubModalOpen(false);
    setSubName("");
    setSubAmount("");
    setSubNotes("");
    setSubBillingType("fixed_day");
    setSubExactDueDate("");

    try {
      const payload: Record<string, unknown> = {
        name: subName.trim(),
        amount: numAmount,
        category: subCategory,
        account: subAccount,
        billing_type: subBillingType === "yearly" ? "fixed_day" : subBillingType,
        billing_cycle: subBillingType === "yearly" ? "yearly" : "monthly",
        notes: subNotes.trim() || undefined,
      };

      if (subBillingType !== "fixed_day") {
        payload.exact_due_date = subExactDueDate;
        const parsed = new Date(subExactDueDate);
        if (!isNaN(parsed.getUTCDate())) {
          payload.billing_day = parsed.getUTCDate();
        }
      } else {
        payload.billing_day = day;
      }

      await authFetch("/api/v1/subscriptions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      fetchData();
    } catch (err) {
      console.error("Subscription Create Error:", err);
    }
  };

  const handleDeleteSubscription = (id: number) => {
    setSubToDelete(id);
  };

  const handleConfirmDeleteSubscription = async () => {
    if (!subToDelete) return;
    try {
      setDeleteLoading(true);
      await authFetch(`/api/v1/subscriptions/${subToDelete}`, { method: "DELETE" });
      await fetchData();
      setSubToDelete(null);
    } catch (err) {
      console.error("Delete subscription error:", err);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleAccountEditSuccess = (updatedAcc?: AccountItem) => {
    if (updatedAcc) {
      setCustomAccounts((prev) =>
        prev.map((acc) => (acc.id === updatedAcc.id ? { ...acc, ...updatedAcc } : acc))
      );
    }
    fetchData();
    showToast(`Rekening ${updatedAcc?.name ? `"${updatedAcc.name}"` : ""} berhasil diperbarui!`);
    setAccountToEdit(null);
  };

  const handleConfirmDeleteTransaction = async () => {
    if (!txToDelete) return;
    setDeleteTxError("");
    try {
      setDeleteLoading(true);
      const response = await authFetch(`/api/v1/transactions/${txToDelete.id}`, { method: "DELETE" });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(typeof data?.detail === "string" ? data.detail : "Transaksi gagal dihapus.");
      }
      if (selectedPeriod.type === "cycle" && selectedPeriod.start === txToDelete.date &&
          txToDelete.type === "income" && txToDelete.category === "Gaji") {
        setSelectedPeriod({ id: "cycle_current", type: "cycle", start: "", end: "", label: "Siklus aktif" });
      } else {
        await fetchData();
      }
      setTxToDelete(null);
    } catch (err) {
      setDeleteTxError(err instanceof Error ? err.message : "Transaksi gagal dihapus.");
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleConfirmDeleteGoal = async () => {
    if (!goalToDelete) return;
    try {
      setDeleteLoading(true);
      await authFetch(`/api/v1/goals/${goalToDelete}`, { method: "DELETE" });
      await fetchData();
      setGoalToDelete(null);
    } catch (err) {
      console.error("Delete goal error:", err);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleToggleSubscription = async (sub: SubscriptionItem) => {
    try {
      await authFetch(`/api/v1/subscriptions/${sub.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !sub.is_active }),
      });
      fetchData();
    } catch (err) {
      console.error("Toggle subscription error:", err);
    }
  };

  const handleExportCSV = async () => {
    if (isExportingCSV) return;
    setIsExportingCSV(true);
    try {
      const token = getAuthToken();
      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      const res = await fetch("/api/v1/transactions/export", {
        headers,
      });

      if (!res.ok) {
        if (res.status === 401) {
          setIsAuthModalOpen(true);
        }
        throw new Error(`Export failed with status: ${res.status}`);
      }

      let filename = "finance_export.csv";
      const disposition = res.headers.get("Content-Disposition");
      if (disposition && disposition.includes("filename=")) {
        const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (match && match[1]) {
          filename = match[1].replace(/['"]/g, "").trim();
        }
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Gagal mengunduh CSV:", err);
    } finally {
      setIsExportingCSV(false);
      setIsExportMenuOpen(false);
    }
  };

  return (
    <div className="luma-app bg-luma-charcoal text-luma-ivory flex flex-col md:flex-row antialiased font-sans overflow-hidden">
      <aside id="desktop-sidebar" aria-label="Sidebar" data-collapsed={sidebarCollapsed} data-motion={sidebarMotion} className="luma-sidebar hidden md:flex shrink-0 bg-luma-charcoal p-5 flex-col justify-between overflow-x-hidden overflow-y-auto">
        <div>
          <div className="luma-sidebar-heading flex items-center justify-between gap-1">
            <div className="luma-sidebar-copy">
              <div className="flex items-center gap-2 font-semibold text-base tracking-tight text-luma-ivory leading-none whitespace-nowrap">
                <img src="/tillfold.svg" width={28} height={28} alt="" />
                Tillfold
              </div>
              <div className="text-xs text-luma-smoke mt-2">
                Catatan keuangan pribadi
              </div>
            </div>
            <button type="button" onClick={toggleSidebar} aria-label={sidebarCollapsed ? "Perluas sidebar" : "Ciutkan sidebar"} title={sidebarCollapsed ? "Perluas sidebar" : "Ciutkan sidebar"} aria-expanded={!sidebarCollapsed} aria-controls="desktop-sidebar" className="luma-sidebar-toggle inline-flex items-center justify-center shrink-0 rounded-lg hover:bg-white/10">
              {sidebarCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
            </button>
          </div>

          {/* Navigation Items — calm pill nav with soft glass hover */}
          <nav aria-label="Navigasi utama" className="mt-8 flex flex-col space-y-1">
            {[
              { name: "Ringkasan", icon: LayoutDashboard },
              { name: "Transaksi", icon: Receipt },
              { name: "Anggaran", icon: Layers },
              { name: "Rencana", icon: Target },
              { name: "Laporan", icon: BarChart2 },
            ].map((item) => {
              const isActive = activeNav === item.name;
              const Icon = item.icon;
              return (
                <button
                  key={item.name}
                  onClick={() => {
                    setActiveNav(item.name);
                    const slug = NAV_SLUGS[item.name];
                    if (slug) window.location.hash = slug;
                  }}
                  aria-current={isActive ? "page" : undefined}
                  aria-label={item.name}
                  title={sidebarCollapsed ? item.name : undefined}
                  className={`luma-touch flex items-center gap-3 w-full px-4 py-2.5 rounded-full text-xs sm:text-sm transition-all text-left whitespace-nowrap select-none outline-none focus:outline-none focus-visible:outline-none focus:ring-0 ${
                    isActive
                      ? "text-luma-ivory bg-white/[0.08] border border-luma-smokeline font-semibold"
                      : "text-luma-smoke hover:text-luma-ivory border border-transparent hover:border-white/[0.06] hover:bg-white/[0.04] font-medium"
                  }`}
                >
                  <Icon className={`w-4 h-4 shrink-0 ${isActive ? "text-luma-transfer" : "text-luma-smoke"}`} />
                  <span className="luma-sidebar-copy truncate whitespace-nowrap">{item.name}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Secondary Navigation (Pengaturan) & Slim user footer */}
        <div className="mt-8 pt-5 border-t border-luma-smokeline space-y-2">
          <nav aria-label="Navigasi sekunder" className="flex flex-col space-y-1">
            <button
              type="button"
              onClick={() => {
                setActiveNav("Pengaturan");
                const slug = NAV_SLUGS["Pengaturan"];
                if (slug) window.location.hash = slug;
              }}
              aria-current={activeNav === "Pengaturan" ? "page" : undefined}
              aria-label="Pengaturan"
              title={sidebarCollapsed ? "Pengaturan" : undefined}
              className={`luma-touch flex items-center gap-3 w-full px-4 py-2.5 rounded-full text-xs sm:text-sm transition-all text-left whitespace-nowrap select-none outline-none focus:outline-none focus-visible:outline-none focus:ring-0 ${
                activeNav === "Pengaturan"
                  ? "text-luma-ivory bg-white/[0.08] border border-luma-smokeline font-semibold"
                  : "text-luma-smoke hover:text-luma-ivory border border-transparent hover:border-white/[0.06] hover:bg-white/[0.04] font-medium"
              }`}
            >
              <Settings className={`w-4 h-4 shrink-0 ${activeNav === "Pengaturan" ? "text-luma-transfer" : "text-luma-smoke"}`} />
              <span className="luma-sidebar-copy truncate whitespace-nowrap">Pengaturan</span>
            </button>
          </nav>

          <button
            type="button"
            aria-label={currentUser ? `Profil ${currentUser.full_name}` : "Masuk atau kelola akun"}
            title={sidebarCollapsed ? (currentUser ? currentUser.full_name : "Masuk / Akun") : undefined}
            onClick={() => {
              if (currentUser) {
                setProfileModalTab("profile");
                setIsProfileModalOpen(true);
              } else {
                setIsAuthModalOpen(true);
              }
            }}
            className="luma-touch w-full p-3 rounded-3xl bg-white/[0.05] hover:bg-white/[0.08] border border-luma-smokeline transition text-left cursor-pointer group"
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-9 h-9 rounded-full bg-luma-sage/15 border border-luma-sage/30 text-luma-sage font-semibold text-xs flex items-center justify-center shrink-0">
                {currentUser ? currentUser.full_name.charAt(0).toUpperCase() : "U"}
              </div>
              <div className="luma-sidebar-copy min-w-0 flex-1">
                <p className="text-luma-ivory font-semibold text-xs truncate group-hover:text-luma-ember transition-colors">
                  {currentUser ? currentUser.full_name : "Masuk / Akun"}
                </p>
                <p className="text-xs text-luma-smoke font-sans truncate">
                  {currentUser ? `@${currentUser.username}` : "Mode Tamu"}
                </p>
              </div>
              {currentUser ? (
                <span className="luma-sidebar-copy inline-flex items-center gap-1.5 text-xs text-luma-sage font-medium px-2 py-0.5 rounded-full bg-luma-sage/10 border border-luma-sage/25 shrink-0">
                  <span className="w-1.5 h-1.5 rounded-full bg-luma-sage"></span>
                  Aktif
                </span>
              ) : (
                <span className="luma-sidebar-copy inline-flex items-center gap-1.5 text-xs text-luma-smoke font-medium px-2 py-0.5 rounded-full bg-white/[0.04] border border-luma-smokeline shrink-0">
                  <span className="w-1.5 h-1.5 rounded-full bg-luma-smoke"></span>
                  Tamu
                </span>
              )}
            </div>
          </button>
        </div>
      </aside>

      {/* MOBILE STICKY TOP APP BAR */}
      <header className="luma-mobile-header md:hidden sticky top-0 z-30 w-full bg-luma-charcoal border-b border-luma-smokeline/60 px-3.5 py-2.5 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <img src="/tillfold.svg" width={28} height={28} alt="" className="shrink-0" />
          <div className="min-w-0">
            <div className="font-semibold text-sm tracking-tight text-luma-ivory leading-none truncate">
              Tillfold
            </div>
            <div className="text-xs text-luma-smoke mt-1 truncate">
              {activeNav}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={fetchData}
            title="Refresh data"
            aria-label="Refresh data"
            className="hidden luma-touch min-w-[44px] items-center justify-center text-luma-smoke hover:text-luma-ivory bg-white/[0.05] border border-luma-smokeline rounded-full transition active:scale-95 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-luma-ember" : ""}`} />
          </button>
          <ThemeToggle size="sm" />
          <button
            onClick={() => setIsPaycheckModalOpen(true)}
            title="Gajian masuk"
            className="hidden luma-touch px-3 py-1.5 bg-luma-sage/15 text-luma-sage border border-luma-sage/30 font-semibold text-xs rounded-full transition active:scale-95 items-center gap-1 cursor-pointer"
          >
            <ArrowDownLeft className="w-3.5 h-3.5 shrink-0" />
            <span className="whitespace-nowrap">Gajian</span>
          </button>
          <button
            onClick={() => {
              if (currentUser) {
                setProfileModalTab("profile");
                setIsProfileModalOpen(true);
              } else {
                setIsAuthModalOpen(true);
              }
            }}
            title={currentUser ? currentUser.full_name : "Masuk / Akun"}
            aria-label={currentUser ? currentUser.full_name : "Masuk atau kelola akun"}
            className="luma-touch min-w-[44px] inline-flex items-center justify-center rounded-full bg-luma-sage/15 border border-luma-sage/30 text-luma-sage font-semibold text-xs shrink-0 active:scale-95 cursor-pointer"
          >
            {currentUser ? currentUser.full_name.charAt(0).toUpperCase() : "U"}
          </button>
          <button
            onClick={() => setIsMobileDrawerOpen(true)}
            title="Buka Menu"
            aria-label="Buka menu navigasi"
            className="luma-touch min-w-[44px] inline-flex items-center justify-center text-luma-smoke hover:text-luma-ivory bg-white/[0.05] border border-luma-smokeline rounded-full transition active:scale-95 cursor-pointer"
          >
            <Menu className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* MOBILE SLIDE-OVER DRAWER */}
      {isMobileDrawerOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/80 backdrop-blur-xs transition-opacity"
            onClick={() => setIsMobileDrawerOpen(false)}
          />

          {/* Drawer Content */}
          <div className="relative w-[280px] max-w-[85vw] bg-luma-charcoal border-r border-luma-smokeline/60 p-5 flex flex-col justify-between h-full z-10 overflow-y-auto">
            <div>
              {/* Header with Close */}
              <div className="flex items-center justify-between pb-4 border-b border-luma-smokeline">
                <div className="flex items-center gap-2.5">
                  <img src="/tillfold.svg" width={28} height={28} alt="" />
                  <div>
                    <div className="font-semibold text-base tracking-tight text-luma-ivory leading-none">
                      Tillfold
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <ThemeToggle size="sm" />
                  <button
                    onClick={() => setIsMobileDrawerOpen(false)}
                    aria-label="Tutup menu navigasi"
                    className="luma-touch min-w-[44px] inline-flex items-center justify-center rounded-full text-luma-smoke hover:text-luma-ivory hover:bg-white/[0.06] transition cursor-pointer"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {/* Navigation Items — 5 Main Menus */}
              <nav className="flex flex-col space-y-1" aria-label="Navigasi utama">
                {[
                  { name: "Ringkasan", icon: LayoutDashboard },
                  { name: "Transaksi", icon: Receipt },
                  { name: "Anggaran", icon: Layers },
                  { name: "Rencana", icon: Target },
                  { name: "Laporan", icon: BarChart2 },
                ].map((item) => {
                  const isActive = activeNav === item.name;
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.name}
                      onClick={() => {
                        setActiveNav(item.name);
                        const slug = NAV_SLUGS[item.name];
                        if (slug) window.location.hash = slug;
                        setIsMobileDrawerOpen(false);
                      }}
                      aria-current={isActive ? "page" : undefined}
                      className={`luma-touch min-h-[44px] flex items-center gap-3 w-full px-4 py-2.5 rounded-full text-xs sm:text-sm transition-all text-left whitespace-nowrap select-none outline-none focus:outline-none focus-visible:outline-none focus:ring-0 ${
                        isActive
                          ? "text-luma-ivory bg-white/[0.08] border border-luma-smokeline font-semibold"
                          : "text-luma-smoke hover:text-luma-ivory border border-transparent hover:border-white/[0.06] hover:bg-white/[0.04] font-medium"
                      }`}
                    >
                      <Icon className={`w-4 h-4 shrink-0 ${isActive ? "text-luma-transfer" : "text-luma-smoke"}`} />
                      <span className="truncate whitespace-nowrap">{item.name}</span>
                    </button>
                  );
                })}
              </nav>

              {/* Secondary Navigation (Pengaturan) */}
              <div className="mt-4 pt-3 border-t border-white/[0.08]">
                <nav aria-label="Navigasi sekunder">
                  <button
                    onClick={() => {
                      setActiveNav("Pengaturan");
                      setSettingsSubTab("rekening");
                      window.location.hash = "#/settings";
                      setIsMobileDrawerOpen(false);
                    }}
                    aria-current={activeNav === "Pengaturan" ? "page" : undefined}
                    className={`luma-touch min-h-[44px] flex items-center gap-3 w-full px-4 py-2.5 rounded-full text-xs sm:text-sm transition-all text-left whitespace-nowrap select-none outline-none focus:outline-none focus-visible:outline-none focus:ring-0 ${
                      activeNav === "Pengaturan"
                        ? "text-luma-ivory bg-white/[0.08] border border-white/[0.1] font-semibold"
                        : "text-luma-smoke hover:text-luma-ivory border border-transparent hover:border-white/[0.06] hover:bg-white/[0.04] font-medium"
                    }`}
                  >
                    <Settings className={`w-4 h-4 shrink-0 ${activeNav === "Pengaturan" ? "text-luma-transfer" : "text-luma-smoke"}`} />
                    <span className="truncate whitespace-nowrap">Pengaturan</span>
                  </button>
                </nav>
              </div>

              {/* Quick Actions inside Drawer */}
              <div className="mt-6 pt-4 border-t border-luma-smokeline space-y-2">
                <span className="text-xs font-semibold text-luma-smoke block mb-1">
                  Aksi cepat
                </span>
                <button
                  onClick={() => {
                    setIsMobileDrawerOpen(false);
                    setIsTransferModalOpen(true);
                  }}
                  className="luma-touch w-full flex items-center gap-2.5 px-3.5 py-2 text-xs font-semibold rounded-full bg-luma-gold/15 text-luma-gold border border-luma-gold/30 hover:bg-luma-gold/25 transition"
                >
                  <ArrowLeftRight className="w-4 h-4 shrink-0" />
                  <span>Transfer antar rekening</span>
                </button>
                <button
                  type="button"
                  onClick={handleExportCSV}
                  disabled={isExportingCSV}
                  className="luma-touch w-full flex items-center gap-2.5 px-3.5 py-2 text-xs font-medium rounded-full bg-white/[0.05] border border-luma-smokeline text-luma-ivory hover:bg-white/[0.08] transition disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  {isExportingCSV ? (
                    <RefreshCw className="w-4 h-4 shrink-0 animate-spin text-luma-ember" />
                  ) : (
                    <Download className="w-4 h-4 shrink-0" />
                  )}
                  <span>{isExportingCSV ? "Mengunduh CSV..." : "Ekspor CSV Transaksi"}</span>
                </button>
                {currentUser && (
                  currentUser.google_spreadsheet_id ? (
                    <div className="space-y-1.5 pt-1">
                      <button
                        type="button"
                        onClick={handleSyncSheets}
                        disabled={isSyncingSheets}
                        className="luma-touch w-full flex items-center justify-between px-3.5 py-2 text-xs font-medium rounded-full bg-white/[0.05] border border-luma-smokeline text-luma-ivory hover:bg-white/[0.08] transition disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                        title="Sinkronisasi data ke Google Sheets"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <RefreshCw className={`w-4 h-4 shrink-0 text-luma-sage ${isSyncingSheets ? "animate-spin" : ""}`} />
                          <span className="truncate">{isSyncingSheets ? "Menyinkronkan..." : "Sync Google Sheets"}</span>
                        </div>
                        <span className="text-[10px] font-mono text-luma-smoke">POST</span>
                      </button>
                      <a
                        href={`https://docs.google.com/spreadsheets/d/${currentUser.google_spreadsheet_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="luma-touch w-full flex items-center justify-between px-3.5 py-2 text-xs font-medium rounded-full bg-luma-sage/10 border border-luma-sage/30 text-luma-sage hover:bg-luma-sage/20 transition"
                        title="Buka Google Sheets di tab baru"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <FileSpreadsheet className="w-4 h-4 shrink-0" />
                          <span className="font-semibold truncate">Buka Spreadsheet</span>
                        </div>
                        <ExternalLink className="w-3.5 h-3.5 shrink-0 opacity-70" />
                      </a>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        setProfileModalTab("sheets");
                        setIsProfileModalOpen(true);
                      }}
                      className="luma-touch w-full flex items-center justify-between px-3.5 py-2 text-xs font-medium rounded-full bg-white/[0.03] border border-dashed border-luma-smokeline text-luma-smoke hover:text-luma-ivory hover:border-luma-sage/40 hover:bg-luma-sage/5 transition cursor-pointer"
                      title="Tautkan spreadsheet Google Sheets pribadi Anda"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <FileSpreadsheet className="w-4 h-4 shrink-0 text-luma-smoke" />
                        <span className="truncate">Tautkan Google Sheets</span>
                      </div>
                      <span className="text-[10px] uppercase font-semibold text-luma-sage bg-luma-sage/10 px-1.5 py-0.5 rounded">Setup</span>
                    </button>
                  )
                )}
              </div>
            </div>

            {/* Slim profile footer — single calm line */}
            <div className="pt-4 border-t border-luma-smokeline text-xs mt-6">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-9 h-9 rounded-full bg-luma-sage/15 border border-luma-sage/30 text-luma-sage font-semibold text-xs flex items-center justify-center shrink-0">
                  {currentUser ? currentUser.full_name.charAt(0).toUpperCase() : "U"}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-luma-ivory font-semibold truncate">{currentUser?.full_name || "Pengguna AI7"}</p>
                  <p className="text-xs text-luma-smoke font-sans truncate">
                    {currentUser?.telegram_chat_id ? `Telegram ID: ${currentUser.telegram_chat_id}` : "Mode Tamu"}
                  </p>
                </div>
                {currentUser ? (
                  <span className="inline-flex items-center gap-1.5 text-xs text-luma-sage font-medium px-2 py-0.5 rounded-full bg-luma-sage/10 border border-luma-sage/25 shrink-0">
                    <span className="w-1.5 h-1.5 rounded-full bg-luma-sage"></span>
                    Aktif
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 text-xs text-luma-smoke font-medium px-2 py-0.5 rounded-full bg-white/[0.04] border border-luma-smokeline shrink-0">
                    <span className="w-1.5 h-1.5 rounded-full bg-luma-smoke"></span>
                    Tamu
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MOBILE FLOATING ACTION BUTTON (Catat Transaksi) */}
      <button
        onClick={() => setIsModalOpen(true)}
        className="md:hidden fixed bottom-20 right-4 z-40 w-12 h-12 rounded-full bg-luma-ivory text-luma-charcoal shadow-xl shadow-black/40 flex items-center justify-center font-bold active:scale-90 transition border border-white/20 cursor-pointer"
        title="Catat transaksi baru"
        aria-label="Catat transaksi baru"
      >
        <Plus className="w-6 h-6 stroke-[3]" />
      </button>

      {/* MOBILE BOTTOM NAVIGATION BAR — 5 Core Menus */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-luma-charcoal border-t border-luma-smokeline px-1.5 py-1.5 flex items-center justify-around safe-bottom shadow-2xl" aria-label="Navigasi utama">
        {[
          { name: "Ringkasan", slug: "#/overview", icon: LayoutDashboard },
          { name: "Transaksi", slug: "#/transactions", icon: Receipt },
          { name: "Anggaran", slug: "#/budget", icon: Layers },
          { name: "Rencana", slug: "#/plan", icon: Target },
          { name: "Laporan", slug: "#/reports", icon: BarChart2 },
        ].map((item) => {
          const isActive = activeNav === item.name;
          const Icon = item.icon;
          return (
            <button
              key={item.name}
              onClick={() => {
                setActiveNav(item.name);
                window.location.hash = item.slug;
              }}
              aria-current={isActive ? "page" : undefined}
              className={`luma-touch flex flex-col items-center justify-center py-1 px-1.5 rounded-2xl transition min-w-[52px] min-h-[44px] select-none ${
                isActive
                  ? "text-luma-transfer font-semibold"
                  : "text-luma-smoke hover:text-luma-ivory"
              }`}
            >
              <Icon className="w-5 h-5 shrink-0" />
              <span className="text-[10px] mt-1 leading-tight tracking-tight">{item.name}</span>
            </button>
          );
        })}
      </nav>

      {/* MAIN VIEWPORT */}
      <main id="main-content" ref={mainContentRef} className="luma-main flex-1 overflow-y-auto w-full">
        {/* Persistent Sticky Topbar Header — slim Luma: period + utilities menu */}
        <header className="luma-topbar sticky top-0 z-20 bg-luma-charcoal/90 backdrop-blur-md border-b border-luma-smokeline/60 py-2.5 px-4 sm:px-6 lg:px-8">
          <div className="luma-topbar-inner max-w-7xl 2xl:max-w-[1600px] mx-auto w-full flex flex-row items-center justify-between gap-3 sm:gap-4">
            {/* Pure Control Period Selector & Theme Switch */}
            <div className="luma-period-controls flex items-center gap-2 sm:gap-2.5 min-w-0">
              {currentUser ? <PeriodSelector
                key={`${selectedPeriod.id}_${currentUser?.id || 1}`}
                currentPeriod={selectedPeriod}
                onSelectPeriod={(p) => setSelectedPeriod(p)}
              /> : <span className="text-xs text-luma-smoke">Keuangan pribadi</span>}
              <div className="hidden md:flex items-center">
                <ThemeToggle />
              </div>
            </div>

            {/* Slim utility toolbar: guest badge + consolidated utilities menu */}
            <div className="luma-toolbar flex items-center gap-1.5 sm:gap-2.5 shrink-0">

              {currentUser && <button type="button" className="luma-action-secondary inline-flex min-h-11 min-w-11 items-center justify-center gap-2 px-3"
                aria-label="Cari di Tillfold" title="Cari (Ctrl+K atau ⌘K)" onClick={() => { setIsExportMenuOpen(false); setIsGlobalSearchOpen(true); }}>
                <Search className="h-4 w-4" aria-hidden="true" /><span className="hidden sm:inline">Cari</span>
              </button>}
              {/* Consolidated utilities menu (refresh, export, paycheck checklist) */}
              <div className="relative" ref={exportMenuRef}>
                <button
                  type="button"
                  onClick={() => setIsExportMenuOpen((prev) => !prev)}
                  aria-haspopup="menu"
                  aria-expanded={isExportMenuOpen}
                  aria-label="Utilitas"
                  className="luma-touch py-2 px-3 sm:px-3.5 text-xs rounded-full font-semibold border border-luma-smokeline bg-white/[0.06] text-luma-ivory hover:bg-white/[0.1] hover:border-white/[0.2] transition inline-flex items-center gap-1.5 sm:gap-2 shrink-0 whitespace-nowrap cursor-pointer active:scale-95"
                >
                  <Download className="w-3.5 h-3.5 text-luma-smoke shrink-0" />
                  <span className="font-semibold hidden sm:inline">Utilitas</span>
                  <ChevronDown className={`w-3.5 h-3.5 text-luma-smoke shrink-0 transition-transform duration-200 ${isExportMenuOpen ? "rotate-180 text-luma-ember" : ""}`} />
                </button>

                {isExportMenuOpen && (
                  <div role="menu" className="absolute right-0 mt-2 w-60 p-2 bg-luma-coal/95 backdrop-blur-md border border-luma-smokeline rounded-3xl shadow-luma-glass z-50 text-xs space-y-1 animate-fadeIn">
                    <button
                      type="button"
                      onClick={() => {
                        fetchData();
                        setIsExportMenuOpen(false);
                      }}
                      role="menuitem"
                      className="luma-touch w-full flex items-center gap-2.5 px-3 py-2 rounded-2xl text-luma-ivory hover:bg-white/[0.06] transition text-left cursor-pointer"
                    >
                      <RefreshCw className={`w-4 h-4 shrink-0 ${loading ? "animate-spin text-luma-ember" : "text-luma-smoke"}`} />
                      <div className="text-left">
                        <div className="font-semibold text-xs text-luma-ivory">
                          Refresh data
                        </div>
                        <div className="text-xs text-luma-smoke">Saldo & transaksi terkini</div>
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setIsPaycheckModalOpen(true);
                        setIsExportMenuOpen(false);
                      }}
                      role="menuitem"
                      className="luma-touch w-full flex items-center gap-2.5 px-3 py-2 rounded-2xl text-luma-sage hover:bg-luma-sage/10 transition text-left cursor-pointer"
                    >
                      <ArrowDownLeft className="w-4 h-4 shrink-0" />
                      <div className="text-left">
                        <div className="font-semibold text-xs">
                          Catat gaji
                        </div>
                        <div className="text-xs text-luma-smoke">Catat pemasukan gaji</div>
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={handleExportCSV}
                      disabled={isExportingCSV}
                      role="menuitem"
                      className="luma-touch w-full flex items-center gap-2.5 px-3 py-2 rounded-2xl text-luma-ivory hover:bg-white/[0.06] transition disabled:opacity-50 disabled:cursor-not-allowed text-left cursor-pointer"
                    >
                      {isExportingCSV ? (
                        <RefreshCw className="w-4 h-4 text-luma-ember shrink-0 animate-spin" />
                      ) : (
                        <Download className="w-4 h-4 text-luma-smoke shrink-0" />
                      )}
                      <div className="text-left">
                        <div className="font-semibold text-xs text-luma-ivory">
                          {isExportingCSV ? "Sedang Mengunduh..." : "Unduh CSV Transaksi"}
                        </div>
                        <div className="text-xs text-luma-smoke">Seluruh histori ledger</div>
                      </div>
                    </button>

                    {currentUser && <button type="button" role="menuitem" onClick={() => {
                      setIsBackupModalOpen(true);
                      setIsExportMenuOpen(false);
                    }} className="luma-touch w-full flex items-center gap-2.5 rounded-[var(--ai7-radius-control)] px-3 py-2 text-left text-luma-ivory hover:bg-white/[0.06] cursor-pointer">
                      <Download className="h-4 w-4 shrink-0" />
                      <span className="text-xs font-semibold">Backup &amp; restore</span>
                    </button>}

                    {currentUser && (
                      currentUser.google_spreadsheet_id ? (
                        <>
                          <button
                            type="button"
                            role="menuitem"
                            disabled={isSyncingSheets}
                            onClick={() => {
                              setIsExportMenuOpen(false);
                              handleSyncSheets();
                            }}
                            className="luma-touch w-full flex items-center gap-2.5 rounded-[var(--ai7-radius-control)] px-3 py-2 text-left text-luma-ivory hover:bg-white/[0.06] cursor-pointer disabled:opacity-50 border-t border-luma-smokeline"
                          >
                            <RefreshCw className={`h-4 w-4 shrink-0 text-luma-sage ${isSyncingSheets ? "animate-spin" : ""}`} />
                            <div className="text-left min-w-0">
                              <div className="font-semibold text-xs text-luma-ivory">
                                {isSyncingSheets ? "Menyinkronkan..." : "Sync Google Sheets"}
                              </div>
                              <div className="text-xs text-luma-smoke">Kirim snapshot data terbaru</div>
                            </div>
                          </button>
                          <a
                            href={`https://docs.google.com/spreadsheets/d/${currentUser.google_spreadsheet_id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={() => setIsExportMenuOpen(false)}
                            role="menuitem"
                            className="luma-touch flex items-center gap-2.5 px-3 py-2 rounded-2xl text-luma-sage hover:bg-luma-sage/10 transition"
                          >
                            <FileSpreadsheet className="w-4 h-4 shrink-0" />
                            <div className="text-left min-w-0">
                              <div className="font-semibold text-xs flex items-center gap-1">
                                Buka Spreadsheet
                                <ExternalLink className="w-3 h-3 opacity-70" />
                              </div>
                              <div className="text-xs text-luma-smoke">Lihat laporan di Google Sheets</div>
                            </div>
                          </a>
                        </>
                      ) : (
                        <button
                          type="button"
                          role="menuitem"
                          onClick={() => {
                            setIsExportMenuOpen(false);
                            setProfileModalTab("sheets");
                            setIsProfileModalOpen(true);
                          }}
                          className="luma-touch w-full flex items-center gap-2.5 px-3 py-2 rounded-2xl text-luma-smoke hover:text-luma-ivory hover:bg-white/[0.04] transition border-t border-luma-smokeline cursor-pointer"
                        >
                          <FileSpreadsheet className="w-4 h-4 shrink-0 text-luma-smoke" />
                          <div className="text-left min-w-0">
                            <div className="font-semibold text-xs text-luma-ivory">Tautkan Google Sheets</div>
                            <div className="text-xs text-luma-smoke">Hubungkan spreadsheet pribadi</div>
                          </div>
                        </button>
                      )
                    )}
                  </div>
                )}
              </div>

              {/* Persistent primary action — stays visible, no stacking */}
              <button
                type="button"
                onClick={() => setIsModalOpen(true)}
                className="luma-touch py-2 px-3 sm:px-4 text-xs font-semibold rounded-full bg-luma-ivory text-luma-charcoal hover:brightness-95 transition inline-flex items-center justify-center gap-1.5 sm:gap-2 shrink-0 whitespace-nowrap active:scale-95 cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5 stroke-[2.5] shrink-0" />
                <span className="font-semibold">Catat transaksi</span>
              </button>
            </div>
          </div>
        </header>

        <div className="luma-page-content p-3.5 sm:p-5 md:p-6 lg:p-8 xl:p-10 pb-24 md:pb-10 max-w-7xl 2xl:max-w-[1600px] mx-auto w-full space-y-6 sm:space-y-8">
          {/* Page Title & Antislop Copy Header */}
          <div className="mb-2 sm:mb-4">
            <h1 className="ai7-type-page tracking-tight text-luma-ivory">
              {activeNav === "Ringkasan" && "Ringkasan"}
              {activeNav === "Transaksi" && "Transaksi"}
              {activeNav === "Anggaran" && "Anggaran"}
              {activeNav === "Rencana" && (planSubTab === "target" ? "Target tabungan" : "Tagihan")}
              {activeNav === "Laporan" && "Laporan"}
              {activeNav === "Pengaturan" && (
                settingsSubTab === "rekening"
                  ? "Rekening"
                  : settingsSubTab === "kantong"
                  ? "Kantong"
                  : settingsSubTab === "kategori"
                  ? "Kategori"
                  : "Profil dan preferensi"
              )}
            </h1>
            <p className="text-sm text-luma-smoke mt-1 tabular-nums">
              {activeNav === "Ringkasan" && "Saldo kas dan batas belanja harian."}
              {activeNav === "Transaksi" && "Cari, filter, dan ekspor transaksi."}
              {activeNav === "Anggaran" && "Atur batas belanja dan alokasi pemasukan."}
              {activeNav === "Rencana" && (planSubTab === "target" ? "Pantau progres target tabungan." : "Tagihan rutin dan tanggal jatuh tempo.")}
              {activeNav === "Laporan" && "Arus kas, kategori pengeluaran, dan laju belanja."}
              {activeNav === "Pengaturan" && (
                settingsSubTab === "kantong"
                  ? "Atur kantong dan alokasi tiap rekening."
                  : "Kelola rekening, kategori, tema, dan profil."
              )}
            </p>
          </div>

          {/* Guest Mode Banner */}
        {!currentUser && activeNav !== "Ringkasan" && (
          <div className="luma-guest-banner flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-full bg-luma-ember/15 border border-luma-ember/40 flex items-center justify-center text-luma-ember shrink-0">
                <AlertCircle className="w-5 h-5" />
              </div>
              <div>
                <p className="text-xs sm:text-sm font-semibold text-luma-ivory tracking-tight">
                  Mode tamu (belum masuk)
                </p>
                <p className="text-xs text-luma-smoke mt-0.5 leading-relaxed">
                  Masuk untuk melihat dan mencatat keuangan Anda.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setIsAuthModalOpen(true)}
              className="luma-touch w-full sm:w-auto px-4 py-2 rounded-full bg-luma-ivory hover:brightness-95 text-luma-charcoal font-semibold text-xs transition shrink-0 cursor-pointer text-center"
            >
              Masuk / daftar sekarang
            </button>
          </div>
        )}

        {/* ============================================================== */}
        {/* VIEW 1: RINGKASAN */}
        {/* ============================================================== */}
        {activeNav === "Ringkasan" && (
          <div className="space-y-5 sm:space-y-8">
            {/* Active Paycheck Session Banner */}
            {activePaycheckSession && activePaycheckSession.status === "in_progress" && (
              <div className="luma-glass !rounded-3xl p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-10 h-10 rounded-full bg-luma-sage/15 border border-luma-sage/30 flex items-center justify-center text-luma-sage shrink-0">
                    <CheckCircle2 className="w-5 h-5 text-luma-sage" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-sm text-luma-ivory">
                        Distribusi gajian sedang berjalan
                      </span>
                      <span className="px-2 py-0.5 rounded-full text-xs font-sans font-semibold bg-luma-sage/15 text-luma-sage border border-luma-sage/30">
                        {activePaycheckSession.completed_steps} / {activePaycheckSession.total_steps} Selesai ({activePaycheckSession.progress_percentage}%)
                      </span>
                    </div>
                    <p className="text-xs text-luma-smoke truncate mt-0.5">
                      Total Rp {activePaycheckSession.total_amount.toLocaleString("id-ID")} · Lanjutkan checklist transfer
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setIsPaycheckModalOpen(true)}
                  className="luma-touch px-4 py-2 rounded-full text-xs font-semibold bg-luma-sage text-luma-charcoal hover:brightness-105 transition shrink-0 inline-flex items-center justify-center gap-1.5 cursor-pointer self-end sm:self-center"
                >
                  <span>Lanjutkan Checklist</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            {/* Main balance with compact cash-flow and daily-budget panels. */}
            <LumaOverview
              totalBalance={summary.total_balance ?? (summary.income - summary.expense)}
              income={summary.income}
              expense={summary.expense}
              accountCount={summary.accounts?.length ?? 0}
              safeDaily={summary.safe_to_spend?.safe_daily ?? 0}
              pocketAccount={summary.safe_to_spend?.pocket_account || "Belanja"}
              pocketRemaining={summary.safe_to_spend?.pocket_remaining || 0}
              pocketBudget={summary.safe_to_spend?.pocket_budget ?? null}
              dayOfCycle={summary.safe_to_spend?.day_of_cycle || 1}
              cycleDays={summary.safe_to_spend?.cycle_days || 14}
              daysRemaining={summary.safe_to_spend?.days_remaining || 0}
              paceStatus={summary.safe_to_spend?.pace_status || "on_track"}
              periodEnded={(summary.safe_to_spend?.days_remaining ?? 1) === 0}
              formatRupiah={formatRupiah}
              loading={loading}
              isGuest={!currentUser}
              error={overviewError}
              onRetry={fetchData}
              onSignIn={() => setIsAuthModalOpen(true)}
              onAddTransaction={() => setIsModalOpen(true)}
              onOpenPaycheck={() => setIsPaycheckModalOpen(true)}
              hideBalance={hideOverviewBalances}
              onToggleBalance={() => setHideOverviewBalances((hidden) => !hidden)}
            />

            {currentUser && !overviewError && <>
            <LumaAccountStrip
              hideBalance={hideOverviewBalances}
              accounts={(summary.accounts || []).map((a) => {
                const found = customAccounts.find((c) => c.name.toLowerCase() === a.account.toLowerCase());
                return {
                  name: a.account,
                  balance: a.balance,
                  type: found?.type,
                };
              })}
              formatRupiah={formatRupiah}
              loading={loading}
              onOpenAccounts={() => {
                setActiveNav("Pengaturan");
                setSettingsSubTab("rekening");
                window.location.hash = "#/settings";
              }}
            />

            <LumaRecentTransactions
              transactions={transactions.slice(0, 5)}
              newTransactionIds={newTransactionIds}
              totalCount={transactions.length}
              formatRupiah={formatRupiah}
              loading={loading}
              onOpenLedger={() => {
                setActiveNav("Transaksi");
                window.location.hash = "#/transactions";
              }}
              onAddTransaction={() => setIsModalOpen(true)}
              onEdit={(tx) => setTxToEdit(tx)}
              onDelete={(tx) => setTxToDelete(tx)}
            />

            <details className="luma-overview-details">
              <summary>Rincian anggaran &amp; tabungan <ChevronDown size={16} /></summary>
              <div className="space-y-6 pt-6">
            {/* 3. Formula Strata Allocation Bar (50/30/20) */}
            <StrataAllocationBar
              cycleType={summary.safe_to_spend?.cycle_type}
              cycleDays={summary.safe_to_spend?.cycle_days}
              totalSalary={paycheckConfig?.total_salary || 0}
              buckets={dynamicStrataBuckets}
              formatRupiah={formatRupiah}
              loading={loading}
            />

            {/* 5. Quick Goals & Milestone Preview (Target Tabungan) */}
            {loading ? (
              <section aria-label="Target tabungan" className="luma-glass p-6 sm:p-7 space-y-4">
                <div className="flex justify-between items-center gap-2">
                  <div className="h-5 w-48 rounded-full bg-white/[0.06] animate-pulse" />
                  <div className="h-4 w-28 rounded-full bg-white/[0.06] animate-pulse" />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="rounded-2xl bg-white/[0.04] border border-luma-smokeline p-4 space-y-3">
                      <div className="flex justify-between items-center gap-2">
                        <div className="h-4 w-24 rounded-full bg-white/[0.06] animate-pulse" />
                        <div className="h-4 w-10 rounded-full bg-white/[0.06] animate-pulse" />
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-white/[0.06] animate-pulse" />
                      <div className="flex justify-between">
                        <div className="h-3 w-16 rounded-full bg-white/[0.06] animate-pulse" />
                        <div className="h-3 w-16 rounded-full bg-white/[0.06] animate-pulse" />
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ) : goals.length > 0 ? (
              <section aria-label="Target tabungan" className="luma-glass p-6 sm:p-7 space-y-4">
                <div className="flex justify-between items-center gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Target className="w-5 h-5 text-luma-ember shrink-0" aria-hidden="true" />
                    <h2 className="ai7-type-section text-luma-ivory tracking-tight truncate">
                      Target &amp; Milestone Tabungan
                    </h2>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveNav("Rencana");
                      setPlanSubTab("target");
                      window.location.hash = "#/plan";
                    }}
                    className="luma-touch inline-flex items-center gap-1 px-2 text-xs text-luma-ember hover:underline font-semibold shrink-0 whitespace-nowrap cursor-pointer"
                  >
                    <span>Buka Seluruh Target ({goals.length})</span>
                    <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
                  {goals.slice(0, 3).map((g, gi) => {
                    const pct = Math.min(100, Math.max(0, Number(g.percentage) || 0));
                    const barClass = gi % 3 === 0
                      ? "bg-luma-ember"
                      : gi % 3 === 1
                      ? "bg-luma-sage"
                      : "bg-luma-gold";
                    const pctClass = gi % 3 === 0
                      ? "text-luma-ember"
                      : gi % 3 === 1
                      ? "text-luma-sage"
                      : "text-luma-gold";

                    return (
                      <button
                        key={g.id}
                        type="button"
                        onClick={() => {
                          setActiveNav("Rencana");
                          setPlanSubTab("target");
                          window.location.hash = "#/plan";
                        }}
                        className="rounded-2xl bg-white/[0.04] border border-luma-smokeline hover:border-white/[0.16] p-4 space-y-3 cursor-pointer transition-all duration-200 text-left"
                      >
                        <div className="flex justify-between items-center gap-2">
                          <span className="text-sm font-semibold text-luma-ivory truncate flex items-center gap-2 min-w-0">
                            <span className={`w-1.5 h-1.5 rounded-full ${barClass} shrink-0`} aria-hidden="true" />
                            <span className="truncate">{g.name}</span>
                          </span>
                          <span className={`text-xs font-sans font-semibold shrink-0 tabular-nums ${pctClass}`}>
                            {pct}%
                          </span>
                        </div>
                        <div
                          className="h-1.5 w-full bg-black/25 rounded-full overflow-hidden"
                          role="progressbar"
                          aria-valuenow={pct}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label={`Progres ${g.name} ${pct} persen`}
                        >
                          <div
                            className={`h-full ${barClass} rounded-full transition-all duration-500`}
                            style={{ width: `${Math.max(3, pct)}%` }}
                          />
                        </div>
                        <div className="flex justify-between text-xs font-sans text-luma-smoke tabular-nums">
                          <span className="truncate">{formatRupiah(g.current_amount)}</span>
                          <span className="shrink-0">Target: {formatRupiah(g.target_amount)}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </section>
            ) : null}

            {/* 6. Kantong Belanja Harian & Saku Operasional */}
            <SmartBudgetEnvelopes
              mandiriExpenses={mandiriExpenses}
              formatRupiah={formatRupiah}
              cycleDays={summary.safe_to_spend?.cycle_days || 14}
              pocketAccount={summary.safe_to_spend?.pocket_account || (customAccounts[0]?.name || "Saku Operasional")}
              pocketBudget={summary.safe_to_spend?.pocket_budget}
              loading={loading}
            />

            {/* 7. Sub-Kantong Rekening */}
            <AccountPockets
              cycleStart={summary.start_date}
              cycleEnd={summary.end_date}
              accountId={(customAccounts.find(account => account.name === summary.safe_to_spend?.pocket_account) || customAccounts.find(account => account.type === "operasional") || customAccounts[0])?.id}
              formatRupiah={formatRupiah}
              refreshSignal={pocketsRefreshSignal}
              onToast={showToast}
              onDataLoaded={setPocketsData}
            />

            {/* 8. Dana Talangan Internal (Internal Loans) */}
            <InternalLoansWidget
              accounts={activeAccounts}
              pockets={pocketsData?.pockets ?? pocketsData?.items}
              formatRupiah={formatRupiah}
              refreshSignal={loansRefreshSignal}
              onToast={showToast}
              onDataChanged={() => {
                fetchData();
                setPocketsRefreshSignal((s) => s + 1);
                setLoansRefreshSignal((s) => s + 1);
              }}
            />

            {/* 9. Grafik Burn Rate */}
            <BurnRateChart summary={summary} formatRupiah={formatRupiah} />

              </div>
            </details>
            </>}
          </div>
        )}

        {/* ============================================================== */}
        {/* VIEW 2: TRANSAKSI (SEBELUMNYA BUKU TRANSAKSI / LEDGER) */}
        {/* ============================================================== */}
        {activeNav === "Transaksi" && (
          <div className="animate-fadeIn">
            <TransactionLedgerView
              key={currentUser?.id ?? "guest"}
              transactions={transactions}
              accounts={allAccountTabs}
              categories={categories}
              currentCycle={
                summary.start_date && summary.end_date
                  ? {
                      start_date: summary.start_date,
                      end_date: summary.end_date,
                      label: summary.period_label || "",
                    }
                  : undefined
              }
              formatRupiah={formatRupiah}
              onEdit={(tx) => setTxToEdit(tx)}
              onDelete={(tx) => setTxToDelete(tx)}
              onOpenAddModal={() => setIsModalOpen(true)}
              loading={loading}
            />
          </div>
        )}

        {/* ============================================================== */}
        {/* VIEW 3: ANGGARAN & ALOKASI KANTONG */}
        {/* ============================================================== */}
        {activeNav === "Anggaran" && (
          <div className="space-y-8 animate-fadeIn">
            <section aria-labelledby="budget-daily-title" className="luma-matte space-y-3 p-4 sm:p-6" aria-busy={loading}>
              <h2 id="budget-daily-title" className="ai7-type-section">Batas belanja harian</h2>
              {loading ? (
                <Skeleton className="h-8 w-40" />
              ) : !summary.safe_to_spend ? (
                <p className="text-sm text-luma-smoke">Anggaran periode belum tersedia.</p>
              ) : summary.safe_to_spend.days_remaining === 0 ? (
                <p className="text-sm text-luma-smoke">Siklus selesai.</p>
              ) : (
                <>
                  <p className="ai7-type-metric">{formatRupiah(summary.safe_to_spend.safe_daily)} <span className="text-sm text-luma-smoke">/ hari</span></p>
                  <p className="text-sm text-luma-smoke">
                    {summary.safe_to_spend.pocket_budget <= 0 ? "Dana belanja belum tersedia" :
                      summary.safe_to_spend.pocket_remaining <= 0 ? "Anggaran belanja habis" :
                      `Sisa anggaran belanja ${formatRupiah(summary.safe_to_spend.pocket_remaining)}`}
                    {" · "}{summary.safe_to_spend.days_remaining} hari tersisa
                  </p>
                </>
              )}
            </section>
            <StrataAllocationBar
              cycleType={summary.safe_to_spend?.cycle_type}
              cycleDays={summary.safe_to_spend?.cycle_days}
              totalSalary={paycheckConfig?.total_salary || 0}
              buckets={dynamicStrataBuckets}
              formatRupiah={formatRupiah}
              loading={loading}
            />
            <AccountPockets
              cycleStart={summary.start_date}
              cycleEnd={summary.end_date}
              accounts={activeAccounts}
              formatRupiah={formatRupiah}
              refreshSignal={pocketsRefreshSignal}
              onToast={showToast}
              onDataLoaded={setPocketsData}
            />

            {/* Dana Talangan Internal (Internal Loans) */}
            <InternalLoansWidget
              accounts={activeAccounts}
              pockets={pocketsData?.pockets ?? pocketsData?.items}
              formatRupiah={formatRupiah}
              refreshSignal={loansRefreshSignal}
              onToast={showToast}
              onDataChanged={() => {
                fetchData();
                setPocketsRefreshSignal((s) => s + 1);
                setLoansRefreshSignal((s) => s + 1);
              }}
            />

            {/* Pos Tagihan & Utilitas */}
            <div className="luma-matte p-5 sm:p-6 space-y-5">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="ai7-type-card text-slateText-primary">
                      Komitmen tagihan dan simpanan
                    </h3>
                    <span className="text-xs font-sans font-semibold px-2.5 py-0.5 rounded-full border bg-coralFall/15 text-coralFall border-coralFall/30">
                      Tagihan
                    </span>
                  </div>
                  <p className="text-xs text-slateText-secondary mt-0.5">
                    Alokasi autodebet tagihan berkala, langganan digital, dan komitmen bulanan
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setActiveNav("Rencana");
                    setPlanSubTab("tagihan");
                    window.location.hash = "#/tagihan";
                  }}
                  className="luma-touch text-xs text-amberGold hover:underline font-medium shrink-0 whitespace-nowrap inline-flex items-center gap-1 group cursor-pointer min-h-[44px]"
                >
                  <span>Lihat tagihan ({subsData.items.length})</span>
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-obsidian-panel border border-obsidian-border rounded-lg p-5 space-y-3">
                  <div className="flex justify-between items-center gap-2">
                    <span className="font-semibold text-slateText-primary text-sm truncate">Komitmen Tagihan Berjalan</span>
                    <span className="text-xs font-sans px-2 py-0.5 rounded bg-obsidian-card border border-obsidian-border text-mintRise shrink-0 whitespace-nowrap">
                      Autodebet
                    </span>
                  </div>
                  {loading ? (
                    <Skeleton className="h-7 w-36 rounded-md" />
                  ) : (
                    <div className="ai7-type-metric text-slateText-primary">
                      {formatRupiah(subsData.total_monthly_commitment)} / bln
                    </div>
                  )}
                  <div className="text-xs text-slateText-muted">
                    {subsData.active_count} tagihan aktif ({subsData.upcoming_this_week} jatuh tempo pekan ini)
                  </div>
                </div>

                <div className="bg-obsidian-panel border border-obsidian-border rounded-lg p-5 space-y-3">
                  <div className="flex justify-between items-center gap-2">
                    <span className="font-semibold text-slateText-primary text-sm truncate">Pos Tabungan &amp; Investasi</span>
                    <span className="text-xs font-sans px-2 py-0.5 rounded bg-obsidian-card border border-obsidian-border text-cyanHub shrink-0 whitespace-nowrap">
                      Pertumbuhan aset
                    </span>
                  </div>
                  {loading ? (
                    <Skeleton className="h-7 w-36 rounded-md" />
                  ) : (
                    <div className="ai7-type-metric text-slateText-primary">
                      {formatRupiah(totalInvestasiReal)}
                    </div>
                  )}
                  <div className="text-xs text-slateText-muted">
                    {investasiLabels ? `${investasiLabels} • Saldo riil investasi` : "Belum ada rekening tipe Investasi"}
                  </div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="bg-obsidian-card border border-obsidian-border rounded-xl p-5 space-y-2">
                <div className="text-cyanHub font-semibold text-sm">Pos Dana Darurat (Cadangan Likuid)</div>
                {loading ? (
                  <Skeleton className="h-8 w-40 rounded-md" />
                ) : (
                  <div className="ai7-type-metric text-slateText-primary">
                    {formatRupiah(totalDaruratReal)}
                  </div>
                )}
                <p className="text-xs text-slateText-muted">
                  {daruratLabels ? `${daruratLabels} • Cadangan likuid darurat` : "Belum ada rekening tipe Dana Darurat"}
                </p>
              </div>
              <div className="bg-obsidian-card border border-obsidian-border rounded-xl p-5 space-y-2">
                <div className="text-purpleLock font-semibold text-sm">Pos Tabungan Terkunci (Target Tabungan)</div>
                {loading ? (
                  <Skeleton className="h-8 w-40 rounded-md" />
                ) : (
                  <div className="ai7-type-metric text-slateText-primary">
                    {formatRupiah(totalTabunganReal)}
                  </div>
                )}
                <p className="text-xs text-slateText-muted">
                  {tabunganLabels ? `${tabunganLabels} • Tabungan terpisah terkunci` : "Belum ada rekening tipe Tabungan"}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* VIEW 4: RENCANA (TARGET TABUNGAN & TAGIHAN) */}
        {/* ============================================================== */}
        {activeNav === "Rencana" && (
          <div className="space-y-6 animate-fadeIn">
            {/* Sub-tab Navigation */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pb-2 border-b border-luma-smokeline">
              <div className="ai7-tab-group inline-flex bg-white/[0.04] border border-luma-smokeline" role="tablist" aria-label="Rencana" onKeyDown={handleTabArrowKeys}>
                <button
                  type="button"
                  role="tab"
                  aria-selected={planSubTab === "target"}
                  id="plan-tab-target"
                  aria-controls="plan-tab-content"
                  tabIndex={planSubTab === "target" ? 0 : -1}
                  onClick={() => {
                    setPlanSubTab("target");
                    window.location.hash = "#/plan";
                  }}
                  className={`luma-touch min-h-[44px] flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition cursor-pointer ${
                    planSubTab === "target"
                      ? "bg-white/[0.1] text-luma-ivory border border-luma-smokeline shadow-xs"
                      : "text-luma-smoke hover:text-luma-ivory hover:bg-white/[0.04] border border-transparent"
                  }`}
                >
                  <Target className="w-4 h-4 shrink-0 text-luma-ember" />
                  <span>Target tabungan</span>
                  <span className="text-xs font-sans font-medium px-2 py-0.5 rounded-full bg-white/[0.06] text-luma-smoke ml-1">
                    {goals.length}
                  </span>
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={planSubTab === "tagihan"}
                  id="plan-tab-tagihan"
                  aria-controls="plan-tab-content"
                  tabIndex={planSubTab === "tagihan" ? 0 : -1}
                  onClick={() => {
                    setPlanSubTab("tagihan");
                    window.location.hash = "#/tagihan";
                  }}
                  className={`luma-touch min-h-[44px] flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition cursor-pointer ${
                    planSubTab === "tagihan"
                      ? "bg-white/[0.1] text-luma-ivory border border-luma-smokeline shadow-xs"
                      : "text-luma-smoke hover:text-luma-ivory hover:bg-white/[0.04] border border-transparent"
                  }`}
                >
                  <Bell className="w-4 h-4 shrink-0 text-luma-gold" />
                  <span>Tagihan</span>
                  <span className="text-xs font-sans font-medium px-2 py-0.5 rounded-full bg-white/[0.06] text-luma-smoke ml-1">
                    {subsData.items.length}
                  </span>
                </button>
              </div>

              {/* Action shortcut depending on active sub-tab */}
              <div className="flex items-center gap-2">
                {planSubTab === "target" ? (
                  <button
                    type="button"
                    onClick={() => setIsAddGoalModalOpen(true)}
                    className="luma-action-primary cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
                    <span>Tambah target</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setIsSubModalOpen(true)}
                    className="luma-action-primary cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
                    <span>Tambah tagihan</span>
                  </button>
                )}
              </div>
            </div>

            <div role="tabpanel" id="plan-tab-content" aria-labelledby={`plan-tab-${planSubTab}`} tabIndex={0}>
            {planSubTab === "target" && (
              <GoalsView
                goals={goals}
                formatRupiah={formatRupiah}
                onOpenAddModal={() => setIsAddGoalModalOpen(true)}
                onEdit={(goal) => setGoalToEdit(goal)}
                onDelete={(id) => setGoalToDelete(id)}
                loading={loading}
              />
            )}

            {planSubTab === "tagihan" && (
              <SubscriptionsView
                subsData={subsData}
                formatRupiah={formatRupiah}
                onToggleActive={handleToggleSubscription}
                onDelete={handleDeleteSubscription}
                onEdit={(sub) => setSubToEdit(sub)}
                onPaymentChanged={fetchData}
                loading={loading}
              />
            )}
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* VIEW 5: LAPORAN (SEBELUMNYA ANALISIS & TREN) */}
        {/* ============================================================== */}
        {activeNav === "Laporan" && (
          <div className="animate-fadeIn">
            <AnalyticsView
              summary={{
                ...summary,
                period_type: summary.period_type || "cycle",
                period_label: summary.period_label || "",
                start_date: summary.start_date || "",
                end_date: summary.end_date || "",
                month_num: 10,
                year: 2026,
                daily_trend: summary.daily_trend || [],
                accounts: (summary.accounts || []).map((a) => ({
                  name: a.account,
                  type: "regular",
                  balance: a.balance,
                  expense: a.expense,
                })),
              }}
              formatRupiah={formatRupiah}
              loading={loading}
            />
          </div>
        )}

        {/* ============================================================== */}
        {/* VIEW 6: PENGATURAN (SEBELUMNYA AKUN & KATEGORI) */}
        {/* ============================================================== */}
        {activeNav === "Pengaturan" && (
          <div className="space-y-6 animate-fadeIn">
            {/* Sub-tab Navigation */}
            <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-luma-smokeline">
              <div className="ai7-tab-group grid w-full grid-cols-2 gap-1 border border-luma-smokeline bg-white/[0.04] sm:flex sm:w-auto sm:max-w-full sm:flex-wrap" role="tablist" aria-label="Pengaturan" onKeyDown={handleTabArrowKeys}>
                <button
                  type="button"
                  role="tab"
                  aria-selected={settingsSubTab === "rekening"}
                  id="settings-tab-rekening"
                  aria-controls="settings-tab-content"
                  tabIndex={settingsSubTab === "rekening" ? 0 : -1}
                  onClick={() => {
                    setSettingsSubTab("rekening");
                    window.location.hash = "#/settings";
                  }}
                  className={`luma-touch min-h-[44px] flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition cursor-pointer shrink-0 ${
                    settingsSubTab === "rekening"
                      ? "bg-white/[0.1] text-luma-ivory border border-luma-smokeline shadow-xs"
                      : "text-luma-smoke hover:text-luma-ivory hover:bg-white/[0.04] border border-transparent"
                  }`}
                >
                  <CreditCard className="w-4 h-4 shrink-0 text-luma-ember" />
                  <span>Rekening</span>
                  <span className="text-xs font-sans font-medium px-2 py-0.5 rounded-full bg-white/[0.06] text-luma-smoke ml-1">
                    {customAccounts.length || summary.accounts?.length || 0}
                  </span>
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={settingsSubTab === "kantong"}
                  id="settings-tab-kantong"
                  aria-controls="settings-tab-content"
                  tabIndex={settingsSubTab === "kantong" ? 0 : -1}
                  onClick={() => {
                    setSettingsSubTab("kantong");
                    window.location.hash = "#/pockets";
                  }}
                  className={`luma-touch min-h-[44px] flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition cursor-pointer shrink-0 ${
                    settingsSubTab === "kantong"
                      ? "bg-white/[0.1] text-luma-ivory border border-luma-smokeline shadow-xs"
                      : "text-luma-smoke hover:text-luma-ivory hover:bg-white/[0.04] border border-transparent"
                  }`}
                >
                  <WalletCards className="w-4 h-4 shrink-0 text-luma-gold" />
                  <span>Kantong</span>
                  <span className="text-xs font-sans font-medium px-2 py-0.5 rounded-full bg-white/[0.06] text-luma-smoke ml-1">
                    {pocketsCount}
                  </span>
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={settingsSubTab === "kategori"}
                  id="settings-tab-kategori"
                  aria-controls="settings-tab-content"
                  tabIndex={settingsSubTab === "kategori" ? 0 : -1}
                  onClick={() => {
                    setSettingsSubTab("kategori");
                    window.location.hash = "#/categories";
                  }}
                  className={`luma-touch min-h-[44px] flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition cursor-pointer shrink-0 ${
                    settingsSubTab === "kategori"
                      ? "bg-white/[0.1] text-luma-ivory border border-luma-smokeline shadow-xs"
                      : "text-luma-smoke hover:text-luma-ivory hover:bg-white/[0.04] border border-transparent"
                  }`}
                >
                  <Layers className="w-4 h-4 shrink-0 text-luma-sage" />
                  <span>Kategori</span>
                  <span className="text-xs font-sans font-medium px-2 py-0.5 rounded-full bg-white/[0.06] text-luma-smoke ml-1">
                    {categories.length}
                  </span>
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={settingsSubTab === "profil"}
                  id="settings-tab-profil"
                  aria-controls="settings-tab-content"
                  tabIndex={settingsSubTab === "profil" ? 0 : -1}
                  onClick={() => {
                    setSettingsSubTab("profil");
                    window.location.hash = "#/profile";
                  }}
                  className={`luma-touch min-h-[44px] flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition cursor-pointer shrink-0 ${
                    settingsSubTab === "profil"
                      ? "bg-white/[0.1] text-luma-ivory border border-luma-smokeline shadow-xs"
                      : "text-luma-smoke hover:text-luma-ivory hover:bg-white/[0.04] border border-transparent"
                  }`}
                >
                  <Settings className="w-4 h-4 shrink-0 text-luma-gold" />
                  <span>Profil</span>
                </button>
              </div>

              {/* Sub-tab action shortcuts */}
              {settingsSubTab === "rekening" && (
                <div className="ml-auto flex flex-wrap items-center justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setIsTransferModalOpen(true)}
                    className="luma-action-secondary cursor-pointer"
                  >
                    <ArrowLeftRight size={16} aria-hidden="true" />
                    <span>Transfer antar rekening</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsAddAccountModalOpen(true)}
                    className="luma-action-primary cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5 stroke-[2.5] shrink-0" />
                    <span>Tambah rekening</span>
                  </button>
                </div>
              )}


            </div>

            <div role="tabpanel" id="settings-tab-content" aria-labelledby={`settings-tab-${settingsSubTab}`} tabIndex={0}>
            {/* Sub-tab 1: Rekening */}
            {settingsSubTab === "rekening" && (
              <div className="space-y-4 animate-fadeIn">
                <div>
                  <h2 className="ai7-type-section text-white tracking-tight">
                    Rekening &amp; Dompet Kas
                  </h2>
                  <p className="text-xs text-zinc-400 mt-0.5">
                    Daftar rekening bank fisik, dompet digital, dan pos simpanan kas aktif.
                  </p>
                </div>
                <AccountGrid
                  summary={summary}
                  customAccounts={customAccounts}
                  formatRupiah={formatRupiah}
                  loading={loading}
                  onAccountDeleted={fetchData}
                  onArchiveChanged={fetchData}
                  onReconciled={fetchData}
                  onEditAccount={(acc) => setAccountToEdit(acc)}
                />
              </div>
            )}

            {/* Sub-tab 2: Kantong */}
            {settingsSubTab === "kantong" && (
              <div className="space-y-4 animate-fadeIn">
                <AccountPockets
                  cycleStart={summary.start_date}
                  cycleEnd={summary.end_date}
                  accounts={activeAccounts}
                  formatRupiah={formatRupiah}
                  refreshSignal={pocketsRefreshSignal}
                  onToast={showToast}
                  onDataLoaded={setPocketsData}
                />
              </div>
            )}

            {/* Sub-tab 3: Kategori */}
            {settingsSubTab === "kategori" && (
              <div className="animate-fadeIn">
                <CategoryGrid
                  categories={categories}
                  summaryCategories={summary.categories}
                  incomeSummaryCategories={summary.income_categories}
                  formatRupiah={formatRupiah}
                  loading={loading}
                  onCategoriesUpdated={fetchData}
                  transactions={transactions}
                  onOpenManageCategories={() => setIsManageCategoriesOpen(true)}
                />
              </div>
            )}

            {/* Sub-tab 3: Profil & Preferensi */}
            {settingsSubTab === "profil" && (
              <div className="space-y-6 animate-fadeIn">
                <div className="luma-glass !rounded-3xl p-6 sm:p-7 space-y-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-luma-smokeline">
                    <div className="flex items-center gap-4">
                      <div className="w-14 h-14 rounded-full bg-luma-sage/15 border border-luma-sage/30 text-luma-sage font-semibold text-xl flex items-center justify-center shrink-0">
                        {currentUser ? currentUser.full_name.charAt(0).toUpperCase() : "U"}
                      </div>
                      <div>
                        <h2 className="ai7-type-section text-luma-ivory tracking-tight">
                          {currentUser?.full_name || "Pengguna Tamu"}
                        </h2>
                        <p className="text-xs text-luma-smoke font-sans mt-0.5">
                          {currentUser ? `@${currentUser.username} • ${currentUser.email || "Email belum disetel"}` : "Mode Tamu (Sesi Lokal)"}
                        </p>
                        <div className="flex items-center gap-2 mt-2 flex-wrap">
                          {currentUser ? (
                            <span className="inline-flex items-center gap-1.5 text-xs text-luma-sage font-medium px-2.5 py-0.5 rounded-full bg-luma-sage/10 border border-luma-sage/25">
                              <span className="w-1.5 h-1.5 rounded-full bg-luma-sage"></span>
                              Akun terverifikasi
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 text-xs text-luma-smoke font-medium px-2.5 py-0.5 rounded-full bg-white/[0.04] border border-luma-smokeline">
                              <span className="w-1.5 h-1.5 rounded-full bg-luma-smoke"></span>
                              Tamu
                            </span>
                          )}
                          {currentUser?.telegram_chat_id ? (
                            <span className="inline-flex items-center gap-1.5 text-xs text-luma-ember font-medium px-2.5 py-0.5 rounded-full bg-luma-ember/10 border border-luma-ember/25">
                              Telegram Terhubung ({currentUser.telegram_chat_id})
                            </span>
                          ) : currentUser ? (
                            <span className="inline-flex items-center gap-1.5 text-xs text-luma-smoke font-medium px-2.5 py-0.5 rounded-full bg-white/[0.04] border border-luma-smokeline">
                              Telegram belum terhubung
                            </span>
                          ) : null}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-start sm:self-auto">
                      {currentUser ? (
                        <button
                          type="button"
                          onClick={() => {
                            setProfileModalTab("profile");
                            setIsProfileModalOpen(true);
                          }}
                          className="luma-touch min-h-[44px] px-4 py-2 rounded-full bg-white/[0.08] hover:bg-white/[0.12] text-luma-ivory border border-luma-smokeline text-xs font-semibold transition cursor-pointer"
                        >
                          Ubah Profil &amp; Telegram
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setIsAuthModalOpen(true)}
                          className="luma-touch min-h-[44px] px-4 py-2 rounded-full bg-luma-ivory hover:brightness-95 text-luma-charcoal text-xs font-semibold transition cursor-pointer"
                        >
                          Masuk / daftar
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Preferensi Antarmuka */}
                  <div className="space-y-3">
                    <h3 className="ai7-type-card text-luma-ivory tracking-tight">
                      Preferensi antarmuka
                    </h3>
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl bg-white/[0.03] border border-luma-smokeline">
                      <div>
                        <div className="text-xs font-semibold text-luma-ivory">Tema Tampilan</div>
                        <div className="text-xs text-luma-smoke mt-0.5">
                          Ganti palet Ink &amp; Silver antara mode Gelap (Dark Glass) dan Terang.
                        </div>
                      </div>
                      <div className="shrink-0">
                        <ThemeToggle />
                      </div>
                    </div>
                  </div>

                  {/* Integrasi Google Sheets Universal */}
                  <div className="space-y-3 pt-2">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="ai7-type-card text-luma-ivory tracking-tight">
                        Integrasi Google Sheets
                      </h3>
                      {currentUser?.google_spreadsheet_id ? (
                        <span className="inline-flex items-center gap-1.5 text-xs text-mintRise font-medium px-2.5 py-0.5 rounded-full bg-mintRise/10 border border-mintRise/25">
                          <span className="w-1.5 h-1.5 rounded-full bg-mintRise"></span>
                          Terhubung
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-xs text-luma-smoke font-medium px-2.5 py-0.5 rounded-full bg-white/[0.04] border border-luma-smokeline">
                          <span className="w-1.5 h-1.5 rounded-full bg-luma-smoke"></span>
                          Belum Terhubung
                        </span>
                      )}
                    </div>

                    <div className="p-4 sm:p-5 rounded-2xl bg-white/[0.03] border border-luma-smokeline space-y-4">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="w-10 h-10 rounded-2xl bg-luma-sage/15 border border-luma-sage/30 text-luma-sage flex items-center justify-center shrink-0">
                            <FileSpreadsheet className="w-5 h-5" />
                          </div>
                          <div className="min-w-0">
                            <div className="text-xs font-semibold text-luma-ivory">Google Sheets Rapor Keuangan</div>
                            <div className="text-xs text-luma-smoke mt-0.5 truncate">
                              {currentUser?.google_spreadsheet_id
                                ? `ID: ${currentUser.google_spreadsheet_id}`
                                : "Cadangkan mutasi kas dan sinkronkan snapshot laporan siklus ke spreadsheet pribadi."}
                            </div>
                          </div>
                        </div>

                        <div className="flex flex-wrap items-center gap-2 shrink-0">
                          {currentUser?.google_spreadsheet_id && (
                            <>
                              <button
                                type="button"
                                onClick={handleSyncSheets}
                                disabled={isSyncingSheets}
                                className="luma-touch min-h-[38px] px-3.5 py-1.5 rounded-full bg-white/[0.08] hover:bg-white/[0.12] text-luma-ivory border border-luma-smokeline text-xs font-semibold transition inline-flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                              >
                                <RefreshCw className={`w-3.5 h-3.5 text-luma-sage ${isSyncingSheets ? "animate-spin" : ""}`} />
                                <span>{isSyncingSheets ? "Menyinkronkan..." : "Sync Sekarang"}</span>
                              </button>
                              <a
                                href={`https://docs.google.com/spreadsheets/d/${currentUser.google_spreadsheet_id}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="luma-touch min-h-[38px] px-3.5 py-1.5 rounded-full bg-luma-sage/15 hover:bg-luma-sage/25 text-luma-sage border border-luma-sage/30 text-xs font-semibold transition inline-flex items-center gap-1.5"
                              >
                                <span>Buka Spreadsheet</span>
                                <ExternalLink className="w-3.5 h-3.5 opacity-80" />
                              </a>
                            </>
                          )}
                          <button
                            type="button"
                            onClick={() => {
                              if (currentUser) {
                                setProfileModalTab("sheets");
                                setIsProfileModalOpen(true);
                              } else {
                                setIsAuthModalOpen(true);
                              }
                            }}
                            className="luma-touch min-h-[38px] px-3.5 py-1.5 rounded-full bg-white/[0.05] hover:bg-white/[0.10] text-luma-ivory border border-luma-smokeline text-xs font-semibold transition cursor-pointer"
                          >
                            {currentUser?.google_spreadsheet_id ? "Atur Spreadsheet" : "Tautkan Google Sheets"}
                          </button>
                        </div>
                      </div>

                      {/* Microcopy box with 1-click copy */}
                      <div className="rounded-xl border border-luma-smokeline/70 bg-luma-coal/50 p-3 sm:p-3.5 space-y-2">
                        <p className="text-xs text-luma-smoke">
                          Bagikan akses <span className="text-luma-ivory font-medium">Editor</span> pada spreadsheet-mu ke:
                        </p>
                        <div className="flex items-center justify-between gap-2 rounded-lg bg-black/40 border border-luma-smokeline px-3 py-1.5">
                          <code className="text-xs font-mono text-luma-sage select-all break-all">
                            tillfold@tillfold.iam.gserviceaccount.com
                          </code>
                          <button
                            type="button"
                            onClick={handleCopySettingsEmail}
                            className="luma-touch px-2.5 py-1 rounded-md bg-white/[0.06] hover:bg-white/[0.12] text-xs text-luma-ivory border border-luma-smokeline flex items-center gap-1.5 shrink-0 cursor-pointer"
                            title="Salin email Service Account"
                          >
                            {copiedSettingsEmail ? (
                              <>
                                <Check className="h-3 w-3 text-mintRise" />
                                <span className="text-mintRise font-medium text-[11px]">Tersalin!</span>
                              </>
                            ) : (
                              <>
                                <Copy className="h-3 w-3 text-luma-smoke" />
                                <span className="text-[11px]">Salin</span>
                              </>
                            )}
                          </button>
                        </div>
                        <p className="text-[11px] text-luma-smoke">
                          Di Google Sheets: Klik <span className="text-luma-ivory font-medium">Bagikan (Share)</span>, tambahkan email bot di atas sebagai <span className="text-luma-ivory font-medium">Editor</span>, lalu simpan tautan sheet Anda di pengaturan.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            </div>
            {/* Seksi 3: Navigasi CTA ke Transaksi */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 sm:p-5 rounded-2xl border border-luma-smokeline bg-obsidian-panel/60 backdrop-blur-xs">
              <div className="text-sm text-zinc-400">
                Ingin melihat seluruh mutasi dan riwayat transaksi kas?
              </div>
              <button
                type="button"
                onClick={() => {
                  setActiveNav("Transaksi");
                  window.location.hash = "#/transactions";
                }}
                className="luma-touch text-xs font-semibold text-amberGold hover:underline flex items-center gap-1.5 cursor-pointer min-h-[44px]"
              >
                <span>Buka transaksi</span>
                <span aria-hidden="true">→</span>
              </button>
            </div>
          </div>
        )}
        </div>
      </main>

      {/* QUICK ADD TRANSACTION MODAL */}
      <AddTransactionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={fetchData}
        accountOptions={availableAccountOptions}
        categories={categories}
        defaultAccount={availableAccountNames[0] || "Rekening Utama"}
      />

      {/* MANAGE CATEGORIES MODAL */}
      <ManageCategoriesModal
        isOpen={isManageCategoriesOpen}
        onClose={() => setIsManageCategoriesOpen(false)}
        onCategoriesUpdated={fetchData}
        transactions={transactions}
      />

      {/* QUICK ADD SUBSCRIPTION MODAL */}
      <CustomModal
        isOpen={isSubModalOpen}
        onClose={() => setIsSubModalOpen(false)}
        title="Tambah Tagihan Rutin"
        subtitle="Pilih akun autodebet dan tanggal jatuh tempo untuk tagihan ini."
        icon={<Bell className="w-5 h-5" />}
        accent="amber"
        maxWidth="md"
      >
        <form onSubmit={handleCreateSubscription} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
              Nama tagihan / layanan
            </label>
            <input
              type="text"
              required
              placeholder="Contoh: Internet rumah atau sewa"
              value={subName}
              onChange={(e) => setSubName(e.target.value)}
              className="w-full bg-obsidian-panel border border-luma-smokeline rounded-2xl px-3.5 py-2.5 text-xs sm:text-sm text-white focus:outline-none focus:border-amberGold transition"
            />
          </div>

          {/* Switch Mode Siklus */}
          <div>
            <label className="block text-xs font-semibold text-zinc-400 mb-2">
              Metode perhitungan jatuh tempo
            </label>
            <div className="grid grid-cols-2 gap-2 p-1 bg-obsidian-panel rounded-2xl border border-luma-smokeline">
              <button
                type="button"
                onClick={() => setSubBillingType("fixed_day")}
                className={`py-2 px-2 text-xs font-semibold rounded-xl transition flex items-center justify-center gap-1.5 cursor-pointer ${
                  subBillingType === "fixed_day"
                    ? "bg-amberGold text-slate-950 font-semibold shadow-xs"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                <Clock className="w-3.5 h-3.5 shrink-0" />
                <span>Tanggal rutin</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setSubBillingType("exact_date");
                  if (!subExactDueDate) {
                    const d = new Date(`${todayWib()}T12:00:00Z`);
                    d.setUTCDate(d.getUTCDate() + 30);
                    setSubExactDueDate(d.toISOString().split("T")[0]);
                  }
                }}
                className={`py-2 px-2 text-xs font-semibold rounded-xl transition flex items-center justify-center gap-1.5 cursor-pointer ${
                  subBillingType === "exact_date"
                    ? "bg-amberGold text-slate-950 font-semibold shadow-xs"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                <Calendar className="w-3.5 h-3.5 shrink-0" />
                <span>Tanggal tertentu</span>
              </button>
              <button
                type="button"
                aria-pressed={subBillingType === "yearly"}
                onClick={() => setSubBillingType("yearly")}
                className={`col-span-2 rounded-xl px-2 py-2 text-xs font-semibold ${subBillingType === "yearly" ? "bg-amberGold text-slate-950" : "text-luma-smoke hover:text-luma-ivory"}`}
              >
                Tahunan
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
                Nominal / periode
              </label>
              <CurrencyInput
                value={subAmount}
                onChange={setSubAmount}
                placeholder="0"
                required
                accent="amber"
                quickAmounts={[25000, 50000, 100000, 225000]}
              />
            </div>

            {subBillingType === "fixed_day" ? (
              <div>
                <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
                  Jatuh tempo (tgl 1-31)
                </label>
                <input
                  type="number"
                  required
                  min={1}
                  max={31}
                  placeholder="Contoh: 25"
                  value={subBillingDay}
                  onChange={(e) => setSubBillingDay(e.target.value)}
                  className="w-full bg-obsidian-panel border border-luma-smokeline rounded-2xl px-3.5 py-2.5 text-xs sm:text-sm text-white font-sans focus:outline-none focus:border-amberGold transition"
                />
              </div>
            ) : (
              <div>
                <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
                  {subBillingType === "yearly" ? "Tanggal tagihan tahunan" : "Tanggal jatuh tempo"}
                </label>
                <DateField label="Tanggal jatuh tempo"
                  required
                  value={subExactDueDate}
                  onChange={(dateValue) => setSubExactDueDate(dateValue)}
                />
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 relative z-20">
            <div>
              <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
                Kategori
              </label>
              <CustomSelect
                value={subCategory}
                onChange={setSubCategory}
                options={SUB_CATEGORY_OPTIONS}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
                Rekening pembayaran
              </label>
              <CustomSelect
                value={subAccount}
                onChange={setSubAccount}
                options={billAccountOptions}
              />
              {billAccountOptions.length === 0 && <p className="mt-1 text-xs text-luma-smoke">Tambahkan rekening terlebih dahulu.</p>}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
              Catatan tambahan (opsional)
            </label>
            <input
              type="text"
              placeholder="Contoh: Dibayar otomatis"
              value={subNotes}
              onChange={(e) => setSubNotes(e.target.value)}
              className="w-full bg-obsidian-panel border border-luma-smokeline rounded-2xl px-3.5 py-2.5 text-xs sm:text-sm text-white focus:outline-none focus:border-amberGold transition placeholder:text-zinc-400"
            />
          </div>

          <div className="pt-3 flex justify-end gap-3 border-t border-luma-smokeline mt-5">
            <button
              type="button"
              onClick={() => setIsSubModalOpen(false)}
              className="px-4 py-2.5 text-xs sm:text-sm font-medium text-zinc-400 hover:text-white border border-luma-smokeline hover:border-white/[0.16] rounded-2xl transition cursor-pointer"
            >
              Batal
            </button>
            <button
              type="submit"
              disabled={billAccountOptions.length === 0}
              className="px-5 py-2.5 text-xs sm:text-sm font-semibold bg-amberGold text-slate-950 hover:bg-amber-300 rounded-2xl transition inline-flex items-center gap-2 shadow-sm cursor-pointer disabled:opacity-50"
            >
              Simpan tagihan
            </button>
          </div>
        </form>
      </CustomModal>

      <GlobalSearchModal isOpen={isGlobalSearchOpen && !!currentUser} onClose={() => setIsGlobalSearchOpen(false)} onChoose={chooseSearchResult} />
      <RecordPaycheckModal
        isOpen={isPaycheckModalOpen && !activePaycheckSession && !isPayrollSettingsOpen}
        accounts={activeAccounts.map(({ name }) => name)}
        allocationAccounts={activeAccounts.flatMap((item) => item.id ? [{ id: item.id, name: item.name }] : [])}
        onClose={() => setIsPaycheckModalOpen(false)}
        onSuccess={(cycle) => {
          if (!cycle) {
            void fetchData();
            return;
          }
          setSelectedPeriod({
            id: `cycle_${cycle.start}`, type: "cycle",
            label: `Siklus (${cycle.start} – ${cycle.end})`,
            start: cycle.start, end: cycle.end, is_current: true,
          });
        }}
        onConfigure={() => setIsPayrollSettingsOpen(true)}
      />
      <PaycheckModal
        isOpen={isPaycheckModalOpen && (!!activePaycheckSession || isPayrollSettingsOpen)}
        settingsOnly={isPayrollSettingsOpen}
        onClose={() => {
          if (isPayrollSettingsOpen) setIsPayrollSettingsOpen(false);
          else setIsPaycheckModalOpen(false);
        }}
        onSuccess={fetchData}
      />

      {/* Transfer Modal */}
      <TransferModal
        isOpen={isTransferModalOpen}
        onClose={() => setIsTransferModalOpen(false)}
        accountOptions={availableAccountOptions}
        onSuccess={fetchData}
      />

      {/* Add Account Modal */}
      <AddAccountModal
        isOpen={isAddAccountModalOpen}
        onClose={() => setIsAddAccountModalOpen(false)}
        onSuccess={fetchData}
      />

      {/* Edit Account Modal */}
      <EditAccountModal
        isOpen={accountToEdit !== null}
        onClose={() => setAccountToEdit(null)}
        account={accountToEdit}
        onSuccess={handleAccountEditSuccess}
      />

      {/* Confirm Delete Subscription Modal */}
      <ConfirmModal
        isOpen={subToDelete !== null}
        onClose={() => setSubToDelete(null)}
        onConfirm={handleConfirmDeleteSubscription}
        title="Hapus Tagihan?"
        message="Tagihan ini akan hilang dari pemantauan bulanan."
        confirmText="Hapus Tagihan"
        loading={deleteLoading}
      />

      {/* Edit Transaction Modal */}
      <EditTransactionModal
        isOpen={txToEdit !== null}
        onClose={() => setTxToEdit(null)}
        transaction={txToEdit}
        onSuccess={fetchData}
        accountOptions={txToEdit && !availableAccountOptions.some((option) => option.value === txToEdit.account)
          ? [...availableAccountOptions, { value: txToEdit.account, label: `${txToEdit.account} (arsip)` }] : availableAccountOptions}
        categoryOptions={dynamicTxCategoryOptions}
      />

      {/* Confirm Delete Transaction Modal */}
      <ConfirmModal
        isOpen={txToDelete !== null}
        onClose={() => { setTxToDelete(null); setDeleteTxError(""); }}
        onConfirm={handleConfirmDeleteTransaction}
        title="Hapus transaksi?"
        message={deleteTxError || (txToDelete?.type === "income" && ["Gaji", "Gaji tambahan"].includes(txToDelete.category)
          ? `Hapus ${formatRupiah(txToDelete.amount)} dari saldo. Jika gaji memulai siklus, periode itu akan dihitung ulang. Hapus transfer pembagian yang masih tercatat terlebih dahulu.`
          : `Hapus "${txToDelete?.description}" senilai ${formatRupiah(txToDelete?.amount || 0)}? Saldo rekening akan disesuaikan.`)}
        confirmText="Hapus transaksi"
        loading={deleteLoading}
      />

      {/* Edit Subscription Modal */}
      <EditSubscriptionModal
        isOpen={subToEdit !== null}
        onClose={() => setSubToEdit(null)}
        subscription={subToEdit}
        onSuccess={fetchData}
        accountOptions={billAccountOptions}
        categoryOptions={SUB_CATEGORY_OPTIONS}
      />


      {/* Add Goal Modal */}
      <AddGoalModal
        isOpen={isAddGoalModalOpen}
        onClose={() => setIsAddGoalModalOpen(false)}
        onSuccess={fetchData}
        availableAccounts={availableAccountNames}
      />

      {/* Edit Goal Modal */}
      <EditGoalModal
        goal={goalToEdit}
        isOpen={goalToEdit !== null}
        onClose={() => setGoalToEdit(null)}
        onSuccess={fetchData}
        availableAccounts={goalToEdit?.linked_account && !availableAccountNames.includes(goalToEdit.linked_account)
          ? [...availableAccountNames, goalToEdit.linked_account] : availableAccountNames}
      />

      {/* Confirm Delete Goal Modal */}
      <ConfirmModal
        isOpen={goalToDelete !== null}
        onClose={() => setGoalToDelete(null)}
        onConfirm={handleConfirmDeleteGoal}
        title="Hapus target tabungan?"
        message="Target dan progresnya akan dihapus."
        confirmText="Hapus target"
        loading={deleteLoading}
      />

      {/* Auth Modal (Masuk / Daftar Akun) */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onSuccess={(user, isNewUser) => {
          setCurrentUser(user);
          fetchData();
          if (isNewUser || !user.is_onboarded) {
            setIsOnboardingModalOpen(true);
          }
        }}
      />

      {/* Onboarding Wizard Modal */}
      <OnboardingWizardModal
        isOpen={isOnboardingModalOpen}
        user={currentUser}
        onClose={() => setIsOnboardingModalOpen(false)}
        onComplete={(updatedUser) => {
          setIsOnboardingModalOpen(false);
          setCurrentUser(updatedUser);
          setStoredUser(updatedUser);
          fetchData();
        }}
      />

      {/* User Profile & Account Settings Modal */}
      {currentUser && <BackupModal isOpen={isBackupModalOpen} onClose={() => setIsBackupModalOpen(false)}
        onRestored={() => {
          setCurrentUser({ ...currentUser, is_onboarded: true });
          setStoredUser({ ...currentUser, is_onboarded: true });
          setIsOnboardingModalOpen(false);
          fetchData();
        }} />}
      {currentUser && (
        <UserProfileModal
          isOpen={isProfileModalOpen}
          onClose={() => setIsProfileModalOpen(false)}
          user={currentUser}
          initialTab={profileModalTab}
          onUserUpdated={(updated) => {
            setCurrentUser(updated);
            fetchData();
          }}
          onLogout={() => {
            setAuthToken(null);
            setStoredUser(null);
            setCurrentUser(null);
            setIsProfileModalOpen(false);
            setIsAuthModalOpen(true);
            fetchData();
          }}
        />
      )}

      {/* Anti-Slop Toast Notification */}
      {toastMessage && (
        <aside
          aria-live="polite"
          className="fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-2xl bg-obsidian-card/95 backdrop-blur-md border border-amberGold/30 text-slateText-primary shadow-2xl animate-in fade-in slide-in-from-bottom-3 duration-200"
        >
          <div className="w-7 h-7 rounded-xl bg-amberGold/15 border border-amberGold/30 flex items-center justify-center text-amberGold shrink-0">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div className="text-xs sm:text-sm font-medium text-zinc-100 pr-2">
            {toastMessage}
          </div>
          <button
            type="button"
            onClick={() => setToastMessage(null)}
            className="text-zinc-400 hover:text-zinc-200 p-1 rounded-lg transition"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </aside>
      )}
    </div>
  );
}
