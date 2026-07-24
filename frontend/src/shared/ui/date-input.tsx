import { useRef } from "react";
import { Calendar } from "lucide-react";
import { clToIso, isoToCl } from "@/shared/lib/period-dates";
import { cn } from "@/shared/lib/utils";
import { Input } from "@/shared/ui/input";

type Props = {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  /** Límite del calendario (primer día del mes del período). */
  minIso?: string;
  /** Límite del calendario (último día del mes del período). */
  maxIso?: string;
  placeholder?: string;
  className?: string;
};

export function DateInput({
  value,
  onChange,
  disabled,
  minIso,
  maxIso,
  placeholder = "dd/mm/aaaa",
  className,
}: Props) {
  const pickerRef = useRef<HTMLInputElement>(null);
  const isoValue = clToIso(value);

  function openPicker() {
    if (disabled) return;
    const el = pickerRef.current;
    if (!el) return;
    el.showPicker?.();
    el.focus();
  }

  return (
    <div className={cn("relative", className)}>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className="pr-9"
        inputMode="numeric"
        aria-label="Fecha en formato dd/mm/aaaa"
      />
      <button
        type="button"
        disabled={disabled}
        title="Abrir calendario"
        className={cn(
          "absolute right-1 top-1/2 -translate-y-1/2 rounded p-1.5 text-muted-foreground",
          "hover:bg-muted hover:text-foreground",
          "disabled:pointer-events-none disabled:opacity-50"
        )}
        onClick={openPicker}
      >
        <Calendar size={16} aria-hidden />
      </button>
      <input
        ref={pickerRef}
        type="date"
        tabIndex={-1}
        aria-hidden
        value={isoValue}
        min={minIso}
        max={maxIso}
        disabled={disabled}
        className="pointer-events-none absolute h-0 w-0 opacity-0"
        onChange={(e) => {
          const next = e.target.value;
          if (!next) return;
          onChange(isoToCl(next));
        }}
      />
    </div>
  );
}
