export interface CashFlowDay {
  date: string;
  income: number;
  expense: number;
}

const DAY = 86_400_000;
function dateTime(value: string): number {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return NaN;
  const time = Date.parse(`${value}T00:00:00Z`);
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value ? time : NaN;
}

// Keep calendar gaps visible: a quiet day must occupy the same space as a busy day.
export function cashFlowDays(items: CashFlowDay[], start: string, end: string): CashFlowDay[] {
  const first = dateTime(start), last = dateTime(end);
  const byDate = new Map(items.map((item) => [item.date, item]));
  if (!Number.isFinite(first) || !Number.isFinite(last) || last < first) return [...items].sort((a, b) => a.date.localeCompare(b.date));
  return Array.from({ length: Math.round((last - first) / DAY) + 1 }, (_, index) => {
    const date = new Date(first + index * DAY).toISOString().slice(0, 10);
    return byDate.get(date) ?? { date, income: 0, expense: 0 };
  });
}

export function cashFlowCeiling(days: CashFlowDay[]): number {
  const max = days.reduce((value, day) => Math.max(value, day.income, day.expense), 0);
  if (max <= 0) return 1;
  const interval = max / 4;
  const power = 10 ** Math.floor(Math.log10(interval));
  const step = ([1, 2, 2.5, 5, 10].find((value) => value * power >= interval) ?? 10) * power;
  return step * 4;
}

export type CashFlowGranularity = "daily" | "weekly" | "monthly";
export interface CashFlowRange { start: string; end: string; category?: string; type: "expense" | "cash_flow"; }
export interface CashFlowBucket extends CashFlowDay { endDate: string; }

export function cashFlowBuckets(days: CashFlowDay[], granularity: CashFlowGranularity): CashFlowBucket[] {
  const groups = new Map<string, CashFlowBucket>();
  for (const day of days) {
    let key = day.date;
    if (granularity === "monthly") key = day.date.slice(0, 7);
    if (granularity === "weekly") {
      const monday = new Date(`${day.date}T00:00:00Z`);
      monday.setUTCDate(monday.getUTCDate() - (monday.getUTCDay() + 6) % 7);
      key = monday.toISOString().slice(0, 10);
    }
    const bucket = groups.get(key);
    if (bucket) {
      bucket.income += day.income; bucket.expense += day.expense; bucket.endDate = day.date;
    } else groups.set(key, { ...day, endDate: day.date });
  }
  return Array.from(groups.values());
}
