import type { Period } from "@/shared/api/types";
import { isPeriodClosed } from "@/shared/lib/period-operation-guard";

export function periodKey(year: number, month: string) {
  return `${year}-${month}`;
}

function sortPeriodsNewestFirst(a: Period, b: Period) {
  if (a.year !== b.year) return b.year - a.year;
  return b.month_num - a.month_num;
}

/**
 * Período por defecto en Operación: el mes abierto más reciente
 * (en curso). Si no hay abiertos, el más reciente de la lista.
 */
export function defaultOperationPeriodKey(periods: Period[]): string | null {
  if (!periods.length) return null;

  const open = periods.filter((p) => !isPeriodClosed(p));
  const pool = open.length > 0 ? open : [...periods];
  pool.sort(sortPeriodsNewestFirst);
  const pick = pool[0];
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
