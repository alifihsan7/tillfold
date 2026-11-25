import React from "react";
import { CashFlowRange } from "@/lib/dailyCashFlow";
import { formatDateRange } from "@/lib/format";
import { DailyCashFlowChart } from "./DailyCashFlowChart";
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
  onOpenTransactions?: (range: CashFlowRange) => void;
}

export function AnalyticsView({ summary, formatRupiah, loading, onOpenTransactions }: AnalyticsViewProps) {
  const safe = summary.safe_to_spend;
  const daily = summary.daily_trend;
  const categories = [...summary.categories].sort((a, b) => b.total - a.total);
  const metrics = [
    { label: "Pemasukan", amount: summary.income, color: "text-mintRise" },
    { label: "Pengeluaran", amount: summary.expense, color: "text-coralFall" },
    { label: "Selisih", amount: summary.net, color: summary.net < 0 ? "text-coralFall" : "text-luma-ivory" },
  ];
  const money = (amount: number) => amount < 0 ? `-${formatRupiah(Math.abs(amount))}` : formatRupiah(amount);

  return (
    <div className="fold-reports" aria-busy={loading}>
      <section aria-labelledby="report-totals" className="fold-report-panel fold-report-summary">
        <header className="fold-report-heading">
          <div><h2 id="report-totals" className="ai7-type-section">Ringkasan periode</h2><p>{formatDateRange(summary.start_date, summary.end_date) || "—"}</p></div>
          {!loading && summary.income > 0 && <span className="fold-report-ratio">{summary.savings_rate.toFixed(1)}%<span>selisih dari pemasukan</span></span>}
        </header>
        <dl className="fold-report-metrics">
          {metrics.map(({ label, amount, color }) => (
            <div key={label}>
              <dt><span className={`fold-report-metric-dot ${color}`} aria-hidden="true" />{label}</dt>
              <dd className={color}>{loading ? <Skeleton className="h-9 w-36 max-w-full" /> : money(amount)}</dd>
              <dd className="fold-report-metric-caption">{label === "Pemasukan" ? "Uang yang diterima" : label === "Pengeluaran" ? "Uang yang dibelanjakan" : "Pemasukan dikurangi pengeluaran"}</dd>
            </div>
          ))}
        </dl>
        {!loading && (summary.opening_balance ?? 0) > 0 && <p className="fold-report-opening">Saldo awal {formatRupiah(summary.opening_balance ?? 0)} dicatat terpisah dari pemasukan.</p>}
      </section>

      {loading ? <section className="fold-report-panel" aria-label="Memuat arus kas harian"><Skeleton className="h-6 w-40" /><Skeleton className="mt-6 h-64 w-full" /></section> : <DailyCashFlowChart key={`${summary.start_date}-${summary.end_date}`} days={daily} start={summary.start_date} end={summary.end_date} formatRupiah={formatRupiah} onOpenTransactions={onOpenTransactions} />}

      <section aria-labelledby="report-categories" className="fold-report-panel">
        <header className="fold-report-heading"><div><h2 id="report-categories" className="ai7-type-section">Pengeluaran terbesar</h2><p>Kategori yang paling banyak memakai dana periode ini.</p></div>{!loading && categories.length > 0 && <span className="fold-report-caption">{categories.length} kategori pengeluaran</span>}</header>
        {loading ? <Skeleton className="mt-5 h-24 w-full" /> : categories.length === 0 ? (
          <p className="fold-report-category-empty">Belum ada pengeluaran di periode ini.</p>
        ) : (
          <ol className="fold-report-categories">
            {categories.slice(0, 5).map(({ category, total, percentage }, index) => (
              <li key={category}>
                <button type="button" className="fold-report-category-link" aria-label={`Lihat transaksi pengeluaran ${category}`} onClick={() => onOpenTransactions?.({ start: summary.start_date, end: summary.end_date, category, type: "expense" })}>
                <span className="fold-report-rank" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                <div className="fold-report-category-body"><div><span>{category}</span><strong>{money(total)}</strong></div><div className="fold-report-category-share"><span className="fold-report-category-track" aria-hidden="true"><i style={{ width: `${Math.min(100, Math.max(0, percentage))}%`, opacity: 1 - index * .12 }} /></span><span>{percentage.toFixed(1)}%</span></div></div>
                </button>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section aria-labelledby="report-pace" className="space-y-3">
        <h2 id="report-pace" className="ai7-type-section">Laju belanja dan batas harian</h2>
        {safe && (safe.pocket_budget ?? 0) > 0 ? (
          <>
            <div className="fold-report-panel flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
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
          <p className="fold-report-panel text-sm text-luma-smoke">Anggaran siklus belum diatur.</p>
        )}
      </section>
    </div>
  );
}
