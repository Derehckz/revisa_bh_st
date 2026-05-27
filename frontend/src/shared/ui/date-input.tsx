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
  const isoValue = clToIso(value);

  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className="min-w-[8.5rem] flex-1"
        inputMode="numeric"
        aria-label="Fecha en formato dd/mm/aaaa"
      />
      <div className="relative shrink-0">
        <Calendar
          size={16}
          className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <input
          type="date"
          value={isoValue}
          min={minIso}
          max={maxIso}
          disabled={disabled}
          title="Elegir fecha en calendario"
          className={cn(
            "h-9 rounded-md border border-border bg-card pl-8 pr-2 text-sm outline-none",
            "transition focus-visible:ring-2 focus-visible:ring-ring",
            "disabled:cursor-not-allowed disabled:opacity-50",
            "[color-scheme:light]"
          )}
          onChange={(e) => {
            const next = e.target.value;
            if (!next) return;
            onChange(isoToCl(next));
          }}
        />
      </div>
    </div>
  );
}
