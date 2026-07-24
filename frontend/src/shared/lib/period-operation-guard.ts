import type { Period } from "@/shared/api/types";

export type PeriodOperationAssessment = {
  needsConfirmation: boolean;
  isPast: boolean;
  isClosed: boolean;
  isFuture: boolean;
  reasonLabel: string;
  confirmMessage: string;
};

function periodIndex(year: number, monthNum: number): number {
  return year * 12 + monthNum;
}

function currentPeriodIndex(now: Date): number {
  return periodIndex(now.getFullYear(), now.getMonth() + 1);
}

export function isPeriodClosed(period: Period): boolean {
  const s = (period.status ?? "").trim().toLowerCase();
  return s.includes("cerrad");
}

export function isPeriodPast(period: Period, now: Date = new Date()): boolean {
  return periodIndex(period.year, period.month_num) < currentPeriodIndex(now);
}

export function isPeriodFuture(period: Period, now: Date = new Date()): boolean {
  return periodIndex(period.year, period.month_num) > currentPeriodIndex(now);
}

export function assessPeriodForOperations(
  period: Period | undefined,
  now: Date = new Date()
): PeriodOperationAssessment {
  const none: PeriodOperationAssessment = {
    needsConfirmation: false,
    isPast: false,
    isClosed: false,
    isFuture: false,
    reasonLabel: "",
    confirmMessage: "",
  };
  if (!period) return none;

  const isClosed = isPeriodClosed(period);
  const isPast = isPeriodPast(period, now);
  const isFuture = isPeriodFuture(period, now);
  const needsConfirmation = isClosed || isPast;

  let reasonLabel = "";
  if (isClosed && isPast) {
    reasonLabel = "cerrado y es un mes pasado";
  } else if (isClosed) {
    reasonLabel = "marcado como cerrado";
  } else if (isPast) {
    reasonLabel = "un mes pasado respecto al calendario actual";
  }

  const label = `${period.month_name} ${period.year}`;
  const confirmMessage = needsConfirmation
    ? `El período ${label} está ${reasonLabel}.\n\n¿Confirmas que quieres ejecutar operaciones sobre ese mes? Los cambios pueden afectar datos históricos o ya cerrados.`
    : "";

  return {
    needsConfirmation,
    isPast,
    isClosed,
    isFuture,
    reasonLabel,
    confirmMessage,
  };
}

export function periodSelectLabel(period: Period, now: Date = new Date()): string {
  const base = `${period.month_name} ${period.year}`;
  if (isPeriodClosed(period)) return `${base} (cerrado)`;
  if (isPeriodPast(period, now)) return `${base} (pasado)`;
  if (isPeriodFuture(period, now)) return `${base} (futuro)`;
  return base;
}
