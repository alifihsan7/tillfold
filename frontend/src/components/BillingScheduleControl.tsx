import { SegmentedControl, SegmentedOption } from "./ui/controls";

type BillingSchedule = "fixed_day" | "exact_date" | "yearly";

const label = "Metode perhitungan jatuh tempo";
const options: SegmentedOption<BillingSchedule>[] = [
  { value: "fixed_day", label: "Tanggal rutin" },
  { value: "exact_date", label: "Tanggal tertentu" },
  { value: "yearly", label: "Tahunan" },
];

export function BillingScheduleControl({ value, onChange }: {
  value: BillingSchedule;
  onChange: (value: BillingSchedule) => void;
}) {
  return (
    <div className="min-w-0">
      <p className="mb-2 text-xs font-semibold text-luma-smoke">{label}</p>
      <SegmentedControl fill label={label} className="billing-schedule-control" value={value} onChange={onChange} options={options} />
    </div>
  );
}
