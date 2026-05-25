import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { mapApiErrorMessage } from "@/shared/api/client";
import type { OperationJob } from "@/shared/api/types";

const OUTPUT_STAGES = new Set([0, 1, 3, 4, 5, 6, 7, 8, 9, 10]);

function hasDownloadableOutput(job: OperationJob) {
  return OUTPUT_STAGES.has(job.stage_num ?? 0);
}

function outputLabel(job: OperationJob) {
  const stage = job.stage_num ?? 0;
  if (stage === 10) return "revision_carpetas.xlsx";
  return job.output_file || "Solicitud.xlsx";
}
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { useToast } from "@/shared/ui/toast";

type Props = {
  baseUrl: string;
  apiKey: string;
  selectedJob: OperationJob | null;
  logs: string;
  logsRef: React.RefObject<HTMLDivElement | null>;
  progress: { current: number; total: number; percent: number };
  showOutputButton?: boolean;
};

export function JobStatusPanel({
  baseUrl,
  apiKey,
  selectedJob,
  logs,
  logsRef,
  progress,
  showOutputButton = true,
}: Props) {
  const { push } = useToast();

  async function openProtectedFile(path: string) {
    try {
      const response = await fetch(`${baseUrl}${path}`, {
        headers: { "x-api-key": apiKey },
      });
      if (!response.ok) {
        push(`No se pudo abrir archivo (${response.status}).`, "error");
        return;
      }
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      window.open(blobUrl, "_blank", "noopener,noreferrer");
    } catch {
      push("No se pudo abrir archivo.", "error");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Estado de ejecución</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {!selectedJob && <p className="text-sm text-muted-foreground">Sin ejecución seleccionada.</p>}
        {selectedJob && (
          <>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span>
                Job: <strong>{selectedJob.id}</strong>
              </span>
              <span className="text-muted-foreground">
                Paso {selectedJob.stage_num ?? 0}
              </span>
              {selectedJob.status === "running" && (
                <Badge>
                  <span className="inline-flex items-center gap-1">
                    <Loader2 size={12} className="animate-spin" />
                    Ejecutando
                  </span>
                </Badge>
              )}
              {selectedJob.status === "success" && (
                <Badge tone="success">
                  <span className="inline-flex items-center gap-1">
                    <CheckCircle2 size={12} />
                    Completado
                  </span>
                </Badge>
              )}
              {selectedJob.status === "failed" && (
                <Badge tone="danger">
                  <span className="inline-flex items-center gap-1">
                    <XCircle size={12} />
                    Error
                  </span>
                </Badge>
              )}
            </div>
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Progreso etapa</span>
                <span>
                  {progress.current}/{progress.total} ({progress.percent}%)
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-muted">
                <div
                  className="h-2 rounded-full bg-primary transition-all"
                  style={{ width: `${progress.percent}%` }}
                />
              </div>
            </div>
            <div
              ref={logsRef}
              className="max-h-[340px] overflow-auto rounded-md border border-border bg-muted p-3 text-xs whitespace-pre-wrap"
            >
              {logs || (selectedJob.status === "running" ? <Skeleton className="h-24 w-full" /> : "Sin logs todavía.")}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" onClick={() => void openProtectedFile(`/operations/jobs/${selectedJob.id}/log-file`)}>
                Descargar log
              </Button>
              {showOutputButton && selectedJob.status === "success" && hasDownloadableOutput(selectedJob) && (
                <Button onClick={() => void openProtectedFile(`/operations/jobs/${selectedJob.id}/output`)}>
                  Abrir {outputLabel(selectedJob)}
                </Button>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
