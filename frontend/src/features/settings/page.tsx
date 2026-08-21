import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAppConfig } from "@/app/app-config";
import { useTheme } from "@/app/theme";
import { getOperatorName, mapApiErrorMessage, setOperatorName } from "@/shared/api/client";
import {
  useAuditEvents,
  useDbBackup,
  useDbBackups,
  useDbConsistencyCheck,
  useDbMigrate,
  useHealth,
  usePeriodBackfill,
  usePeriodVerify,
  usePeriods,
} from "@/shared/api/queries";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { ErrorState } from "@/shared/ui/error-state";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { useToast } from "@/shared/ui/toast";

export function SettingsPage() {
  const { baseUrl, apiKey, setBaseUrl, setApiKey, sameOrigin } = useAppConfig();
  const { theme, toggleTheme } = useTheme();
  const { push } = useToast();
  const queryClient = useQueryClient();
  const periods = usePeriods(baseUrl, apiKey);
  const health = useHealth(baseUrl);
  const dbMigrate = useDbMigrate(baseUrl, apiKey);
  const dbConsistency = useDbConsistencyCheck(baseUrl, apiKey);
  const periodVerify = usePeriodVerify(baseUrl, apiKey);
  const periodBackfill = usePeriodBackfill(baseUrl, apiKey);
  const dbBackup = useDbBackup(baseUrl, apiKey);
  const dbBackups = useDbBackups(baseUrl, apiKey);
  const audit = useAuditEvents(baseUrl, apiKey);
  const [operator, setOperator] = useState("");
  const [syncYear, setSyncYear] = useState(2026);
  const [syncMonth, setSyncMonth] = useState("Julio");

  useEffect(() => {
    setOperator(getOperatorName());
  }, []);

  const saveAndTest = () => {
    setOperatorName(operator);
    void queryClient.invalidateQueries();
    void health.refetch();
    void periods.refetch().then((r) => {
      if (r.error) {
        push(mapApiErrorMessage(r.error as never), "error");
      } else {
        push("Conexión OK — clave y operador guardados", "success");
      }
    });
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader
        title="Ajustes"
        description="Conexión local y preferencias de la interfaz."
      />

      {(health.isError || periods.isError || !apiKey.trim()) && (
        <ErrorState
          title={!apiKey.trim() ? "Falta la API key" : "Problemas de conectividad"}
          description={
            !apiKey.trim()
              ? "Abre el archivo .env en la raíz del proyecto, copia el valor de BH_API_KEY y pégalo abajo."
              : mapApiErrorMessage((health.error || periods.error) as never)
          }
          onRetry={() => {
            health.refetch();
            periods.refetch();
          }}
        />
      )}

      <Card>
        <CardHeader>
          <CardTitle>Conexión</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            {sameOrigin
              ? "Modo embebido: la interfaz y la API comparten este servidor. Solo necesitas la API key del archivo .env (línea BH_API_KEY=…)."
              : "La clave no se envía a terceros; solo se guarda en este navegador."}
          </p>
        </CardHeader>
        <CardContent className="grid gap-4">
          <label className="grid gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">URL base</span>
            <Input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="http://127.0.0.1:8000"
              disabled={sameOrigin}
            />
            {sameOrigin && (
              <span className="text-2xs text-muted-foreground">Fijada al origen actual (servidor embebido).</span>
            )}
          </label>
          <label className="grid gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">API key (x-api-key)</span>
            <Input
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value.trim())}
              placeholder="Pega solo el valor de BH_API_KEY (sin comillas)"
              type="password"
              autoComplete="off"
            />
            <span className="text-2xs text-muted-foreground">
              Archivo <code className="rounded bg-muted px-1">.env</code> en la raíz del proyecto →
              copia solo el valor después de <code className="rounded bg-muted px-1">BH_API_KEY=</code>.
            </span>
          </label>
          <label className="grid gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">Nombre del operador</span>
            <Input
              value={operator}
              onChange={(e) => setOperator(e.target.value)}
              placeholder="Ej. Ana Pérez"
              autoComplete="name"
            />
            <span className="text-2xs text-muted-foreground">
              Se envía en cada acción para la bitácora (cierre, backups, exports).
            </span>
          </label>
          <div className="flex flex-wrap gap-2">
            <Button onClick={saveAndTest}>Guardar y probar</Button>
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

      <Card>
        <CardHeader>
          <CardTitle>Mantenimiento</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            Tareas técnicas del sistema (solo si te lo indica soporte).
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              disabled={!apiKey || dbMigrate.isPending}
              onClick={() => {
                void dbMigrate.mutateAsync().then(
                  (res) => push(res.message || "Esquema actualizado", "success"),
                  (err) => push(err instanceof Error ? err.message : "Migración falló", "error")
                );
              }}
            >
              {dbMigrate.isPending ? "Migrando…" : "Actualizar esquema DB"}
            </Button>
            <Button
              variant="outline"
              disabled={!apiKey || dbConsistency.isPending}
              onClick={() => {
                void dbConsistency.mutateAsync(20).then(
                  (res) => {
                    const msg =
                      res.ok
                        ? `Consistencia OK (${res.total_boletas} boletas)`
                        : `${res.critical_count} críticos, ${res.warning_count} advertencias`;
                    push(msg, res.ok ? "success" : "info");
                  },
                  (err) => push(err instanceof Error ? err.message : "Chequeo falló", "error")
                );
              }}
            >
              {dbConsistency.isPending ? "Revisando…" : "Revisar consistencia global"}
            </Button>
          </div>
          {dbConsistency.data ? (
            <ul className="space-y-1 text-xs text-muted-foreground">
              {dbConsistency.data.findings
                .filter((f) => f.count > 0)
                .slice(0, 6)
                .map((f) => (
                  <li key={f.name}>
                    {f.name}: {f.count}
                  </li>
                ))}
            </ul>
          ) : null}

          <div className="rounded-md border border-border/80 p-3 space-y-2">
            <p className="text-sm font-medium">Sincronizar mes / backfill a PostgreSQL</p>
            <p className="text-xs text-muted-foreground">
              Importa Solicitud, proyecta boletas y guarda snapshots de informe final y pagos para
              ver meses cerrados en Avance e Informes.
            </p>
            <div className="flex flex-wrap items-end gap-2">
              <label className="text-xs space-y-1">
                <span className="text-muted-foreground">Año</span>
                <Input
                  type="number"
                  className="w-24"
                  value={syncYear}
                  onChange={(e) => setSyncYear(Number(e.target.value) || 2026)}
                />
              </label>
              <label className="text-xs space-y-1">
                <span className="text-muted-foreground">Mes</span>
                <Input
                  className="w-28"
                  value={syncMonth}
                  onChange={(e) => setSyncMonth(e.target.value)}
                  placeholder="Julio"
                />
              </label>
              <Button
                variant="outline"
                disabled={!apiKey || periodVerify.isPending || !syncMonth.trim()}
                onClick={() => {
                  void periodVerify
                    .mutateAsync({ year: syncYear, month: syncMonth.trim() })
                    .then(
                      (res) =>
                        push(
                          res.ok
                            ? `Mes sincronizado: ${res.month} ${res.year}`
                            : `Sincronizado con diferencias Excel/DB (${res.compare?.differences ?? "?"})`,
                          res.ok ? "success" : "info"
                        ),
                      (err) =>
                        push(err instanceof Error ? err.message : "Sincronización falló", "error")
                    );
                }}
              >
                {periodVerify.isPending ? "Sincronizando…" : "Sincronizar mes a BD"}
              </Button>
              <Button
                variant="outline"
                disabled={!apiKey || periodBackfill.isPending}
                onClick={() => {
                  void periodBackfill.mutateAsync({ year: syncYear }).then(
                    (res) =>
                      push(
                        `Backfill ${res.year}: ${res.ok_count}/${res.total} meses OK`,
                        res.ok ? "success" : "info"
                      ),
                    (err) => push(err instanceof Error ? err.message : "Backfill falló", "error")
                  );
                }}
              >
                {periodBackfill.isPending ? "Backfill…" : `Backfill año ${syncYear}`}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Backup PostgreSQL</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            Crea un dump local. Programa uno diario con el Programador de tareas de Windows
            (script <code className="text-xs">herramientas/backup_postgres.ps1</code>).
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button
            variant="outline"
            disabled={!apiKey || dbBackup.isPending}
            onClick={() => {
              void dbBackup.mutateAsync().then(
                (res) => push(res.message || "Backup creado", "success"),
                (err) => push(err instanceof Error ? err.message : "Backup falló", "error")
              );
            }}
          >
            {dbBackup.isPending ? "Creando backup…" : "Crear backup ahora"}
          </Button>
          {dbBackups.data?.backups_dir ? (
            <p className="text-2xs text-muted-foreground">Carpeta: {dbBackups.data.backups_dir}</p>
          ) : null}
          <ul className="space-y-1 text-xs text-muted-foreground">
            {(dbBackups.data?.backups || []).slice(0, 5).map((b) => (
              <li key={b.filename}>
                {b.filename} · {(b.size_bytes / (1024 * 1024)).toFixed(1)} MB
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Bitácora reciente</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">Últimas acciones registradas (cierre, backup, export).</p>
        </CardHeader>
        <CardContent>
          <ul className="max-h-56 space-y-1 overflow-y-auto text-xs text-muted-foreground">
            {(audit.data?.events || []).slice(0, 20).map((e) => (
              <li key={e.id}>
                <span className="font-medium text-foreground">{e.action}</span>
                {e.operator ? ` · ${e.operator}` : ""}
                {e.period_month ? ` · ${e.period_month} ${e.period_year}` : ""}
                {e.ts ? ` · ${new Date(e.ts).toLocaleString("es-CL")}` : ""}
              </li>
            ))}
            {!audit.data?.events?.length ? <li>Sin eventos aún.</li> : null}
          </ul>
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
