import { useEffect, useMemo, useState } from "react";
import { FolderPlus } from "lucide-react";
import type { Period, PeriodKpis } from "@/shared/api/types";
import { useCreatePeriod, useMissingMonths } from "@/shared/api/queries";
import { periodSelectLabel } from "@/shared/lib/period-operation-guard";
import { Button } from "@/shared/ui/button";
import { Select } from "@/shared/ui/select";
import { mapApiErrorMessage, type ApiError } from "@/shared/api/client";
import { PeriodExportButton } from "./period-db-panel";

type Props = {
  periods: Period[];
  selectedPeriod: Period | undefined;
  selectedPeriodKey: string;
  onPeriodChange: (key: string) => void;
  onPeriodCreated?: (key: string) => void;
  kpis?: PeriodKpis;
  runningLabel: string | null;
  baseUrl: string;
  apiKey: string;
  onExportPeriod?: () => void;
  exportPending?: boolean;
};

export function PeriodToolbar({
  periods,
  selectedPeriod,
  selectedPeriodKey,
  onPeriodChange,
  onPeriodCreated,
  kpis,
  runningLabel,
  baseUrl,
  apiKey,
  onExportPeriod,
  exportPending,
}: Props) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const defaultYear = selectedPeriod?.year ?? new Date().getFullYear();
  const [year, setYear] = useState(defaultYear);
  const [monthName, setMonthName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const missing = useMissingMonths(baseUrl, apiKey, year, dialogOpen);
  const createPeriod = useCreatePeriod(baseUrl, apiKey);

  useEffect(() => {
    if (!dialogOpen) return;
    setYear(selectedPeriod?.year ?? new Date().getFullYear());
    setError(null);
  }, [dialogOpen, selectedPeriod?.year]);

  const missingMonths = missing.data?.missing ?? [];
  useEffect(() => {
    if (!dialogOpen) return;
    if (missingMonths.length && !missingMonths.some((m) => m.month_name === monthName)) {
      setMonthName(missingMonths[0].month_name);
    }
  }, [dialogOpen, missingMonths, monthName]);

  const yearOptions = useMemo(() => {
    const years = new Set<number>([defaultYear, new Date().getFullYear()]);
    for (const p of periods) years.add(p.year);
    years.add(defaultYear + 1);
    return Array.from(years).sort((a, b) => b - a);
  }, [periods, defaultYear]);

  async function handleCreate() {
    if (!monthName) return;
    setError(null);
    try {
      const res = await createPeriod.mutateAsync({ year, month_name: monthName });
      const key = `${res.period.year}-${res.period.month_name}`;
      onPeriodCreated?.(key);
      onPeriodChange(key);
      setDialogOpen(false);
    } catch (err) {
      setError(mapApiErrorMessage(err as ApiError) || "No se pudo crear el mes");
    }
  }

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

        <Button
          type="button"
          variant="outline"
          size="sm"
          className="shrink-0"
          onClick={() => setDialogOpen(true)}
          disabled={Boolean(runningLabel)}
        >
          <FolderPlus size={14} className="mr-1.5" />
          Nuevo mes
        </Button>

        {(kpis?.total_rows ?? 0) > 0 && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.8125rem] text-muted-foreground">
            <Metric label="Solicitudes" value={kpis?.total_rows ?? 0} />
            <Metric label="Recibidos" value={kpis?.recibidos ?? 0} />
            <Metric label="Pendientes" value={kpis?.no_recibidos ?? 0} />
            <Metric label="XML" value={kpis?.xml_files_in_month ?? 0} />
          </div>
        )}

        <PeriodExportButton
          year={selectedPeriod?.year}
          month={selectedPeriod?.month_name}
          onDownload={onExportPeriod}
          downloadPending={exportPending}
          disabled={Boolean(runningLabel) || (kpis?.total_rows ?? 0) === 0}
        />
      </div>

      {runningLabel && (
        <p className="rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">
          Hay una tarea en curso — espera a que termine.
        </p>
      )}

      {dialogOpen && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/45 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="new-month-title"
        >
          <div className="w-full max-w-md rounded-xl border border-border bg-card/95 p-5 shadow-elevated backdrop-blur-md">
            <h2 id="new-month-title" className="text-[1.0625rem] font-semibold tracking-tight">
              Crear mes de trabajo
            </h2>
            <p className="mt-2 text-sm leading-snug text-muted-foreground">
              Crea la carpeta del período (ej. 2026/Agosto). Luego sube el maestro y la base de
              docentes en el panel de preparación.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                <span className="mb-1 block text-xs font-medium text-muted-foreground">Año</span>
                <Select value={String(year)} onChange={(e) => setYear(Number(e.target.value))}>
                  {yearOptions.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="text-sm">
                <span className="mb-1 block text-xs font-medium text-muted-foreground">Mes</span>
                <Select
                  value={monthName}
                  onChange={(e) => setMonthName(e.target.value)}
                  disabled={missing.isLoading || missingMonths.length === 0}
                >
                  {missingMonths.length === 0 ? (
                    <option value="">Sin meses pendientes</option>
                  ) : (
                    missingMonths.map((m) => (
                      <option key={m.month_num} value={m.month_name}>
                        {m.month_name}
                      </option>
                    ))
                  )}
                </Select>
              </label>
            </div>
            {error && <p className="mt-3 text-sm text-danger">{error}</p>}
            {missing.isError && (
              <p className="mt-3 text-sm text-danger">No se pudo listar meses faltantes.</p>
            )}
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                Cancelar
              </Button>
              <Button
                type="button"
                onClick={() => void handleCreate()}
                disabled={!monthName || createPeriod.isPending || missingMonths.length === 0}
              >
                {createPeriod.isPending ? "Creando…" : "Crear mes"}
              </Button>
            </div>
          </div>
        </div>
      )}
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
