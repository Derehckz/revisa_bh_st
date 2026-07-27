import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useAppConfig } from "@/app/app-config";
import { usePeriods } from "@/shared/api/queries";
import {
  defaultOperationPeriodKey,
  resolveOperationPeriod,
} from "@/shared/lib/default-period";
import { Select } from "@/shared/ui/select";
import { ExcelAvancePanel } from "@/features/operacion/excel-avance-panel";

export function AvancePage() {
  const { baseUrl, apiKey } = useAppConfig();
  const periods = usePeriods(baseUrl, apiKey);
  const [selectedKey, setSelectedKey] = useState("");

  useEffect(() => {
    if (!periods.data?.length) return;
    setSelectedKey((prev) => prev || defaultOperationPeriodKey(periods.data ?? []) || "");
  }, [periods.data]);

  const selectedPeriod = useMemo(
    () => resolveOperationPeriod(periods.data ?? [], selectedKey),
    [periods.data, selectedKey]
  );

  return (
    <div className="flex min-h-[calc(100vh-3.5rem-1.5rem)] flex-col gap-3">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <div className="min-w-0 flex-1">
          <h1 className="text-lg font-semibold tracking-tight text-foreground md:text-xl">
            Avance Excel
          </h1>
          <p className="text-xs text-muted-foreground md:text-[0.8125rem]">
            Solicitud.xlsx · recepción, correos, XML y detalle por fila
          </p>
        </div>
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="shrink-0 font-medium">Período</span>
          <Select
            value={selectedKey}
            onChange={(e) => setSelectedKey(e.target.value)}
            className="min-w-[180px]"
          >
            {(periods.data ?? []).map((p) => (
              <option key={`${p.year}-${p.month_name}`} value={`${p.year}-${p.month_name}`}>
                {p.month_name} {p.year}
              </option>
            ))}
          </Select>
        </label>
        <Link
          to="/operacion"
          className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border bg-card px-3 text-xs font-medium text-foreground hover:bg-muted/80"
        >
          <ArrowLeft className="h-4 w-4" />
          Operación
        </Link>
      </header>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border/80 bg-card shadow-xs">
        <ExcelAvancePanel
          baseUrl={baseUrl}
          apiKey={apiKey}
          year={selectedPeriod?.year}
          month={selectedPeriod?.month_name}
          layout="full"
        />
      </div>
    </div>
  );
}
