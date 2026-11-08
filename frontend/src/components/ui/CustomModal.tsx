import React, { useEffect, useRef } from "react";
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
}

export function CustomModal({
  isOpen,
  onClose,
  title,
  subtitle,
  icon,
  children,
  maxWidth = "md",
}: CustomModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);
  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onCloseRef.current();
      }
      if (e.key === "Tab" && isOpen && dialogRef.current) {
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
    if (isOpen) {
      document.body.style.overflow = "hidden";
      window.addEventListener("keydown", handleKeyDown);
      dialogRef.current?.querySelector<HTMLElement>("button")?.focus();
    }
    return () => {
      document.body.style.overflow = "unset";
      window.removeEventListener("keydown", handleKeyDown);
      if (isOpen) previousFocus?.focus();
    };
  }, [isOpen]);

  if (!isOpen || typeof document === "undefined") return null;

  const maxWidthStyles = {
    sm: "max-w-sm",
    md: "max-w-lg",
    lg: "max-w-xl",
    xl: "max-w-2xl",
  };

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-3 sm:p-5 overflow-y-auto"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className={`luma-dialog-panel relative rounded-3xl w-full shadow-luma-glass flex flex-col max-h-[90dvh] my-auto ${maxWidthStyles[maxWidth]}`}
      >
        {/* Close Button — 44x44 touch target */}
        <button
          type="button"
          onClick={onClose}
          aria-label="Tutup dialog"
          className="absolute top-3 sm:top-4 right-3 sm:right-4 w-11 h-11 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-full text-luma-smoke hover:text-luma-ivory hover:bg-white/[0.08] active:bg-white/[0.14] active:scale-95 border border-transparent hover:border-white/[0.1] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-luma-ember/70 transition-all duration-150 z-20 touch-manipulation cursor-pointer"
        >
          <X className="w-5 h-5" aria-hidden="true" />
        </button>

        {/* Modal Header (Fixed at top of modal) */}
        <div className="p-5 sm:p-6 pb-4 border-b border-luma-smokeline shrink-0">
          <div className="flex items-start gap-3.5 pr-12 sm:pr-14">
            {icon && (
              <div
                className="ai7-dialog-icon p-2.5 rounded-xl border shrink-0"
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
