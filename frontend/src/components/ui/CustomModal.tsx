import React, { useCallback, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

interface CustomModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  accent?: "amber" | "cyan" | "mint" | "coral" | "ember" | "sage" | "gold";
  children: React.ReactNode;
  maxWidth?: "sm" | "md" | "lg" | "xl";
  mobileSheet?: boolean;
}

export function CustomModal({
  isOpen,
  onClose,
  title,
  subtitle,
  icon,
  children,
  maxWidth = "md",
  mobileSheet = false,
}: CustomModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const backdropRef = useRef<HTMLDivElement>(null);
  const dismissAnimations = useRef<Animation[]>([]);
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);

  const dismiss = useCallback(() => {
    if (dismissAnimations.current.length) return;
    const panel = dialogRef.current;
    const backdrop = backdropRef.current;
    if (!panel?.animate || !backdrop?.animate || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      onCloseRef.current();
      return;
    }
    const sheet = panel.classList.contains("fold-sheet-panel") && window.matchMedia("(max-width: 767px)").matches;
    const duration = 150;
    const slide = panel.animate(
      [{ transform: "none" }, { transform: `translateY(${sheet ? 22 : 7}px)` }],
      { duration, easing: "ease-in" },
    );
    const fade = backdrop.animate([{ opacity: 1 }, { opacity: 0 }], { duration, easing: "ease-in" });
    dismissAnimations.current = [slide, fade];
    fade.onfinish = () => {
      dismissAnimations.current = [];
      onCloseRef.current();
    };
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !e.defaultPrevented) {
        dismiss();
      }
      if (e.key === "Tab" && dialogRef.current) {
        const focusRoot = dialogRef.current.closest('[role="dialog"]') || dialogRef.current;
        const controls = Array.from(focusRoot.querySelectorAll<HTMLElement>(
          'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]'
        )).filter((element) => element.getClientRects().length > 0);
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
      }
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);
    dialogRef.current?.querySelector<HTMLElement>("button")?.focus();
    return () => {
      for (const animation of dismissAnimations.current) animation.cancel();
      dismissAnimations.current = [];
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
      previousFocus?.focus();
    };
  }, [dismiss, isOpen]);

  if (!isOpen || typeof document === "undefined") return null;

  const maxWidthStyles = {
    sm: "max-w-sm",
    md: "max-w-lg",
    lg: "max-w-xl",
    xl: "max-w-2xl",
  };

  return createPortal(
    <div
      ref={backdropRef}
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className={`luma-dialog-backdrop fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-3 sm:p-5 overflow-y-auto ${mobileSheet ? "fold-sheet-backdrop" : ""}`}
      onClick={(e) => {
        if (e.target === e.currentTarget) dismiss();
      }}
    >
      <div
        ref={dialogRef}
        className={`luma-dialog-panel relative rounded-3xl w-full shadow-luma-glass flex flex-col max-h-[90dvh] my-auto ${maxWidthStyles[maxWidth]} ${mobileSheet ? "fold-sheet-panel" : ""}`}
      >
        {/* Close Button — 44x44 touch target */}
        <button
          type="button"
          onClick={dismiss}
          aria-label="Tutup dialog"
          className="absolute top-3 sm:top-4 right-3 sm:right-4 w-11 h-11 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-xl text-luma-smoke hover:text-luma-ivory hover:bg-luma-coal transition-colors duration-150 z-20 touch-manipulation cursor-pointer"
        >
          <X className="w-5 h-5" aria-hidden="true" />
        </button>

        {/* Modal Header (Fixed at top of modal) */}
        <div className="p-5 sm:p-6 pb-4 border-b border-luma-smokeline shrink-0">
          <div className="flex items-start gap-3.5 pr-12 sm:pr-14">
            {icon && (
              <div
                className="ai7-dialog-icon p-2.5 rounded-xl shrink-0"
              >
                {icon}
              </div>
            )}
            <div>
              <h3 className="ai7-type-card text-luma-ivory tracking-tight">
                {title}
              </h3>
              {subtitle && (
                <p className="text-xs text-luma-smoke mt-1 leading-relaxed">
                  {subtitle}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Modal Scrollable Body — Luma form wells live here */}
        <div className="p-5 sm:p-6 overflow-y-auto luma-form-scope">
          {children}
        </div>
      </div>
    </div>,
    document.querySelector(".luma-app") || document.body
  );
}
