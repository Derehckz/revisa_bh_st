import { useState } from "react";
import { FileSpreadsheet, Loader2, Play, Square } from "lucide-react";
import type { Period, Step0OptionsResponse } from "@/shared/api/types";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import type { UseQueryResult } from "@tanstack/react-query";
import { useInteractiveSession } from "./use-interactive-session";

type Props = {
  selectedPeriod: Period;
  options: UseQueryResult<Step0OptionsResponse>;
  baseUrl: string;
  apiKey: string;
  disabled?: boolean;
};

export function Stage4InteractivePanel({
  selectedPeriod,
  options,
  baseUrl,
  apiKey,
  disabled,
}: Props) {
  const sheetDefault =
    options.data?.params_schema?.find((f) => f.name === "sheet")?.default ??
    options.data?.choices?.solicitud_sheet_auto ??
    "Solicitud";

  const { session, events, pendingPrompt, connected, error, startSession, respond, cancelSession } =
    useInteractiveSession(baseUrl, apiKey);
  const [strict, setStrict] = useState(false);
  const [overwrite, setOverwrite] = useState(false);
  const [starting, setStarting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const scanReady = [...events].reverse().find((e) => e.type === "scan.ready");
  const analysis = [...events].reverse().find((e) => e.type === "analysis.complete");
  const logs = events.filter((e) => e.type === "log");
  const okRows = events.filter((e) => e.type === "row.ok").length;

  async function handleStart() {
    setLocalError(null);
    setStarting(true);
    try {
      await startSession(4, {
        year: selectedPeriod.year,
        month: selectedPeriod.month_name,
        sheet: sheetDefault,
        strict,
        ...(overwrite ? { overwrite_ok: true } : {}),
      });
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "No se pudo iniciar la sesión");
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card className="border-emerald-500/30 bg-emerald-500/5">
        <CardHeader className="py-3">
          <CardTitle className="text-base flex items-center gap-2">
            <FileSpreadsheet className="h-4 w-4" />
            Extracción XML → Excel (supervisada)
          </CardTitle>
          <p className="text-xs text-muted-foreground font-normal">
            Lee cada XML referenciado en archivo_xml y completa las columnas *_XML en
            Solicitud. Requiere haber ejecutado el paso 3 antes.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm">
            Hoja: <strong>{String(sheetDefault)}</strong>
            {scanReady && (
              <>
                {" "}
                · Filas con XML:{" "}
                <strong>
                  {String((scanReady.payload as { rows_with_xml?: number }).rows_with_xml ?? "—")}
                </strong>
              </>
            )}
          </p>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={strict}
              onChange={(e) => setStrict(e.target.checked)}
              disabled={Boolean(session) || disabled}
            />
            Validación estricta del esquema
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={overwrite}
              onChange={(e) => setOverwrite(e.target.checked)}
              disabled={Boolean(session) || disabled}
            />
            Sobrescribir filas que ya tienen «Datos extraídos OK» (si no marcas, se pregunta en la sesión)
          </label>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              onClick={() => void handleStart()}
              disabled={disabled || starting || Boolean(session)}
            >
              {starting ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Play className="h-4 w-4 mr-2" />
              )}
              Iniciar extracción
            </Button>
            {session && (
              <Button type="button" variant="outline" onClick={() => void cancelSession()}>
                <Square className="h-4 w-4 mr-2" />
                Cancelar
              </Button>
            )}
          </div>
          {session && (
            <p className="text-xs text-muted-foreground">
              Sesión {session.id} — {session.status}
              {connected ? " · en vivo" : ""}
              {okRows > 0 ? ` · ${okRows} filas OK en esta corrida` : ""}
            </p>
          )}
          {(localError || error) && (
            <p className="text-sm text-destructive">{localError || error}</p>
          )}
        </CardContent>
      </Card>

      {analysis && (
        <Card>
          <CardHeader className="py-2">
            <CardTitle className="text-sm">Resumen</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Exitosas:{" "}
            <strong>{String((analysis.payload as { exitos?: number }).exitos ?? 0)}</strong>
            {" · "}
            Errores:{" "}
            <strong>{String((analysis.payload as { errores?: number }).errores ?? 0)}</strong>
            {" · "}
            Omitidas:{" "}
            <strong>{String((analysis.payload as { omitidos?: number }).omitidos ?? 0)}</strong>
          </CardContent>
        </Card>
      )}

      {pendingPrompt && (
        <Card className="border-amber-500/50">
          <CardHeader className="py-3">
            <CardTitle className="text-sm">{pendingPrompt.title}</CardTitle>
            <p className="text-xs text-muted-foreground">{pendingPrompt.message}</p>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button type="button" className="text-sm h-8" onClick={() => respond("accept")}>
              Sí
            </Button>
            <Button type="button" className="text-sm h-8" variant="outline" onClick={() => respond("reject")}>
              No
            </Button>
            <Button type="button" className="text-sm h-8" variant="ghost" onClick={() => respond("cancel")}>
              Cancelar
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm">Consola en vivo</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="font-mono text-xs max-h-64 overflow-y-auto bg-muted/20 rounded p-2 space-y-0.5">
            {logs.map((e) => (
              <div key={e.seq}>{String(e.payload.message ?? "")}</div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
