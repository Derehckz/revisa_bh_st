import { useJobArtifacts } from "@/shared/api/queries";
import type { OperationJob } from "@/shared/api/types";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { useToast } from "@/shared/ui/toast";

type Props = {
  baseUrl: string;
  apiKey: string;
  selectedJob: OperationJob | null;
};

export function StageArtifactsPanel({ baseUrl, apiKey, selectedJob }: Props) {
  const { push } = useToast();
  const artifactsQuery = useJobArtifacts(baseUrl, apiKey, selectedJob?.id ?? null);
  const artifacts = artifactsQuery.data?.artifacts ?? [];

  async function download(path: string) {
    try {
      const response = await fetch(`${baseUrl}${path}`, { headers: { "x-api-key": apiKey } });
      if (!response.ok) {
        push(`No se pudo descargar (${response.status}).`, "error");
        return;
      }
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      window.open(blobUrl, "_blank", "noopener,noreferrer");
    } catch {
      push("Error al descargar artefacto.", "error");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Resultados</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {selectedJob && (selectedJob.id.startsWith("hist_") || selectedJob.source === "filesystem") && (
          <p className="text-sm text-muted-foreground">
            Ejecución desde consola: los artefactos están en la carpeta del mes ({selectedJob.month}{" "}
            {selectedJob.year}).
          </p>
        )}
        {!selectedJob && (
          <p className="text-sm text-muted-foreground">Selecciona un job para ver artefactos.</p>
        )}
        {selectedJob && artifactsQuery.isLoading && (
          <p className="text-sm text-muted-foreground">Cargando artefactos…</p>
        )}
        {selectedJob && !artifactsQuery.isLoading && artifacts.length === 0 && (
          <p className="text-sm text-muted-foreground">Sin archivos disponibles aún.</p>
        )}
        {artifacts.map((art) => (
          <div
            key={art.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border px-3 py-2 text-sm"
          >
            <span>
              {art.label}
              {art.size_bytes != null ? (
                <span className="ml-2 text-xs text-muted-foreground">
                  ({Math.round(art.size_bytes / 1024)} KB)
                </span>
              ) : null}
            </span>
            <Button variant="outline" onClick={() => void download(art.download_url)}>
              Abrir
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
