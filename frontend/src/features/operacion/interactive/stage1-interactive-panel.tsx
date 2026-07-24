import { useEffect, useState } from "react";
import { Loader2, Mail, Play, Square } from "lucide-react";
import type { Period, Step0OptionsResponse } from "@/shared/api/types";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import type { UseQueryResult } from "@tanstack/react-query";
import { isSessionRunning, useInteractiveSession } from "./use-interactive-session";
import { usePeriodOperationGuard } from "../period-operation-context";
import { MailReviewPrompt } from "./mail-review-prompt";
import { ActiveSessionCard, SessionDoneCard } from "./session-recovery-cards";
import {
  InteractivePeriodExcelFields,
  usePeriodExcelDefaults,
  useSyncPeriodExcelDefaults,
  type PeriodExcelFieldValues,
} from "./interactive-period-excel-fields";
import { OutlookHealthBanner, outlookBlocksStart } from "./outlook-health-banner";

type Props = {
  selectedPeriod: Period;
  options: UseQueryResult<Step0OptionsResponse>;
  baseUrl: string;
  apiKey: string;
  disabled?: boolean;
  onGoToNextStage?: () => void;
};

export function Stage1InteractivePanel({
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
  const [periodExcel, setPeriodExcel] = useState<PeriodExcelFieldValues>(excelDefaults);
  useSyncPeriodExcelDefaults(excelDefaults, setPeriodExcel);

  const [sendReal, setSendReal] = useState(true);
  const [sendConfirm, setSendConfirm] = useState(false);
  const [forceResend, setForceResend] = useState(false);
  const [fechaLimiteRecepcion, setFechaLimiteRecepcion] = useState("");
  const [horarioRecepcion, setHorarioRecepcion] = useState("19:00");
  const [fechaLimiteRecordatorio, setFechaLimiteRecordatorio] = useState("");
  const [horarioRecordatorio, setHorarioRecordatorio] = useState("19:00");
  const [starting, setStarting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [sessionSendEnabled, setSessionSendEnabled] = useState(false);
  const [outlookOverride, setOutlookOverride] = useState(false);
  const outlookHealth = options.data?.outlook_health ?? null;
  const outlookBlocks = outlookBlocksStart(outlookHealth, outlookOverride);

  // Plazos del período (API: guardados del mes o sugeridos para este mes — no el .env viejo).
  useEffect(() => {
    const schema = options.data?.params_schema ?? [];
    if (!schema.length) return;
    const pick = (name: string) => schema.find((f) => f.name === name)?.default;
    const fr = pick("fecha_limite_recepcion");
    const hr = pick("horario_recepcion");
    const frec = pick("fecha_limite_recordatorio");
    const hrec = pick("horario_recordatorio");
    if (fr != null && String(fr).trim()) setFechaLimiteRecepcion(String(fr));
    if (hr != null && String(hr).trim()) setHorarioRecepcion(String(hr));
    if (frec != null && String(frec).trim()) setFechaLimiteRecordatorio(String(frec));
    if (hrec != null && String(hrec).trim()) setHorarioRecordatorio(String(hrec));
  }, [selectedPeriod.year, selectedPeriod.month_name, options.data?.params_schema]);

  const canStart = (!sendReal || sendConfirm) && !outlookBlocks;

  async function handleStart() {
    setLocalError(null);
    if (outlookBlocks) {
      setLocalError("Outlook no está listo. Ábrelo o confirma continuar de todos modos.");
      return;
    }
    if (!periodExcel.monthDir.trim()) {
      setLocalError("Indica la carpeta del período.");
      return;
    }
    if (!periodExcel.excelFile.trim()) {
      setLocalError("Selecciona el archivo Excel.");
      return;
    }
    if (!periodExcel.sheet.trim()) {
      setLocalError("Indica la hoja del Excel.");
      return;
    }
    if (sendReal && !sendConfirm) {
      setLocalError("Confirma el envío real a producción antes de iniciar.");
      return;
    }
    if (!(await confirmBeforeOperation())) return;
    setStarting(true);
    try {
      setSessionSendEnabled(sendReal);
      await startSession(1, {
        year: selectedPeriod.year,
        month: selectedPeriod.month_name,
        month_dir: periodExcel.monthDir.trim(),
        excel_file: periodExcel.excelFile.trim(),
        sheet: periodExcel.sheet.trim(),
        send: sendReal,
        force_resend: forceResend,
        strict: false,
        fecha_limite_recepcion: fechaLimiteRecepcion.trim(),
        horario_recepcion: horarioRecepcion.trim(),
        fecha_limite_recordatorio: fechaLimiteRecordatorio.trim(),
        horario_recordatorio: horarioRecordatorio.trim(),
        supervision_mode: "batch",
        streamlined: true,
      });
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "No se pudo iniciar el paso");
      setSessionSendEnabled(false);
    } finally {
      setStarting(false);
    }
  }

  async function handleResumeActive() {
    if (!activeSessionId) return;
    try {
      await attachToSession(activeSessionId);
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "No se pudo continuar");
    }
  }

  async function handleCancelActive() {
    if (!activeSessionId) return;
    try {
      await cancelSessionById(activeSessionId);
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "No se pudo cancelar");
    }
  }

  const logs = events.filter((e) => e.type === "log");
  const lastPreview = [...events].reverse().find((e) => e.type === "mail.preview");
  const summary = [...events].reverse().find((e) => e.type === "session.summary");
  const done = session?.status === "completed" || Boolean(summary);
  const running = isSessionRunning(session?.status);
  const sessionSend = Boolean(session) ? sessionSendEnabled : sendReal;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-[0.9375rem]">
            <Mail className="h-4 w-4 text-muted-foreground" strokeWidth={1.75} />
            Paso 1 — Enviar solicitudes
          </CardTitle>
          <p className="text-[0.8125rem] font-normal leading-snug text-muted-foreground">
            Envía el lote por Outlook con una sola confirmación. Outlook debe estar abierto en esta máquina.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <OutlookHealthBanner
            health={outlookHealth}
            blockStart
            override={outlookOverride}
            onOverrideChange={setOutlookOverride}
          />
          <label className="flex items-center gap-2 text-sm tracking-tight">
            <input
              type="checkbox"
              className="rounded border-border"
              checked={sendReal}
              onChange={(e) => {
                setSendReal(e.target.checked);
                if (!e.target.checked) setSendConfirm(false);
              }}
              disabled={Boolean(session) || disabled}
            />
            Enviar correos reales (producción / Outlook)
          </label>
          {sendReal && (
            <label className="flex items-center gap-2 rounded-md border border-danger/30 bg-danger/10 p-3 text-sm font-medium text-danger">
              <input
                type="checkbox"
                className="rounded border-border"
                checked={sendConfirm}
                onChange={(e) => setSendConfirm(e.target.checked)}
                disabled={Boolean(session) || disabled}
              />
              Confirmo envío real a docentes
            </label>
          )}
          {!sendReal && (
            <p className="text-[0.8125rem] text-muted-foreground">Solo vista previa: no se envían correos.</p>
          )}
          <details className="rounded-md border border-border/80 bg-muted/20">
            <summary className="cursor-pointer px-3 py-2 text-[0.8125rem] text-muted-foreground hover:text-foreground">
              Opciones (archivo, plazos, reenvío)
            </summary>
            <div className="space-y-3 border-t border-border/80 px-3 py-3">
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
                  className="rounded border-border"
                  checked={forceResend}
                  onChange={(e) => setForceResend(e.target.checked)}
                  disabled={Boolean(session) || disabled}
                />
                Forzar reenvío a quien ya recibió
              </label>
              <p className="text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">
                Plazo correo original
              </p>
              <label className="grid gap-1 text-[0.8125rem]">
                <span className="text-muted-foreground">Fecha límite recepción</span>
                <Input
                  value={fechaLimiteRecepcion}
                  onChange={(e) => setFechaLimiteRecepcion(e.target.value)}
                  disabled={Boolean(session) || disabled}
                />
              </label>
              <label className="grid gap-1 text-[0.8125rem]">
                <span className="text-muted-foreground">Horario</span>
                <Input
                  value={horarioRecepcion}
                  onChange={(e) => setHorarioRecepcion(e.target.value)}
                  disabled={Boolean(session) || disabled}
                />
              </label>
              <p className="text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">
                Plazo recordatorio
              </p>
              <label className="grid gap-1 text-[0.8125rem]">
                <span className="text-muted-foreground">Fecha</span>
                <Input
                  value={fechaLimiteRecordatorio}
                  onChange={(e) => setFechaLimiteRecordatorio(e.target.value)}
                  disabled={Boolean(session) || disabled}
                />
              </label>
              <label className="grid gap-1 text-[0.8125rem]">
                <span className="text-muted-foreground">Horario</span>
                <Input
                  value={horarioRecordatorio}
                  onChange={(e) => setHorarioRecordatorio(e.target.value)}
                  disabled={Boolean(session) || disabled}
                />
              </label>
            </div>
          </details>
          <div className="flex flex-wrap gap-2 pt-1">
            <Button
              type="button"
              onClick={() => void handleStart()}
              disabled={disabled || starting || running || !canStart}
            >
              {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {sendReal ? "Enviar solicitudes" : "Solo vista previa"}
            </Button>
            {running && (
              <Button type="button" variant="outline" onClick={() => void cancelSession()}>
                <Square className="h-4 w-4" />
                Cancelar
              </Button>
            )}
          </div>
          {running && (
            <p className="text-xs text-muted-foreground">
              En curso{connected ? " · en vivo" : " · reconectando…"}
              {sessionSend ? " · envío real" : " · solo preview"}
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
          onResume={() => void handleResumeActive()}
          onCancel={() => void handleCancelActive()}
        />
      )}

      {done && (
        <SessionDoneCard
          title="Paso 1 listo"
          detail="Revisa el detalle si hace falta. Siguiente: bajar boletas del correo."
          nextLabel={onGoToNextStage ? "Ir al paso 2" : undefined}
          onNext={onGoToNextStage}
        />
      )}

      {pendingPrompt &&
        (pendingPrompt.kind === "mail_review" ? (
          <MailReviewPrompt
            pendingPrompt={pendingPrompt}
            lastPreviewEvent={lastPreview}
            onAccept={() => respond("accept")}
            onSkip={() => respond("skip")}
            onCancel={() => respond("cancel")}
            acceptLabel={sessionSend ? "Enviar todos" : "Continuar (sin enviar)"}
          />
        ) : (
          <Card className="border-warning/30 bg-warning/10">
            <CardHeader className="py-3">
              <CardTitle className="text-sm">{pendingPrompt.title}</CardTitle>
              <p className="text-xs text-muted-foreground">{pendingPrompt.message}</p>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Button type="button" className="text-sm h-8 px-3" onClick={() => respond("accept")}>
                {sessionSend && pendingPrompt.title?.toLowerCase().includes("envío")
                  ? "Sí, enviar todos"
                  : "Sí / Continuar"}
              </Button>
              <Button type="button" className="text-sm h-8 px-3" variant="outline" onClick={() => respond("reject")}>
                No / Cancelar
              </Button>
            </CardContent>
          </Card>
        ))}

      <details className="rounded-lg border border-border p-3">
        <summary className="cursor-pointer text-sm text-muted-foreground">Ver detalle técnico</summary>
        <div className="font-mono text-xs max-h-64 overflow-y-auto space-y-0.5 bg-muted/20 rounded p-2 mt-2">
          {logs.length === 0 && <p className="text-muted-foreground">Sin eventos aún.</p>}
          {logs.map((e) => (
            <div
              key={e.seq}
              className={
                (e.payload.level as string) === "error"
                  ? "text-danger"
                  : (e.payload.level as string) === "success"
                    ? "text-green-600"
                    : ""
              }
            >
              {String(e.payload.message ?? "")}
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
