import { useEffect, useRef, useState } from "react";
import { cashFlowCeiling, cashFlowDays, CashFlowDay } from "@/lib/dailyCashFlow";
import { formatShortDate } from "@/lib/format";
import { todayWib } from "@/lib/transactionCalendar";

interface DailyCashFlowChartProps {
  days: CashFlowDay[];
  start: string;
  end: string;
  formatRupiah: (amount: number) => string;
}

const compact = new Intl.NumberFormat("id-ID", { notation: "compact", maximumFractionDigits: 1 });
const axisDate = new Intl.DateTimeFormat("id-ID", { day: "numeric", month: "short", timeZone: "UTC" });
const fullDate = new Intl.DateTimeFormat("id-ID", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

export function DailyCashFlowChart({ days, start, end, formatRupiah }: DailyCashFlowChartProps) {
  const daily = cashFlowDays(days, start, end);
  const [selectedDate, setSelectedDate] = useState<string>();
  const [visible, setVisible] = useState({ income: true, expense: true });
  const scrollArea = useRef<HTMLDivElement>(null);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const today = todayWib();
  const latest = [...daily].reverse().find((day) => day.income > 0 || day.expense > 0);
  const selected = daily.find((day) => day.date === selectedDate) ?? latest ?? daily[0];
  const ceiling = cashFlowCeiling(daily.map((day) => ({ ...day, income: visible.income ? day.income : 0, expense: visible.expense ? day.expense : 0 })));
  const hasActivity = daily.some((day) => day.income > 0 || day.expense > 0);
  const activeDays = daily.filter((day) => day.income > 0 || day.expense > 0).length;
  const peak = daily.reduce<CashFlowDay | undefined>((best, day) => day.expense > (best?.expense ?? 0) ? day : best, undefined);
  const latestDate = latest?.date;
  const selectedIndex = useRef(0);
  selectedIndex.current = daily.findIndex((day) => day.date === selected?.date);
  const dayCount = daily.length;
  useEffect(() => {
    const scroll = scrollArea.current;
    if (!scroll || !latestDate) return;
    const centerSelection = () => {
      scroll.scrollLeft = Math.max(0, (selectedIndex.current + .5) * scroll.scrollWidth / dayCount - scroll.clientWidth / 2);
    };
    centerSelection();
    const observer = new ResizeObserver(centerSelection);
    observer.observe(scroll);
    return () => observer.disconnect();
  }, [start, end, latestDate, dayCount]);
  const toggle = (series: "income" | "expense") => setVisible((previous) => {
    if (previous[series] && !(series === "income" ? previous.expense : previous.income)) return previous;
    return { ...previous, [series]: !previous[series] };
  });
  const signed = (amount: number) => `${amount < 0 ? "−" : amount > 0 ? "+" : ""}${formatRupiah(Math.abs(amount))}`;

  return (
    <section aria-labelledby="report-flow" className="fold-report-panel fold-report-flow">
      <header className="fold-report-heading">
        <div><h2 id="report-flow" className="ai7-type-section">Arus kas harian</h2><p>Pemasukan dan pengeluaran sepanjang periode.</p></div>
        {hasActivity && <div className="fold-report-legend" aria-label="Legenda grafik">
          <button type="button" aria-pressed={visible.income} onClick={() => toggle("income")} title="Tampilkan atau sembunyikan pemasukan"><i className="fold-report-income" />Pemasukan</button><button type="button" aria-pressed={visible.expense} onClick={() => toggle("expense")} title="Tampilkan atau sembunyikan pengeluaran"><i className="fold-report-expense" />Pengeluaran</button>
        </div>}
      </header>
      {!hasActivity ? (
        <div className="fold-report-empty"><span className="fold-report-empty-bars" aria-hidden="true"><i /><i /><i /><i /><i /></span><h3>Belum ada arus kas</h3><p>Transaksi pemasukan dan pengeluaran di periode ini akan muncul di sini.</p></div>
      ) : <>
        <div className="fold-report-chart-layout">
          <div className="fold-report-y-axis" aria-hidden="true">{[1, .75, .5, .25, 0].map((level) => <span key={level}>{level === 0 ? "0" : `Rp ${compact.format(ceiling * level)}`}</span>)}</div>
          <div ref={scrollArea} className="fold-report-chart-scroll" role="region" aria-label="Grafik arus kas; pilih hari untuk melihat rincian">
            <div className="fold-report-plot" style={{ minWidth: `${Math.max(daily.length * 30, 240)}px` }}>
              <div className="fold-report-grid" aria-hidden="true">{[0, 1, 2, 3, 4].map((line) => <span key={line} />)}</div>
              <div className="fold-report-days" role="group" aria-label="Hari dalam periode">
                {daily.map((day, index) => {
                  const active = day.date === selected?.date;
                  const date = new Date(`${day.date}T00:00:00Z`);
                  const showMonth = index === 0 || date.getUTCDate() === 1;
                  return <button key={day.date} ref={(element) => { buttons.current[index] = element; }} type="button"
                    className="fold-report-day" aria-pressed={active} tabIndex={active ? 0 : -1}
                    aria-label={`${formatShortDate(day.date)}, pemasukan ${formatRupiah(day.income)}, pengeluaran ${formatRupiah(day.expense)}`}
                    onClick={() => setSelectedDate(day.date)} onFocus={() => setSelectedDate(day.date)}
                    onPointerEnter={(event) => { if (event.pointerType === "mouse") setSelectedDate(day.date); }}
                    onKeyDown={(event) => {
                      const next = event.key === "ArrowRight" ? Math.min(daily.length - 1, index + 1) : event.key === "ArrowLeft" ? Math.max(0, index - 1) : event.key === "Home" ? 0 : event.key === "End" ? daily.length - 1 : -1;
                      if (next >= 0) { event.preventDefault(); buttons.current[next]?.focus(); }
                    }}>
                    <span className="fold-report-bar-pair" aria-hidden="true">
                      <span hidden={!visible.income} className="fold-report-income" style={{ height: `${day.income / ceiling * 100}%`, minHeight: day.income > 0 ? 3 : 0 }} />
                      <span hidden={!visible.expense} className="fold-report-expense" style={{ height: `${day.expense / ceiling * 100}%`, minHeight: day.expense > 0 ? 3 : 0 }} />
                    </span>
                    <span className="fold-report-day-label" aria-hidden="true">{showMonth ? axisDate.format(date) : date.getUTCDate()}</span>
                  </button>;
                })}
              </div>
            </div>
          </div>
        </div>
        <p className="fold-report-chart-hint">Pilih hari untuk rincian; gunakan legenda untuk fokus. <span className="fold-report-scroll-hint">Geser grafik untuk melihat hari lain.</span></p>
        {selected && <div className="fold-report-day-detail" aria-label="Rincian hari terpilih">
          <div className="fold-report-selected-date"><span>Rincian harian</span><strong>{fullDate.format(new Date(`${selected.date}T00:00:00Z`))}</strong>{selected.date > today && selected.income === 0 && selected.expense === 0 && <small>Tanggal mendatang</small>}</div>
          <dl><div><dt>Pemasukan</dt><dd className="text-mintRise">{formatRupiah(selected.income)}</dd></div><div><dt>Pengeluaran</dt><dd className="text-coralFall">{formatRupiah(selected.expense)}</dd></div><div><dt>Selisih</dt><dd className={selected.income < selected.expense ? "text-coralFall" : ""}>{signed(selected.income - selected.expense)}</dd></div></dl>
        </div>}
        <footer className="fold-report-flow-notes"><span><strong>{activeDays}</strong> hari dengan transaksi</span>{peak && <span>Pengeluaran tertinggi <strong>{formatRupiah(peak.expense)}</strong> · {formatShortDate(peak.date)}</span>}<span>Transfer dan saldo awal di luar arus kas.</span></footer>
      </>}
    </section>
  );
}
