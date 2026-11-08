import React, { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { ChevronDown, Check } from "lucide-react";

export interface SelectOption {
  value: string;
  label: string;
  color?: string;
  description?: string;
}

interface CustomSelectProps {
  label?: string;
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  accent?: "amber" | "mint" | "cyan";
}

export function CustomSelect({
  label,
  value,
  onChange,
  options,
  placeholder = "Pilih opsi...",
  disabled = false,
  className = "",
}: CustomSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const [coords, setCoords] = useState<{
    top?: number;
    bottom?: number;
    left: number;
    width: number;
    maxHeight: number;
    openUpward: boolean;
  }>({
    left: 0,
    width: 0,
    maxHeight: 240,
    openUpward: false,
  });

  const selectedOption = options.find((opt) => opt.value === value);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    const selected = dropdownRef.current?.querySelector<HTMLButtonElement>('button[data-selected="true"]');
    (selected || dropdownRef.current?.querySelector<HTMLButtonElement>("button"))?.focus();
  }, [isOpen]);

  const updatePosition = () => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const dropdownEstimatedHeight = 220;
    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;

    const openUpward = spaceBelow < dropdownEstimatedHeight && spaceAbove > spaceBelow;

    if (openUpward) {
      setCoords({
        bottom: window.innerHeight - rect.top + 6,
        left: rect.left,
        width: rect.width,
        maxHeight: Math.min(260, Math.max(140, spaceAbove - 20)),
        openUpward: true,
      });
    } else {
      setCoords({
        top: rect.bottom + 6,
        left: rect.left,
        width: rect.width,
        maxHeight: Math.min(260, Math.max(140, spaceBelow - 20)),
        openUpward: false,
      });
    }
  };

  useEffect(() => {
    if (!isOpen) return;
    updatePosition();

    function handleScrollOrResize() {
      updatePosition();
    }

    window.addEventListener("resize", handleScrollOrResize);
    window.addEventListener("scroll", handleScrollOrResize, true);

    return () => {
      window.removeEventListener("resize", handleScrollOrResize);
      window.removeEventListener("scroll", handleScrollOrResize, true);
    };
  }, [isOpen]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node;
      if (
        triggerRef.current &&
        !triggerRef.current.contains(target) &&
        dropdownRef.current &&
        !dropdownRef.current.contains(target)
      ) {
        setIsOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && isOpen) {
        setIsOpen(false);
        triggerRef.current?.focus();
      }
    }

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const handleSelect = (optValue: string) => {
    onChange(optValue);
    setIsOpen(false);
    triggerRef.current?.focus();
  };

  const handleToggle = () => {
    if (disabled) return;
    if (!isOpen) {
      updatePosition();
    }
    setIsOpen(!isOpen);
  };

  return (
    <div className={`relative ${className}`}>
      {/* Trigger Button */}
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        onClick={handleToggle}
        aria-expanded={isOpen}
        aria-label={label ? `${label}: ${selectedOption?.label || placeholder}` : undefined}
        className={`ai7-select-trigger w-full border px-3.5 py-2.5 min-h-[44px] text-left text-sm flex items-center justify-between gap-2 select-none cursor-pointer ${
          disabled
            ? "opacity-50 cursor-not-allowed border-luma-smokeline"
            : isOpen
            ? "border-luma-ember text-slateText-primary"
            : "border-luma-smokeline hover:border-white/[0.18] text-slateText-primary"
        }`}
      >
        <span className="min-w-0 flex-1 font-medium flex items-center gap-2 pr-1 overflow-hidden">
          {selectedOption?.color && (
            <span className={`w-2 h-2 rounded-full shrink-0 ${selectedOption.color}`} />
          )}
          <span className={`truncate block flex-1 ${selectedOption ? "text-slateText-primary" : "text-zinc-400 font-normal"}`}>
            {selectedOption ? selectedOption.label : placeholder}
          </span>
        </span>
        <ChevronDown
          className={`w-4 h-4 text-slateText-muted shrink-0 ${isOpen ? "rotate-180" : ""}`}
        />
      </button>

      {/* Floating Custom Dropdown Menu via Portal to break out of modal overflow clipping */}
      {mounted &&
        isOpen &&
        createPortal(
          <div
            ref={dropdownRef}
            onKeyDown={(event) => {
              if (event.key === "Tab") {
                event.preventDefault();
                event.stopPropagation();
                const trigger = triggerRef.current;
                const scope = trigger?.closest('[role="dialog"]') || document.body;
                const controls = Array.from(scope.querySelectorAll<HTMLElement>(
                  'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]'
                )).filter((element) => element.tabIndex >= 0 && element.getClientRects().length > 0 && !dropdownRef.current?.contains(element));
                const index = trigger ? controls.indexOf(trigger) : -1;
                const next = index + (event.shiftKey ? -1 : 1);
                setIsOpen(false);
                (controls[(next + controls.length) % controls.length] || trigger)?.focus();
                return;
              }
              if (event.key === "Escape") {
                event.preventDefault();
                event.stopPropagation();
                setIsOpen(false);
                triggerRef.current?.focus();
                return;
              }
              if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
              event.preventDefault();
              const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button"));
              const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
              const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1
                : (index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length;
              buttons[next]?.focus();
            }}
            style={{
              position: "fixed",
              top: coords.openUpward ? undefined : coords.top,
              bottom: coords.openUpward ? coords.bottom : undefined,
              left: coords.left,
              width: coords.width,
              maxHeight: coords.maxHeight,
              zIndex: 99999,
            }}
            className="ai7-select-menu border rounded-xl py-1.5 overflow-y-auto scrollbar-thin"
          >
            {options.map((opt) => {
              const isSelected = opt.value === value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  data-selected={isSelected}
                  onClick={() => handleSelect(opt.value)}
                  className={`w-full min-h-[44px] px-3.5 py-2.5 text-left text-xs sm:text-sm flex items-center justify-between gap-2 transition-colors select-none cursor-pointer ${
                    isSelected
                      ? "bg-amberGold/10 text-amberGold font-semibold"
                      : "text-slateText-primary hover:bg-obsidian-hover hover:text-slateText-primary"
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    {opt.color && (
                      <span className={`w-2 h-2 rounded-full shrink-0 ${opt.color}`} />
                    )}
                    <div className="truncate">
                      <div>{opt.label}</div>
                      {opt.description && (
                        <div className="text-xs text-slateText-muted font-normal">
                          {opt.description}
                        </div>
                      )}
                    </div>
                  </div>
                  {isSelected && <Check className="w-4 h-4 text-luma-transfer shrink-0" />}
                </button>
              );
            })}
          </div>,
          document.body
        )}
    </div>
  );
}
