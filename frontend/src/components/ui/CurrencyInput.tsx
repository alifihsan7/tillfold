import React from "react";

interface CurrencyInputProps {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  accent?: "amber" | "cyan" | "mint" | "coral";
  quickAmounts?: number[];
  className?: string;
  autoFocus?: boolean;
}

export function CurrencyInput({
  id,
  value,
  onChange,
  placeholder = "0",
  required = false,
  disabled = false,
  quickAmounts,
  className = "",
  autoFocus = false,
}: CurrencyInputProps) {
  // Format raw digits to Indonesian thousand separated string (e.g., "150.000")
  const formatDisplay = (raw: string) => {
    if (!raw) return "";
    const clean = raw.replace(/[^\d]/g, "");
    if (!clean) return "";
    return parseInt(clean, 10).toLocaleString("id-ID");
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const rawVal = e.target.value.replace(/[^\d]/g, "");
    onChange(rawVal);
  };

  return (
    <div className={`space-y-2 ${className}`}>
      <div
        className="ai7-currency-field relative flex items-stretch min-h-[44px] overflow-hidden border bg-obsidian-panel"
      >
        {/* Rp Prefix Badge */}
        <div
          className="ai7-currency-prefix px-3.5 sm:px-4 py-2.5 flex items-center justify-center text-sm border-r select-none"
        >
          Rp
        </div>

        {/* Input Element */}
        <input
          id={id}
          type="text"
          inputMode="numeric"
          autoFocus={autoFocus}
          required={required}
          disabled={disabled}
          value={formatDisplay(value)}
          onChange={handleInputChange}
          placeholder={placeholder}
          className="w-full bg-transparent px-3.5 py-2.5 text-slateText-primary font-sans font-semibold text-base sm:text-lg focus:outline-none placeholder:text-zinc-400 placeholder:font-normal"
        />
      </div>

      {/* Quick Amount Suggestion Pills */}
      {quickAmounts && quickAmounts.length > 0 && (
        <div className={`grid gap-2 pt-1 ${quickAmounts.length === 4 ? "grid-cols-4" : quickAmounts.length === 3 ? "grid-cols-3" : "grid-cols-2"}`}>
          {quickAmounts.map((amt) => {
            const label =
              amt >= 1000000
                ? `${amt / 1000000}jt`
                : `${amt / 1000}k`;
            return (
              <button
                key={amt}
                type="button"
                onClick={() => onChange(amt.toString())}
                className="ai7-amount-preset min-h-[44px] py-2 px-2.5 rounded-xl border text-xs sm:text-sm font-medium text-center flex items-center justify-center cursor-pointer"
              >
                +{label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
