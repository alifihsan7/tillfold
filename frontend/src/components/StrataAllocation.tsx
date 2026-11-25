import { Skeleton } from "./ui/Skeleton";

interface DistributionItem {
  account: string;
  amount: number;
  pending: number;
}

interface StrataAllocationBarProps {
  distribution: DistributionItem[];
  periodLabel?: string;
  formatRupiah: (amount: number) => string;
  loading?: boolean;
}

const percentage = new Intl.NumberFormat("id-ID", {
  style: "percent",
  maximumFractionDigits: 1,
});

function allocationColor(index: number) {
  return `var(--allocation-${index % 8 + 1})`;
}

export function StrataAllocationBar({ distribution, periodLabel, formatRupiah, loading }: StrataAllocationBarProps) {
  const total = distribution.reduce((sum, item) => sum + item.amount, 0);
  const pending = distribution.reduce((sum, item) => sum + item.pending, 0);

  return (
    <section aria-labelledby="salary-distribution-title" aria-busy={loading} className="allocation-panel luma-glass p-5 sm:p-7 space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="salary-distribution-title" className="ai7-type-section">Pembagian gaji</h2>
        {periodLabel && <span className="text-xs text-luma-smoke">{periodLabel}</span>}
      </header>
      {loading ? <Skeleton className="h-20 w-full" /> : total === 0 ? (
        <p className="text-sm text-luma-smoke">Belum ada gaji tercatat untuk periode ini. Isi pembagian saat mencatat gaji.</p>
      ) : (
        <>
          <p className="text-sm text-luma-smoke">
            Total {formatRupiah(total)}{pending > 0 ? ` · ${formatRupiah(pending)} belum dicatat sebagai transfer` : ""}
          </p>
          <div className="fold-allocation-bar flex overflow-hidden gap-0.5" aria-hidden="true">
            {distribution.map(({ account, amount }, index) => (
              <span key={account} style={{ flex: amount / total, backgroundColor: allocationColor(index) }} />
            ))}
          </div>
          <ul tabIndex={0} aria-label="Rincian pembagian gaji" className="flex min-w-0 gap-3 overflow-x-auto">
            {distribution.map(({ account, amount, pending }, index) => (
              <li key={account} className="allocation-legend-item min-w-max flex-1 whitespace-nowrap">
                <div className="flex items-center gap-2">
                  <span className="size-2.5 rounded-sm shrink-0" aria-hidden="true" style={{ background: allocationColor(index) }} />
                  <strong className="font-medium">{account}</strong>
                </div>
                <p className="text-sm tabular-nums">{formatRupiah(amount)} · {percentage.format(amount / total)}</p>
                {pending > 0 && <p className="text-xs text-luma-smoke">Belum ditransfer: {formatRupiah(pending)}</p>}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
