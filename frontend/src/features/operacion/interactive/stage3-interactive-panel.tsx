import { useMemo, useState } from "react";
import { ClipboardCheck, Loader2, Play, Square } from "lucide-react";
import type { Period, Step0OptionsResponse } from "@/shared/api/types";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import type { UseQueryResult } from "@tanstack/react-query";
import { isSessionRunning, useInteractiveSession } from "./use-interactive-session";
import { usePeriodOperationGuard } from "../period-operation-context";
import {
  InteractivePeriodExcelFields,
  usePeriodExcelDefaults,
  useSyncPeriodExcelDefaults,
} from "./interactive-period-excel-fields";
import { ActiveSessionCard, SessionDoneCard } from "./session-recovery-cards";

type Props = {
  selectedPeriod: Period;
  options: UseQueryResult<Step0OptionsResponse>;
  baseUrl: string;
  apiKey: string;
  disabled?: boolean;
  onGoToNextStage?: () => void;
  onGoToReminders?: () => void;
  noRecibidos?: number;
};

export function Stage3InteractivePanel({
  selectedPeriod,
  options,
  baseUrl,
  apiKey,
  disabled,
  onGoToNextStage,
  onGoToReminders,
  noRecibidos = 0,
}: Props) {
  const excelDefaults = usePeriodExcelDefaults(selectedPeriod, options);

  const { confirmBeforeOperation } = usePeriodOperationGuard();
  const {
    session,
    events,
    pendingPrompt,
    connected,
    error,
    activeSessionId,
    startSession,
    attachToSession,
    cancelSessionById,
    respond,
    cancelSession,
  } = useInteractiveSession(baseUrl, apiKey);
  const [periodExcel, setPeriodExcel] = useState(excelDefaults);
  useSyncPeriodExcelDefaults(excelDefaults, setPeriodExcel);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [strict, setStrict] = useState(false);
  const [starting, setStarting] = useState(false);
  const [resolvingActive, setResolvingActive] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const scanReady = [...events].reverse().find((e) => e.type === "scan.ready");
  const analysis = [...events].reverse().find((e) => e.type === "analysis.complete");
  const summary = [...events].reverse().find((e) => e.type === "session.summary");
  const logs = events.filter((e) => e.type === "log");
  const done = session?.status === "completed" || Boolean(summary);
  const running = isSessionRunning(session?.status);

  const xmlCount = useMemo(() => {
    const p = scanReady?.payload as { xml_files?: number } | undefined;
    return p?.xml_files ?? null;
  }, [scanReady]);

  const excelSaved = Boolean((summary?.payload as { excel_saved?: boolean } | undefined)?.excel_saved);

  async function handleStart() {
    setLocalError(null);
    if (!periodExcel.monthDir.trim() || !periodExcel.excelFile.trim() || !periodExcel.sheet.trim()) {
      setLocalError("Falta carpeta, Excel u hoja del período.");
      return;
    }
    if (!(await confirmBeforeOperation())) return;
    setStarting(true);
    try {
      await startSession(3, {
        year: selectedPeriod.year,
        month: selectedPeriod.month_name,
        month_dir: periodExcel.monthDir.trim(),
        excel_file: periodExcel.excelFile.trim(),
        sheet: periodExcel.sheet.trim(),
        strict,
        streamlined: true,
      });
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "No se pudo iniciar el paso");
    } finally {
      setStarting(false);
    }
  }

  async function handleResumeActive() {
    if (!activeSessionId) return;
    setLocalError(null);
    setResolvingActive(true);
    try {
      await attachToSession(activeSessionId);
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "No se pudo continuar");
    } finally {
      setResolvingActive(false);
    }
  }

  async function handleCancelActive() {
    if (!activeSessionId) return;
    setLocalError(null);
    setResolvingActive(true);
    try {
      await cancelSessionById(activeSessionId);
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "No se pudo cancelar");
    } finally {
      setResolvingActive(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-base flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4" />
            Paso 3 — Marcar recibidos
          </CardTitle>
          <p className="text-xs text-muted-foreground font-normal">
            Compara la planilla con las boletas de la carpeta y guarda los cambios en Solicitud.xlsx
            automáticamente. Cierra el Excel antes de ejecutar.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <button
            type="button"
            className="text-xs text-muted-foreground underline"
            onClick={() => setShowAdvanced((v) => !v)}
          >
            {showAdvanced ? "Ocultar opciones" : "Cambiar archivo / opciones"}
          </button>
          {showAdvanced && (
            <>
              <InteractivePeriodExcelFields
                selectedPeriod={selectedPeriod}
                options={options}
                values={periodExcel}
                onChange={setPeriodExcel}
                disabled={Boolean(session) || disabled}
              />
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={strict}
                  onChange={(e) => setStrict(e.target.checked)}
                  disabled={Boolean(session) || disabled}
                />
                Validación estricta de columnas
              </label>
            </>
          )}
          {xmlCount !== null && (
            <p className="text-sm">
              Boletas XML en carpeta: <strong>{xmlCount}</strong>
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              onClick={() => void handleStart()}
              disabled={disabled || starting || running}
            >
              {starting ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Play className="h-4 w-4 mr-2" />
              )}
              Marcar recibidos en la planilla
            </Button>
            {running && (
              <Button type="button" variant="outline" onClick={() => void cancelSession()}>
                <Square className="h-4 w-4 mr-2" />
                Cancelar
              </Button>
            )}
          </div>
          {running && (
            <p className="text-xs text-muted-foreground">
              En curso{connected ? " · en vivo" : " · reconectando…"}
            </p>
          )}
          {(localError || error) && (
            <p className="text-sm text-danger">{localError || error}</p>
          )}
        </CardContent>
      </Card>

      {activeSessionId && (
        <ActiveSessionCard
          sessionId={activeSessionId}
          busy={resolvingActive || starting}
          onResume={() => void handleResumeActive()}
          onCancel={() => void handleCancelActive()}
        />
      )}

      {done && (
        <SessionDoneCard
          title={excelSaved ? "Planilla guardada" : "Paso terminado"}
          detail={
            excelSaved
              ? noRecibidos > 0
                ? `Solicitud.xlsx actualizado. Hay ${noRecibidos} NO RECIBIDO: puedes seguir al paso 4 o enviar recordatorios.`
                : "Solicitud.xlsx ya tiene el estado de recepción. Puedes seguir al paso 4."
              : "Revisa el detalle abajo. Si no se guardó el Excel, vuelve a ejecutar con el archivo cerrado."
          }
          nextLabel={onGoToNextStage ? "Ir al paso 4" : undefined}
          onNext={onGoToNextStage}
          secondaryLabel={
            noRecibidos > 0 && onGoToReminders
              ? `Recordatorios (${noRecibidos})`
              : undefined
          }
          onSecondary={onGoToReminders}
        />
      )}

      {analysis && (
        <Card>
          <CardHeader className="py-2">
            <CardTitle className="text-sm">Resumen</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            Recibidos:{" "}
            <strong>
              {String((analysis.payload as { revis_fin?: number }).revis_fin ?? "—")}
            </strong>
            {" / "}
            {String((analysis.payload as { total?: number }).total ?? "—")}
          </CardContent>
        </Card>
      )}

      {pendingPrompt && (
        <Card className="border-warning/30 bg-warning/10">
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

      <details className="rounded-lg border border-border p-3">
        <summary className="text-sm cursor-pointer">Ver detalle técnico</summary>
        <div className="font-mono text-xs max-h-64 overflow-y-auto bg-muted/20 rounded p-2 space-y-0.5 mt-2">
          {logs.length === 0 && <p className="text-muted-foreground">Sin eventos aún.</p>}
          {logs.map((e) => (
            <div
              key={e.seq}
              className={(e.payload.level as string) === "error" ? "text-danger" : undefined}
            >
              {String(e.payload.message ?? "")}
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
