import { X } from "lucide-react";
import { useAppConfig } from "@/app/app-config";
import { useBoletaDetail } from "@/shared/api/queries";
import { toCurrency } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Skeleton } from "@/shared/ui/skeleton";
import { useToast } from "@/shared/ui/toast";

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
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30">
      <div className="h-full w-full max-w-xl overflow-auto border-l border-border bg-card p-4 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">Detalle boleta</h3>
          <Button variant="ghost" onClick={onClose}>
            <X size={16} />
          </Button>
        </div>

        {detail.isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        )}

        {detail.data && (
          <div className="space-y-4 text-sm">
            <div className="rounded-md border border-border p-3">
              <p><strong>ID:</strong> {detail.data.boleta.id}</p>
              <p><strong>EMPLID:</strong> {detail.data.boleta.emplid || "-"}</p>
              <p><strong>Nombre:</strong> {detail.data.boleta.docente_nombre || "-"}</p>
              <p><strong>Sede:</strong> {detail.data.boleta.sede || "-"}</p>
              <p><strong>Boleta Key:</strong> {detail.data.boleta.boleta_key || "-"}</p>
              <p><strong>Monto:</strong> {toCurrency(detail.data.boleta.monto_bruto)}</p>
              <p><strong>Estado:</strong> <Badge>{detail.data.boleta.estado_recepcion || "-"}</Badge></p>
              <div className="mt-2 flex gap-2">
                <Button variant="outline" onClick={() => void openFile("xml")}>Ver XML</Button>
                <Button variant="outline" onClick={() => void openFile("pdf")}>Ver PDF</Button>
              </div>
            </div>

            <div className="rounded-md border border-border p-3">
              <p className="mb-2 font-medium">XML</p>
              {detail.data.xml_data ? (
                <>
                  <p><strong>Número:</strong> {detail.data.xml_data.numero_boleta || "-"}</p>
                  <p><strong>Fecha:</strong> {detail.data.xml_data.fecha_boleta || "-"}</p>
                  <p><strong>Total:</strong> {toCurrency(detail.data.xml_data.total_honorarios)}</p>
                </>
              ) : (
                <p className="text-muted-foreground">Sin XML asociado.</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
