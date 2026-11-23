import React from "react";
import { getCategoryColorDef } from "@/lib/categoryColors";
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

const GOAL_COLOR_KEYS: Record<string, string> = {
  emerald: "mintRise", cyan: "cyanHub", amber: "amberGold", purple: "purpleLock", rose: "coralFall",
};

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

const GOAL_ICON_GLYPHS: Record<string, React.ReactNode> = {
  "🛡️": <ShieldCheck className="w-5 h-5 text-luma-sage" />,
  "📈": <TrendingUp className="w-5 h-5 text-luma-gold" />,
  "🚨": <AlertTriangle className="w-5 h-5 text-luma-gold" />,
  "💻": <Laptop className="w-5 h-5 text-luma-ember" />,
  "✨": <Sparkles className="w-5 h-5 text-luma-ember" />,
  "✈️": <Plane className="w-5 h-5 text-luma-gold" />,
  "🚗": <Car className="w-5 h-5 text-luma-ember" />,
  "🏠": <Home className="w-5 h-5 text-luma-sage" />,
  "🪙": <Coins className="w-5 h-5 text-luma-gold" />,
  "🎓": <GraduationCap className="w-5 h-5 text-luma-ember" />,
  "❤️": <Heart className="w-5 h-5 text-luma-coral" />,
};

const DEFAULT_GOAL_ICON = "🎯";

// The icon the user picked always wins. Name/category keywords only fill in
// when the goal still carries the default icon. Category alone is not used:
// every goal defaults to the "Tabungan" category, which would match everything.
export function renderGoalIcon(icon: string, name: string) {
  const picked = (icon || "").trim();
  if (picked && picked !== DEFAULT_GOAL_ICON) {
    if (GOAL_ICON_GLYPHS[picked]) return GOAL_ICON_GLYPHS[picked];
    if (Array.from(picked).length <= 3 && !picked.startsWith("http")) {
      return <span className="text-xl leading-none select-none" aria-hidden="true">{picked}</span>;
    }
  }
  const lower = name.toLowerCase();
  if (lower.includes("dingin") || lower.includes("tabungan")) return GOAL_ICON_GLYPHS["🛡️"];
  if (lower.includes("darurat")) return GOAL_ICON_GLYPHS["🚨"];
  if (lower.includes("investasi") || lower.includes("bibit") || lower.includes("reksadana")) return GOAL_ICON_GLYPHS["📈"];
  if (lower.includes("laptop") || lower.includes("gadget")) return GOAL_ICON_GLYPHS["💻"];
  return <Target className="w-5 h-5 text-luma-ember" />;
}

// Money above a goal's target does not count toward other goals, so the
// collected total is capped per goal and any excess is reported apart.
export function summarizeGoals(goals: { target_amount: number; current_amount: number }[]) {
  let target = 0, collected = 0, surplus = 0, pctSum = 0;
  for (const g of goals) {
    const goalTarget = Math.max(0, g.target_amount);
    const current = Math.max(0, g.current_amount);
    target += goalTarget;
    collected += Math.min(current, goalTarget);
    surplus += Math.max(0, current - goalTarget);
    pctSum += goalTarget > 0 ? Math.min(100, (current / goalTarget) * 100) : 0;
  }
  const averagePercentage = goals.length ? Math.round((pctSum / goals.length) * 10) / 10 : 0;
  return { target, collected, surplus, remaining: target - collected, averagePercentage };
}

export function GoalsView({
  goals,
  formatRupiah,
  onOpenAddModal,
  onEdit,
  onDelete,
  loading,
}: GoalsViewProps) {
  const totals = summarizeGoals(goals);

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
              {formatRupiah(totals.target)}
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
              {formatRupiah(totals.collected)}
            </div>
          )}
          <div className="text-xs text-luma-smoke font-sans truncate tabular-nums">
            {totals.surplus > 0 ? `Lebih ${formatRupiah(totals.surplus)} di atas target` : "Dihitung sampai batas tiap target"}
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
              {totals.averagePercentage}%
            </div>
          )}
          <div className="text-xs text-luma-smoke font-sans truncate tabular-nums">
            Sisa {formatRupiah(totals.remaining)}
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

      <h2 className="ai7-type-section text-luma-ivory tracking-tight">
        Progres tabungan &amp; investasi
      </h2>

      {/* Goal cards */}
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
            const theme = getCategoryColorDef(GOAL_COLOR_KEYS[goal.color] || "mintRise");
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
                      <div className="ai7-account-icon w-12 h-12 rounded-full flex items-center justify-center shrink-0">
                        {renderGoalIcon(goal.icon, goal.name)}
                      </div>

                      <div className="min-w-0 space-y-1">
                        {/* Ghost badges with glowing status dot */}
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/[0.06] text-xs font-medium text-luma-smoke">
                            <span className={`w-1.5 h-1.5 rounded-full ${theme.dotClass}`} />
                            {goal.category}
                          </span>

                          {goal.linked_account ? (
                            <span className="text-xs font-sans text-luma-smoke bg-white/[0.04] px-2.5 py-0.5 rounded-full truncate">
                              Rek. {goal.linked_account}
                            </span>
                          ) : (
                            <span className="text-xs font-sans text-luma-smoke bg-white/[0.04] px-2.5 py-0.5 rounded-full">
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
                        title="Ubah target"
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
                      <div className="ai7-type-metric text-luma-ivory tracking-tight tabular-nums">
                        {formatRupiah(goal.current_amount)}
                      </div>
                      <div
                        className={`text-xs font-sans font-semibold px-3 py-1 rounded-full tabular-nums ${theme.badgeBg} ${theme.badgeText}`}
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
                      className="fold-goal-progress h-2 w-full rounded-full overflow-hidden"
                      role="progressbar"
                      aria-valuenow={Math.round(Number(goal.percentage) || 0)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={`Progres ${goal.name}`}
                    >
                      <div
                        className={`h-full ${theme.dotClass} transition-all duration-700 rounded-full`}
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

                    {!isCompleted && goal.is_behind_schedule && goal.required_per_cycle ? (
                      <p role="note" className="flex items-start gap-2 text-xs text-luma-gold">
                        <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" aria-hidden="true" />
                        <span>
                          {goal.target_date && goal.target_date <= new Date().toLocaleDateString("en-CA")
                            ? `Deadline sudah lewat, masih kurang ${formatRupiah(goal.required_per_cycle)}.`
                            : `Perkiraan selesai lewat deadline. Sisihkan ${formatRupiah(goal.required_per_cycle)} per siklus agar tepat waktu.`}
                        </span>
                      </p>
                    ) : null}

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
