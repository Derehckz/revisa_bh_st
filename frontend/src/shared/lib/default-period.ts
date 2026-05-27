import type { Period } from "@/shared/api/types";

/** Período de referencia: mes cerrado (Pagos, correos, carpetas). No usar Mayo u otros en curso aquí. */
export const DEFAULT_OPERATION_PERIOD = {
  year: 2026,
  month: "Abril",
} as const;

export function periodKey(year: number, month: string) {
  return `${year}-${month}`;
}

export const DEFAULT_OPERATION_PERIOD_KEY = periodKey(
  DEFAULT_OPERATION_PERIOD.year,
  DEFAULT_OPERATION_PERIOD.month
);

export function defaultOperationPeriodKey(periods: Period[]): string | null {
  if (!periods.length) return DEFAULT_OPERATION_PERIOD_KEY;
  const preferred = periods.find(
    (p) =>
      p.year === DEFAULT_OPERATION_PERIOD.year &&
      p.month_name.localeCompare(DEFAULT_OPERATION_PERIOD.month, "es", { sensitivity: "base" }) === 0
  );
  return preferred ? periodKey(preferred.year, preferred.month_name) : DEFAULT_OPERATION_PERIOD_KEY;
}

export function resolveOperationPeriod(periods: Period[], selectedPeriodKey: string): Period | undefined {
  const key = selectedPeriodKey || defaultOperationPeriodKey(periods);
  return periods.find((p) => periodKey(p.year, p.month_name) === key);
}
