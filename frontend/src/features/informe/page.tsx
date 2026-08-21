import { useEffect, useMemo, useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { useAppConfig } from "@/app/app-config";
import { useFinalReport, usePagosReport, usePeriods } from "@/shared/api/queries";
import {
  defaultOperationPeriodKey,
  resolveOperationPeriod,
} from "@/shared/lib/default-period";
import { cn, toCurrency } from "@/shared/lib/utils";
import { EmptyState } from "@/shared/ui/empty-state";
import { ErrorState } from "@/shared/ui/error-state";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import { Button } from "@/shared/ui/button";
import { TD, TH, Table, TableWrapper } from "@/shared/ui/table";
import { PagosReportPanel } from "./pagos-report-panel";

function formatGeneratedAt(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("es-CL", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function sourceBadge(source?: string | null, frozen?: boolean): string {
  if (frozen) return "Congelado en PostgreSQL";
  if (source === "postgresql" || source === "db_snapshot") return "Fuente: PostgreSQL";
  if (source === "excel" || source === "excel_pagos_sheet") return "Fuente: Excel";
  if (source) return `Fuente: ${source}`;
  return "Fuente: —";
}

type TabId = "final" | "pagos";

export function InformePage() {
  const { baseUrl, apiKey } = useAppConfig();
  const periods = usePeriods(baseUrl, apiKey);
  const [selectedKey, setSelectedKey] = useState("");
  const [tab, setTab] = useState<TabId>("final");
  const [downloadPending, setDownloadPending] = useState(false);

  useEffect(() => {
    if (!periods.data?.length) return;
    const exists = periods.data.some((p) => `${p.year}-${p.month_name}` === selectedKey);
    if (!selectedKey || !exists) {
      setSelectedKey(defaultOperationPeriodKey(periods.data) || "");
    }
  }, [periods.data, selectedKey]);

  const selectedPeriod = useMemo(
    () => resolveOperationPeriod(periods.data ?? [], selectedKey),
    [periods.data, selectedKey]
  );

  const report = useFinalReport(baseUrl, apiKey, selectedPeriod?.year, selectedPeriod?.month_name);
  const pagos = usePagosReport(baseUrl, apiKey, selectedPeriod?.year, selectedPeriod?.month_name);

  async function handleDownload() {
    if (!selectedPeriod || !apiKey) return;
    setDownloadPending(true);
    try {
      const url = `${baseUrl}/operations/period/file?year=${selectedPeriod.year}&month=${encodeURIComponent(selectedPeriod.month_name)}&filename=Solicitud.xlsx`;
      const response = await fetch(url, { headers: { "x-api-key": apiKey } });
      if (!response.ok) throw new Error("No se pudo descargar el archivo");
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = `Solicitud_${selectedPeriod.year}_${selectedPeriod.month_name}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(blobUrl);
    } finally {
      setDownloadPending(false);
    }
  }

  const rows = report.data?.rows ?? [];

  return (
    <div className="space-y-5">
      <PageHeader
        title="Informes del mes"
        description="Informe final (paso 6) e informe de pagos (paso 7), leídos desde PostgreSQL cuando hay snapshot."
      />

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          <span className="text-xs font-medium text-muted-foreground">Período</span>
          <Select
            value={selectedKey}
            onChange={(e) => setSelectedKey(e.target.value)}
            className="min-w-[180px]"
          >
            {(periods.data ?? []).map((p) => (
              <option key={`${p.year}-${p.month_name}`} value={`${p.year}-${p.month_name}`}>
                {p.month_name} {p.year}
                {p.status === "cerrado" ? " (cerrado)" : ""}
              </option>
            ))}
          </Select>
        </label>

        <div className="inline-flex rounded-md border border-border p-0.5">
          <button
            type="button"
            className={cn(
              "rounded px-3 py-1.5 text-sm",
              tab === "final" ? "bg-muted font-medium text-foreground" : "text-muted-foreground"
            )}
            onClick={() => setTab("final")}
          >
            Informe final
          </button>
          <button
            type="button"
            className={cn(
              "rounded px-3 py-1.5 text-sm",
              tab === "pagos" ? "bg-muted font-medium text-foreground" : "text-muted-foreground"
            )}
            onClick={() => setTab("pagos")}
          >
            Informe de pagos
          </button>
        </div>

        {tab === "final" && report.data?.exists ? (
          <Button type="button" variant="outline" size="sm" disabled={downloadPending} onClick={() => void handleDownload()}>
            {downloadPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Download className="mr-2 h-4 w-4" />
            )}
            Descargar Excel
          </Button>
        ) : null}
      </div>

      {tab === "final" ? (
        report.isLoading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Cargando informe…
          </p>
        ) : report.isError ? (
          <ErrorState title="No se pudo cargar el informe" onRetry={() => void report.refetch()} />
        ) : !report.data?.exists ? (
          <EmptyState
            title="Sin informe generado"
            description={report.data?.read_error || "Ejecuta el paso 6 o sincroniza el mes a BD."}
          />
        ) : (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <StatCard
                label={report.data.frozen ? "Congelado" : "Generado"}
                value={
                  report.data.frozen
                    ? formatGeneratedAt(report.data.frozen_at || report.data.generated_at)
                    : formatGeneratedAt(report.data.generated_at)
                }
              />
              <StatCard label="Boletas incluidas" value={String(report.data.total_rows)} />
              <StatCard label="Monto total" value={toCurrency(report.data.total_monto)} />
            </div>

            <p className="text-xs text-muted-foreground">
              {sourceBadge(report.data.source || report.data.generated_at_source, report.data.frozen)}.{" "}
              {report.data.frozen
                ? `Informe congelado al cerrar${report.data.frozen_by ? ` (por ${report.data.frozen_by})` : ""}.`
                : `Hoja «${report.data.sheet_name}» · boletas válidas (recibidas, XML OK, glosa correcta).`}
            </p>

            <TableWrapper>
              <Table>
                <thead>
                  <tr>
                    <TH>RUT</TH>
                    <TH>Docente</TH>
                    <TH>INS</TH>
                    <TH>Boleta</TH>
                    <TH>Tipo pago</TH>
                    <TH>Fecha</TH>
                    <TH className="text-right">Monto</TH>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={`${row.rut}-${row.numero_boleta}`}>
                      <TD className="font-mono text-xs">{row.rut}</TD>
                      <TD>{row.nombre_docente}</TD>
                      <TD>{row.ins}</TD>
                      <TD className="tabular-nums">{row.numero_boleta}</TD>
                      <TD>{row.tipo_pago}</TD>
                      <TD>{row.fecha_emision}</TD>
                      <TD className="text-right tabular-nums">
                        {typeof row.monto_bruto === "number" ? toCurrency(row.monto_bruto) : row.monto_bruto}
                      </TD>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </TableWrapper>
          </div>
        )
      ) : pagos.isLoading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Cargando pagos…
        </p>
      ) : pagos.isError ? (
        <ErrorState title="No se pudo cargar pagos" onRetry={() => void pagos.refetch()} />
      ) : !pagos.data?.exists ? (
        <EmptyState
          title="Sin informe de pagos"
          description={pagos.data?.read_error || "Carga la hoja Pagos en el paso 7 o sincroniza el mes a BD."}
        />
      ) : (
        <PagosReportPanel
          data={pagos.data}
          year={selectedPeriod?.year ?? 0}
          month={selectedPeriod?.month_name ?? ""}
          sourceLabel={sourceBadge(pagos.data.source_kind || pagos.data.source, pagos.data.frozen)}
        />
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/80 bg-card px-4 py-3 shadow-xs">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold tracking-tight">{value}</p>
    </div>
  );
}
