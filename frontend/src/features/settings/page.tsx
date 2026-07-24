import { useAppConfig } from "@/app/app-config";
import { useTheme } from "@/app/theme";
import { mapApiErrorMessage } from "@/shared/api/client";
import { useHealth, usePeriods } from "@/shared/api/queries";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { ErrorState } from "@/shared/ui/error-state";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { useToast } from "@/shared/ui/toast";

export function SettingsPage() {
  const { baseUrl, apiKey, setBaseUrl, setApiKey } = useAppConfig();
  const { theme, toggleTheme } = useTheme();
  const { push } = useToast();
  const periods = usePeriods(baseUrl, apiKey);
  const health = useHealth(baseUrl);

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader
        title="Ajustes"
        description="Conexión a la API local y preferencias de la interfaz."
      />

      {(health.isError || periods.isError) && (
        <ErrorState
          title="Problemas de conectividad"
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
          <p className="mt-1 text-sm text-muted-foreground">
            La clave no se envía a terceros; solo se guarda en este navegador.
          </p>
        </CardHeader>
        <CardContent className="grid gap-4">
          <label className="grid gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">URL base</span>
            <Input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="http://127.0.0.1:8000"
            />
          </label>
          <label className="grid gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">API key (x-api-key)</span>
            <Input
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Pega tu clave"
              type="password"
              autoComplete="off"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => push("Configuración guardada", "success")}>Guardar</Button>
            <Button variant="outline" onClick={toggleTheme}>
              Apariencia: {theme === "dark" ? "Oscuro" : "Claro"}
            </Button>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <StatusRow
              label="API"
              ok={!health.isError && health.data?.status === "ok"}
              loading={health.isLoading}
              detail={
                health.isError
                  ? mapApiErrorMessage(health.error as never)
                  : health.data?.status === "ok"
                    ? "Operativa"
                    : "Desconocido"
              }
            />
            <StatusRow
              label="Autenticación"
              ok={!periods.isError && Boolean(periods.data)}
              loading={periods.isLoading}
              detail={
                periods.isError
                  ? mapApiErrorMessage(periods.error as never)
                  : periods.isLoading
                    ? "Validando…"
                    : "OK"
              }
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function StatusRow({
  label,
  ok,
  loading,
  detail,
}: {
  label: string;
  ok: boolean;
  loading: boolean;
  detail: string;
}) {
  return (
    <div className="rounded-md border border-border bg-muted/40 px-3 py-2.5">
      <p className="text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-sm font-medium tracking-tight">
        {loading ? "…" : ok ? (
          <span className="text-success">{detail}</span>
        ) : (
          <span className="text-danger">{detail}</span>
        )}
      </p>
    </div>
  );
}
