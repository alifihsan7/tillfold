import { DateField } from "@/components/ui/DateField";
import React, { useState, useEffect, useRef, useId } from "react";
import { Calendar, ChevronDown, Check, Clock, CalendarDays, SlidersHorizontal } from "lucide-react";
import { authFetch } from "@/lib/api";

export interface PeriodOption {
  id: string;
  type: "cycle" | "week" | "month" | "custom";
  label: string;
  start: string;
  end: string;
  month?: string;
  is_current?: boolean;
}

interface PeriodSelectorProps {
  currentPeriod: PeriodOption;
  onSelectPeriod: (period: PeriodOption) => void;
  formatRupiah?: (val: number) => string;
}

export function PeriodSelector({
  currentPeriod,
  onSelectPeriod,
}: PeriodSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"cycle" | "week" | "month" | "custom">("cycle");
  const [periodGroups, setPeriodGroups] = useState<{
    cycles: PeriodOption[];
    weeks: PeriodOption[];
    months: PeriodOption[];
  }>({
    cycles: [],
    weeks: [],
    months: [],
  });

  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popupId = useId();

  useEffect(() => {
    authFetch("/api/v1/analytics/periods")
      .then((res) => res.json())
      .then((data) => {
        if (data) {
          const cycles: PeriodOption[] = data.cycles || [];
          setPeriodGroups({
            cycles,
            weeks: data.weeks || [],
            months: data.months || [],
          });

          // Auto-sync initial active cycle if placeholder was passed
          const activeCycle = cycles.find((c) => c.is_current) || cycles[0];
          if (activeCycle && (currentPeriod.id === "cycle_current" || !currentPeriod.id)) {
            onSelectPeriod(activeCycle);
          }
        }
      })
      .catch((err) => console.error("Error fetching periods:", err));
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (e.target instanceof Element && e.target.closest(".tillfold-calendar")) return;
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setIsOpen(false);
        triggerRef.current?.focus();
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const handleApplyCustom = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customStart || !customEnd) return;
    const customOpt: PeriodOption = {
      id: `custom_${customStart}_${customEnd}`,
      type: "custom",
      label: `Kustom (${customStart} – ${customEnd})`,
      start: customStart,
      end: customEnd,
    };
    onSelectPeriod(customOpt);
    setIsOpen(false);
  };

  return (
    <div ref={dropdownRef} className="luma-period-selector relative min-w-0 text-left">
      {/* Trigger Button */}
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={isOpen}
        aria-controls={popupId}
        aria-label={currentPeriod.label || "Pilih periode"}
        title={currentPeriod.label || "Pilih periode"}
        onClick={() => setIsOpen(!isOpen)}
        className="w-full min-w-0 min-h-11 py-2 px-3.5 rounded-[var(--ai7-radius-control)] text-xs font-medium bg-obsidian-card border border-luma-smokeline hover:border-luma-smoke text-slateText-primary hover:bg-obsidian-hover transition inline-flex items-center gap-2 group"
      >
        <Calendar className="w-3.5 h-3.5 text-luma-ivory shrink-0" />
        <span className="min-w-0 flex-1 text-left truncate">
          {currentPeriod.label || "Pilih Periode"}
        </span>
        <ChevronDown
          className={`w-3.5 h-3.5 text-slateText-muted shrink-0 transition-transform duration-200 ${
            isOpen ? "rotate-180 text-luma-ivory" : ""
          }`}
        />
      </button>

      {/* Floating Modal Popover */}
      {isOpen && (
        <div id={popupId} aria-label="Pilih periode" className="luma-period-popup absolute left-0 mt-2 z-[90] bg-obsidian-card border border-luma-smokeline rounded-[var(--ai7-radius-panel)] shadow-2xl p-3.5">
          {/* Header Type Tabs */}
          <div className="ai7-tab-group grid grid-cols-4 gap-1 bg-obsidian-panel border border-luma-smokeline mb-3">
            <button
              type="button"
              onClick={() => setActiveTab("cycle")}
              className={`py-1.5 text-xs font-semibold rounded-[var(--ai7-radius-control)] transition-all flex items-center justify-center gap-1 ${
                activeTab === "cycle"
                  ? "bg-amberGold text-slate-950 font-semibold shadow-xs"
                  : "text-slateText-secondary hover:text-white"
              }`}
            >
              <Clock className="w-3.5 h-3.5" />
              <span>Siklus</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("week")}
              className={`py-1.5 text-xs font-semibold rounded-[var(--ai7-radius-control)] transition-all flex items-center justify-center gap-1 ${
                activeTab === "week"
                  ? "bg-amberGold text-slate-950 font-semibold shadow-xs"
                  : "text-slateText-secondary hover:text-white"
              }`}
            >
              <CalendarDays className="w-3.5 h-3.5" />
              <span>Minggu</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("month")}
              className={`py-1.5 text-xs font-semibold rounded-[var(--ai7-radius-control)] transition-all flex items-center justify-center gap-1 ${
                activeTab === "month"
                  ? "bg-amberGold text-slate-950 font-semibold shadow-xs"
                  : "text-slateText-secondary hover:text-white"
              }`}
            >
              <Calendar className="w-3.5 h-3.5" />
              <span>Bulan</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("custom")}
              className={`py-1.5 text-xs font-semibold rounded-[var(--ai7-radius-control)] transition-all flex items-center justify-center gap-1 ${
                activeTab === "custom"
                  ? "bg-amberGold text-slate-950 font-semibold shadow-xs"
                  : "text-slateText-secondary hover:text-white"
              }`}
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
              <span>Kustom</span>
            </button>
          </div>

          {/* Tab Content List */}
          <div className="max-h-64 overflow-y-auto space-y-1.5 pr-1">
            {activeTab === "cycle" && (
              <>
                <div className="text-xs font-semibold text-slateText-muted px-2 py-1">
                  Siklus Anggaran Dinamis
                </div>
                {periodGroups.cycles.length === 0 ? (
                  <div className="text-xs text-slateText-muted p-3 text-center">
                    Belum ada riwayat siklus
                  </div>
                ) : (
                  periodGroups.cycles.map((opt) => {
                    const isSelected = currentPeriod.id === opt.id || currentPeriod.start === opt.start;
                    return (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => {
                          onSelectPeriod(opt);
                          setIsOpen(false);
                        }}
                        className={`w-full px-3 py-2 rounded-[var(--ai7-radius-control)] text-left text-xs transition flex items-center justify-between gap-2 ${
                          isSelected
                            ? "bg-luma-coal border border-luma-smokeline text-luma-ivory font-semibold"
                            : "hover:bg-obsidian-hover border border-transparent text-slateText-primary"
                        }`}
                      >
                        <div>
                          <div>{opt.label}</div>
                          <div className="text-xs text-slateText-muted font-sans mt-0.5">
                            {opt.start} s/d {opt.end}
                          </div>
                        </div>
                        {isSelected && <Check className="w-4 h-4 text-luma-ivory shrink-0" />}
                      </button>
                    );
                  })
                )}
              </>
            )}

            {activeTab === "week" && (
              <>
                <div className="text-xs font-semibold text-slateText-muted px-2 py-1">
                  Periode Mingguan (7 Hari)
                </div>
                {periodGroups.weeks.map((opt) => {
                  const isSelected = currentPeriod.id === opt.id;
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => {
                        onSelectPeriod(opt);
                        setIsOpen(false);
                      }}
                      className={`w-full px-3 py-2 rounded-[var(--ai7-radius-control)] text-left text-xs transition flex items-center justify-between gap-2 ${
                        isSelected
                          ? "bg-luma-coal border border-luma-smokeline text-luma-ivory font-semibold"
                          : "hover:bg-obsidian-hover border border-transparent text-slateText-primary"
                      }`}
                    >
                      <div>
                        <div>{opt.label}</div>
                        <div className="text-xs text-slateText-muted font-sans mt-0.5">
                          {opt.start} s/d {opt.end}
                        </div>
                      </div>
                      {isSelected && <Check className="w-4 h-4 text-luma-ivory shrink-0" />}
                    </button>
                  );
                })}
              </>
            )}

            {activeTab === "month" && (
              <>
                <div className="text-xs font-semibold text-slateText-muted px-2 py-1">
                  Kalender Bulanan
                </div>
                {periodGroups.months.map((opt) => {
                  const isSelected = currentPeriod.id === opt.id;
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => {
                        onSelectPeriod(opt);
                        setIsOpen(false);
                      }}
                      className={`w-full px-3 py-2 rounded-[var(--ai7-radius-control)] text-left text-xs transition flex items-center justify-between gap-2 ${
                        isSelected
                          ? "bg-luma-coal border border-luma-smokeline text-luma-ivory font-semibold"
                          : "hover:bg-obsidian-hover border border-transparent text-slateText-primary"
                      }`}
                    >
                      <div>
                        <div>{opt.label}</div>
                        <div className="text-xs text-slateText-muted font-sans mt-0.5">
                          {opt.start} s/d {opt.end}
                        </div>
                      </div>
                      {isSelected && <Check className="w-4 h-4 text-luma-ivory shrink-0" />}
                    </button>
                  );
                })}
              </>
            )}

            {activeTab === "custom" && (
              <form onSubmit={handleApplyCustom} className="p-2 space-y-3">
                <div className="text-xs font-semibold text-slateText-muted">
                  Tentukan Rentang Tanggal Bebas
                </div>
                <div className="space-y-2">
                  <div>
                    <label htmlFor={`${popupId}-start`} className="block text-xs text-slateText-muted mb-1">Tanggal Mulai</label>
                    <DateField
                      id={`${popupId}-start`}
                      required
                      value={customStart}
                      onChange={(dateValue) => setCustomStart(dateValue)}
                    />
                  </div>
                  <div>
                    <label htmlFor={`${popupId}-end`} className="block text-xs text-slateText-muted mb-1">Tanggal Selesai</label>
                    <DateField
                      id={`${popupId}-end`}
                      required
                      value={customEnd}
                      onChange={(dateValue) => setCustomEnd(dateValue)}
                    />
                  </div>
                </div>
                <button
                  type="submit"
                  className="luma-action-primary w-full"
                >
                  Terapkan Rentang
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
