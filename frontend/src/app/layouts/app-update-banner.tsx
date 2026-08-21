import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";
import { useAppConfig } from "@/app/app-config";
import { useHealth, useServerRestart } from "@/shared/api/queries";
import { isApiCapabilitiesStale } from "@/shared/lib/app-capabilities";
import { Button } from "@/shared/ui/button";
import { useToast } from "@/shared/ui/toast";

export function AppUpdateBanner() {
  const { baseUrl, apiKey } = useAppConfig();
  const health = useHealth(baseUrl);
  const serverRestart = useServerRestart(baseUrl, apiKey);
  const { push } = useToast();

  if (health.isLoading || health.isError || !health.data) {
    return null;
  }

  if (!isApiCapabilitiesStale(health.data.capabilities_version)) {
    return null;
  }

  async function handleRestart() {
    try {
      const res = await serverRestart.mutateAsync(undefined);
      push(res.message || "Reiniciando servidor…", "success");
      window.setTimeout(() => window.location.reload(), 8000);
    } catch (e) {
      push(e instanceof Error ? e.message : "No se pudo reiniciar el servidor", "error");
    }
  }

  return (
    <div
      className="border-b border-warning/40 bg-warning/10 px-4 py-2.5 md:px-6 lg:px-8"
      role="status"
    >
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2 text-sm text-foreground">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
          <div className="space-y-1">
            <p className="font-medium">Hay una versión más reciente del programa</p>
            <p className="text-[0.8125rem] leading-snug text-muted-foreground">
              El servidor en segundo plano no tiene las reglas nuevas (por ejemplo, validación estricta
              de glosa). Reinícialo desde aquí para cargar el código actualizado.
            </p>
          </div>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="shrink-0"
          disabled={!apiKey || serverRestart.isPending}
          onClick={() => void handleRestart()}
        >
          {serverRestart.isPending ? (
            <Loader2 size={14} className="mr-1.5 animate-spin" />
          ) : (
            <RefreshCw size={14} className="mr-1.5" />
          )}
          {serverRestart.isPending ? "Reiniciando…" : "Reiniciar servidor"}
        </Button>
      </div>
    </div>
  );
}
