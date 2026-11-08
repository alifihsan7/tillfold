export function calendarDate(year: number, month: number, day: number): Date {
  const value = new Date(0);
  value.setUTCFullYear(year, month - 1, day);
  value.setUTCHours(12, 0, 0, 0);
  return value;
}

export function monthCells(year: number, month: number): (string | null)[] {
  const first = calendarDate(year, month, 1);
  const offset = (first.getUTCDay() + 6) % 7;
  const count = calendarDate(year, month + 1, 0).getUTCDate();
  const length = Math.ceil((offset + count) / 7) * 7;
  return Array.from({ length }, (_, index) => {
    const day = index - offset + 1;
    return day >= 1 && day <= count ? `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}` : null;
  });
}

export function shiftCalendarMonth(year: number, month: number, delta: number): { year: number; month: number } | null {
  const shifted = calendarDate(year, month + delta, 1);
  return shifted.getUTCFullYear() >= 1 && shifted.getUTCFullYear() <= 9999
    ? { year: shifted.getUTCFullYear(), month: shifted.getUTCMonth() + 1 } : null;
}

export function compactRupiah(amount: number): string {
  for (const [unit, suffix] of [[1e12, "T"], [1e9, "M"], [1e6, "jt"], [1e3, "rb"]] as const) {
    if (amount >= unit) return `${(amount / unit).toLocaleString("id-ID", { maximumFractionDigits: 1 })}${suffix}`;
  }
  return amount.toLocaleString("id-ID");
}
