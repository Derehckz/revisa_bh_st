import type { Period, PeriodKpis } from "@/shared/api/types";
import { Select } from "@/shared/ui/select";

type Props = {
  periods: Period[];
  selectedPeriod: Period | undefined;
  selectedPeriodKey: string;
  onPeriodChange: (key: string) => void;
  kpis?: PeriodKpis;
  runningLabel: string | null;
};

export function PeriodToolbar({
  periods,
  selectedPeriod,
  selectedPeriodKey,
  onPeriodChange,
  kpis,
  runningLabel,
}: Props) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      <div className="flex flex-wrap items-end gap-4">
        <label className="min-w-[180px] flex-1 space-y-1">
          <span className="text-xs font-medium text-muted-foreground">Período de trabajo</span>
          <Select
            value={selectedPeriod ? `${selectedPeriod.year}-${selectedPeriod.month_name}` : selectedPeriodKey}
            onChange={(e) => onPeriodChange(e.target.value)}
          >
            {periods.map((p) => (
              <option key={p.id} value={`${p.year}-${p.month_name}`}>
                {p.month_name} {p.year}
              </option>
            ))}
          </Select>
        </label>
        {kpis && (
          <div className="flex flex-wrap gap-3 text-sm">
            <KpiPill label="Recibidos" value={kpis.solicitud_exists ? String(kpis.recibidos) : "—"} />
            <KpiPill label="Pendientes" value={kpis.solicitud_exists ? String(kpis.no_recibidos) : "—"} />
            <KpiPill label="XML" value={String(kpis.xml_files_in_month)} />
          </div>
        )}
      </div>
      {runningLabel && (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900 border border-amber-200">
          Hay un job en ejecución: {runningLabel}. Espera a que termine antes de lanzar otro.
        </p>
      )}
    </div>
  );
}

function KpiPill({ label, value }: { label: string; value: string }) {
  return (
    <span className="rounded-md bg-muted px-2 py-1">
      <span className="text-muted-foreground">{label}: </span>
      <strong>{value}</strong>
    </span>
  );
}
