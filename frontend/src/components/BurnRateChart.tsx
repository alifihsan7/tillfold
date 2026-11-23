import { useState } from "react";
import { formatShortDate } from "@/lib/format";
import { Activity } from "@/components/icons";

interface CycleBurnDay {
  day: number;
  date: string;
  spent: number;
  cumulative_spent: number;
  ideal_pace: number;
}

interface SafeToSpendInfo {
  cycle_start?: string;
  cycle_end?: string;
  cycle_type?: string;
  cycle_days?: number;
  pocket_account?: string;
  pocket_budget?: number;
  day_of_cycle: number;
  pocket_spent: number;
  ideal_pace_today: number;
  burn_chart: CycleBurnDay[];
}

interface BurnRateChartProps {
  summary: {
    safe_to_spend?: SafeToSpendInfo;
  };
  formatRupiah: (val: number) => string;
}

export function BurnRateChart({ summary, formatRupiah }: BurnRateChartProps) {
  const chartData = summary.safe_to_spend?.burn_chart || [];
  const dayOfCycle = summary.safe_to_spend?.day_of_cycle || 1;
  const cycleDays = summary.safe_to_spend?.cycle_days || (chartData.length > 0 ? chartData.length : 14);
  const pocketAccount = summary.safe_to_spend?.pocket_account || "Saku Belanja";
  const maxBudget = summary.safe_to_spend?.pocket_budget && summary.safe_to_spend.pocket_budget > 0
    ? summary.safe_to_spend.pocket_budget
    : (summary.safe_to_spend?.pocket_spent && summary.safe_to_spend.pocket_spent > 0 ? summary.safe_to_spend.pocket_spent : 0);
  const idealDailyRate = maxBudget > 0 ? Math.round(maxBudget / (cycleDays || 14)) : 0;

  const [selectedDate, setSelectedDate] = useState<string>();
  const selected = chartData.find((item) => item.date === selectedDate)
    ?? chartData.find((item) => item.day === dayOfCycle)
    ?? chartData[0];

  return (
    <section aria-label={`Laju belanja siklus ${cycleDays} hari`} className="luma-glass p-4 sm:p-6 space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-luma-secondary" aria-hidden="true" />
            <h2 className="ai7-type-section text-luma-ivory tracking-tight">
              Belanja kumulatif
            </h2>
          </div>
          <p className="text-xs sm:text-sm text-luma-smoke mt-0.5 tabular-nums">
            {pocketAccount} · Anggaran {formatRupiah(maxBudget)}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs font-sans">
          <span className="flex items-center gap-1.5 text-luma-smoke">
            <span className="w-2.5 h-2.5 rounded-full bg-luma-coral inline-block" aria-hidden="true"></span>
            Aktual
          </span>
          <span className="flex items-center gap-1.5 text-luma-smoke">
            <span className="w-2.5 h-0.5 bg-luma-smoke inline-block" aria-hidden="true"></span>
            Target
          </span>
        </div>
      </div>

      {selected && (
        <div className="fold-burn-detail luma-inset p-4" aria-live="polite">
          <p key={selected.date} className="font-semibold">Hari {selected.day} · {formatShortDate(selected.date)}</p>
          <dl key={`amounts-${selected.date}`}>
            <div><dt>Pengeluaran</dt><dd>{formatRupiah(selected.spent)}</dd></div>
            <div><dt>Kumulatif</dt><dd>{formatRupiah(selected.cumulative_spent)}</dd></div>
            <div><dt>Batas ideal</dt><dd>{formatRupiah(selected.ideal_pace)}</dd></div>
          </dl>
        </div>
      )}

      <div className="fold-burn-grid" role="group" aria-label="Hari dalam siklus">
        {chartData.map((day) => {
          const idealHeight = Math.min(100, Math.round((day.ideal_pace / Math.max(1, maxBudget)) * 100));
          const actualHeight = Math.min(100, Math.round((day.cumulative_spent / Math.max(1, maxBudget)) * 100));
          return (
            <button key={day.date} type="button" className="fold-burn-day"
              aria-label={`Hari ${day.day}, ${formatShortDate(day.date)}`}
              aria-pressed={day.date === selected?.date}
              aria-current={day.day === dayOfCycle ? "date" : undefined}
              onClick={() => setSelectedDate(day.date)}>
              <span className="fold-burn-track" aria-hidden="true">
                <span className="fold-burn-target" style={{ bottom: `${idealHeight}%` }} />
                {day.day <= dayOfCycle && <span className="fold-burn-actual" style={{ height: `${actualHeight}%` }} />}
              </span>
              <span>{day.day}</span>
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-luma-smokeline text-xs font-sans text-luma-smoke tabular-nums">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 min-w-0">
          <span>Laju ideal (anggaran dibagi {cycleDays} hari):</span>
          <strong className="text-luma-ivory">{formatRupiah(idealDailyRate)} / hari</strong>
        </div>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 min-w-0">
          <span>Batas ideal sampai hari ini:</span>
          <strong className="text-luma-ivory">
            {formatRupiah(summary.safe_to_spend?.ideal_pace_today || 0)}
          </strong>
        </div>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 min-w-0">
          <span>Terpakai sampai hari ini:</span>
          <strong
            className={
              (summary.safe_to_spend?.pocket_spent || 0) >
              (summary.safe_to_spend?.ideal_pace_today || 0)
                ? "text-luma-coral font-semibold"
                : "text-luma-sage font-semibold"
            }
          >
            {formatRupiah(summary.safe_to_spend?.pocket_spent || 0)}
          </strong>
        </div>
      </div>
    </section>
  );
}
