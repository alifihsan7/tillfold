"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, ArrowLeftRight } from "lucide-react";
import { authFetch } from "@/lib/api";
import { calendarDate, monthCells, shiftCalendarMonth, compactRupiah, expenseHeatLevel } from "@/lib/transactionCalendar";
import { CustomSelect } from "./ui/CustomSelect";
import { CustomModal } from "./ui/CustomModal";
import { TransactionTable, Transaction } from "./TransactionTable";
import { Skeleton } from "./ui/Skeleton";

interface DayTotals {
  date: string; count: number; income: number; expense: number; net: number;
  transfer_in: number; transfer_out: number; adjustment_in: number; adjustment_out: number;
  transfer_count: number; adjustment_count: number;
}
interface CalendarData { year: number; month: number; days: DayTotals[]; totals: Omit<DayTotals, "date">; available_years: number[] }
interface Props {
  accounts: { id: string; label: string }[]; account: string; onAccountChange: (account: string) => void;
  refreshSignal: Transaction[]; formatRupiah: (amount: number) => string;
  onEdit: (transaction: Transaction) => void; onDelete: (transaction: Transaction) => void;
}
const todayWib = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Jakarta" });
const months = Array.from({ length: 12 }, (_, index) => new Intl.DateTimeFormat("id-ID", { month: "long", timeZone: "UTC" }).format(calendarDate(2000, index + 1, 1)));
const longDate = (date: string) => new Intl.DateTimeFormat("id-ID", { dateStyle: "full", timeZone: "UTC" }).format(new Date(`${date}T12:00:00Z`));

export function TransactionCalendar({ accounts, account, onAccountChange, refreshSignal, formatRupiah, onEdit, onDelete }: Props) {
  const today = todayWib();
  const [period, setPeriod] = useState(() => ({ year: Number(today.slice(0, 4)), month: Number(today.slice(5, 7)) }));
  const [data, setData] = useState<CalendarData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [dayPage, setDayPage] = useState(1);
  const [detail, setDetail] = useState<{ items: Transaction[]; total: number } | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [detailRetry, setDetailRetry] = useState(0);
  const [knownYears, setKnownYears] = useState<number[]>([]);
  const { year, month } = period;
  const cells = useMemo(() => monthCells(year, month), [year, month]);
  const byDate = useMemo(() => new Map(data?.days.map((day) => [day.date, day])), [data]);
  const selectedDay = selected ? byDate.get(selected) : undefined;
  const maximumExpense = Math.max(0, ...(data?.days.map((day) => day.expense) || []));
  const years = Array.from(new Set([...knownYears, year, ...Array.from({ length: 11 }, (_, index) => year - 5 + index)])).filter((value) => value >= 1 && value <= 9999).sort((a, b) => b - a);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setData(null); setError("");
    const params = new URLSearchParams({ year: String(year), month: String(month), account });
    void authFetch(`/api/v1/transactions/calendar?${params}`, { signal: controller.signal, cache: "no-store" }).then(async (response) => {
      if (!response.ok) throw new Error("Kalender gagal dimuat.");
      const result: CalendarData = await response.json();
      if (!controller.signal.aborted) { setData(result); setKnownYears(result.available_years); }
    }).catch((err) => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Kalender gagal dimuat."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [year, month, account, refreshSignal, retry]);

  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    setDetail(null); setDetailLoading(true); setDetailError("");
    const params = new URLSearchParams({ start_date: selected, end_date: selected, account, skip: String((dayPage - 1) * 25), limit: "25" });
    void authFetch(`/api/v1/transactions/history?${params}`, { signal: controller.signal, cache: "no-store" }).then(async (response) => {
      if (!response.ok) throw new Error("Transaksi harian gagal dimuat.");
      const result = await response.json();
      if (controller.signal.aborted) return;
      const lastPage = Math.max(1, Math.ceil(result.total / 25));
      if (dayPage > lastPage) { setDayPage(lastPage); return; }
      setDetail(result);
    }).catch((err) => { if (!controller.signal.aborted) setDetailError(err instanceof Error ? err.message : "Transaksi harian gagal dimuat."); })
      .finally(() => { if (!controller.signal.aborted) setDetailLoading(false); });
    return () => controller.abort();
  }, [selected, dayPage, account, refreshSignal, detailRetry]);

  const changePeriod = (next: { year: number; month: number }) => { setPeriod(next); setSelected(null); };
  const changeMonth = (delta: number) => { const next = shiftCalendarMonth(year, month, delta); if (next) changePeriod(next); };
  const openDate = (date: string) => { setDayPage(1); setDetail(null); setDetailLoading(true); setDetailError(""); setSelected(date); };

  return <div className="transaction-finance-calendar space-y-4">
    <div className="calendar-toolbar">
      <div className="calendar-period-fields">
        <div className="min-w-0 space-y-1"><span className="text-xs text-luma-smoke">Bulan</span>
          <CustomSelect label="Bulan kalender" value={String(month)} onChange={(value) => changePeriod({ year, month: Number(value) })} options={months.map((name, index) => ({ value: String(index + 1), label: name }))} /></div>
        <div className="min-w-0 space-y-1"><span className="text-xs text-luma-smoke">Tahun</span>
          <CustomSelect label="Tahun kalender" value={String(year)} onChange={(value) => changePeriod({ year: Number(value), month })} options={years.map((value) => ({ value: String(value), label: String(value) }))} /></div>
      </div>
        <div className="calendar-account-field min-w-0 space-y-1"><span className="text-xs text-luma-smoke">Rekening</span>
          <CustomSelect label="Rekening kalender" value={account} onChange={(value) => { onAccountChange(value); setSelected(null); }} options={accounts.map((item) => ({ value: item.id, label: item.id === "all" ? "Semua rekening" : item.label }))} /></div>
      <div className="calendar-month-actions flex items-center gap-2">
        <button type="button" className="luma-action-secondary min-h-11 min-w-11" aria-label="Bulan sebelumnya" disabled={year === 1 && month === 1} onClick={() => changeMonth(-1)}><ChevronLeft className="h-4 w-4" aria-hidden="true" /></button>
        <button type="button" className="luma-action-secondary" onClick={() => { changePeriod({ year: Number(today.slice(0, 4)), month: Number(today.slice(5, 7)) }); openDate(today); }}>Hari ini</button>
        <button type="button" className="luma-action-secondary min-h-11 min-w-11" aria-label="Bulan berikutnya" disabled={year === 9999 && month === 12} onClick={() => changeMonth(1)}><ChevronRight className="h-4 w-4" aria-hidden="true" /></button>
      </div>
    </div>
    <div className="calendar-month-summary grid grid-cols-3 gap-2 sm:gap-6">
      {[{ label: "Pemasukan", value: data?.totals.income, color: "text-luma-sage" }, { label: "Pengeluaran", value: data?.totals.expense, color: "text-luma-coral" }, { label: "Selisih", value: data?.totals.net, color: (data?.totals.net ?? 0) < 0 ? "text-luma-coral" : "text-luma-ivory" }].map((item) => <div key={item.label} className="min-w-0 py-3 sm:py-4">
        <p className="text-[11px] text-luma-smoke sm:text-sm">{item.label}</p>{loading ? <Skeleton className="mt-2 h-7 w-full max-w-28" /> : <p className={`mt-1 text-sm font-semibold tabular-nums sm:text-xl ${item.color}`} title={item.value === undefined ? "Belum tersedia" : formatRupiah(item.value)}>
          {item.value === undefined ? <span className="text-xs">Belum tersedia</span> : <><span className="calendar-value-compact">{item.value < 0 ? "−" : ""}Rp{compactRupiah(Math.abs(item.value))}</span><span className="calendar-value-full truncate">{formatRupiah(item.value)}</span></>}
        </p>}
      </div>)}
    </div>
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="ai7-type-section">{months[month - 1]} {year}</h2><p className="text-xs text-luma-smoke">Transfer di luar arus kas.</p></div>
    {error && <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-luma-coral"><p>{error}</p><button type="button" className="luma-action-secondary" onClick={() => setRetry((value) => value + 1)}>Coba lagi</button></div>}
    <p role="status" aria-live="polite" className="text-sm text-luma-smoke">{loading ? "Memuat kalender…" : error ? "" : data?.totals.count === 0 ? "Belum ada transaksi bulan ini. Klik tanggal untuk melihat rincian." : "Klik tanggal untuk melihat transaksi harian."}</p>
    {maximumExpense > 0 && <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-luma-smoke">
      <span>Intensitas pengeluaran bulan ini</span>
      <div className="flex items-center gap-1.5" role="img" aria-label="Skala pengeluaran relatif pada bulan dan rekening terpilih, dari lebih rendah ke lebih tinggi">
        <span>Rendah</span>{[1, 2, 3, 4].map((level) => <span key={level} className="calendar-heat-key" data-expense-level={level} aria-hidden="true" />)}<span>Tinggi</span>
      </div>
    </div>}
    <div className="overflow-hidden rounded-2xl border border-luma-smokeline" role="group" aria-label={`Kalender transaksi ${months[month - 1]} ${year}`} aria-busy={loading}>
      <div className="grid grid-cols-7 border-b border-luma-smokeline bg-luma-coal">
        {["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"].map((day) => <div key={day} className="py-2 text-center text-xs font-medium text-luma-smoke">{day}</div>)}
      </div>
      <div className="transaction-calendar-grid grid grid-cols-7 gap-px bg-luma-smokeline">
        {cells.map((date, index) => {
          if (!date) return <div key={`empty-${index}`} aria-hidden="true" className="min-h-[100px] bg-luma-charcoal sm:min-h-[120px]" />;
          const day = byDate.get(date);
          const otherCount = (day?.transfer_count || 0) + (day?.adjustment_count || 0);
          return <button key={date} type="button" disabled={loading || !data} aria-current={date === today ? "date" : undefined}
            data-expense-level={expenseHeatLevel(day?.expense || 0, maximumExpense)}
            aria-pressed={selected === date} aria-label={data ? `${longDate(date)}. Pemasukan ${formatRupiah(day?.income || 0)}. Pengeluaran ${formatRupiah(day?.expense || 0)}. ${day?.count || 0} catatan, ${otherCount} mutasi transfer atau penyesuaian.` : `${longDate(date)}. Data belum tersedia.`}
            onClick={() => openDate(date)} className={`flex min-h-[100px] min-w-0 flex-col items-stretch gap-1 bg-luma-charcoal p-1 text-left text-luma-ivory transition-colors hover:bg-luma-coal focus-visible:z-10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-luma-ember disabled:cursor-wait sm:min-h-[120px] sm:p-2 ${date === today ? "shadow-[inset_0_0_0_2px_var(--luma-transfer)]" : ""}`}>
            <span className="text-xs font-semibold sm:text-sm">{Number(date.slice(-2))}{date === today && <span className="sr-only">, hari ini</span>}</span>
            {day && day.income > 0 && <span className="min-w-0 calendar-day-amount font-medium tabular-nums text-luma-sage" title={`Pemasukan ${formatRupiah(day.income)}`}><span className="calendar-value-compact">+{compactRupiah(day.income)}</span><span className="calendar-value-full truncate">+{formatRupiah(day.income)}</span></span>}
            {day && day.expense > 0 && <span className="min-w-0 calendar-day-amount font-medium tabular-nums text-luma-coral" title={`Pengeluaran ${formatRupiah(day.expense)}`}><span className="calendar-value-compact">−{compactRupiah(day.expense)}</span><span className="calendar-value-full truncate">−{formatRupiah(day.expense)}</span></span>}
            {otherCount > 0 && <span className="mt-auto flex items-center gap-0.5 text-[10px] text-luma-transfer sm:text-xs" title="Transfer atau penyesuaian saldo"><ArrowLeftRight className="h-3 w-3 shrink-0" aria-hidden="true" /><span>{otherCount}</span><span className="hidden lg:inline">mutasi</span></span>}
          </button>;
        })}
      </div>
    </div>
    {data && !loading && (data.totals.transfer_count > 0 || data.totals.adjustment_count > 0) && <div className="luma-matte grid gap-2 p-4 text-sm sm:grid-cols-2">
      <p>Transfer masuk {formatRupiah(data.totals.transfer_in)} · keluar {formatRupiah(data.totals.transfer_out)}</p>
      <p>Penyesuaian +{formatRupiah(data.totals.adjustment_in)} / −{formatRupiah(data.totals.adjustment_out)}</p>
    </div>}
    <CustomModal isOpen={selected !== null} onClose={() => setSelected(null)} title={selected ? longDate(selected) : "Transaksi harian"} maxWidth="xl">
      <div className="space-y-4">
        <p className="text-sm text-luma-smoke">{accounts.find((item) => item.id === account)?.label || "Semua rekening"}</p>
        {selectedDay && <div className="luma-matte space-y-1 p-3 text-sm">
          <p className="text-luma-sage">Pemasukan: {formatRupiah(selectedDay.income)}</p><p className="text-luma-coral">Pengeluaran: {formatRupiah(selectedDay.expense)}</p>
          {selectedDay.transfer_count > 0 && <p>Transfer masuk {formatRupiah(selectedDay.transfer_in)} · keluar {formatRupiah(selectedDay.transfer_out)}</p>}
          {selectedDay.adjustment_count > 0 && <p>Penyesuaian +{formatRupiah(selectedDay.adjustment_in)} / −{formatRupiah(selectedDay.adjustment_out)}</p>}
        </div>}
        {detailError ? <div role="alert" className="space-y-2 text-sm text-luma-coral"><p>{detailError}</p><button type="button" className="luma-action-secondary" onClick={() => setDetailRetry((value) => value + 1)}>Coba lagi</button></div> :
          <TransactionTable transactions={detail?.items || []} loading={detailLoading} formatRupiah={formatRupiah} onEdit={(tx) => { setSelected(null); onEdit(tx); }} onDelete={(tx) => { setSelected(null); onDelete(tx); }} />}
        {detail && detail.total > 25 && <div className="flex flex-wrap items-center justify-between gap-2 text-sm"><span>Halaman {dayPage} / {Math.ceil(detail.total / 25)} · {detail.total} catatan</span><div className="flex gap-2">
          <button type="button" className="luma-action-secondary" disabled={detailLoading || dayPage === 1} onClick={() => setDayPage((value) => value - 1)}>Sebelumnya</button>
          <button type="button" className="luma-action-secondary" disabled={detailLoading || dayPage * 25 >= detail.total} onClick={() => setDayPage((value) => value + 1)}>Berikutnya</button>
        </div></div>}
        <div className="flex justify-end"><button type="button" className="luma-action-secondary" onClick={() => setSelected(null)}>Tutup</button></div>
      </div>
    </CustomModal>
  </div>;
}
