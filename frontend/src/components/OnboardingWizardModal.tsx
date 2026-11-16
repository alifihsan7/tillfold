"use client";

import { DateField } from "@/components/ui/DateField";
import React, { useState } from "react";
import {
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  Wallet,
  Calendar,
  Layers,
  ShieldCheck,
  Plus,
  Trash2,
  AlertCircle
} from "lucide-react";
import { CustomModal } from "./ui/CustomModal";
import { CustomSelect } from "./ui/CustomSelect";
import { CurrencyInput } from "./ui/CurrencyInput";
import { authFetch, UserProfile, setStoredUser } from "@/lib/api";

interface InitialAccountInput {
  name: string;
  type: string;
  tag: string;
  color: string;
  initial_balance: number;
}

interface BucketInput {
  account: string;
  percentage: number;
  via_gate: boolean;
  via_secondary?: string | null;
  purpose: string;
}

interface OnboardingWizardModalProps {
  isOpen: boolean;
  user?: UserProfile | null;
  onClose?: () => void;
  onComplete: (updatedUser: UserProfile) => void;
}

const DEFAULT_INITIAL_ACCOUNTS: InitialAccountInput[] = [
  { name: "Rekening Utama", type: "operasional", tag: "Saku Belanja Harian", color: "amberGold", initial_balance: 0 },
  { name: "Uang Tunai (Cash)", type: "operasional", tag: "Dompet Tunai", color: "amberGold", initial_balance: 0 },
  { name: "Tabungan", type: "tabungan", tag: "Pos Simpanan", color: "purpleLock", initial_balance: 0 },
];

function generateBucketsFromAccounts(accList: InitialAccountInput[]): BucketInput[] {
  if (!accList || accList.length === 0) return [];
  const n = accList.length;
  if (n === 1) {
    return [{
      account: accList[0].name,
      percentage: 100.0,
      via_gate: false,
      via_secondary: null,
      purpose: "Alokasi Operasional & Saku",
    }];
  }
  if (n === 2) {
    return [
      { account: accList[0].name, percentage: 70.0, via_gate: false, via_secondary: null, purpose: "Kebutuhan Pokok & Saku" },
      { account: accList[1].name, percentage: 30.0, via_gate: false, via_secondary: null, purpose: "Tabungan & Cadangan" },
    ];
  }
  if (n === 3) {
    return [
      { account: accList[0].name, percentage: 50.0, via_gate: false, via_secondary: null, purpose: "Kebutuhan Pokok & Saku" },
      { account: accList[1].name, percentage: 30.0, via_gate: false, via_secondary: null, purpose: "Tagihan & Kebutuhan Rutin" },
      { account: accList[2].name, percentage: 20.0, via_gate: false, via_secondary: null, purpose: "Tabungan & Investasi" },
    ];
  }
  const basePct = Math.floor((100 / n) * 10) / 10;
  const remPct = Math.round((100 - basePct * (n - 1)) * 10) / 10;
  return accList.map((acc, idx) => ({
    account: acc.name,
    percentage: idx === 0 ? remPct : basePct,
    via_gate: false,
    via_secondary: null,
    purpose: acc.tag || (acc.type === "investasi" ? "Investasi & Aset" : acc.type === "darurat" ? "Dana Darurat" : "Operasional"),
  }));
}

function getMonthlyDateStart(payday: number): string {
  const now = new Date();
  const curDay = now.getDate();
  const curMonth = now.getMonth();
  const curYear = now.getFullYear();
  let startYear = curYear;
  let startMonth = curMonth;
  if (curDay < payday) {
    if (curMonth === 0) {
      startYear = curYear - 1;
      startMonth = 11;
    } else {
      startMonth = curMonth - 1;
    }
  }
  const maxDays = new Date(startYear, startMonth + 1, 0).getDate();
  const actualDay = Math.min(payday, maxDays);
  const mm = String(startMonth + 1).padStart(2, "0");
  const dd = String(actualDay).padStart(2, "0");
  return `${startYear}-${mm}-${dd}`;
}

export function OnboardingWizardModal({ isOpen, user, onClose, onComplete }: OnboardingWizardModalProps) {
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1: Accounts
  const [accounts, setAccounts] = useState<InitialAccountInput[]>(DEFAULT_INITIAL_ACCOUNTS);
  const [newAccName, setNewAccName] = useState("");
  const [newAccType, setNewAccType] = useState("operasional");

  // Step 2: Budget Cycle & Pocket
  const [cycleType, setCycleType] = useState<"biweekly" | "monthly_date" | "monthly" | "weekly" | "custom">("biweekly");
  const [paycheckDay, setPaycheckDay] = useState(25);
  const [customDays, setCustomDays] = useState(14);
  const [pocketAccount, setPocketAccount] = useState("Rekening Utama");
  const [startDateStr, setStartDateStr] = useState(new Date().toISOString().split("T")[0]);

  // Step 3: Paycheck & Gate
  const [sourceAccount, setSourceAccount] = useState("Rekening Utama");
  const [useGate, setUseGate] = useState(false);
  const gateName = "Perantara transfer";
  const [buckets, setBuckets] = useState<BucketInput[]>(() => generateBucketsFromAccounts(DEFAULT_INITIAL_ACCOUNTS));

  const syncAccountsWithState = (updatedAccounts: InitialAccountInput[]) => {
    if (!updatedAccounts.some((a) => a.name === pocketAccount)) {
      if (updatedAccounts.length > 0) setPocketAccount(updatedAccounts[0].name);
    }
    if (!updatedAccounts.some((a) => a.name === sourceAccount)) {
      if (updatedAccounts.length > 0) setSourceAccount(updatedAccounts[0].name);
    }
    setBuckets((prevBuckets) => {
      const accNames = new Set(updatedAccounts.map((a) => a.name));
      const validBuckets = prevBuckets.filter((b) => accNames.has(b.account));
      const existingNames = new Set(validBuckets.map((b) => b.account));
      const missingAccounts = updatedAccounts.filter((a) => !existingNames.has(a.name));

      if (validBuckets.length === 0) {
        return generateBucketsFromAccounts(updatedAccounts);
      }
      if (missingAccounts.length > 0) {
        const added: BucketInput[] = missingAccounts.map((a) => ({
          account: a.name,
          percentage: 0,
          via_gate: false,
          via_secondary: null,
          purpose: a.tag || "Alokasi Pos",
        }));
        return [...validBuckets, ...added];
      }
      return validBuckets;
    });
  };

  const getEffectiveCycleDays = () => {
    if (cycleType === "biweekly") return 14;
    if (cycleType === "monthly") return 30;
    if (cycleType === "weekly") return 7;
    if (cycleType === "monthly_date") {
      // Days between cycle start and next month's payday - 1
      try {
        const s = new Date(startDateStr);
        const nextMonth = new Date(s.getFullYear(), s.getMonth() + 1, paycheckDay);
        const diffMs = nextMonth.getTime() - s.getTime();
        return Math.max(1, Math.round(diffMs / (1000 * 60 * 60 * 24)));
      } catch {
        return 30;
      }
    }
    return customDays;
  };

  const handleAccountBalanceChange = (index: number, val: number) => {
    setAccounts((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], initial_balance: val };
      return copy;
    });
  };

  const handleAddAccount = () => {
    if (!newAccName.trim()) return;
    const clean = newAccName.trim();
    if (accounts.some((a) => a.name.toLowerCase() === clean.toLowerCase())) {
      setError("Nama rekening sudah ada");
      return;
    }
    const updated = [
      ...accounts,
      {
        name: clean,
        type: newAccType,
        tag: `Akun ${clean}`,
        color: "amberGold",
        initial_balance: 0,
      },
    ];
    setAccounts(updated);
    syncAccountsWithState(updated);
    setNewAccName("");
    setError(null);
  };

  const handleRemoveAccount = (index: number) => {
    if (accounts.length <= 1) {
      setError("Minimal harus ada 1 rekening");
      return;
    }
    const updated = accounts.filter((_, idx) => idx !== index);
    setAccounts(updated);
    syncAccountsWithState(updated);
  };

  const handleFinishOnboarding = async () => {
    setError(null);
    setLoading(true);

    try {
      const payload = {
        initial_accounts: accounts,
        cycle_type: cycleType,
        cycle_days: getEffectiveCycleDays(),
        paycheck_day: paycheckDay,
        cycle_start_date: startDateStr,
        pocket_account: pocketAccount,
        source_account: sourceAccount,
        use_gate: useGate,
        gate_name: gateName,
        buckets: buckets,
      };

      const res = await authFetch("/api/v1/onboarding/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      let data: Record<string, unknown> | null = null;
      try {
        data = await res.json();
      } catch {
        // non-JSON response fallback
      }

      if (!res.ok || !data) {
        const detail = (data as { detail?: string })?.detail;
        throw new Error(detail || `Gagal menyelesaikan proses onboarding (Status: ${res.status})`);
      }

      const userData = data as unknown as UserProfile;
      setStoredUser(userData);
      onComplete(userData);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Terjadi kesalahan pada server saat onboarding");
    } finally {
      setLoading(false);
    }
  };

  const formatRp = (n: number) => `Rp ${n.toLocaleString("id-ID")}`;
  const totalInitialBalance = accounts.reduce((acc, curr) => acc + curr.initial_balance, 0);

  const getCycleTypeLabel = () => {
    if (cycleType === "monthly_date") return `Bulanan (Tiap Tgl ${paycheckDay})`;
    if (cycleType === "monthly") return "Bulanan (30 Hari)";
    if (cycleType === "biweekly") return "2-Mingguan";
    if (cycleType === "weekly") return "Mingguan";
    return "Kustom";
  };

  const getEstimatedEndDate = () => {
    if (!startDateStr) return "";
    try {
      const d = new Date(startDateStr);
      d.setDate(d.getDate() + getEffectiveCycleDays() - 1);
      return d.toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" });
    } catch {
      return "";
    }
  };

  return (
    <CustomModal
      isOpen={isOpen}
      onClose={onClose || (() => {})}
      title="Pengaturan awal keuangan"
      subtitle={`Selamat datang ${user?.full_name || ""}! Mari konfigurasi fondasi keuangan Anda`}
      icon={<Layers className="w-4 h-4 text-amber-400" />}
      accent="amber"
      maxWidth="lg"
    >
      <div className="space-y-5">
        {/* Step Progress Indicators */}
        <div className="grid grid-cols-4 gap-2">
          {[
            { num: 1, label: "Rekening" },
            { num: 2, label: "Siklus" },
            { num: 3, label: "Gajian" },
            { num: 4, label: "Selesai" },
          ].map((s) => {
            const isActive = step === s.num;
            const isDone = step > s.num;
            return (
              <div
                key={s.num}
                className={`flex items-center gap-2 p-2 rounded-2xl border transition ${
                  isActive
                    ? "bg-amberGold/10 border-amberGold/40 text-amberGold"
                    : isDone
                    ? "bg-mintRise/10 border-mintRise/30 text-mintRise"
                    : "bg-obsidian-panel border-luma-smokeline text-zinc-400"
                }`}
              >
                <div
                  className={`w-5 h-5 rounded-lg flex items-center justify-center text-xs font-semibold ${
                    isActive
                      ? "bg-amberGold text-slate-950"
                      : isDone
                      ? "bg-mintRise text-slate-950"
                      : "bg-white/[0.08] text-zinc-400"
                  }`}
                >
                  {isDone ? <CheckCircle2 className="w-3.5 h-3.5 stroke-[2.5]" /> : s.num}
                </div>
                <div className="hidden sm:block min-w-0">
                  <p className="text-xs font-medium leading-none truncate">{s.label}</p>
                </div>
              </div>
            );
          })}
        </div>

        {error && (
          <div className="flex items-start gap-2.5 p-3 rounded-2xl bg-coralFall/10 border border-coralFall/25 text-coralFall text-xs leading-relaxed animate-fadeIn">
            <AlertCircle className="w-4 h-4 shrink-0 text-coralFall mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* STEP 1: INITIAL ACCOUNTS */}
        {step === 1 && (
          <div className="space-y-4 animate-fadeIn">
            <div className="bg-obsidian-card p-4 rounded-2xl border border-luma-smokeline">
              <h4 className="text-xs font-semibold text-white mb-1 flex items-center gap-2">
                <Wallet className="w-4 h-4 text-amberGold" />
                Rekening dan saldo saat ini
              </h4>
              <p className="text-xs text-zinc-400">
                Masukkan saldo yang Anda miliki saat ini. Saldo ini akan menjadi saldo modal awal di pembukuan.
              </p>
            </div>

            <div className="space-y-2.5 max-h-[300px] overflow-y-auto pr-1">
              {accounts.map((acc, idx) => (
                <div
                  key={idx}
                  className="p-3.5 rounded-2xl bg-obsidian-card border border-luma-smokeline flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="w-2.5 h-2.5 rounded-full bg-amberGold shrink-0" />
                    <div>
                      <p className="text-xs font-semibold text-white truncate">{acc.name}</p>
                      <p className="text-xs text-zinc-400 capitalize">{acc.type} • {acc.tag}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 sm:w-[220px]">
                    <div className="flex-1">
                      <CurrencyInput
                        value={acc.initial_balance ? acc.initial_balance.toString() : ""}
                        onChange={(val) => handleAccountBalanceChange(idx, parseInt(val || "0", 10))}
                        placeholder="0"
                        accent="amber"
                      />
                    </div>
                    {accounts.length > 1 && (
                      <button
                        type="button"
                        onClick={() => handleRemoveAccount(idx)}
                        className="p-2 text-zinc-400 hover:text-coralFall rounded-xl hover:bg-coralFall/10 transition cursor-pointer"
                        title="Hapus rekening"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Quick add custom account */}
            <div className="p-3.5 rounded-2xl bg-obsidian-panel border border-dashed border-luma-smokeline flex flex-col sm:flex-row gap-2.5 items-center">
              <input
                type="text"
                value={newAccName}
                onChange={(e) => setNewAccName(e.target.value)}
                placeholder="Nama rekening"
                className="flex-1 bg-obsidian-card border border-luma-smokeline text-white placeholder-zinc-400 rounded-2xl px-3 py-2 text-xs focus:outline-none focus:border-amberGold"
              />
              <div className="w-full sm:w-[150px]">
                <CustomSelect
                  value={newAccType}
                  onChange={(val) => setNewAccType(val)}
                  options={[
                    { value: "operasional", label: "Operasional" },
                    { value: "tagihan", label: "Tagihan" },
                    { value: "gajian", label: "Gajian" },
                    { value: "tabungan", label: "Tabungan" },
                    { value: "investasi", label: "Investasi" },
                    { value: "darurat", label: "Dana darurat" },
                    { value: "ewallet", label: "E-Wallet" },
                  ]}
                  accent="amber"
                />
              </div>
              <button
                type="button"
                onClick={handleAddAccount}
                className="w-full sm:w-auto px-4 py-2 rounded-2xl bg-amberGold/15 hover:bg-amberGold/25 border border-amberGold/30 text-amberGold text-xs font-semibold flex items-center justify-center gap-1.5 transition cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                Tambah
              </button>
            </div>

            <div className="flex items-center justify-between text-xs text-zinc-400 px-1 pt-1">
              <span>Total saldo awal:</span>
              <span className="font-semibold text-mintRise font-sans text-sm">{formatRp(totalInitialBalance)}</span>
            </div>
          </div>
        )}

        {/* STEP 2: BUDGET CYCLE */}
        {step === 2 && (
          <div className="space-y-4 animate-fadeIn">
            <div className="bg-obsidian-card p-4 rounded-2xl border border-luma-smokeline">
              <h4 className="text-xs font-semibold text-white mb-1 flex items-center gap-2">
                <Calendar className="w-4 h-4 text-cyanHub" />
                Pilih durasi siklus anggaran
              </h4>
              <p className="text-xs text-zinc-400">
                Batas belanja harian dihitung otomatis dari panjang siklus ini.
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-2">
                Durasi siklus
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                {[
                  { id: "biweekly", label: "2-Mingguan", desc: "14 hari" },
                  { id: "monthly_date", label: "Tanggal gajian", desc: `Rutin Tiap Tgl ${paycheckDay}` },
                  { id: "monthly", label: "Bulanan", desc: "30 hari kalender" },
                  { id: "weekly", label: "Mingguan", desc: "7 hari" },
                  { id: "custom", label: "Kustom", desc: "Jumlah hari sendiri" },
                ].map((item) => {
                  const isSel = cycleType === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => {
                        const newType = item.id as "biweekly" | "monthly_date" | "monthly" | "weekly" | "custom";
                        setCycleType(newType);
                        if (newType === "monthly_date") {
                          setStartDateStr(getMonthlyDateStart(paycheckDay));
                        }
                      }}
                      className={`p-3 rounded-2xl border text-left transition cursor-pointer ${
                        isSel
                          ? "bg-cyanHub/15 border-cyanHub/50 text-cyanHub shadow-xs"
                          : "bg-obsidian-card border-luma-smokeline text-zinc-400 hover:text-white hover:border-white/[0.16]"
                      }`}
                    >
                      <p className="text-xs font-semibold">{item.label}</p>
                      <p className="text-xs text-zinc-400 mt-0.5 leading-snug">{item.desc}</p>
                    </button>
                  );
                })}
              </div>
            </div>

            {cycleType === "monthly_date" && (
              <div className="p-4 rounded-2xl bg-obsidian-card border border-cyanHub/30 space-y-2 animate-fadeIn">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-medium text-white">
                    Gajian setiap tanggal berapa?
                  </label>
                  <span className="text-xs font-sans text-cyanHub font-semibold px-2.5 py-0.5 rounded-full bg-cyanHub/10 border border-cyanHub/20">
                    Tanggal {paycheckDay}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min={1}
                    max={31}
                    value={paycheckDay}
                    onChange={(e) => {
                      const d = parseInt(e.target.value, 10);
                      setPaycheckDay(d);
                      setStartDateStr(getMonthlyDateStart(d));
                    }}
                    aria-label="Tanggal gajian tiap bulan"
                    className="tillfold-range min-w-0 flex-1 cursor-pointer"
                  />
                  <input
                    type="number"
                    min={1}
                    max={31}
                    value={paycheckDay}
                    onChange={(e) => {
                      const d = Math.min(31, Math.max(1, parseInt(e.target.value, 10) || 1));
                      setPaycheckDay(d);
                      setStartDateStr(getMonthlyDateStart(d));
                    }}
                    className="w-16 bg-obsidian-panel border border-luma-smokeline text-white rounded-2xl px-2.5 py-1.5 text-xs text-center font-sans focus:outline-none focus:border-cyanHub"
                  />
                </div>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  Siklus anggaran bulanan Anda akan otomatis berjalan dari setiap tanggal {paycheckDay} hingga H-1 tanggal {paycheckDay} bulan berikutnya.
                </p>
              </div>
            )}

            {cycleType === "custom" && (
              <div className="p-4 rounded-2xl bg-obsidian-card border border-luma-smokeline space-y-1.5 animate-fadeIn">
                <label className="block text-xs font-medium text-zinc-300">
                  Jumlah hari per siklus
                </label>
                <input
                  type="number"
                  min={1}
                  max={90}
                  value={customDays}
                  onChange={(e) => setCustomDays(Math.max(1, parseInt(e.target.value) || 1))}
                  className="w-full bg-obsidian-panel border border-luma-smokeline text-white rounded-2xl px-3.5 py-2 text-xs focus:outline-none focus:border-cyanHub font-sans"
                />
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                  Rekening belanja harian
                </label>
                <CustomSelect
                  value={pocketAccount}
                  onChange={(val) => setPocketAccount(val)}
                  options={accounts.map((a) => ({
                    value: a.name,
                    label: `${a.name} (${a.tag})`,
                  }))}
                  accent="cyan"
                />
                <p className="text-xs text-zinc-400 mt-1">
                  Rekening ini yang dihitung burn-rate dan pengeluaran harian makanan/jajan.
                </p>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                  Tanggal mulai siklus pertama
                </label>
                <DateField label="Tanggal mulai siklus"
                  value={startDateStr}
                  onChange={(dateValue) => setStartDateStr(dateValue)}
                />
                <p className="text-xs text-zinc-400 mt-1">
                  Tanggal mulai siklus anggaran Anda saat ini.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: PAYCHECK DISTRIBUTION & GATE */}
        {step === 3 && (
          <div className="space-y-4 animate-fadeIn">
            <div className="bg-obsidian-card p-4 rounded-2xl border border-luma-smokeline">
              <h4 className="text-xs font-semibold text-white mb-1 flex items-center gap-2">
                <Layers className="w-4 h-4 text-mintRise" />
                Pembagian gaji
              </h4>
              <p className="text-xs text-zinc-400">
                Atur rekening penampung gaji utama dan apakah ingin mengaktifkan jembatan perantara bebas biaya transfer.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                  Rekening penerima gaji
                </label>
                <CustomSelect
                  value={sourceAccount}
                  onChange={(val) => setSourceAccount(val)}
                  options={accounts.map((a) => ({
                    value: a.name,
                    label: `${a.name} (Hub Gajian)`,
                  }))}
                  accent="mint"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                  Pakai perantara transfer?
                </label>
                <CustomSelect
                  value={useGate ? "yes" : "no"}
                  onChange={(val) => setUseGate(val === "yes")}
                  options={[
                    { value: "yes", label: "Ya, lewat perantara" },
                    { value: "no", label: "Tidak, transfer langsung" },
                  ]}
                  accent="mint"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                Pembagian gaji per rekening (%)
              </label>
              <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
                {buckets.map((b, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-2xl bg-obsidian-card border border-luma-smokeline flex items-center justify-between text-xs"
                  >
                    <div className="min-w-0 pr-2">
                      <p className="font-semibold text-white truncate">{b.account}</p>
                      <p className="text-xs text-zinc-400 truncate">{b.purpose}</p>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <input
                        type="number"
                        step="0.01"
                        min={0}
                        max={100}
                        value={b.percentage}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value) || 0;
                          setBuckets((prev) => {
                            const c = [...prev];
                            c[idx] = { ...c[idx], percentage: val };
                            return c;
                          });
                        }}
                        className="w-16 bg-obsidian-panel border border-luma-smokeline text-white rounded-xl px-2 py-1 text-xs text-right font-sans"
                      />
                      <span className="text-zinc-400 text-xs">%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* STEP 4: SUMMARY & READY */}
        {step === 4 && (
          <div className="space-y-4 animate-fadeIn">
            <div className="bg-mintRise/10 p-5 rounded-3xl border border-mintRise/30 text-center space-y-1">
              <div className="w-12 h-12 rounded-2xl bg-mintRise/20 text-mintRise flex items-center justify-center mx-auto mb-2">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <h4 className="text-sm font-semibold text-mintRise">Pengaturan siap dipakai</h4>
              <p className="text-xs text-zinc-300 max-w-sm mx-auto">
                Data keuangan Anda tersimpan terpisah dari pengguna lain.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3.5 rounded-2xl bg-obsidian-card border border-luma-smokeline space-y-1">
                <span className="text-xs text-zinc-400 font-medium">Siklus anggaran</span>
                <p className="font-semibold text-white">
                  {getEffectiveCycleDays()} Hari ({getCycleTypeLabel()})
                </p>
                <p className="text-xs text-cyanHub">
                  Mulai {startDateStr ? new Date(startDateStr).toLocaleDateString("id-ID", { day: "numeric", month: "short" }) : "Hari ini"}{getEstimatedEndDate() ? ` s.d. ${getEstimatedEndDate()}` : ""}
                </p>
                <p className="text-xs text-zinc-400">Saku: {pocketAccount}</p>
              </div>

              <div className="p-3.5 rounded-2xl bg-obsidian-card border border-luma-smokeline space-y-1">
                <span className="text-xs text-zinc-400 font-medium">Rekening dan saldo awal</span>
                <p className="font-semibold text-mintRise font-sans">
                  {formatRp(totalInitialBalance)}
                </p>
                <p className="text-xs text-zinc-400">{accounts.length} Akun Terdaftar</p>
              </div>

              <div className="p-3.5 rounded-2xl bg-obsidian-card border border-luma-smokeline space-y-1 col-span-2">
                <span className="text-xs text-zinc-400 font-medium">Alur gajian</span>
                <p className="font-medium text-white">
                  Sumber: <span className="text-amberGold">{sourceAccount}</span> • Gerbang:{" "}
                  <span className="text-mintRise">{useGate ? "Lewat perantara" : "Transfer langsung"}</span>
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Navigation Buttons */}
        <div className="flex items-center justify-between pt-3 border-t border-luma-smokeline">
          {step > 1 ? (
            <button
              type="button"
              onClick={() => { setError(null); setStep((prev) => (Math.max(1, prev - 1) as 1 | 2 | 3 | 4)); }}
              className="px-4 py-2.5 rounded-2xl bg-obsidian-card hover:bg-white/[0.06] border border-luma-smokeline text-zinc-300 text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Kembali
            </button>
          ) : (
            <div />
          )}

          {step < 4 ? (
            <button
              type="button"
              onClick={() => { setError(null); setStep((prev) => (Math.min(4, prev + 1) as 1 | 2 | 3 | 4)); }}
              className="px-5 py-2.5 rounded-2xl bg-amberGold hover:bg-amber-300 text-slate-950 text-xs font-semibold flex items-center gap-1.5 shadow-sm transition cursor-pointer"
            >
              Lanjutkan
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          ) : (
            <button
              type="button"
              disabled={loading}
              onClick={handleFinishOnboarding}
              className="px-6 py-2.5 rounded-2xl bg-amberGold hover:bg-amber-300 text-slate-950 text-xs font-semibold flex items-center gap-2 shadow-sm transition cursor-pointer disabled:opacity-50"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="w-3.5 h-3.5 border-2 border-slate-950/20 border-t-slate-950 rounded-full animate-spin" />
                  Menyimpan pengaturan…
                </span>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  Selesai dan buka ringkasan
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </CustomModal>
  );
}
