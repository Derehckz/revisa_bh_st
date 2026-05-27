import { useMemo, useState } from "react";
import { ClipboardCheck, Loader2, Play, Square } from "lucide-react";
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

export function Stage3InteractivePanel({
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
  const [starting, setStarting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const scanReady = [...events].reverse().find((e) => e.type === "scan.ready");
  const analysis = [...events].reverse().find((e) => e.type === "analysis.complete");
  const logs = events.filter((e) => e.type === "log");

  const xmlCount = useMemo(() => {
    const p = scanReady?.payload as { xml_files?: number } | undefined;
    return p?.xml_files ?? null;
  }, [scanReady]);

  async function handleStart() {
    setLocalError(null);
    setStarting(true);
    try {
      await startSession(3, {
        year: selectedPeriod.year,
        month: selectedPeriod.month_name,
        sheet: sheetDefault,
        strict,
      });
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "No se pudo iniciar la sesión");
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card className="border-violet-500/30 bg-violet-500/5">
        <CardHeader className="py-3">
          <CardTitle className="text-base flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4" />
            Revisión supervisada (planilla vs XML/PDF)
          </CardTitle>
          <p className="text-xs text-muted-foreground font-normal">
            Compara Solicitud.xlsx con los archivos bhe_ del mes. Confirma antes de procesar y
            antes de guardar el Excel.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm">
            Hoja: <strong>{String(sheetDefault)}</strong>
            {xmlCount !== null && (
              <>
                {" "}
                · XML en carpeta: <strong>{xmlCount}</strong>
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
            Validación estricta del esquema Excel
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
              Iniciar revisión
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
            <CardTitle className="text-sm">Resultado</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            Recibidos al final:{" "}
            <strong>
              {String((analysis.payload as { revis_fin?: number }).revis_fin ?? "—")}
            </strong>
            {" / "}
            {String((analysis.payload as { total?: number }).total ?? "—")}
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
            {logs.length === 0 && <p className="text-muted-foreground">Sin eventos aún.</p>}
            {logs.map((e) => (
              <div
                key={e.seq}
                className={
                  (e.payload.level as string) === "error" ? "text-destructive" : undefined
                }
              >
                {String(e.payload.message ?? "")}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
