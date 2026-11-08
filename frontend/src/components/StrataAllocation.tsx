import React from "react";
import { Skeleton } from "./ui/Skeleton";

export interface BucketAllocationItem {
  account: string;
  percentage: number;
  purpose?: string;
}

interface StrataAllocationBarProps {
  cycleType?: string;
  cycleDays?: number;
  totalSalary?: number;
  buckets?: BucketAllocationItem[];
  formatRupiah?: (val: number) => string;
  loading?: boolean;
}

const ALLOCATION_COLORS = Array.from({ length: 8 }, (_, index) => `var(--allocation-${index + 1})`);

const DEFAULT_BUCKETS: BucketAllocationItem[] = [
  { account: "Rekening Utama", percentage: 50.0, purpose: "Belanja & Operasional" },
  { account: "Tabungan", percentage: 30.0, purpose: "Simpanan & Cadangan" },
  { account: "Investasi", percentage: 20.0, purpose: "Pertumbuhan aset" },
];

export function StrataAllocationBar({
  cycleType = "biweekly",
  cycleDays = 14,
  totalSalary,
  buckets = DEFAULT_BUCKETS,
  formatRupiah = (n: number) => `Rp ${n.toLocaleString("id-ID")}`,
  loading,
}: StrataAllocationBarProps) {
  if (loading) {
    return (
      <section aria-label="Distribusi alokasi anggaran" className="luma-glass p-6 sm:p-7 space-y-5">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
          <div>
            <Skeleton className="w-48 h-5 rounded-md" />
            <Skeleton className="w-72 h-3.5 rounded-md mt-1.5" />
          </div>
          <Skeleton className="w-36 h-6 rounded-full" />
        </div>
        <Skeleton className="w-full h-9 rounded-full" />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5 pt-1">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="p-3.5 rounded-2xl bg-white/[0.04] border border-luma-smokeline space-y-2">
              <div className="flex items-center gap-1.5">
                <Skeleton className="w-2 h-2 rounded-full" />
                <Skeleton className="w-16 h-3 rounded-md" />
              </div>
              <Skeleton className="w-20 h-4 rounded-md" />
              <Skeleton className="w-12 h-3 rounded-md" />
            </div>
          ))}
        </div>
      </section>
    );
  }

  // Determine standard baseline salary based on cycle duration if explicitly passed
  const effectiveSalary = totalSalary && totalSalary > 0 ? totalSalary : 0;

  // Determine friendly formula badge
  const formulaLabel = cycleDays === 30 || cycleType === "monthly" || cycleType === "monthly_date"
    ? `Formula Bulanan (${cycleDays} Hari)`
    : cycleDays === 7 || cycleType === "weekly"
    ? "Formula Mingguan (7 Hari)"
    : cycleDays === 14 || cycleType === "biweekly"
    ? "Formula 2-Mingguan (14 Hari)"
    : `Formula Anggaran (${cycleDays} Hari)`;

  const activeBuckets = buckets && buckets.length > 0 ? buckets : DEFAULT_BUCKETS;

  return (
    <section aria-label="Distribusi alokasi anggaran" className="allocation-panel luma-glass p-6 sm:p-7 space-y-5">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
        <div>
          <h2 className="ai7-type-section text-luma-ivory tracking-tight">
            Distribusi alokasi anggaran
          </h2>
          <p className="text-xs sm:text-sm text-luma-smoke mt-0.5 tabular-nums">
            {effectiveSalary > 0
              ? `Alokasi anggaran ${formatRupiah(effectiveSalary)} / ${cycleDays} hari dipecah ke ${activeBuckets.length} pos rekening`
              : `Proporsi alokasi dipecah ke ${activeBuckets.length} pos rekening sesuai rasio alur gajian`}
          </p>
        </div>
        <span className="text-xs font-sans font-semibold text-luma-gold px-3 py-1.5 rounded-full bg-luma-gold/10 border border-luma-gold/30 shrink-0 self-start sm:self-center whitespace-nowrap">
          {formulaLabel}
        </span>
      </div>

      <div
        className="flex gap-0.5 min-h-[44px] rounded-xl overflow-hidden p-1 bg-luma-charcoal border border-luma-smokeline"
        role="img"
        aria-label={`Proporsi alokasi: ${activeBuckets.map((b) => `${b.account} ${b.percentage.toFixed(1)} persen`).join(", ")}`}
      >
        {activeBuckets.map((b, idx) => {
          const seg = ALLOCATION_COLORS[idx % ALLOCATION_COLORS.length];
          const isFirst = idx === 0;
          const isLast = idx === activeBuckets.length - 1;
          const showText = b.percentage >= 4;

          return (
            <div
              key={b.account}
              style={{ flex: b.percentage, backgroundColor: seg }}
              className={`${isFirst ? "rounded-l-md" : ""} ${isLast ? "rounded-r-md" : ""} min-w-0 overflow-hidden flex items-center justify-center`}
              title={`${b.account}: ${b.percentage.toFixed(1)}%`}
            >
              {showText ? (
                <span className="allocation-bar-label text-xs leading-none select-none font-semibold font-sans px-1 whitespace-nowrap">
                  {Number(b.percentage.toFixed(1))}%
                </span>
              ) : null}
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-2.5 sm:gap-3 pt-1">
        {activeBuckets.map((b, idx) => {
          const seg = ALLOCATION_COLORS[idx % ALLOCATION_COLORS.length];
          const allocatedAmt = Math.round((b.percentage / 100) * effectiveSalary);
          const shortPurpose = b.purpose
            ? b.purpose.split("(")[0].trim()
            : "Alokasi Pos";

          return (
            <div
              key={b.account}
              style={{ "--allocation-color": seg } as React.CSSProperties}
              className="allocation-legend-item rounded-2xl border p-3.5 min-w-0"
            >
              <div className="flex items-center gap-1.5 min-w-0">
                <span
                  aria-hidden="true"
                  className="w-3 h-3 rounded-[3px] shrink-0"
                  style={{ backgroundColor: seg }}
                />
                <span className="text-luma-ivory font-semibold text-xs sm:text-sm break-words leading-snug">
                  {b.account}
                </span>
              </div>
              <div className="text-luma-smoke font-sans text-xs sm:text-xs mt-1.5 tabular-nums break-words leading-relaxed">
                {b.percentage.toFixed(1)}%
                {effectiveSalary > 0 ? ` · ${formatRupiah(allocatedAmt)}` : ""}
              </div>
              <div className="text-luma-smoke text-xs mt-0.5 break-words leading-snug">
                {shortPurpose}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
