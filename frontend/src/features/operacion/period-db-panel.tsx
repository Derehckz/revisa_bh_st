import { Download, Loader2 } from "lucide-react";
import { Button } from "@/shared/ui/button";

type Props = {
  year?: number;
  month?: string;
  onDownload?: () => void;
  downloadPending?: boolean;
  disabled?: boolean;
};

/** Acción secundaria: exportar el período a Excel (snapshot desde BD). */
export function PeriodExportButton({
  year,
  month,
  onDownload,
  downloadPending,
  disabled,
}: Props) {
  if (!onDownload || !year || !month) return null;

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="shrink-0"
      disabled={disabled || downloadPending}
      onClick={onDownload}
      title={`Exportar solicitudes de ${month} ${year} a Excel`}
    >
      {downloadPending ? (
        <Loader2 size={14} className="mr-1.5 animate-spin" />
      ) : (
        <Download size={14} className="mr-1.5" />
      )}
      {downloadPending ? "Exportando…" : "Exportar Solicitud"}
    </Button>
  );
}
