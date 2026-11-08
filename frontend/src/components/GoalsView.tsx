import React from "react";
import {
  Plus,
  Target,
  Edit2,
  Trash2,
  Calendar,
  ShieldCheck,
  TrendingUp,
  AlertTriangle,
  Sparkles,
  Laptop,
  Plane,
  Car,
  Home,
  Coins,
  GraduationCap,
  Heart,
  Clock,
  CheckCircle2,
} from "lucide-react";
import { GoalItem } from "./EditGoalModal";
import { Skeleton } from "./ui/Skeleton";

interface GoalsViewProps {
  goals: GoalItem[];
  formatRupiah: (val: number) => string;
  onOpenAddModal: () => void;
  onEdit: (goal: GoalItem) => void;
  onDelete: (id: number) => void;
  loading?: boolean;
}

const COLOR_THEMES: Record<
  string,
  {
    dot: string;
    badgeBg: string;
    badgeText: string;
    badgeBorder: string;
    barBg: string;
  }
> = {
  emerald: {
    dot: "bg-luma-sage",
    badgeBg: "bg-luma-sage/10",
    badgeText: "text-luma-sage",
    badgeBorder: "border-luma-sage/30",
    barBg: "bg-luma-sage",
  },
  cyan: {
    dot: "bg-luma-gold",
    badgeBg: "bg-luma-gold/10",
    badgeText: "text-luma-gold",
    badgeBorder: "border-luma-gold/30",
    barBg: "bg-luma-gold",
  },
  amber: {
    dot: "bg-luma-ember",
    badgeBg: "bg-luma-ember/10",
    badgeText: "text-luma-ember",
    badgeBorder: "border-luma-ember/30",
    barBg: "bg-luma-ember",
  },
  purple: {
    dot: "bg-luma-ember",
    badgeBg: "bg-luma-ember/10",
    badgeText: "text-luma-ember",
    badgeBorder: "border-luma-ember/30",
    barBg: "bg-luma-ember",
  },
  rose: {
    dot: "bg-luma-coral",
    badgeBg: "bg-luma-coral/10",
    badgeText: "text-luma-coral",
    badgeBorder: "border-luma-coral/30",
    barBg: "bg-luma-coral",
  },
};

function formatNumber(num: number): string {
  return new Intl.NumberFormat("id-ID").format(num);
}

function formatDateIndo(dateStr: string | null): string {
  if (!dateStr) return "";
  try {
    const parts = dateStr.trim().split("-");
    if (parts.length === 3) {
      const year = parts[0].trim();
      const monthNames = [
        "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
        "Jul", "Agu", "Sep", "Okt", "Nov", "Des"
      ];
      const month = monthNames[parseInt(parts[1], 10) - 1] || parts[1];
      const day = parseInt(parts[2], 10);
      return `${day} ${month} ${year}`.trim();
    }
    const d = new Date(dateStr);
    return d.toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" }).trim();
  } catch {
    return dateStr;
  }
}

function renderGoalIcon(icon: string, name: string, category: string) {
  const lower = (name + " " + category).toLowerCase();
  if (lower.includes("dingin") || lower.includes("tabungan") || icon === "🛡️") {
    return <ShieldCheck className="w-5 h-5 text-luma-sage" />;
  }
  if (lower.includes("investasi") || lower.includes("bibit") || lower.includes("reksadana") || icon === "📈") {
    return <TrendingUp className="w-5 h-5 text-luma-gold" />;
  }
  if (lower.includes("darurat") || icon === "🚨") {
    return <AlertTriangle className="w-5 h-5 text-luma-gold" />;
  }
  if (lower.includes("laptop") || lower.includes("gadget") || icon === "💻") {
    return <Laptop className="w-5 h-5 text-luma-ember" />;
  }
  if (icon === "✨") {
    return <Sparkles className="w-5 h-5 text-luma-ember" />;
  }
  if (icon === "✈️") {
    return <Plane className="w-5 h-5 text-luma-gold" />;
  }
  if (icon === "🚗") {
    return <Car className="w-5 h-5 text-luma-ember" />;
  }
  if (icon === "🏠") {
    return <Home className="w-5 h-5 text-luma-sage" />;
  }
  if (icon === "🪙") {
    return <Coins className="w-5 h-5 text-luma-gold" />;
  }
  if (icon === "🎓") {
    return <GraduationCap className="w-5 h-5 text-luma-ember" />;
  }
  if (icon === "❤️") {
    return <Heart className="w-5 h-5 text-luma-coral" />;
  }
  if (icon && icon.length <= 4 && !icon.startsWith("http") && icon !== "🎯") {
    return <span className="text-xl leading-none select-none">{icon}</span>;
  }
  return <Target className="w-5 h-5 text-luma-ember" />;
}

export function GoalsView({
  goals,
  formatRupiah,
  onOpenAddModal,
  onEdit,
  onDelete,
  loading,
}: GoalsViewProps) {
  const totalTarget = goals.reduce((acc, g) => acc + g.target_amount, 0);
  const totalCurrent = goals.reduce((acc, g) => acc + g.current_amount, 0);
  const overallPercentage = totalTarget > 0 ? Math.round((totalCurrent / totalTarget) * 1000) / 10 : 0;

  return (
    <div className="space-y-8 sm:space-y-10">
      {/* Top Metrics Cards — Luma smoked glass */}
      <div className="ai7-metric-grid grid gap-4">
        <div className="luma-glass !rounded-3xl p-5 sm:p-6 space-y-2.5">
          <div className="text-xs font-semibold text-luma-smoke truncate">
            Total target tabungan
          </div>
          {loading ? (
            <Skeleton className="h-8 w-36 rounded-full" />
          ) : (
            <div className="ai7-type-metric text-luma-ivory tracking-tight truncate tabular-nums">
              {formatRupiah(totalTarget)}
            </div>
          )}
          <div className="text-xs text-luma-smoke font-sans">
            Jumlah semua target
          </div>
        </div>

        <div className="luma-glass !rounded-3xl p-5 sm:p-6 space-y-2.5">
          <div className="text-xs font-semibold text-luma-smoke truncate">
            Total terkumpul
          </div>
          {loading ? (
            <Skeleton className="h-8 w-36 rounded-full" />
          ) : (
            <div className="ai7-type-metric text-luma-sage tracking-tight truncate tabular-nums">
              {formatRupiah(totalCurrent)}
            </div>
          )}
          <div className="text-xs text-luma-smoke font-sans">
            Progres all-time tersinkronisasi
          </div>
        </div>

        <div className="luma-glass !rounded-3xl p-5 sm:p-6 space-y-2.5">
          <div className="text-xs font-semibold text-luma-smoke truncate">
            Rata-rata capaian
          </div>
          {loading ? (
            <Skeleton className="h-8 w-24 rounded-full" />
          ) : (
            <div className="ai7-type-metric text-luma-gold tracking-tight truncate tabular-nums">
              {overallPercentage}%
            </div>
          )}
          <div className="text-xs text-luma-smoke font-sans truncate tabular-nums">
            Sisa {formatRupiah(Math.max(0, totalTarget - totalCurrent))}
          </div>
        </div>

        <div className="luma-glass !rounded-3xl p-5 sm:p-6 space-y-2.5">
          <div className="text-xs font-semibold text-luma-smoke truncate">
            Status sasaran
          </div>
          {loading ? (
            <Skeleton className="h-8 w-28 rounded-full" />
          ) : (
            <div className="ai7-type-metric text-luma-ivory tracking-tight truncate tabular-nums">
              {goals.filter((g) => g.remaining_amount === 0).length} / {goals.length}{" "}
              <span className="text-xs font-normal text-luma-smoke font-sans">Tercapai</span>
            </div>
          )}
          <div className="text-xs text-luma-smoke font-sans">
            {goals.filter((g) => g.remaining_amount > 0).length} target masih berjalan
          </div>
        </div>
      </div>

      {/* Action Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 py-1">
        <div>
          <h2 className="ai7-type-section text-luma-ivory tracking-tight flex items-center gap-2.5">
            <Target className="w-5 h-5 text-luma-ember" aria-hidden="true" />
            Milestone Tracker Tabungan &amp; Investasi
          </h2>
          <p className="text-xs sm:text-sm text-luma-smoke mt-1">
            Pantau progres tabungan dan investasi
          </p>
        </div>

        <button
          type="button"
          onClick={onOpenAddModal}
          className="luma-touch flex items-center gap-2 px-5 py-2.5 bg-luma-ivory text-luma-charcoal font-semibold rounded-full hover:brightness-95 transition text-xs sm:text-sm shrink-0 whitespace-nowrap cursor-pointer active:scale-95"
        >
          <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
          <span>Tambah target</span>
        </button>
      </div>

      {/* Milestone Cards Grid — Luma smoked glass, Ember/Sage/Gold/Coral bars */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 sm:gap-7 lg:gap-8">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="luma-glass p-6 sm:p-7 space-y-6"
            >
              <div className="flex items-start justify-between gap-3.5">
                <div className="flex items-center gap-3.5">
                  <Skeleton className="w-12 h-12 rounded-full" />
                  <div className="space-y-2">
                    <Skeleton className="w-32 h-5 rounded-full" />
                    <Skeleton className="w-20 h-3 rounded-full" />
                  </div>
                </div>
                <Skeleton className="w-16 h-6 rounded-full" />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <Skeleton className="w-24 h-4 rounded-full" />
                  <Skeleton className="w-28 h-4 rounded-full" />
                </div>
                <Skeleton className="w-full h-3 rounded-full" />
              </div>
              <div className="pt-2 border-t border-luma-smokeline flex justify-between">
                <Skeleton className="w-20 h-4 rounded-full" />
                <Skeleton className="w-24 h-4 rounded-full" />
              </div>
            </div>
          ))}
        </div>
      ) : goals.length === 0 ? (
        <div className="luma-glass p-12 text-center space-y-4">
          <div className="w-14 h-14 rounded-full bg-luma-ember/10 border border-luma-ember/30 flex items-center justify-center mx-auto text-luma-ember">
            <Target className="w-7 h-7" />
          </div>
          <div>
            <h3 className="ai7-type-card text-luma-ivory">Belum ada target tabungan</h3>
            <p className="text-xs sm:text-sm text-luma-smoke mt-1 max-w-md mx-auto">
              Buat target untuk mulai melacak tabungan atau investasi.
            </p>
          </div>
          <button
            onClick={onOpenAddModal}
            className="luma-touch inline-flex items-center gap-2 px-5 py-2.5 bg-luma-ivory text-luma-charcoal font-semibold rounded-full hover:brightness-95 transition text-sm whitespace-nowrap cursor-pointer"
          >
            <Plus className="w-4 h-4 stroke-[2.5]" />
            <span>Buat target pertama</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 sm:gap-7 lg:gap-8">
          {goals.map((goal) => {
            const theme = COLOR_THEMES[goal.color] || COLOR_THEMES.emerald;
            const isCompleted = goal.remaining_amount === 0;

            return (
              <div
                key={goal.id}
                className="ai7-goal-card luma-glass group relative p-6 sm:p-7 flex flex-col justify-between overflow-hidden"
              >
                <div className="space-y-6 relative z-[1]">
                  {/* Top Header: Icon + Category Badge + Account + Actions */}
                  <div className="flex items-start justify-between gap-3.5">
                    <div className="flex items-center gap-3.5 min-w-0">
                      {/* Circular icon well */}
                      <div className="ai7-account-icon w-12 h-12 rounded-xl border flex items-center justify-center shrink-0">
                        {renderGoalIcon(goal.icon, goal.name, goal.category)}
                      </div>

                      <div className="min-w-0 space-y-1">
                        {/* Ghost badges with glowing status dot */}
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/[0.06] border border-luma-smokeline text-xs font-medium text-luma-smoke">
                            <span className={`w-1.5 h-1.5 rounded-full ${theme.dot}`} />
                            {goal.category}
                          </span>

                          {goal.linked_account ? (
                            <span className="text-xs font-sans text-luma-smoke bg-white/[0.04] border border-luma-smokeline px-2.5 py-0.5 rounded-full truncate">
                              Rek. {goal.linked_account}
                            </span>
                          ) : (
                            <span className="text-xs font-sans text-luma-smoke bg-white/[0.04] border border-luma-smokeline px-2.5 py-0.5 rounded-full">
                              Manual
                            </span>
                          )}
                        </div>

                        <h3 className="ai7-type-card text-luma-ivory line-clamp-2 tracking-tight">
                          {goal.name}
                        </h3>
                      </div>
                    </div>

                    {/* Actions: thumb-friendly 44px pill buttons */}
                    <div className="flex items-center gap-1 shrink-0 opacity-80 group-hover:opacity-100 transition-opacity">
                      <button
                        type="button"
                        onClick={() => onEdit(goal)}
                        aria-label={`Ubah target ${goal.name}`}
                        className="luma-touch min-w-[44px] inline-flex items-center justify-center text-luma-smoke hover:text-luma-ivory hover:bg-white/[0.06] rounded-full transition-colors border border-transparent hover:border-white/[0.08] cursor-pointer"
                        title="Ubah Target"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => onDelete(goal.id)}
                        aria-label={`Hapus target ${goal.name}`}
                        className="luma-touch min-w-[44px] inline-flex items-center justify-center text-luma-smoke hover:text-luma-coral hover:bg-luma-coral/10 rounded-full transition-colors border border-transparent hover:border-luma-coral/25 cursor-pointer"
                        title="Hapus target"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Amounts & Percentage Display — tabular numerals, mono percent */}
                  <div className="space-y-2 pt-1">
                    <div className="flex items-baseline justify-between gap-2">
                      <div className="flex items-baseline gap-1 ai7-type-metric text-luma-ivory tracking-tight tabular-nums">
                        <span className="text-sm font-sans font-normal text-luma-smoke">Rp</span>
                        <span>{formatNumber(goal.current_amount)}</span>
                      </div>
                      <div
                        className={`text-xs font-sans font-semibold px-3 py-1 rounded-full border tabular-nums ${theme.badgeBg} ${theme.badgeText} ${theme.badgeBorder}`}
                      >
                        {goal.percentage >= 100 ? "100%" : `${Number(goal.percentage).toFixed(1)}%`}
                      </div>
                    </div>
                    <div className="flex justify-between items-center text-xs font-sans text-luma-smoke tabular-nums">
                      <span>Target: {formatRupiah(goal.target_amount)}</span>
                    </div>
                  </div>

                  {/* Luma progress bar */}
                  <div className="space-y-2 pt-1">
                    <div
                      className="h-2 w-full bg-black/25 rounded-full overflow-hidden border border-luma-smokeline"
                      role="progressbar"
                      aria-valuenow={Math.round(Number(goal.percentage) || 0)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={`Progres ${goal.name}`}
                    >
                      <div
                        className={`h-full bg-luma-sage transition-all duration-700 rounded-full`}
                        style={{ width: `${Math.min(100, Math.max(3, goal.percentage))}%` }}
                      />
                    </div>
                    <div className="flex justify-between items-center text-xs font-sans text-luma-smoke tabular-nums">
                      <span>{isCompleted ? "Tercapai 100%" : `${Number(goal.percentage).toFixed(1)}% terkumpul`}</span>
                      <span>{isCompleted ? "Selesai" : `Sisa ${formatRupiah(goal.remaining_amount)}`}</span>
                    </div>
                  </div>

                  {/* Clean Projections Separator */}
                  <div className="border-t border-luma-smokeline pt-4 space-y-2 text-xs">
                    {isCompleted ? (
                      <div className="flex items-center gap-2 text-luma-sage font-medium">
                        <CheckCircle2 className="w-4 h-4 shrink-0" />
                        <span>Target tabungan ini telah tercapai 100%.</span>
                      </div>
                    ) : goal.estimated_cycles !== null ? (
                      <div className="flex items-start justify-between gap-2 text-luma-smoke">
                        <div className="flex items-center gap-2 min-w-0">
                          <Clock className="w-3.5 h-3.5 text-luma-smoke shrink-0" />
                          <span className="text-luma-ivory font-medium truncate tabular-nums">
                            ~{goal.estimated_cycles} siklus lagi{" "}
                            <span className="text-luma-smoke font-normal">
                              (~{Number(goal.estimated_months).toFixed(1)} bln)
                            </span>
                          </span>
                        </div>
                        {goal.estimated_finish_date && (
                          <div className="text-xs font-sans text-luma-smoke shrink-0 whitespace-nowrap tabular-nums">
                            <span>Est: </span><span className="text-luma-ivory">{formatDateIndo(goal.estimated_finish_date)}</span>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-luma-smoke text-xs">
                        Konsisten sisihkan dana rutin untuk melihat perkiraan tuntas.
                      </div>
                    )}

                    {goal.target_date && (
                      <div className="flex items-center gap-2 text-xs text-luma-smoke pt-0.5">
                        <Calendar className="w-3.5 h-3.5 text-luma-smoke shrink-0" />
                        <span>Deadline: <span className="font-sans text-luma-ivory tabular-nums">{formatDateIndo(goal.target_date)}</span></span>
                      </div>
                    )}
                  </div>

                  {/* Clean Notes */}
                  {goal.notes && (
                    <p className="text-xs text-luma-smoke line-clamp-2 leading-relaxed pt-3 border-t border-luma-smokeline text-pretty">
                      {goal.notes}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
