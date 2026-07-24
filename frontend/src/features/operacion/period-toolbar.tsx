import type { Period, PeriodKpis, SyncStatus } from "@/shared/api/types";
import { periodSelectLabel } from "@/shared/lib/period-operation-guard";
import { Button } from "@/shared/ui/button";
import { Select } from "@/shared/ui/select";

type Props = {
  periods: Period[];
  selectedPeriod: Period | undefined;
  selectedPeriodKey: string;
  onPeriodChange: (key: string) => void;
  kpis?: PeriodKpis;
  runningLabel: string | null;
  syncStatus?: SyncStatus;
  onResync?: () => void;
  resyncPending?: boolean;
};

function SyncStatusBadge({ syncStatus }: { syncStatus: SyncStatus }) {
  if (syncStatus.status === "ok") return null;
  const isDegraded = syncStatus.status === "degraded";
  return (
    <p
      title={syncStatus.message}
      className={
        "w-full rounded-md border px-3 py-2 text-xs leading-snug " +
        (isDegraded
          ? "border-warning/30 bg-warning/10 text-warning"
          : "border-border bg-muted text-muted-foreground")
      }
    >
      {isDegraded ? "Excel y base de datos desalineados" : "Sync Excel/BD sin datos"}
      <span className="opacity-80"> — {syncStatus.message}</span>
    </p>
  );
}

export function PeriodToolbar({
  periods,
  selectedPeriod,
  selectedPeriodKey,
  onPeriodChange,
  kpis,
  runningLabel,
  syncStatus,
  onResync,
  resyncPending,
}: Props) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex min-w-[200px] flex-1 items-center gap-2 text-sm">
          <span className="shrink-0 text-xs font-medium text-muted-foreground">Mes</span>
          <Select
            value={selectedPeriod ? `${selectedPeriod.year}-${selectedPeriod.month_name}` : selectedPeriodKey}
            onChange={(e) => onPeriodChange(e.target.value)}
          >
            {periods.map((p) => (
              <option key={p.id} value={`${p.year}-${p.month_name}`}>
                {periodSelectLabel(p)}
              </option>
            ))}
          </Select>
        </label>

        {kpis?.solicitud_exists && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.8125rem] text-muted-foreground">
            <Metric label="Recibidos" value={kpis.recibidos} />
            <Metric label="Pendientes" value={kpis.no_recibidos} />
            <Metric label="XML" value={kpis.xml_files_in_month} />
          </div>
        )}

        {onResync && selectedPeriod && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="ml-auto shrink-0"
            disabled={resyncPending || Boolean(runningLabel)}
            onClick={onResync}
            title="Recalcula alineación Excel↔PostgreSQL"
          >
            {resyncPending ? "Sincronizando…" : "Re-sync"}
          </Button>
        )}
      </div>

      {runningLabel && (
        <p className="rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">
          Hay una tarea en curso — espera a que termine.
        </p>
      )}
      {syncStatus && <SyncStatusBadge syncStatus={syncStatus} />}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <span>
      {label}{" "}
      <strong className="font-semibold tabular-nums text-foreground">{value}</strong>
    </span>
  );
}
