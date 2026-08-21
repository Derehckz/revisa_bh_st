import type { Period } from "@/shared/api/types";

export function periodKey(year: number, month: string) {
  return `${year}-${month}`;
}

export function sortPeriodsNewestFirst(a: Period, b: Period) {
  if (a.year !== b.year) return b.year - a.year;
  return b.month_num - a.month_num;
}

/** Siempre el mes más reciente (cronológico), abierto o cerrado. */
export function defaultOperationPeriodKey(periods: Period[]): string | null {
  if (!periods.length) return null;
  const sorted = [...periods].sort(sortPeriodsNewestFirst);
  const pick = sorted[0];
  return periodKey(pick.year, pick.month_name);
}

export function resolveOperationPeriod(
  periods: Period[],
  selectedPeriodKey: string
): Period | undefined {
  if (!periods.length) return undefined;

  if (selectedPeriodKey) {
    const found = periods.find((p) => periodKey(p.year, p.month_name) === selectedPeriodKey);
    if (found) return found;
  }

  const fallbackKey = defaultOperationPeriodKey(periods);
  if (!fallbackKey) return periods[0];
  return periods.find((p) => periodKey(p.year, p.month_name) === fallbackKey) ?? periods[0];
}

export function yearsFromPeriods(periods: Period[]): number[] {
  return [...new Set(periods.map((p) => p.year))].sort((a, b) => b - a);
}

export function monthsForYear(periods: Period[], year: number): Period[] {
  return periods
    .filter((p) => p.year === year)
    .sort((a, b) => b.month_num - a.month_num);
}
