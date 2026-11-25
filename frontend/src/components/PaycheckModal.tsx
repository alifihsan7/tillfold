"use client";
import { todayWib } from "@/lib/transactionCalendar";

import { DateField } from "@/components/ui/DateField";
import { useLatest } from "@/lib/useLatest";
import React, { useState, useEffect, useMemo } from "react";
import {
  ArrowDownLeft,
  ArrowRight,
  Settings2,
  Plus,
  Trash2,
  RotateCcw,
  Check,
  AlertCircle,
} from "@/components/icons";
import { CustomModal } from "./ui/CustomModal";
import { CurrencyInput } from "./ui/CurrencyInput";
import { CustomSelect } from "./ui/CustomSelect";
import { authFetch } from "@/lib/api";

interface PaycheckConfig {
  id: number;
  source_account: string;
  use_gate: boolean;
  gate_name: string;
  cycle_type: string;
  cycle_days: number;
  pocket_account: string;
  is_active: boolean;
}

interface PaycheckBucket {
  id?: number;
  account: string;
  percentage: number;
  fixed_amount?: number | null;
  via_gate: boolean;
  via_secondary?: string | null;
  purpose: string;
  sort_order: number;
}

interface PaycheckStep {
  id: string;
  phase: number;
  app: string;
  title: string;
  badge?: string;
  description: string;
  source_account: string;
  target_account: string;
  amount: number;
  is_done: boolean;
  is_auto: boolean;
  creates_income: boolean;
  transaction_id?: number | null;
}

interface PaycheckSession {
  id: number;
  total_amount: number;
  date: string;
  status: string;
  note?: string;
  steps: PaycheckStep[];
  completed_steps: number;
  total_steps: number;
  progress_percentage: number;
}

interface PaycheckModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  settingsOnly?: boolean;
}

export default function PaycheckModal({
  isOpen,
  onClose,
  onSuccess,
  settingsOnly = false,
}: PaycheckModalProps) {
  // Modal Views: 'setup' | 'checklist' | 'customize'
  const [view, setView] = useState<"setup" | "checklist" | "customize">("setup");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Setup state
  const [totalAmountStr, setTotalAmountStr] = useState<string>("0");
  const [cycleDate, setCycleDate] = useState<string>(todayWib());
  const [cycleChoice, setCycleChoice] = useState("");
  const [customCycleEnd, setCustomCycleEnd] = useState("");
  const [saveCycleDefault, setSaveCycleDefault] = useState(false);
  const [config, setConfig] = useState<PaycheckConfig>({
    id: 1,
    source_account: "Rekening Utama",
    use_gate: true,
    gate_name: "Perantara transfer",
    cycle_type: "monthly_date",
    cycle_days: 30,
    pocket_account: "Rekening Utama",
    is_active: true,
  });
  const [buckets, setBuckets] = useState<PaycheckBucket[]>([]);
  const [customAmounts, setCustomAmounts] = useState<{ [account: string]: number }>({});

  // Active Session state
  const [activeSession, setActiveSession] = useState<PaycheckSession | null>(null);
  const [togglingStepId, setTogglingStepId] = useState<string | null>(null);

  // Customizer state
  const [customConfig, setCustomConfig] = useState<PaycheckConfig>(config);
  const [customBuckets, setCustomBuckets] = useState<PaycheckBucket[]>([]);
  const allocationPercent = Math.round(customBuckets.reduce((total, bucket) => total + bucket.percentage, 0) * 100) / 100;
  const unallocatedPercent = Math.round((100 - allocationPercent) * 100) / 100;

  // Fetch initial config & active session
  const fetchConfigAndSession = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);

      // Check active session
      const sessRes = await authFetch("/api/v1/paycheck/session/active");
      if (sessRes.ok) {
        const sessData = await sessRes.json();
        if (sessData && sessData.id && sessData.status === "in_progress") {
          setActiveSession(sessData);
          setView("checklist");
          setLoading(false);
          return;
        }
      }

      // If no active session, fetch config & buckets
      const cfgRes = await authFetch(settingsOnly ? "/api/v1/paycheck/config?include_buckets=false" : "/api/v1/paycheck/config");
      if (cfgRes.ok) {
        const data = await cfgRes.json();
        setConfig(data.config);
        setCustomConfig(data.config);
        setBuckets(data.buckets);
        setCustomBuckets(data.buckets);

        // Precompute default amounts from salary if available or existing input
        const initialTotal = data.config.total_salary && data.config.total_salary > 0 
          ? data.config.total_salary 
          : (parseInt(totalAmountStr.replace(/\D/g, ""), 10) || 0);
        if (initialTotal > 0) {
          setTotalAmountStr(initialTotal.toString());
          initAmounts(initialTotal, data.buckets);
        } else {
          initAmounts(0, data.buckets);
        }
      }
      setView(settingsOnly ? "customize" : "setup");
    } catch (err) {
      console.error("Error fetching paycheck data:", err);
      setErrorMsg("Gagal memuat pengaturan alokasi gajian.");
    } finally {
      setLoading(false);
    }
  };

  const initAmounts = (total: number, bList: PaycheckBucket[]) => {
    const calculated: { [account: string]: number } = {};
    if (!bList || bList.length === 0) {
      setCustomAmounts({});
      return;
    }
    if (total <= 0) {
      bList.forEach((b) => {
        calculated[b.account] = 0;
      });
      setCustomAmounts(calculated);
      return;
    }
    let sum = 0;
    bList.forEach((b, idx) => {
      if (idx === bList.length - 1) {
        calculated[b.account] = Math.max(0, total - sum);
      } else {
        const amt = Math.round(total * (b.percentage / 100));
        calculated[b.account] = amt;
        sum += amt;
      }
    });
    setCustomAmounts(calculated);
  };

  const fetchConfigAndSessionRef = useLatest(fetchConfigAndSession);
  useEffect(() => {
    if (isOpen) {
      fetchConfigAndSessionRef.current();
    }
  }, [isOpen, fetchConfigAndSessionRef]);

  // Recalculate amounts when totalAmountStr changes in setup
  const numTotal = useMemo(() => {
    return parseInt(totalAmountStr.replace(/\D/g, ""), 10) || 0;
  }, [totalAmountStr]);

  const totalAllocated = useMemo(() => {
    return Object.values(customAmounts).reduce((acc, val) => acc + (val || 0), 0);
  }, [customAmounts]);

  const balanceDifference = useMemo(() => {
    return numTotal - totalAllocated;
  }, [numTotal, totalAllocated]);

  const cycleType = cycleChoice || config.cycle_type;
  const startTime = Date.parse(cycleDate);
  const dayMs = 86400000;
  const cycleDays = cycleType === "custom" && customCycleEnd
    ? (Date.parse(customCycleEnd) - startTime) / dayMs + 1
    : cycleChoice === "weekly" ? 7 : cycleChoice === "biweekly" ? 14 : cycleChoice === "monthly" ? 30 : config.cycle_days || 14;
  const cycleValid = Number.isFinite(startTime) && cycleDays >= 1 && cycleDays <= 365;
  const endTime = startTime + (cycleDays - 1) * dayMs;
  const endDate = cycleValid && cycleType !== "monthly_date"
    ? new Date(endTime).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })
    : "";

  const handleTotalChange = (val: string) => {
    setTotalAmountStr(val);
    const parsed = parseInt(val.replace(/\D/g, ""), 10) || 0;
    if (parsed > 0) {
      initAmounts(parsed, buckets);
    }
  };

  const handleAmountAdjust = (account: string, amount: number) => {
    setCustomAmounts((prev) => ({
      ...prev,
      [account]: amount,
    }));
  };

  // Start new Paycheck Session
  const handleStartSession = async () => {
    if (!cycleValid) {
      setErrorMsg("Pilih tanggal dan durasi siklus antara 1–365 hari.");
      return;
    }
    if (balanceDifference !== 0) {
      setErrorMsg("Total alokasi harus seimbang dengan total uang masuk sebelum memulai.");
      return;
    }

    try {
      setLoading(true);
      setErrorMsg(null);
      const res = await authFetch("/api/v1/paycheck/session/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          total_amount: numTotal,
          date: cycleDate,
          note: "Alokasi Gajian Siklus",
          allocations: customAmounts,
          ...(cycleType && cycleType !== "monthly_date" ? {
            cycle_type: cycleChoice || "custom",
            cycle_days: cycleDays,
            save_cycle_default: saveCycleDefault && Boolean(cycleChoice),
          } : {}),
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail || "Gagal memulai checklist gajian");
      }

      const sessionData = await res.json();
      if (saveCycleDefault && cycleChoice) {
        setConfig((previous) => ({ ...previous, cycle_type: cycleChoice, cycle_days: cycleDays }));
        setCycleChoice("");
        setSaveCycleDefault(false);
        setCustomCycleEnd("");
      }
      setActiveSession(sessionData);
      setView("checklist");
      onSuccess(); // Refresh parent balances for auto-steps
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Terjadi kesalahan saat memulai sesi gajian";
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  // Toggle single step
  const handleToggleStep = async (stepId: string) => {
    if (!activeSession) return;
    try {
      setTogglingStepId(stepId);
      const res = await authFetch(
        `/api/v1/paycheck/session/${activeSession.id}/step/${stepId}/toggle`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error("Gagal mengupdate langkah");
      const updatedSession = await res.json();
      setActiveSession(updatedSession);
      onSuccess();
    } catch (err) {
      console.error("Step toggle error:", err);
    } finally {
      setTogglingStepId(null);
    }
  };

  // Complete all steps fast
  const handleCompleteAll = async () => {
    if (!activeSession) return;
    try {
      setLoading(true);
      const res = await authFetch(`/api/v1/paycheck/session/${activeSession.id}/complete_all`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Gagal menyelesaikan semua langkah");
      const updatedSession = await res.json();
      setActiveSession(updatedSession);
      onSuccess();
    } catch (err) {
      console.error("Complete all error:", err);
    } finally {
      setLoading(false);
    }
  };

  // Cancel active session
  const handleCancelSession = async () => {
    if (!activeSession) return;
    try {
      setLoading(true);
      const res = await authFetch(`/api/v1/paycheck/session/${activeSession.id}/cancel`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Gagal membatalkan sesi");
      setActiveSession(null);
      setView("setup");
      onSuccess();
    } catch (err) {
      console.error("Cancel session error:", err);
    } finally {
      setLoading(false);
    }
  };

  // Save customized pipeline configuration
  const handleSaveCustomize = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      // 1. Update config
      const cfgRes = await authFetch("/api/v1/paycheck/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_account: customConfig.source_account,
          use_gate: customConfig.use_gate,
          gate_name: customConfig.gate_name,
          cycle_type: customConfig.cycle_type,
          cycle_days: customConfig.cycle_days,
          pocket_account: customConfig.pocket_account,
        }),
      });
      if (!cfgRes.ok) throw new Error("Gagal menyimpan konfigurasi alur");
      const savedCfg = await cfgRes.json();
      setConfig(savedCfg);

      if (settingsOnly) {
        onSuccess?.();
        onClose();
        return;
      }

      // 2. Update buckets
      const bRes = await authFetch("/api/v1/paycheck/buckets", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          customBuckets.map((b, i) => ({
            account: b.account,
            percentage: b.percentage,
            fixed_amount: b.fixed_amount || null,
            via_gate: b.via_gate,
            via_secondary: b.via_secondary || null,
            purpose: b.purpose,
            sort_order: i + 1,
          }))
        ),
      });
      if (!bRes.ok) throw new Error("Gagal menyimpan pos alokasi");
      const savedBuckets = await bRes.json();
      setBuckets(savedBuckets);

      // Re-init amounts
      initAmounts(numTotal, savedBuckets);
      setView("setup");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal menyimpan perubahan alur";
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  // Group steps by phase for checklist view
  const groupedSteps = useMemo(() => {
    if (!activeSession) return {};
    const groups: { [phase: number]: PaycheckStep[] } = {};
    activeSession.steps.forEach((s) => {
      if (!groups[s.phase]) groups[s.phase] = [];
      groups[s.phase].push(s);
    });
    return groups;
  }, [activeSession]);

  const isAllCompleted = activeSession?.status === "completed";

  return (
    <CustomModal
      isOpen={isOpen}
      onClose={onClose}
      title={
        view === "checklist"
          ? "Checklist transfer gajian"
          : view === "customize"
          ? settingsOnly ? "Atur rekening gaji" : "Atur alokasi gaji"
          : config.cycle_type === "monthly" || config.cycle_days === 30
          ? "Alokasi gajian bulanan"
          : config.cycle_type === "weekly" || config.cycle_days === 7
          ? "Alokasi gajian mingguan"
          : config.cycle_type === "biweekly" || config.cycle_days === 14
          ? "Alokasi gajian 2 mingguan"
          : `Alokasi gajian (siklus ${config.cycle_days || 14} hari)`
      }
      subtitle={
        view === "checklist"
          ? "Centang setiap transfer yang sudah dilakukan."
          : view === "customize"
          ? (settingsOnly ? "Pilih rekening penerima gaji dan rekening belanja harian." : "Pilih rekening penerima dan atur pembagiannya.")
          : "Atur siklus dan cek pembagian gaji."
      }
      icon={<ArrowDownLeft className="w-5 h-5 text-mintRise" />}
      accent="mint"
      maxWidth="xl"
    >
      {errorMsg && (
        <div className="p-3.5 mb-4 rounded-2xl bg-coralFall/10 border border-coralFall/20 flex items-center gap-2.5 text-xs text-coralFall">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* -------------------- VIEW 1: SETUP & ADJUSTMENT -------------------- */}
      {view === "setup" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <div>
              <label className="block text-xs font-semibold text-luma-smoke mb-1.5">
                Total uang masuk
              </label>
              <CurrencyInput
                value={totalAmountStr}
                onChange={handleTotalChange}
                placeholder="1500000"
                accent="mint"
                quickAmounts={[1000000, 1500000, 2000000, 2500000]}
              />
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor="paycheck-cycle-date" className="block text-xs font-semibold text-luma-smoke">
                  Tanggal gajian
                </label>
              </div>
              <DateField
                id="paycheck-cycle-date"
                value={cycleDate}
                onChange={(dateValue) => setCycleDate(dateValue)}
              />
            </div>
          </div>

          <fieldset className="space-y-3 rounded-2xl border border-luma-smokeline p-4">
            <legend className="px-1 text-sm font-semibold">Siklus anggaran</legend>
            <div className="space-y-1 text-sm">
              <span>Durasi</span>
              <CustomSelect
                label="Durasi siklus"
                value={cycleChoice}
                onChange={(value) => {
                  setCycleChoice(value);
                  setSaveCycleDefault(false);
                  setCustomCycleEnd("");
                }}
                options={[
                  { value: "", label: `Default · ${config.cycle_type === "monthly_date" ? "Bulanan" : `${config.cycle_days || 14} hari`}` },
                  { value: "weekly", label: "Mingguan · 7 hari" },
                  { value: "biweekly", label: "Dua mingguan · 14 hari" },
                  { value: "monthly", label: "Bulanan · 30 hari" },
                  { value: "custom", label: "Kustom" },
                ]}
              />
            </div>
            {cycleType === "custom" && (
              <div className="space-y-1 text-sm">
                <label htmlFor="paycheck-cycle-end">Tanggal akhir</label>
                <DateField id="paycheck-cycle-end"
                  min={cycleDate}
                  value={customCycleEnd || (cycleValid ? new Date(endTime).toISOString().slice(0, 10) : "")}
                  onChange={(dateValue) => {
                    if (dateValue) setCycleChoice("custom");
                    setCustomCycleEnd(dateValue);
                  }}
                />
              </div>
            )}
            {endDate && <p className="text-xs text-luma-smoke">Berakhir {endDate} · {cycleDays} hari</p>}
            {cycleChoice && (
              <label className="flex min-h-11 cursor-pointer items-center gap-2 text-sm">
                <input type="checkbox" checked={saveCycleDefault} onChange={(event) => setSaveCycleDefault(event.target.checked)} />
                Jadikan default untuk gajian berikutnya
              </label>
            )}
          </fieldset>

          <p className="text-sm text-luma-smoke">
            Gaji masuk ke <strong className="text-luma-ivory">{config.source_account || "rekening penerima"}</strong>
            {" · "}{buckets.length} pos alokasi
          </p>

          {/* Allocation Breakdown Table */}
          <div className="p-5 rounded-3xl luma-inset space-y-3.5 shadow-sm">
            <div className="flex justify-between items-center pb-3 border-b border-luma-smokeline">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-luma-smoke ">
                  Pembagian (bisa diubah)
                </span>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-sans font-semibold bg-obsidian-card text-luma-secondary border border-luma-smokeline">
                  {buckets.length} Pos
                </span>
              </div>
              <button
                type="button"
                onClick={() => initAmounts(numTotal, buckets)}
                className="text-xs font-medium text-luma-smoke hover:text-mintRise flex items-center gap-1 transition cursor-pointer"
                title="Kembalikan ke formula persentase standar"
              >
                <RotateCcw className="w-3 h-3" />
                Kembalikan bawaan
              </button>
            </div>

            <div className="space-y-2.5">
              {buckets.map((b) => {
                const currentAmt = customAmounts[b.account] || 0;
                return (
                  <div
                    key={b.account}
                    className="p-3.5 rounded-2xl bg-obsidian-card border border-luma-smokeline hover:border-white/[0.16] transition flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-luma-smoke" aria-hidden="true" />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-sm text-white truncate">
                            {b.account}
                          </span>
                          <span className="px-2 py-0.5 rounded-full text-xs font-sans text-luma-smoke bg-obsidian-panel border border-luma-smokeline">
                            {b.percentage}%
                          </span>
                          {config.use_gate && b.via_gate && (
                            <span className="ui-badge ui-badge--neutral">
                              Lewat perantara
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-luma-smoke truncate mt-0.5">
                          {b.purpose}
                        </p>
                      </div>
                    </div>

                    <div className="w-full sm:w-44 shrink-0 self-end sm:self-center">
                      <CurrencyInput
                        value={currentAmt > 0 ? currentAmt.toString() : ""}
                        onChange={(val) => {
                          const num = parseInt(val, 10) || 0;
                          handleAmountAdjust(b.account, num);
                        }}
                        placeholder="0"
                        accent="mint"
                      />
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Total Balance Status Banner */}
            <div className="pt-3 border-t border-luma-smokeline flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
              <div className="flex items-center gap-2">
                <span className="text-xs text-luma-smoke">Total terbagi:</span>
                <span className="font-sans font-semibold text-sm text-white">
                  Rp {totalAllocated.toLocaleString("id-ID")}
                </span>
                <span className="text-xs text-luma-smoke">/ Rp {numTotal.toLocaleString("id-ID")}</span>
              </div>

              <div>
                {balanceDifference === 0 ? (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-mintRise/10 text-mintRise border border-mintRise/20">
                    <Check className="w-3.5 h-3.5" />
                    Terbagi 100%
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amberGold/10 text-amberGold border border-amberGold/20">
                    <AlertCircle className="w-3.5 h-3.5" />
                    Selisih: {balanceDifference > 0 ? "+" : ""}
                    Rp {balanceDifference.toLocaleString("id-ID")}{" "}
                    {balanceDifference > 0 ? "(belum terbagi semua)" : "(Kelebihan)"}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Action Row */}
          <div className="pt-3 flex flex-wrap items-center justify-between gap-3 border-t border-luma-smokeline">
            <button
              type="button"
              onClick={() => {
                setCustomConfig({ ...config });
                setCustomBuckets(buckets.map((bucket) => ({ ...bucket })));
                setErrorMsg(null);
                setView("customize");
              }}
              className="text-xs font-semibold text-luma-secondary hover:text-white flex items-center gap-1.5 px-3.5 py-2.5 rounded-2xl border border-luma-smokeline hover:border-white/[0.16] transition cursor-pointer"
            >
              <Settings2 className="w-4 h-4 text-luma-smoke" />
              <span>Ubah alokasi</span>
            </button>

            <div className="flex items-center gap-2 ml-auto">
              <button
                type="button"
                onClick={onClose}
                className="luma-action-secondary"
              >
                Batal
              </button>
              <button
                type="button"
                onClick={handleStartSession}
                disabled={loading || !cycleValid || balanceDifference !== 0}
                className="luma-action-primary"
              >
                <span>{loading ? "Menyiapkan..." : "Mulai checklist transfer"}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* -------------------- VIEW 2: STEP-BY-STEP CHECKLIST -------------------- */}
      {view === "checklist" && activeSession && (
        <div className="space-y-4">
          {/* Progress Header Card */}
          <div className="p-5 rounded-3xl luma-inset space-y-3 shadow-sm">
            <div className="flex justify-between items-center">
              <div>
                <span className="text-xs font-semibold text-luma-smoke ">
                  Status pembagian
                </span>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="font-sans font-semibold text-lg sm:text-xl text-white">
                    Rp {activeSession.total_amount.toLocaleString("id-ID")}
                  </span>
                  <span className="text-xs text-luma-smoke">
                    • Siklus {activeSession.date}
                  </span>
                </div>
              </div>
              <div className="text-right">
                <span className="text-xs font-semibold font-sans text-mintRise">
                  {activeSession.completed_steps} / {activeSession.total_steps} Selesai
                </span>
                <div className="text-xs text-luma-smoke">
                  {activeSession.progress_percentage}% terdistribusi
                </div>
              </div>
            </div>

            {/* Progress Bar */}
            <div className="w-full h-2 rounded-full bg-obsidian-card overflow-hidden p-0.5 border border-luma-smokeline">
              <div
                className="h-full rounded-full bg-mintRise transition-all duration-500"
                style={{ width: `${activeSession.progress_percentage}%` }}
              />
            </div>
          </div>

          {/* Congratulations banner if completed */}
          {isAllCompleted && (
            <div className="p-4 rounded-2xl bg-mintRise/10 border border-mintRise/30 flex items-center justify-between gap-3 shadow-sm">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-mintRise/20 flex items-center justify-center text-mintRise shrink-0">
                  <Check className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-semibold text-sm text-mintRise">Pembagian gaji selesai</h4>
                  <p className="text-xs text-luma-secondary mt-0.5">
                    Seluruh transfer alokasi berhasil dicatat ke saldo rekening.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="luma-action-secondary shrink-0"
              >
                Tutup
              </button>
            </div>
          )}

          {/* Grouped Steps List */}
          <div className="space-y-4 max-h-[55vh] overflow-y-auto scrollbar-thin pr-1">
            {[1, 2, 3].map((phaseNum) => {
              const phaseSteps = groupedSteps[phaseNum];
              if (!phaseSteps || phaseSteps.length === 0) return null;

              const phaseTitle =
                phaseNum === 1
                  ? `FASE 1: Buka ${config.source_account} (Rekening Hub)`
                  : phaseNum === 2
                  ? `FASE 2: Buka ${config.gate_name} (Distribusi Bebas Admin)`
                  : "Fase 3: rekening investasi dan sekunder";

              const phaseColor =
                phaseNum === 1
                  ? "border-luma-smokeline text-luma-ivory bg-white/[0.03]"
                  : phaseNum === 2
                  ? "border-luma-smokeline text-luma-ivory bg-white/[0.03]"
                  : "border-luma-smokeline text-luma-ivory bg-white/[0.03]";

              return (
                <div key={phaseNum} className="space-y-2">
                  <div className="flex items-center gap-2 px-1">
                    <span className={`text-xs font-semibold px-3 py-0.5 rounded-full border ${phaseColor}`}>
                      {phaseTitle}
                    </span>
                  </div>

                  <div className="space-y-2">
                    {phaseSteps.map((step) => {
                      const isToggling = togglingStepId === step.id;
                      return (
                        <div
                          key={step.id}
                          onClick={() => !isToggling && handleToggleStep(step.id)}
                          className={`p-3.5 rounded-2xl border transition cursor-pointer select-none flex items-center justify-between gap-3 shadow-xs ${
                            step.is_done
                              ? "bg-obsidian-panel/60 border-luma-smokeline opacity-80"
                              : "bg-obsidian-card border-luma-smokeline hover:border-mintRise/40"
                          }`}
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            {/* Checkbox button */}
                            <div className="shrink-0">
                              {step.is_done ? (
                                <div className="w-6 h-6 rounded-lg bg-mintRise/20 border border-mintRise/50 flex items-center justify-center text-mintRise">
                                  <Check className="w-4 h-4" />
                                </div>
                              ) : (
                                <div className="w-6 h-6 rounded-lg bg-obsidian-panel border border-luma-smokeline flex items-center justify-center hover:border-mintRise transition">
                                  {isToggling && (
                                    <div className="w-3 h-3 rounded-full border-2 border-mintRise border-t-transparent animate-spin" />
                                  )}
                                </div>
                              )}
                            </div>

                            {/* Step details */}
                            <div className="min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span
                                  className={`font-semibold text-sm truncate ${
                                    step.is_done
                                      ? "text-luma-smoke line-through"
                                      : "text-white"
                                  }`}
                                >
                                  {step.title}
                                </span>
                                {step.badge && (
                                  <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-obsidian-panel border border-luma-smokeline text-luma-secondary shrink-0">
                                    {step.badge}
                                  </span>
                                )}
                                {step.is_auto && (
                                  <span className="px-2 py-0.5 rounded-full text-xs font-sans text-cyanHub bg-cyanHub/10 border border-cyanHub/20">
                                    Otomatis
                                  </span>
                                )}
                              </div>
                              <p className="text-xs text-luma-smoke truncate mt-0.5">
                                {step.description}
                              </p>
                            </div>
                          </div>

                          {/* Step amount */}
                          <div className="text-right shrink-0">
                            <span
                              className={`font-sans font-semibold text-sm ${
                                step.is_done
                                  ? "text-luma-smoke"
                                  : "text-mintRise"
                              }`}
                            >
                              Rp {step.amount.toLocaleString("id-ID")}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Action Row */}
          <div className="pt-3 flex flex-wrap items-center justify-between gap-3 border-t border-luma-smokeline">
            <button
              type="button"
              onClick={handleCancelSession}
              disabled={loading}
              className="text-xs font-semibold text-coralFall hover:brightness-110 flex items-center gap-1.5 px-3 py-2 rounded-2xl border border-coralFall/20 hover:border-coralFall/40 transition cursor-pointer"
              title="Batalkan sesi ini dan hapus transaksi yang sempat dicatat"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Batalkan sesi</span>
            </button>

            <div className="flex items-center gap-2 ml-auto">
              {!isAllCompleted && (
                <button
                  type="button"
                  onClick={handleCompleteAll}
                  disabled={loading}
                  className="px-4 py-2 text-xs font-semibold text-luma-secondary hover:text-white border border-luma-smokeline hover:border-white/[0.16] rounded-2xl transition cursor-pointer"
                >
                  Tandai semua selesai
                </button>
              )}
              <button
                type="button"
                onClick={onClose}
                className="luma-action-primary"
              >
                {isAllCompleted ? "Selesai & tutup" : "Simpan & lanjutkan nanti"}
              </button>
            </div>
          </div>
        </div>
      )}


      {view === "customize" && (
        <div className="payroll-form space-y-4">
          <fieldset className="grid gap-3 rounded-2xl border border-luma-smokeline p-4 sm:grid-cols-2">
            <legend className="px-1 text-sm font-semibold">Rekening</legend>
            <label className="block space-y-1 text-sm">
              <span>Rekening penerima gaji</span>
              <input
                type="text"
                className="w-full"
                value={customConfig.source_account}
                onChange={(event) => setCustomConfig({ ...customConfig, source_account: event.target.value })}
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span>Rekening belanja harian</span>
              <input
                type="text"
                className="w-full"
                value={customConfig.pocket_account}
                onChange={(event) => setCustomConfig({ ...customConfig, pocket_account: event.target.value })}
              />
            </label>
          </fieldset>

          {!settingsOnly && <>
          {/* Buckets Editor */}
          <div className="p-5 rounded-3xl luma-inset space-y-3 shadow-sm">
            <div className="flex justify-between items-center pb-2 border-b border-luma-smokeline">
              <span className="text-xs font-semibold text-luma-smoke ">
                Pembagian gaji
              </span>
              <button
                type="button"
                onClick={() => {
                  setCustomBuckets([
                    ...customBuckets,
                    {
                      account: "",
                      percentage: 0,
                      via_gate: customConfig.use_gate,
                      purpose: "",
                      sort_order: customBuckets.length + 1,
                    },
                  ]);
                }}
                className="text-xs font-semibold text-mintRise hover:brightness-110 flex items-center gap-1 transition cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                Tambah rekening
              </button>
            </div>

            <div className="space-y-2.5">
              {customBuckets.map((b, idx) => (
                <div
                  key={idx}
                  className="space-y-2 rounded-xl border border-luma-smokeline p-3"
                >
                  <div className="grid grid-cols-[minmax(0,1fr)_minmax(5.5rem,7rem)] gap-2 sm:grid-cols-[minmax(0,1.2fr)_6rem_minmax(0,1fr)]">
                    <label className="block min-w-0 space-y-1">
                      <span>Rekening</span>
                    <input
                      type="text"
                      value={b.account}
                      onChange={(e) => {
                        const copy = [...customBuckets];
                        copy[idx].account = e.target.value;
                        setCustomBuckets(copy);
                      }}
                      className="w-full"
                      aria-label={`Rekening alokasi ${idx + 1}`}
                      placeholder="Nama rekening"
                    />
                    </label>
                    <label className="block min-w-0 space-y-1">
                      <span>Porsi (%)</span>
                      <input
                        type="number"
                        step="0.1"
                        value={b.percentage}
                        onChange={(e) => {
                          const copy = [...customBuckets];
                          copy[idx].percentage = parseFloat(e.target.value) || 0;
                          setCustomBuckets(copy);
                        }}
                        className="w-full tabular-nums"
                        min={0}
                        max={100}
                        aria-label={`Persentase alokasi ${idx + 1}`}
                        placeholder="%"
                      />
                    </label>
                    <label className="col-span-2 block min-w-0 space-y-1 sm:col-span-1">
                      <span>Keterangan</span>
                    <input
                      type="text"
                      value={b.purpose}
                      onChange={(e) => {
                        const copy = [...customBuckets];
                        copy[idx].purpose = e.target.value;
                        setCustomBuckets(copy);
                      }}
                      className="w-full"
                      aria-label={`Keterangan alokasi ${idx + 1}`}
                      placeholder="Keterangan"
                    />
                    </label>
                  </div>

                  <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
                    {customConfig.use_gate && <label className="text-xs text-luma-smoke flex items-center gap-1 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={b.via_gate}
                        onChange={(e) => {
                          const copy = [...customBuckets];
                          copy[idx].via_gate = e.target.checked;
                          setCustomBuckets(copy);
                        }}
                        className="rounded border-luma-smokeline"
                      />
                      Lewat perantara
                    </label>}

                    <button
                      type="button"
                      onClick={() => {
                        setCustomBuckets(customBuckets.filter((_, i) => i !== idx));
                      }}
                      className="p-1.5 rounded-lg text-luma-smoke hover:text-coralFall transition cursor-pointer"
                      aria-label={`Hapus alokasi ${b.account || idx + 1}`}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* Validation sum */}
            <div className="flex flex-wrap justify-between gap-2 border-t border-luma-smokeline pt-3 text-xs tabular-nums" aria-live="polite">
              <span>Total pembagian {allocationPercent}%</span>
              <span className={unallocatedPercent === 0 ? "text-mintRise" : "text-amberGold"}>
                {unallocatedPercent === 0 ? "Sudah terbagi semua" :
                  unallocatedPercent > 0 ? `Belum terbagi ${unallocatedPercent}%` : `Lebih ${Math.abs(unallocatedPercent)}%`}
              </span>
            </div>
          </div>

          <fieldset className="space-y-3 rounded-2xl border border-luma-smokeline p-4">
            <legend className="px-1 text-sm font-semibold">Opsi transfer</legend>
            <label className="flex min-h-11 cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={customConfig.use_gate}
                onChange={(event) => setCustomConfig({ ...customConfig, use_gate: event.target.checked })}
              />
              Pakai perantara transfer
            </label>
            {customConfig.use_gate && (
              <label className="block space-y-1 text-sm">
                <span>Nama perantara</span>
                <input
                  type="text"
                  className="w-full"
                  value={customConfig.gate_name}
                  onChange={(event) => setCustomConfig({ ...customConfig, gate_name: event.target.value })}
                />
              </label>
            )}
          </fieldset>

          </>}

          <div className="pt-3 flex justify-end gap-3 border-t border-luma-smokeline">
            <button
              type="button"
              onClick={() => settingsOnly ? onClose() : setView("setup")}
              className="luma-action-secondary"
            >
              Batal
            </button>
            <button
              type="button"
              onClick={handleSaveCustomize}
              disabled={loading}
              className="luma-action-primary"
            >
              {loading ? "Menyiapkan..." : settingsOnly ? "Simpan rekening" : "Simpan alokasi"}
            </button>
          </div>
        </div>
      )}
    </CustomModal>
  );
}
