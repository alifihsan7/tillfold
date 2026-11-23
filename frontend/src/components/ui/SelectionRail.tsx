"use client";

import React, { useEffect, useRef } from "react";

/** A moving background; the buttons, focus and accessible selection stay in place. */
export function SelectionRail({ selection, children, className = "", ...props }: React.HTMLAttributes<HTMLDivElement> & { selection: string }) {
  const group = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = group.current;
    if (!element) return;
    const update = () => {
      const selected = element.querySelector<HTMLButtonElement>('button[aria-selected="true"], button[aria-pressed="true"]');
      if (!selected || !selected.offsetWidth) {
        delete element.dataset.measured;
        return;
      }
      element.style.setProperty("--choice-x", `${selected.offsetLeft}px`);
      element.style.setProperty("--choice-y", `${selected.offsetTop}px`);
      element.style.setProperty("--choice-width", `${selected.offsetWidth}px`);
      element.style.setProperty("--choice-height", `${selected.offsetHeight}px`);
      element.dataset.tone = selected.dataset.tone || "neutral";
      element.dataset.measured = "true";
    };
    update();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    observer?.observe(element);
    element.querySelectorAll("button").forEach((button) => observer?.observe(button));
    // Font loading can change label widths without a window resize.
    let mounted = true;
    void document.fonts?.ready.then(() => { if (mounted) update(); });
    return () => { mounted = false; observer?.disconnect(); };
  }, [selection, children]);

  return (
    <div ref={group} className={`fold-choice-rail ${className}`} {...props}>
      <span className="fold-choice-indicator" aria-hidden="true" />
      {children}
    </div>
  );
}
