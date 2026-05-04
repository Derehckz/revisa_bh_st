import { useAppConfig } from "@/app/app-config";
import { useTheme } from "@/app/theme";
import { mapApiErrorMessage } from "@/shared/api/client";
import { useHealth, usePeriods } from "@/shared/api/queries";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { ErrorState } from "@/shared/ui/error-state";
import { Input } from "@/shared/ui/input";
import { useToast } from "@/shared/ui/toast";

export function SettingsPage() {
  const { baseUrl, apiKey, setBaseUrl, setApiKey } = useAppConfig();
  const { theme, toggleTheme } = useTheme();
  const { push } = useToast();
  const periods = usePeriods(baseUrl, apiKey);
  const health = useHealth(baseUrl);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Configuración</h1>
      {(health.isError || periods.isError) && (
        <ErrorState
          title="Problemas de conectividad detectados"
          description={mapApiErrorMessage((health.error || periods.error) as never)}
          onRetry={() => {
            health.refetch();
            periods.refetch();
          }}
        />
      )}
      <Card>
        <CardHeader>
          <CardTitle>Conexión API</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="http://127.0.0.1:8000" />
          <Input value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="x-api-key" />
          <div className="md:col-span-2">
            <Button onClick={() => push("Configuración guardada", "success")}>Guardar</Button>
            <Button className="ml-2" variant="outline" onClick={toggleTheme}>
              Theme: {theme}
            </Button>
          </div>
          <div className="md:col-span-2 rounded-md border border-border bg-muted p-3 text-sm">
            <strong>Health:</strong>{" "}
            {health.isError
              ? mapApiErrorMessage(health.error as never)
              : health.isLoading
                ? "Validando..."
                : health.data?.status === "ok"
                  ? "API operativa"
                  : "Estado desconocido"}
          </div>
          <div className="md:col-span-2 rounded-md border border-border bg-muted p-3 text-sm">
            <strong>Conectividad API key:</strong>{" "}
            {periods.isError ? mapApiErrorMessage(periods.error as never) : periods.isLoading ? "Validando..." : "Autenticación OK"}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
