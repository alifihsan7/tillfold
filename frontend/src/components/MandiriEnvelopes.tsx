import React from "react";
import { Wallet } from "lucide-react";
import { Skeleton } from "./ui/Skeleton";

export interface SmartBudgetEnvelopesProps {
  mandiriExpenses?: {
    makan: number;
    jajan: number;
    laundry: number;
    galon: number;
  };
  expenses?: {
    makan: number;
    jajan: number;
    laundry: number;
    galon: number;
  };
  formatRupiah: (val: number) => string;
  cycleDays?: number;
  pocketAccount?: string;
  pocketBudget?: number;
  loading?: boolean;
}

export type MandiriEnvelopesProps = SmartBudgetEnvelopesProps;

const ENVELOPE_ICONS = ["Makan Harian", "Jajan & Kopi", "Laundry", "Galon & Air"];

export function SmartBudgetEnvelopes({
  mandiriExpenses,
  expenses: propExpenses,
  formatRupiah,
  cycleDays = 14,
  pocketAccount = "Saku Operasional",
  pocketBudget,
  loading,
}: SmartBudgetEnvelopesProps) {
  const currentExpenses = propExpenses || mandiriExpenses || {
    makan: 0,
    jajan: 0,
    laundry: 0,
    galon: 0,
  };
  const totalPlafond = pocketBudget && pocketBudget > 0 ? pocketBudget : 0;
  const activePocketName = pocketAccount || "Saku Operasional";

  // Round envelope limits to nearest thousand IDR to avoid awkward fractions
  const roundToThousand = (val: number) => Math.round(val / 1000) * 1000;

  const envelopes = [
    {
      title: "Makan Harian",
      limit: totalPlafond > 0 ? roundToThousand(totalPlafond * 0.55) : 0,
      spent: currentExpenses.makan,
    },
    {
      title: "Jajan & Kopi",
      limit: totalPlafond > 0 ? roundToThousand(totalPlafond * 0.15) : 0,
      spent: currentExpenses.jajan,
    },
    {
      title: "Laundry",
      limit: totalPlafond > 0 ? roundToThousand(totalPlafond * 0.15) : 0,
      spent: currentExpenses.laundry,
    },
    {
      title: "Galon & Air",
      limit: totalPlafond > 0 ? roundToThousand(totalPlafond * 0.15) : 0,
      spent: currentExpenses.galon,
    },
  ];

  if (loading) {
    return (
      <section aria-label="Kantong belanja harian" className="luma-glass p-6 sm:p-7 space-y-5">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
          <div>
            <Skeleton className="w-56 h-5 rounded-full" />
            <Skeleton className="w-80 h-3.5 rounded-full mt-1.5" />
          </div>
          <Skeleton className="w-28 h-6 rounded-full" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3.5 sm:gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="rounded-2xl luma-inset p-4 sm:p-5 space-y-4"
            >
              <div className="flex justify-between items-center gap-2">
                <Skeleton className="w-24 h-4 rounded-full" />
                <Skeleton className="w-10 h-4 rounded-full" />
              </div>
              <div>
                <Skeleton className="w-28 h-6 rounded-full" />
                <Skeleton className="w-16 h-3 rounded-full mt-1.5" />
              </div>
              <Skeleton className="w-full h-1.5 rounded-full" />
              <div className="flex justify-between items-center pt-2 border-t border-luma-smokeline">
                <Skeleton className="w-16 h-3 rounded-full" />
                <Skeleton className="w-16 h-3 rounded-full" />
              </div>
            </div>
          ))}
        </div>
      </section>
    );
  }

  const pocketTitle = activePocketName.toLowerCase().startsWith("kantong")
    ? activePocketName
    : `Kantong ${activePocketName}`;

  return (
    <section aria-label={`Kantong belanja ${activePocketName}`} className="luma-glass p-6 sm:p-7 space-y-5">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
        <div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <h2 className="ai7-type-section text-luma-ivory tracking-tight">
              {pocketTitle}{" "}
              <span className="font-sans font-semibold text-luma-smoke text-sm">
                {totalPlafond > 0 ? `(Plafon ${formatRupiah(totalPlafond)})` : "(Monitoring Saku Harian)"}
              </span>
            </h2>
            <span className="text-xs sm:text-xs font-sans font-semibold px-2.5 py-0.5 rounded-full border bg-amberGold/15 text-amberGold border-amberGold/30">
              OPERASIONAL
            </span>
          </div>
          <p className="text-xs sm:text-sm text-luma-smoke mt-0.5">
            Monitoring limit pos belanja harian agar pengeluaran terkontrol sampai siklus berikutnya
          </p>
        </div>
        <span className="text-xs text-luma-gold font-sans font-semibold px-3 py-1.5 rounded-full bg-luma-gold/10 border border-luma-gold/30 shrink-0 self-start sm:self-center whitespace-nowrap">
          Reset Tiap {cycleDays} Hari
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3.5 sm:gap-4">
        {envelopes.map((env) => {
          const rem = env.limit > 0 ? env.limit - env.spent : 0;
          const pct = env.limit > 0 ? Math.min(100, Math.round((env.spent / env.limit) * 100)) : 0;
          const barClass = pct >= 100 || pct >= 90
            ? "bg-luma-coral"
            : pct >= 75
            ? "bg-luma-gold"
            : "bg-luma-sage";
          const isIcon = ENVELOPE_ICONS.includes(env.title);

          return (
            <div
              key={env.title}
              className="rounded-2xl luma-inset p-4 sm:p-5 space-y-3.5 flex flex-col justify-between transition-all duration-200"
            >
              <div className="space-y-3">
                <div className="flex justify-between items-center gap-2">
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <span
                      aria-hidden="true"
                      className="w-8 h-8 rounded-[var(--ai7-radius-control)] bg-luma-coal border border-luma-smokeline flex items-center justify-center shrink-0"
                    >
                      <Wallet className={`w-3.5 h-3.5 ${isIcon ? "text-luma-ember" : "text-luma-smoke"}`} />
                    </span>
                    <span className="text-luma-ivory font-semibold text-sm break-words leading-snug flex-1">
                      {env.title}
                    </span>
                  </div>
                  <span
                    className={`text-xs font-sans font-semibold px-2.5 py-1 rounded-full border shrink-0 tabular-nums ${
                      pct >= 90
                        ? "bg-luma-coral/10 border-luma-coral/30 text-luma-coral"
                        : pct >= 75
                        ? "bg-luma-gold/10 border-luma-gold/30 text-luma-gold"
                        : "bg-white/[0.06] border-luma-smokeline text-luma-smoke"
                    }`}
                  >
                    {pct}%
                  </span>
                </div>

                <div>
                  <div className="ai7-type-metric text-luma-ivory tracking-tight tabular-nums break-words">
                    {formatRupiah(rem)}
                  </div>
                  <div className="text-xs text-luma-smoke mt-0.5">Sisa saldo pos</div>
                </div>

                <div
                  className="h-1.5 bg-black/25 rounded-full overflow-hidden"
                  role="progressbar"
                  aria-valuenow={pct}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`Pemakaian ${env.title} ${pct} persen`}
                >
                  <div
                    style={{ width: `${pct}%` }}
                    className={`h-full transition-all duration-500 rounded-full ${barClass}`}
                  ></div>
                </div>
              </div>

              <div className="flex items-center justify-between text-xs text-luma-smoke font-sans pt-3 border-t border-luma-smokeline gap-2 tabular-nums">
                <div className="flex items-center gap-1 min-w-0">
                  <span className="text-xs">Limit:</span>
                  <span className="font-semibold text-luma-ivory text-xs whitespace-nowrap">{formatRupiah(env.limit)}</span>
                </div>
                <div className="flex items-center gap-1 min-w-0">
                  <span className="text-xs">Pakai:</span>
                  <span className={`font-semibold text-xs whitespace-nowrap ${pct >= 90 ? "text-luma-coral font-semibold" : "text-luma-ivory"}`}>
                    {formatRupiah(env.spent)}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export const MandiriEnvelopes = SmartBudgetEnvelopes;
export const SmartBudgetPockets = SmartBudgetEnvelopes;
export const MandiriPockets = SmartBudgetEnvelopes;
export default SmartBudgetEnvelopes;
