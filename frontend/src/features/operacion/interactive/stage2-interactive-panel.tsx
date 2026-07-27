import { useEffect, useMemo, useState } from "react";
import { Download, Loader2, Play, Square } from "lucide-react";
import type { Period, Step0OptionsResponse } from "@/shared/api/types";
import { clToIso, periodDateRange } from "@/shared/lib/period-dates";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { DateInput } from "@/shared/ui/date-input";
import type { UseQueryResult } from "@tanstack/react-query";
import { isSessionRunning, useInteractiveSession } from "./use-interactive-session";
import { usePeriodOperationGuard } from "../period-operation-context";
import { ActiveSessionCard, SessionDoneCard } from "./session-recovery-cards";
import { OutlookHealthBanner, outlookBlocksStart } from "./outlook-health-banner";

type Props = {
  selectedPeriod: Period;
  options?: UseQueryResult<Step0OptionsResponse>;
  baseUrl: string;
  apiKey: string;
  disabled?: boolean;
  onGoToNextStage?: () => void;
};

export function Stage2InteractivePanel({
  selectedPeriod,
  options,
  baseUrl,
  apiKey,
  disabled,
  onGoToNextStage,
}: Props) {
  const monthDefaults = useMemo(() => periodDateRange(selectedPeriod), [selectedPeriod]);
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
  const [fechaInicio, setFechaInicio] = useState(monthDefaults.inicio);
  const [fechaFin, setFechaFin] = useState(monthDefaults.fin);
  const [dryRun, setDryRun] = useState(false);
  const [starting, setStarting] = useState(false);
  const [resolvingActive, setResolvingActive] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [outlookOverride, setOutlookOverride] = useState(false);
  const outlookHealth = options?.data?.outlook_health ?? null;
  const outlookBlocks = outlookBlocksStart(outlookHealth, outlookOverride);

  useEffect(() => {
    setFechaInicio(monthDefaults.inicio);
    setFechaFin(monthDefaults.fin);
  }, [monthDefaults.fin, monthDefaults.inicio]);

  const scanReady = [...events].reverse().find((e) => e.type === "scan.ready");
  const duplicates = [...events].reverse().find((e) => e.type === "duplicates.detected");
  const logs = events.filter((e) => e.type === "log");
  const filesSaved = events.filter((e) => e.type === "file.saved").length;
  const summary = [...events].reverse().find((e) => e.type === "session.summary");
  const done = session?.status === "completed" || Boolean(summary);
  const running = isSessionRunning(session?.status);

  const choiceOptions =
    (pendingPrompt?.payload?.options as string[] | undefined) ??
    (pendingPrompt?.kind === "choice" ? ["S", "A", "I"] : []);

  function validateDates(): string | null {
    if (!fechaInicio.trim() || !fechaFin.trim()) {
      return "Indica fecha inicio y fecha fin del filtro.";
    }
    const isoInicio = clToIso(fechaInicio);
    const isoFin = clToIso(fechaFin);
    if (!isoInicio || !isoFin) {
      return "Usa formato dd/mm/aaaa (ej. 01/05/2026).";
    }
    if (isoInicio > isoFin) {
      return "La fecha inicio no puede ser posterior a la fecha fin.";
    }
    return null;
  }

  async function handleStart() {
    setLocalError(null);
    if (outlookBlocks) {
      setLocalError("Outlook no está listo. Ábrelo o confirma continuar de todos modos.");
      return;
    }
    const dateErr = validateDates();
    if (dateErr) {
      setLocalError(dateErr);
      return;
    }
    if (!(await confirmBeforeOperation())) return;
    setStarting(true);
    try {
      await startSession(2, {
        year: selectedPeriod.year,
        month: selectedPeriod.month_name,
        fecha_inicio: fechaInicio.trim(),
        fecha_fin: fechaFin.trim(),
        dry_run: dryRun,
        streamlined: true,
        duplicate_policy: "S",
      });
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "No se pudo iniciar la sesión");
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
      setLocalError(e instanceof Error ? e.message : "No se pudo retomar la sesión activa");
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
      setLocalError(e instanceof Error ? e.message : "No se pudo cancelar la sesión activa");
    } finally {
      setResolvingActive(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Download className="h-4 w-4" />
            Paso 2 — Bajar boletas
          </CardTitle>
          <p className="text-xs text-muted-foreground font-normal">
            Descarga PDF y XML desde Outlook a la carpeta del mes. No modifica el Excel (eso es el
            paso 3). Outlook debe estar abierto.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <OutlookHealthBanner
            health={outlookHealth}
            blockStart
            override={outlookOverride}
            onOverrideChange={setOutlookOverride}
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">Fecha inicio (filtro Outlook)</span>
              <DateInput
                value={fechaInicio}
                onChange={setFechaInicio}
                disabled={running || disabled}
                minIso={monthDefaults.minIso}
                maxIso={monthDefaults.maxIso}
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">Fecha fin (filtro Outlook)</span>
              <DateInput
                value={fechaFin}
                onChange={setFechaFin}
                disabled={running || disabled}
                minIso={monthDefaults.minIso}
                maxIso={monthDefaults.maxIso}
              />
            </label>
          </div>
          <p className="text-xs text-muted-foreground">
            Rango del filtro Outlook (por defecto el mes: {monthDefaults.inicio} —{" "}
            {monthDefaults.fin}). Tú defines inicio y fin; solo se bajan correos en ese
            intervalo. Al reejecutar se sobrescriben archivos ya existentes con el mismo
            folio.
          </p>
          {fechaInicio.trim() !== monthDefaults.inicio && (
            <p className="text-xs text-muted-foreground">
              Inicio distinto al día 1 del mes.
              <button
                type="button"
                className="ml-2 underline"
                onClick={() => {
                  setFechaInicio(monthDefaults.inicio);
                  setFechaFin(monthDefaults.fin);
                }}
              >
                Usar mes completo
              </button>
            </p>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              disabled={running || disabled}
            />
            Solo simular (no guarda archivos en disco)
          </label>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              onClick={() => void handleStart()}
              disabled={disabled || starting || running || outlookBlocks}
            >
              {starting ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Play className="h-4 w-4 mr-2" />
              )}
              Bajar boletas del mes
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
              {filesSaved > 0 ? ` · ${filesSaved} archivo(s)` : ""}
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
          title="Boletas en la carpeta del mes"
          detail="PDF y XML listos. El Excel se actualiza en el paso 3."
          nextLabel={onGoToNextStage ? "Ir al paso 3" : undefined}
          onNext={onGoToNextStage}
        />
      )}

      {scanReady && (
        <Card>
          <CardHeader className="py-2">
            <CardTitle className="text-sm">Resumen de escaneo</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Correos con PDF+XML:{" "}
            <strong>{String((scanReady.payload as { emails_with_bhe?: number }).emails_with_bhe ?? 0)}</strong>
            {" · "}
            Adjuntos:{" "}
            <strong>
              {String((scanReady.payload as { attachments_planned?: number }).attachments_planned ?? 0)}
            </strong>
            {" · "}
            Duplicados:{" "}
            <strong>{String((scanReady.payload as { duplicates?: number }).duplicates ?? 0)}</strong>
          </CardContent>
        </Card>
      )}

      {pendingPrompt && (
        <Card className="border-warning/30 bg-warning/10">
          <CardHeader className="py-3">
            <CardTitle className="text-sm">{pendingPrompt.title}</CardTitle>
            <p className="text-xs text-muted-foreground">{pendingPrompt.message}</p>
          </CardHeader>
          <CardContent className="space-y-3">
            {duplicates && (
              <ul className="text-xs max-h-24 overflow-y-auto text-muted-foreground list-disc pl-4">
                {((duplicates.payload as { sample?: string[] }).sample ?? []).map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            )}
            {pendingPrompt.kind === "confirm" && (
              <div className="flex gap-2">
                <Button type="button" className="text-sm h-8" onClick={() => respond("accept")}>
                  Sí / Continuar
                </Button>
                <Button type="button" className="text-sm h-8" variant="outline" onClick={() => respond("reject")}>
                  No
                </Button>
                <Button type="button" className="text-sm h-8" variant="ghost" onClick={() => respond("cancel")}>
                  Cancelar sesión
                </Button>
              </div>
            )}
            {pendingPrompt.kind === "choice" && (
              <div className="flex flex-wrap gap-2">
                {choiceOptions.map((opt) => (
                  <Button
                    key={opt}
                    type="button"
                    className="text-sm h-8"
                    variant="outline"
                    onClick={() => respond("choice", opt)}
                  >
                    {opt === "S" && "Sobrescribir"}
                    {opt === "A" && "Sufijo"}
                    {opt === "I" && "Ignorar"}
                    {!["S", "A", "I"].includes(opt) && opt}
                  </Button>
                ))}
                <Button type="button" className="text-sm h-8" variant="ghost" onClick={() => respond("cancel")}>
                  Cancelar
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm">Registro en vivo</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="font-mono text-xs max-h-64 overflow-y-auto space-y-0.5 bg-muted/20 rounded p-2">
            {logs.length === 0 && <p className="text-muted-foreground">Sin eventos aún.</p>}
            {logs.map((e) => (
              <div key={e.seq}>{String(e.payload.message ?? "")}</div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
