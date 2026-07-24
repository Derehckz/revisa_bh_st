import { usePeriodOperationGuard } from "./period-operation-context";

export function PeriodOperationBanner() {
  const { period, assessment } = usePeriodOperationGuard();
  if (!period || !assessment.needsConfirmation) return null;

  return (
    <div
      className="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-foreground"
      role="status"
    >
      <p className="font-semibold tracking-tight">
        Período restringido: {period.month_name} {period.year}
        {assessment.isClosed ? " · cerrado" : null}
        {assessment.isPast ? " · mes pasado" : null}
      </p>
      <p className="mt-1 text-[0.8125rem] leading-snug text-muted-foreground">
        Las ejecuciones pedirán confirmación explícita. Para el flujo habitual, elige el mes en curso abierto.
      </p>
    </div>
  );
}
