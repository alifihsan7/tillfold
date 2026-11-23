"use client";

import React from "react";
import { SelectionRail } from "./SelectionRail";

/*
 * Shared controls. One look per role, so pages cannot drift apart again:
 * Button acts, Chip filters a list, SegmentedControl switches between views
 * of the same content, Badge labels a state. Styles live in globals.css under
 * "Shared controls"; every selected state uses the same silver treatment.
 */

function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  icon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", icon, className, children, type = "button", ...props },
  ref,
) {
  return (
    <button ref={ref} type={type} className={cx("ui-btn", `ui-btn--${variant}`, className)} {...props}>
      {icon && <span className="ui-btn-icon" aria-hidden="true">{icon}</span>}
      {children}
    </button>
  );
});

export interface ChipProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "aria-pressed"> {
  selected: boolean;
}

export function Chip({ selected, className, children, type = "button", ...props }: ChipProps) {
  return (
    <button type={type} aria-pressed={selected} className={cx("ui-chip", className)} {...props}>
      {children}
    </button>
  );
}

/**
 * Horizontal row of chips. When the chips overflow, the row scrolls and the
 * clipped edge fades, so a cut-off chip reads as "more to the side".
 */
export function ChipRow({ label, className, children }: { label: string; className?: string; children: React.ReactNode }) {
  const ref = React.useRef<HTMLDivElement>(null);
  const [edges, setEdges] = React.useState({ start: false, end: false });

  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setEdges({
      start: el.scrollLeft > 1,
      end: el.scrollLeft + el.clientWidth < el.scrollWidth - 1,
    });
    update();
    el.addEventListener("scroll", update, { passive: true });
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(update) : null;
    observer?.observe(el);
    return () => { el.removeEventListener("scroll", update); observer?.disconnect(); };
  }, []);

  return (
    <div ref={ref} role="group" aria-label={label} className={cx("ui-chip-row", className)}
      data-fade-start={edges.start || undefined} data-fade-end={edges.end || undefined}>
      {children}
    </div>
  );
}

export interface SegmentedOption<T extends string> {
  value: T;
  label: React.ReactNode;
  icon?: React.ReactNode;
  /** Money direction: the selected segment takes the expense or income color. */
  tone?: "expense" | "income";
}

export function SegmentedControl<T extends string>({ label, value, options, onChange, className, fill }: {
  label: string;
  value: T;
  options: SegmentedOption<T>[];
  onChange: (value: T) => void;
  className?: string;
  /** Stretch segments to share the full width, as in dialog forms. */
  fill?: boolean;
}) {
  return (
    <SelectionRail selection={value} role="group" aria-label={label} className={cx("ui-segmented", fill && "ui-segmented--fill", className)}>
      {options.map((option) => (
        <button key={option.value} type="button" className="ui-segment" aria-pressed={value === option.value}
          data-tone={option.tone} onClick={() => onChange(option.value)}>
          {option.icon && <span className="ui-btn-icon" aria-hidden="true">{option.icon}</span>}
          {option.label}
        </button>
      ))}
    </SelectionRail>
  );
}

export type BadgeTone = "neutral" | "positive" | "negative" | "warning" | "transfer";

export function Badge({ tone = "neutral", className, children }: {
  tone?: BadgeTone;
  className?: string;
  children: React.ReactNode;
}) {
  return <span className={cx("ui-badge", `ui-badge--${tone}`, className)}>{children}</span>;
}
