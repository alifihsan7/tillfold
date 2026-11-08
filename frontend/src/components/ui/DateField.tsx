import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { todayWib } from "@/lib/transactionCalendar";
import { Calendar, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";

interface Props {
  id?: string;
  label?: string;
  value: string;
  onChange: (value: string) => void;
  min?: string;
  max?: string;
  required?: boolean;
}

const monthName = new Intl.DateTimeFormat("id-ID", { month: "long", timeZone: "UTC" });
const monthLabels = Array.from({ length: 12 }, (_, index) => monthName.format(new Date(Date.UTC(2020, index, 1))));
const iso = (date: Date) => date.toISOString().slice(0, 10);
const validDate = (value: string) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(value);
  return Number.isFinite(date.getTime()) && iso(date) === value && value >= "0001-01-01";
};

export function DateField({ id, label, value, onChange, min, max, required }: Props) {
  const uid = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const field = useRef<HTMLDivElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const calendarBody = useRef<HTMLDivElement>(null);
  const [draft, setDraft] = useState(value);
  const [open, setOpen] = useState(false);
  const [month, setMonth] = useState(() => new Date());
  const [view, setView] = useState<"days" | "months" | "years">("days");
  const [decade, setDecade] = useState(2020);
  const [touched, setTouched] = useState(false);
  const [position, setPosition] = useState<{ left: number; top: number; width: number; maxHeight: number; transform?: string }>();

  const inRange = (date: string) => (!min || date >= min) && (!max || date <= max);
  const error = draft && (!validDate(draft) || !inRange(draft))
    ? "Isi tanggal yang valid dalam format YYYY-MM-DD dan rentang yang tersedia."
    : "";
  useEffect(() => { setDraft(value); }, [value]);
  useEffect(() => { input.current?.setCustomValidity(error); }, [error]);
  useEffect(() => {
    if (calendarBody.current) calendarBody.current.scrollTop = 0;
  }, [view, decade, month]);
  useEffect(() => {
    if (!open) return;
    function placeCalendar() {
      const rect = field.current?.getBoundingClientRect();
      if (!rect) return;
      const width = Math.min(320, window.innerWidth - 16);
      const below = window.innerHeight - rect.bottom - 14;
      const above = rect.top - 14;
      const upward = below < 360 && above > below;
      const height = Math.min(360, Math.max(0, upward ? above : below));
      setPosition({
        left: Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8)),
        top: upward ? rect.top - 6 : rect.bottom + 6,
        width,
        maxHeight: height,
        transform: upward ? "translateY(-100%)" : undefined,
      });
    }
    function closeOutside(event: PointerEvent) {
      if (event.target instanceof Node && !field.current?.contains(event.target) && !popup.current?.contains(event.target)) setOpen(false);
    }
    placeCalendar();
    window.addEventListener("resize", placeCalendar);
    window.addEventListener("scroll", placeCalendar, true);
    document.addEventListener("pointerdown", closeOutside);
    return () => {
      window.removeEventListener("resize", placeCalendar);
      window.removeEventListener("scroll", placeCalendar, true);
      document.removeEventListener("pointerdown", closeOutside);
    };
  }, [open]);

  const shiftMonth = (amount: number) => {
    const next = new Date(month);
    next.setUTCMonth(month.getUTCMonth() + amount, 1);
    if (next.getUTCFullYear() >= 1 && next.getUTCFullYear() <= 9999) setMonth(next);
  };
  const days = new Date(month);
  days.setUTCMonth(month.getUTCMonth() + 1, 0);
  const first = new Date(month);
  first.setUTCDate(1);
  const offset = (first.getUTCDay() + 6) % 7;
  const year = month.getUTCFullYear();
  const monthIndex = month.getUTCMonth();
  const jump = (nextYear: number, nextMonth: number) => {
    const date = new Date(month);
    date.setUTCFullYear(nextYear, nextMonth, 1);
    setMonth(date);
  };

  return (
    <div ref={field} className="tillfold-date" onKeyDown={(event) => {
      if (event.key === "Escape" && open) {
        event.stopPropagation();
        setOpen(false);
        trigger.current?.focus();
      }
    }}>
      <div className="tillfold-date-field">
        <input ref={input} id={id} aria-label={label} type="text" value={draft}
          placeholder="YYYY-MM-DD" autoComplete="off" maxLength={10} required={required}
          aria-invalid={Boolean(touched && error)} aria-describedby={touched && error ? `${uid}-error` : undefined}
          onBlur={() => setTouched(true)}
          onChange={(event) => {
            const next = event.target.value;
            setDraft(next);
            if (!next || (validDate(next) && inRange(next))) onChange(next);
          }} />
        <button ref={trigger} type="button" aria-label="Pilih tanggal" title="Pilih tanggal"
          aria-expanded={open} aria-controls={open ? uid : undefined}
          onClick={() => {
            if (!open) {
              setMonth(new Date(validDate(value) ? value : todayWib()));
              setView("days");
            }
            setOpen(!open);
          }}><Calendar size={16} aria-hidden="true" /></button>
      </div>
      {touched && error && <p id={`${uid}-error`} className="mt-1 text-xs text-luma-coral">{error}</p>}
      {open && position && createPortal(
        <div ref={popup} id={uid} className="tillfold-calendar" style={position} role="group" aria-label="Kalender">
          <div className="tillfold-calendar-toolbar">
            <button type="button" aria-label={view === "years" ? "Sepuluh tahun sebelumnya" : view === "months" ? "Tahun sebelumnya" : "Bulan sebelumnya"}
              disabled={view === "years" && decade === 0}
              onClick={() => view === "years" ? setDecade(decade - 10) : shiftMonth(view === "months" ? -12 : -1)}><ChevronLeft size={16} aria-hidden="true" /></button>
            <div className="tillfold-calendar-switch">
              <button type="button" className="tillfold-calendar-heading" aria-label={`Pilih bulan: ${monthLabels[monthIndex]}`}
                aria-pressed={view === "months"} onClick={() => setView(view === "months" ? "days" : "months")}>
                {monthLabels[monthIndex]} <ChevronDown size={12} aria-hidden="true" />
              </button>
              <button type="button" className="tillfold-calendar-heading" aria-label={`Pilih tahun: ${year}`}
                aria-pressed={view === "years"} onClick={() => {
                  setDecade(Math.floor(year / 10) * 10);
                  setView(view === "years" ? "days" : "years");
                }}>
                {year} <ChevronDown size={12} aria-hidden="true" />
              </button>
            </div>
            <button type="button" aria-label={view === "years" ? "Sepuluh tahun berikutnya" : view === "months" ? "Tahun berikutnya" : "Bulan berikutnya"}
              disabled={view === "years" && decade === 9990}
              onClick={() => view === "years" ? setDecade(decade + 10) : shiftMonth(view === "months" ? 12 : 1)}><ChevronRight size={16} aria-hidden="true" /></button>
          </div>
          <div ref={calendarBody} className="tillfold-calendar-body">
          {view === "years" && (
            <div className="grid grid-cols-3 gap-1 text-center" aria-label="Daftar tahun" role="group">
              {Array.from({ length: 10 }, (_, index) => decade + index).filter(Boolean).map((option) => (
                <button key={option} type="button" aria-pressed={year === option} onClick={() => {
                  jump(option, monthIndex);
                  setView("months");
                }}>{option}</button>
              ))}
            </div>
          )}
          {view === "months" && (
            <div className="grid grid-cols-3 gap-1 text-center" aria-label="Daftar bulan" role="group">
              {monthLabels.map((name, index) => (
                <button key={name} type="button" aria-pressed={monthIndex === index} onClick={() => {
                  jump(year, index);
                  setView("days");
                }}>{name}</button>
              ))}
            </div>
          )}
          {view === "days" && <div className="grid grid-cols-7 gap-px text-center">
            {["Sn", "Sl", "Rb", "Km", "Jm", "Sb", "Mg"].map((day) => <span key={day} aria-hidden="true" className="py-1 text-[10px] text-luma-smoke">{day}</span>)}
            {Array.from({ length: offset }, (_, index) => <span key={`blank-${index}`} />)}
            {Array.from({ length: days.getUTCDate() }, (_, index) => {
              const day = index + 1;
              const date = new Date(first);
              date.setUTCDate(day);
              const key = iso(date);
              return <button key={key} type="button" aria-label={key} aria-pressed={key === value}
                disabled={!inRange(key)} onClick={() => {
                  setDraft(key);
                  onChange(key);
                  setOpen(false);
                  trigger.current?.focus();
                }}>{day}</button>;
            })}
          </div>}
          </div>
        </div>,
        field.current?.closest('[role="dialog"]') || document.body
      )}
    </div>
  );
}
