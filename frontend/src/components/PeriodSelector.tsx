import React, { useEffect, useId, useRef, useState } from "react";
import { Calendar, Check, ChevronDown } from "@/components/icons";
import { DateField } from "@/components/ui/DateField";
import { Badge, SegmentedControl, type SegmentedOption } from "@/components/ui/controls";
import { authFetch } from "@/lib/api";
import { formatCompactRange, formatDateRange } from "@/lib/format";
import { useLatest } from "@/lib/useLatest";

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
}

const periodTabs: SegmentedOption<PeriodOption["type"]>[] = [
  { value: "cycle", label: "Siklus" },
  { value: "week", label: "Minggu" },
  { value: "month", label: "Bulan" },
  { value: "custom", label: "Kustom" },
];
const currentBadges = { cycle: "Berjalan", week: "Minggu ini", month: "Bulan ini" };
const monthOnly = new Intl.DateTimeFormat("id-ID", { month: "long", timeZone: "UTC" });
const monthAndYear = new Intl.DateTimeFormat("id-ID", { month: "long", year: "numeric", timeZone: "UTC" });
const recentCycleCount = 3;

/** Shorter label for the trigger button; the full title stays in the tooltip and accessible name. */
function periodTriggerTitle(period: PeriodOption) {
  if (!period.start || !period.end) return period.label || "Pilih periode";
  if (period.type === "month") {
    const start = new Date(period.start);
    return start.getUTCFullYear() === new Date().getFullYear() ? monthOnly.format(start) : monthAndYear.format(start);
  }
  return formatCompactRange(period.start, period.end);
}

function periodTitle(period: PeriodOption) {
  if (!period.start || !period.end) return period.label || "Pilih periode";
  return period.type === "month"
    ? monthAndYear.format(new Date(period.start))
    : formatDateRange(period.start, period.end);
}

export function PeriodSelector({ currentPeriod, onSelectPeriod }: PeriodSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<PeriodOption["type"]>(currentPeriod.type);
  const [showHistory, setShowHistory] = useState(false);
  const [periods, setPeriods] = useState<Record<"cycles" | "weeks" | "months", PeriodOption[]>>({
    cycles: [], weeks: [], months: [],
  });
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const currentPeriodIdRef = useLatest(currentPeriod.id);
  const onSelectPeriodRef = useLatest(onSelectPeriod);
  const popupId = useId();
  const cycleId = currentPeriod.type === "cycle" ? currentPeriod.id : null;

  useEffect(() => {
    const request = new AbortController();
    authFetch("/api/v1/analytics/periods", { signal: request.signal })
      .then((res) => res.json())
      .then((data) => {
        if (!data || request.signal.aborted) return;
        const cycles: PeriodOption[] = data.cycles || [];
        setPeriods({ cycles, weeks: data.weeks || [], months: data.months || [] });
        const activeCycle = cycles.find((cycle) => cycle.is_current) || cycles[0];
        if (activeCycle && currentPeriodIdRef.current === "cycle_current") {
          onSelectPeriodRef.current(activeCycle);
        }
      })
      .catch((error) => {
        if (!request.signal.aborted) console.error("Error fetching periods:", error);
      });
    return () => request.abort();
  }, [cycleId, currentPeriodIdRef, onSelectPeriodRef]);

  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (event.target instanceof Element && event.target.closest(".tillfold-calendar")) return;
      if (!dropdownRef.current?.contains(event.target as Node)) setIsOpen(false);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !event.defaultPrevented) {
        if (dropdownRef.current?.querySelector(".tillfold-date-field button[aria-expanded='true']")) return;
        event.preventDefault();
        setIsOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const activeCycle = periods.cycles.find((cycle) => cycle.is_current);
  const cycles = activeCycle ? [activeCycle, ...periods.cycles.filter((cycle) => cycle !== activeCycle)] : periods.cycles;
  const cycleHeading = (activeCycle || cycles[0])?.label.split(" · ")[0].replace(", gajian", " · Gajian");
  const recentCycles = cycles.slice(0, recentCycleCount);
  const options = {
    cycle: showHistory ? cycles : recentCycles,
    week: periods.weeks,
    month: periods.months,
  };

  const selectPeriod = (period: PeriodOption) => {
    onSelectPeriod(period);
    setIsOpen(false);
    triggerRef.current?.focus();
  };

  const togglePopup = () => {
    if (!isOpen) {
      setActiveTab(currentPeriod.type);
      setShowHistory(currentPeriod.type === "cycle" && cycles.slice(recentCycleCount).some((cycle) => cycle.id === currentPeriod.id));
      setCustomStart(currentPeriod.type === "custom" ? currentPeriod.start : "");
      setCustomEnd(currentPeriod.type === "custom" ? currentPeriod.end : "");
    }
    setIsOpen(!isOpen);
  };

  const applyCustom = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!customStart || !customEnd || customStart > customEnd) return;
    selectPeriod({
      id: `custom_${customStart}_${customEnd}`,
      type: "custom",
      label: `Kustom · ${formatDateRange(customStart, customEnd)}`,
      start: customStart,
      end: customEnd,
    });
  };

  const title = periodTitle(currentPeriod);
  const triggerTitle = periodTriggerTitle(currentPeriod);

  return (
    <div ref={dropdownRef} className="luma-period-selector relative min-w-0 text-left">
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={isOpen}
        aria-controls={isOpen ? popupId : undefined}
        aria-label={`Pilih periode: ${title}`}
        title={title}
        onClick={togglePopup}
        className="w-full min-w-0 min-h-11 py-2 px-3.5 text-xs font-medium inline-flex items-center gap-2"
      >
        <Calendar className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
        <span className="min-w-0 flex-1 text-left truncate">{triggerTitle}</span>
        <ChevronDown className={`w-3.5 h-3.5 shrink-0 ${isOpen ? "rotate-180" : ""}`} aria-hidden="true" />
      </button>

      {isOpen && (
        <div id={popupId} className="luma-period-popup absolute left-0 mt-2 z-[90] border p-3">
          <SegmentedControl
            label="Jenis periode"
            value={activeTab}
            options={periodTabs}
            onChange={setActiveTab}
            className="luma-period-tabs"
            fill
          />

          {activeTab === "custom" ? (
            <form onSubmit={applyCustom} className="fold-period-custom space-y-3 p-1">
              <div className="fold-period-dates">
                <div>
                  <label htmlFor={`${popupId}-start`} className="block text-xs text-luma-smoke mb-1">Mulai</label>
                  <DateField id={`${popupId}-start`} required value={customStart} onChange={setCustomStart} />
                </div>
                <div>
                  <label htmlFor={`${popupId}-end`} className="block text-xs text-luma-smoke mb-1">Sampai</label>
                  <DateField id={`${popupId}-end`} required value={customEnd} min={customStart || undefined} onChange={setCustomEnd} />
                </div>
              </div>
              <button type="submit" className="luma-action-primary w-full">Terapkan</button>
            </form>
          ) : (
            <div className="fold-period-options" key={activeTab}>
              {activeTab === "cycle" && cycleHeading && (
                <p className="px-2 pb-1 text-xs font-medium text-luma-smoke">{cycleHeading}</p>
              )}
              {options[activeTab].length === 0 ? (
                <p className="p-2 text-xs text-luma-smoke">
                  {activeTab === "cycle" ? "Belum ada riwayat siklus." : "Belum ada pilihan periode."}
                </p>
              ) : (
                <ul id={`${popupId}-options`} className="fold-period-list">
                  {options[activeTab].map((option) => {
                    const selected = currentPeriod.id === option.id;
                    return (
                      <li key={option.id}>
                        <button type="button" className="fold-period-option" aria-pressed={selected} onClick={() => selectPeriod(option)}>
                          <span className="fold-period-check" aria-hidden="true">{selected && <Check size={15} />}</span>
                          <span>{periodTitle(option)}</span>
                          {option.is_current && <Badge>{currentBadges[activeTab]}</Badge>}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
              {activeTab === "cycle" && cycles.length > recentCycleCount && (
                <button type="button" className="fold-period-history" aria-expanded={showHistory}
                  aria-controls={`${popupId}-options`} onClick={() => setShowHistory((visible) => !visible)}>
                  {showHistory ? "Ringkas riwayat" : "Lihat riwayat"}
                  <ChevronDown size={14} className={showHistory ? "rotate-180" : ""} aria-hidden="true" />
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
