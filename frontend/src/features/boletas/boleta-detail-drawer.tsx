import { X } from "lucide-react";
import { useAppConfig } from "@/app/app-config";
import { useBoletaDetail } from "@/shared/api/queries";
import { toCurrency } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Skeleton } from "@/shared/ui/skeleton";
import { useToast } from "@/shared/ui/toast";

function estadoTone(estado: string | null | undefined): "success" | "warning" | "danger" | "default" {
  const e = (estado || "").toUpperCase();
  if (e === "RECIBIDO") return "success";
  if (e.includes("ERROR")) return "warning";
  if (e === "NO RECIBIDO") return "danger";
  return "default";
}

export function BoletaDetailDrawer({
  open,
  onClose,
  year,
  month,
  boletaId,
}: {
  open: boolean;
  onClose: () => void;
  year?: number;
  month?: string;
  boletaId?: number;
}) {
  const { baseUrl, apiKey } = useAppConfig();
  const { push } = useToast();
  const detail = useBoletaDetail(baseUrl, apiKey, { year, month, boletaId, enabled: open });

  async function openFile(fileType: "xml" | "pdf") {
    if (!year || !month || !boletaId) return;
    const endpoint = `${baseUrl}/period/${year}/${month}/boletas/${boletaId}/files/${fileType}`;
    const response = await fetch(endpoint, {
      headers: { "x-api-key": apiKey },
    });
    if (!response.ok) {
      push(`No se pudo abrir ${fileType.toUpperCase()} (${response.status}).`, "error");
      return;
    }
    const blob = await response.blob();
    const blobUrl = URL.createObjectURL(blob);
    window.open(blobUrl, "_blank", "noopener,noreferrer");
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/35 backdrop-blur-[2px]"
      onClick={onClose}
      role="presentation"
    >
      <aside
        className="flex h-full w-full max-w-md flex-col border-l border-border bg-card shadow-elevated"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Detalle boleta"
      >
        <div className="flex items-center justify-between border-b border-border/80 px-4 py-3">
          <div>
            <p className="text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">Boleta</p>
            <h3 className="text-[1.0625rem] font-semibold tracking-tight">
              {detail.data?.boleta.docente_nombre || "Detalle"}
            </h3>
          </div>
          <Button variant="ghost" size="sm" className="h-8 w-8 px-0" onClick={onClose} aria-label="Cerrar">
            <X size={16} strokeWidth={1.75} />
          </Button>
        </div>

        <div className="min-h-0 flex-1 overflow-auto p-4">
          {detail.isLoading && (
            <div className="space-y-3">
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          )}

          {detail.data && (
            <div className="space-y-4 text-sm">
              <section className="space-y-2 rounded-lg border border-border/80 p-3">
                <Row label="ID" value={String(detail.data.boleta.id)} />
                <Row label="EMPLID" value={detail.data.boleta.emplid || "—"} />
                <Row label="Sede" value={detail.data.boleta.sede || "—"} />
                <Row label="Key" value={detail.data.boleta.boleta_key || "—"} />
                <Row label="Monto" value={toCurrency(detail.data.boleta.monto_bruto)} />
                <div className="flex items-center justify-between gap-2 pt-1">
                  <span className="text-muted-foreground">Estado</span>
                  <Badge tone={estadoTone(detail.data.boleta.estado_recepcion)}>
                    {detail.data.boleta.estado_recepcion || "—"}
                  </Badge>
                </div>
                <div className="flex gap-2 pt-2">
                  <Button variant="outline" size="sm" onClick={() => void openFile("xml")}>
                    XML
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => void openFile("pdf")}>
                    PDF
                  </Button>
                </div>
              </section>

              <section className="rounded-lg border border-border/80 p-3">
                <p className="mb-2 text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">
                  Datos XML
                </p>
                {detail.data.xml_data ? (
                  <div className="space-y-2">
                    <Row label="Número" value={detail.data.xml_data.numero_boleta || "—"} />
                    <Row label="Fecha" value={detail.data.xml_data.fecha_boleta || "—"} />
                    <Row label="Total" value={toCurrency(detail.data.xml_data.total_honorarios)} />
                  </div>
                ) : (
                  <p className="text-[0.8125rem] text-muted-foreground">Sin XML asociado.</p>
                )}
              </section>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className="truncate text-right font-medium tracking-tight tabular-nums text-foreground">
        {value}
      </span>
    </div>
  );
}
