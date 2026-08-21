import { AlertTriangle, Loader2 } from "lucide-react";
import type { ArrastrePreview } from "@/shared/api/types";
import { formatMontoCl } from "@/shared/lib/display-format";
import { Table, TableWrapper, TD, TH } from "@/shared/ui/table";

type Props = {
  preview?: ArrastrePreview;
  compact?: boolean;
  loading?: boolean;
};

export function ArrastrePreviewCard({ preview, compact = false, loading = false }: Props) {
  if (loading && !preview) {
    return (
      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Calculando arrastre de provisionados…
      </p>
    );
  }
  if (!preview) return null;

  const lookbackLabel = (preview.lookback || [])
    .map((m) => `${m.month}${m.closed ? " (cerrado)" : ""}`)
    .join(" → ");

  return (
    <div className="space-y-2 rounded-md border border-border bg-muted/20 px-3 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium">Provisionados que se agregarán</p>
        <p className="text-xs text-muted-foreground">
          {preview.count > 0
            ? `${preview.count} fila${preview.count === 1 ? "" : "s"} · ${formatMontoCl(preview.total_monto)}`
            : "Ninguna"}
        </p>
      </div>
      <p className="text-xs text-muted-foreground">{preview.message}</p>
      {lookbackLabel && (
        <p className="text-2xs text-muted-foreground">Meses revisados: {lookbackLabel}</p>
      )}
      {preview.previous_closed && preview.count > 0 && (
        <p className="flex items-start gap-1.5 text-xs text-amber-800">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          El mes anterior está cerrado; igual se arrastra su NO RECIBIDO a este mes.
        </p>
      )}
      {!compact && preview.rows.length > 0 && (
        <TableWrapper className="max-h-64 overflow-auto">
          <Table>
            <thead>
              <tr>
                <TH>Docente</TH>
                <TH>Inst.</TH>
                <TH className="text-right">Monto</TH>
                <TH>Correo</TH>
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((row) => (
                <tr key={`${row.emplid}-${row.rut_razon}`}>
                  <TD>
                    <p className="font-medium">{row.name || row.emplid}</p>
                    <p className="text-2xs text-muted-foreground">{row.emplid}</p>
                  </TD>
                  <TD>{row.institucion || "—"}</TD>
                  <TD className="text-right tabular-nums">{formatMontoCl(row.monto)}</TD>
                  <TD className="text-2xs">{row.email || "—"}</TD>
                </tr>
              ))}
            </tbody>
          </Table>
        </TableWrapper>
      )}
    </div>
  );
}
