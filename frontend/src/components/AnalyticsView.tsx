import React from "react";
import { BurnRateChart } from "./BurnRateChart";
import { Skeleton } from "./ui/Skeleton";

interface CategorySummary {
  category: string;
  total: number;
  count: number;
  percentage: number;
}

interface DailyTrendItem {
  date: string;
  income: number;
  expense: number;
}

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
  days_remaining: number;
  pocket_spent: number;
  safe_daily: number;
  pace_status: string;
  ideal_pace_today: number;
  burn_chart: CycleBurnDay[];
}

export interface AnalyticsSummary {
  period_type: string;
  period_label: string;
  start_date: string;
  end_date: string;
  month: string;
  year: number;
  month_num: number;
  income: number;
  opening_balance?: number;
  expense: number;
  net: number;
  savings_rate: number;
  categories: CategorySummary[];
  accounts: {
    name: string;
    type: string;
    balance: number;
    expense?: number;
  }[];
  total_balance: number;
  daily_trend: DailyTrendItem[];
  safe_to_spend?: SafeToSpendInfo;
}

interface AnalyticsViewProps {
  summary: AnalyticsSummary;
  formatRupiah: (val: number) => string;
  loading?: boolean;
}

const shortDate = new Intl.DateTimeFormat("id-ID", { day: "numeric", month: "short", timeZone: "UTC" });

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : shortDate.format(date);
}

export function AnalyticsView({ summary, formatRupiah, loading }: AnalyticsViewProps) {
  const safe = summary.safe_to_spend;
  const daily = summary.daily_trend;
  const maxDaily = daily.reduce((max, day) => Math.max(max, day.income, day.expense), 1);
  const categories = [...summary.categories].sort((a, b) => b.total - a.total);
  const metrics = [
    { label: "Pemasukan", amount: summary.income, color: "text-mintRise" },
    { label: "Pengeluaran", amount: summary.expense, color: "text-coralFall" },
    { label: "Selisih", amount: summary.net, color: summary.net < 0 ? "text-coralFall" : "text-luma-ivory" },
  ];
  const money = (amount: number) => amount < 0 ? `-${formatRupiah(Math.abs(amount))}` : formatRupiah(amount);

  return (
    <div className="space-y-6 sm:space-y-8" aria-busy={loading}>
      <section aria-labelledby="report-totals" className="luma-matte p-4 sm:p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 id="report-totals" className="ai7-type-section">Ringkasan periode</h2>
          <p className="text-sm text-luma-smoke">{formatDate(summary.start_date)} – {formatDate(summary.end_date)}</p>
        </div>
        <dl className="mt-4 grid gap-x-6 gap-y-3 sm:grid-cols-3">
          {metrics.map(({ label, amount, color }) => (
            <div key={label} className="min-w-0 border-t border-luma-smokeline pt-3 max-sm:flex max-sm:flex-wrap max-sm:items-baseline max-sm:justify-between max-sm:gap-x-4">
              <dt className="text-sm text-luma-smoke">{label}</dt>
              <dd className={`ai7-type-metric sm:mt-1 ${color}`}>
                {loading ? <Skeleton className="h-7 w-24 max-w-full" /> : money(amount)}
              </dd>
            </div>
          ))}
        </dl>
        {!loading && summary.income > 0 && (
          <p className="mt-4 text-xs text-luma-smoke">Selisih dari pemasukan: {summary.savings_rate.toFixed(1)}%</p>
        )}
        {!loading && (summary.opening_balance ?? 0) > 0 && (
          <p className="mt-1 text-xs text-luma-smoke">Saldo awal {formatRupiah(summary.opening_balance ?? 0)} dicatat terpisah, tidak termasuk pemasukan.</p>
        )}
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <section aria-labelledby="report-flow" className="luma-matte min-w-0 p-4 sm:p-6">
          <h2 id="report-flow" className="ai7-type-section">Arus kas harian</h2>
          {daily.length === 0 ? (
            <p className="mt-3 text-sm text-luma-smoke">Belum ada transaksi di periode ini.</p>
          ) : (
            <>
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-luma-smoke">
                <span><span className="mr-1.5 inline-block size-2 rounded-sm bg-mintRise" aria-hidden="true" />Pemasukan</span>
                <span><span className="mr-1.5 inline-block size-2 rounded-sm bg-coralFall" aria-hidden="true" />Pengeluaran</span>
              </div>
              <div className="mt-4 flex h-32 items-end gap-px border-b border-luma-smokeline sm:gap-1" aria-hidden="true">
                {daily.map(({ date, income, expense }) => (
                  <div key={date} className="flex h-full min-w-0 flex-1 items-end justify-center gap-px"
                    title={`${formatDate(date)} · Masuk ${money(income)} · Keluar ${money(expense)}`}>
                    <div className="w-full max-w-3 rounded-t-sm bg-mintRise" style={{ height: `${income / maxDaily * 100}%` }} />
                    <div className="w-full max-w-3 rounded-t-sm bg-coralFall" style={{ height: `${expense / maxDaily * 100}%` }} />
                  </div>
                ))}
              </div>
              <div className="mt-2 flex justify-between gap-2 text-xs text-luma-smoke" aria-hidden="true">
                <span>{formatDate(daily[0].date)}</span>
                <span>{formatDate(daily[daily.length - 1].date)}</span>
              </div>
              <details className="mt-3 text-sm">
                <summary className="luma-text-action cursor-pointer">Lihat angka per hari</summary>
                <dl className="space-y-2">
                  {daily.map(({ date, income, expense }) => (
                    <div key={date} className="flex flex-wrap justify-between gap-x-3 border-t border-luma-smokeline pt-2">
                      <dt>{formatDate(date)}</dt>
                      <dd className="text-luma-smoke">Masuk {money(income)} · Keluar {money(expense)}</dd>
                    </div>
                  ))}
                </dl>
              </details>
            </>
          )}
        </section>

        <section aria-labelledby="report-categories" className="luma-matte min-w-0 p-4 sm:p-6">
          <h2 id="report-categories" className="ai7-type-section">Pengeluaran terbesar</h2>
          {categories.length === 0 ? (
            <p className="mt-3 text-sm text-luma-smoke">Belum ada pengeluaran di periode ini.</p>
          ) : (
            <ol className="mt-3 space-y-3">
              {categories.slice(0, 5).map(({ category, total, percentage }) => (
                <li key={category} className="border-t border-luma-smokeline pt-2">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-sm">
                    <span className="min-w-0 break-words">{category}</span>
                    <strong className="tabular-nums">{money(total)}</strong>
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <div className="luma-flow-track min-w-0 flex-1" aria-hidden="true">
                      <div className="bg-coralFall" style={{ width: `${Math.min(100, Math.max(0, percentage))}%` }} />
                    </div>
                    <span className="text-xs tabular-nums text-luma-smoke">{percentage.toFixed(1)}%</span>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>

      <section aria-labelledby="report-pace" className="space-y-3">
        <h2 id="report-pace" className="ai7-type-section">Laju belanja dan batas harian</h2>
        {safe && (safe.pocket_budget ?? 0) > 0 ? (
          <>
            <div className="luma-matte flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2 p-4 sm:p-6">
              <p className="text-sm text-luma-smoke">
                {safe.pace_status === "ahead" ? "Belanja di bawah target" :
                  safe.pace_status === "on_track" ? "Belanja sesuai rencana" : "Belanja melewati target"}
              </p>
              <p className="text-sm tabular-nums">
                {safe.days_remaining > 0
                  ? <><span className="text-luma-smoke">Sisa anggaran dibagi {safe.days_remaining} hari:</span> <strong>{money(safe.safe_daily)} per hari</strong></>
                  : "Siklus selesai"}
              </p>
            </div>
            <BurnRateChart summary={summary} formatRupiah={formatRupiah} />
          </>
        ) : (
          <p className="luma-matte p-4 text-sm text-luma-smoke sm:p-6">Anggaran siklus belum diatur.</p>
        )}
      </section>
    </div>
  );
}
