import { useState } from "react";
import { FileSpreadsheet, Loader2, Play, Square } from "lucide-react";
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
};

export function Stage4InteractivePanel({
  selectedPeriod,
  options,
  baseUrl,
  apiKey,
  disabled,
  onGoToNextStage,
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
  const [overwrite, setOverwrite] = useState(false);
  const [starting, setStarting] = useState(false);
  const [resolvingActive, setResolvingActive] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const scanReady = [...events].reverse().find((e) => e.type === "scan.ready");
  const analysis = [...events].reverse().find((e) => e.type === "analysis.complete");
  const summary = [...events].reverse().find((e) => e.type === "session.summary");
  const logs = events.filter((e) => e.type === "log");
  const okRows = events.filter((e) => e.type === "row.ok").length;
  const done = session?.status === "completed" || Boolean(summary);
  const running = isSessionRunning(session?.status);
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
      await startSession(4, {
        year: selectedPeriod.year,
        month: selectedPeriod.month_name,
        month_dir: periodExcel.monthDir.trim(),
        excel_file: periodExcel.excelFile.trim(),
        sheet: periodExcel.sheet.trim(),
        strict,
        streamlined: true,
        ...(overwrite ? { overwrite_ok: true } : { overwrite_ok: false }),
      });
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "No se pudo iniciar el paso");
    } finally {
      setStarting(false);
    }
  }

  async function handleResumeActive() {
    if (!activeSessionId) return;
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
            <FileSpreadsheet className="h-4 w-4" />
            Paso 4 — Completar datos desde boletas
          </CardTitle>
          <p className="text-xs text-muted-foreground font-normal">
            Rellena las columnas XML en Solicitud.xlsx y guarda automáticamente. Cierra el Excel antes
            de ejecutar.
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
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={overwrite}
                  onChange={(e) => setOverwrite(e.target.checked)}
                  disabled={Boolean(session) || disabled}
                />
                Sobrescribir filas que ya tenían datos extraídos
              </label>
            </>
          )}
          {scanReady && (
            <p className="text-sm">
              Filas con XML:{" "}
              <strong>
                {String((scanReady.payload as { rows_with_xml?: number }).rows_with_xml ?? "—")}
              </strong>
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
              Completar datos desde las boletas
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
              {okRows > 0 ? ` · ${okRows} filas OK` : ""}
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
              ? "Solicitud.xlsx ya tiene los datos XML."
              : "Revisa el detalle. Si no se guardó, cierra el Excel y vuelve a ejecutar."
          }
          nextLabel={onGoToNextStage ? "Ir al paso 5" : undefined}
          onNext={onGoToNextStage}
        />
      )}

      {analysis && (
        <Card>
          <CardHeader className="py-2">
            <CardTitle className="text-sm">Resumen</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Exitosas: <strong>{String((analysis.payload as { exitos?: number }).exitos ?? 0)}</strong>
            {" · "}
            Errores: <strong>{String((analysis.payload as { errores?: number }).errores ?? 0)}</strong>
            {" · "}
            Omitidas: <strong>{String((analysis.payload as { omitidos?: number }).omitidos ?? 0)}</strong>
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
          {logs.map((e) => (
            <div key={e.seq}>{String(e.payload.message ?? "")}</div>
          ))}
        </div>
      </details>
    </div>
  );
}
