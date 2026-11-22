// One date and one signed-amount format for every list in the app.

const shortDate = new Intl.DateTimeFormat("id-ID", { day: "numeric", month: "short", timeZone: "UTC" });
const shortDateWithYear = new Intl.DateTimeFormat("id-ID", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

/** "15 Nov" within the current year, "15 Nov 2025" otherwise. Accepts YYYY-MM-DD. */
export function formatShortDate(value: string, today: Date = new Date()): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value || "");
  if (!match) return value || "";
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  if (Number.isNaN(date.getTime())) return value;
  return (date.getUTCFullYear() === today.getFullYear() ? shortDate : shortDateWithYear).format(date);
}

/** Range for tight controls: the year is dropped when both ends fall in the current year. */
export function formatCompactRange(start: string, end: string, today: Date = new Date()): string {
  const first = new Date(start);
  const last = new Date(end);
  if (!Number.isFinite(first.getTime()) || !Number.isFinite(last.getTime())) return "";
  const year = today.getFullYear();
  if (first.getUTCFullYear() !== year || last.getUTCFullYear() !== year) return formatDateRange(start, end);
  if (start === end) return shortDate.format(last);
  if (first.getUTCMonth() === last.getUTCMonth()) return `${first.getUTCDate()}–${shortDate.format(last)}`;
  return `${shortDate.format(first)} – ${shortDate.format(last)}`;
}

/** Compact inclusive range, with the year repeated only when it changes. */
export function formatDateRange(start: string, end: string): string {
  const first = new Date(start);
  const last = new Date(end);
  if (!Number.isFinite(first.getTime()) || !Number.isFinite(last.getTime())) return "";
  if (start === end) return shortDateWithYear.format(last);
  if (first.getUTCFullYear() !== last.getUTCFullYear()) {
    return `${shortDateWithYear.format(first)} – ${shortDateWithYear.format(last)}`;
  }
  if (first.getUTCMonth() === last.getUTCMonth()) {
    return `${first.getUTCDate()}–${shortDateWithYear.format(last)}`;
  }
  return `${shortDate.format(first)} – ${shortDateWithYear.format(last)}`;
}

/** "+Rp 750.000" or "-Rp 120.000": the sign sits directly against the currency. */
export function formatSignedRupiah(amount: number, positive: boolean, formatRupiah: (value: number) => string): string {
  return `${positive ? "+" : "-"}${formatRupiah(Math.abs(amount))}`;
}
