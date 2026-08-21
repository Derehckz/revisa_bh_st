import { useEffect, useMemo, useState } from "react";
import { Loader2, Play, Square } from "lucide-react";
import type {
  Period,
  RecepcionAudience,
  RecepcionPreviewCandidate,
  ReenvioTipo,
  StageParamField,
  Step0OptionsResponse,
} from "@/shared/api/types";
import { apiPost } from "@/shared/api/client";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Select } from "@/shared/ui/select";
import { useToast } from "@/shared/ui/toast";
import type { UseQueryResult } from "@tanstack/react-query";
import { isSessionRunning, useInteractiveSession, type InteractiveEvent } from "./use-interactive-session";
import { usePeriodOperationGuard } from "../period-operation-context";
import { MailReviewPrompt } from "./mail-review-prompt";
import { ActiveSessionCard, SessionDoneCard } from "./session-recovery-cards";
import { OutlookHealthBanner, outlookBlocksStart } from "./outlook-health-banner";
import { ArrastrePreviewCard } from "../arrastre-preview-card";
import { cn } from "@/shared/lib/utils";

const MAIL_REVIEW_STAGES = new Set([5, 7]);
const EMAIL_SEND_STAGES = new Set([5, 7]);
const OUTLOOK_STAGES = new Set([5, 7]);

function parseStage0Stats(events: InteractiveEvent[]): {
  maestro: number;
  prov: number;
  filas: number;
  sinCorreo: number;
} | null {
  const table = [...events].reverse().find((e) => {
    if (e.type !== "table") return false;
    return /estad/i.test(String(e.payload.title ?? ""));
  });
  if (!table) return null;
  const rows = (table.payload.rows as Array<[string, string | number]> | undefined) ?? [];
  const map = new Map(rows.map(([k, v]) => [String(k), v]));
  const num = (label: string) => {
    const raw = map.get(label);
    const n = Number(raw);
    return Number.isFinite(n) ? n : 0;
  };
  return {
    maestro: num("Filas en maestro"),
    prov: num("Provisionados arrastrados"),
    filas: num("Filas en Solicitud.xlsx"),
    sinCorreo: num("Filas sin correo válido"),
  };
}

const STAGE_PRIMARY_CTA: Record<number, string> = {
  0: "Generar Solicitud del mes",
  5: "Enviar correos de recepción",
  6: "Generar informe final",
  7: "Enviar correos de pago",
  8: "Ejecutar clasificación",
  9: "Ejecutar paso 9",
  10: "Ejecutar revisión de carpetas",
};

const AUDIENCE_LABEL: Record<RecepcionAudience, string> = {
  ok: "Confirmación",
  error: "Error de boleta",
  reenvio: "Reenvío",
};

const REENVIO_TIPO_LABEL: Record<ReenvioTipo, string> = {
  recordatorio: "Recordatorio",
  boleta_incorrecta: "Boleta incorrecta",
};

function candidateAudienceLabel(c: RecepcionPreviewCandidate): string {
  if (c.audience === "reenvio" && c.reenvio_tipo) {
    return REENVIO_TIPO_LABEL[c.reenvio_tipo];
  }
  return AUDIENCE_LABEL[c.audience];
}

function candidateMatchesSelection(
  c: RecepcionPreviewCandidate,
  selected: {
    ok: boolean;
    error: boolean;
    recordatorio: boolean;
    boleta_incorrecta: boolean;
  }
): boolean {
  if (c.audience === "ok") return selected.ok;
  if (c.audience === "error") return selected.error;
  if (c.audience === "reenvio") {
    if (c.reenvio_tipo === "recordatorio") return selected.recordatorio;
    if (c.reenvio_tipo === "boleta_incorrecta") return selected.boleta_incorrecta;
    return selected.recordatorio || selected.boleta_incorrecta;
  }
  return false;
}

type Props = {
  stageNum: number;
  stageTitle: string;
  selectedPeriod: Period;
  options: UseQueryResult<Step0OptionsResponse>;
  baseUrl: string;
  apiKey: string;
  disabled?: boolean;
  maestroFile?: string;
  setMaestroFile?: (v: string) => void;
  bdFile?: string;
  setBdFile?: (v: string) => void;
  onGoToNextStage?: () => void;
  onGoToReminders?: () => void;
  noRecibidos?: number;
};

function initialParams(schema: StageParamField[], stageNum: number): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const f of schema) {
    if (f.type === "boolean") {
      if (f.name === "send" && EMAIL_SEND_STAGES.has(stageNum)) {
        out[f.name] = true;
      } else {
        out[f.name] = Boolean(f.default);
      }
    } else if (f.default != null && f.default !== "") {
      out[f.name] = f.default;
    }
  }
  return out;
}

export function BridgedInteractivePanel({
  stageNum,
  stageTitle,
  selectedPeriod,
  options,
  baseUrl,
  apiKey,
  disabled,
  maestroFile,
  setMaestroFile,
  bdFile,
  setBdFile,
  onGoToNextStage,
  onGoToReminders,
  noRecibidos = 0,
}: Props) {
  const schema = options.data?.params_schema ?? [];
  const [params, setParams] = useState<Record<string, unknown>>(() =>
    initialParams(schema, stageNum)
  );
  const [sendConfirm, setSendConfirm] = useState(false);
  const [sessionSendEnabled, setSessionSendEnabled] = useState(false);
  const [starting, setStarting] = useState(false);
  const [resolvingActive, setResolvingActive] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [outlookOverride, setOutlookOverride] = useState(false);
  const [openingReport, setOpeningReport] = useState(false);
  const [includeOk, setIncludeOk] = useState(true);
  const [includeError, setIncludeError] = useState(true);
  const [includeRecordatorio, setIncludeRecordatorio] = useState(true);
  const [includeBoletaIncorrecta, setIncludeBoletaIncorrecta] = useState(true);
  const { push } = useToast();

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

  useEffect(() => {
    setParams(initialParams(options.data?.params_schema ?? [], stageNum));
    setSendConfirm(false);
    setSessionSendEnabled(false);
    setOutlookOverride(false);
    setIncludeOk(true);
    setIncludeError(true);
    setIncludeRecordatorio(true);
    setIncludeBoletaIncorrecta(true);
  }, [stageNum, options.data?.params_schema, selectedPeriod.year, selectedPeriod.month_name]);

  const recepcionPreview = options.data?.choices?.recepcion_preview;
  const forceResend = Boolean(params.force_resend);
  const audienceSelection = useMemo(
    () => ({
      ok: includeOk,
      error: includeError,
      recordatorio: includeRecordatorio,
      boleta_incorrecta: includeBoletaIncorrecta,
    }),
    [includeOk, includeError, includeRecordatorio, includeBoletaIncorrecta]
  );
  const hasAudienceSelection =
    includeOk || includeError || includeRecordatorio || includeBoletaIncorrecta;

  const previewRows = useMemo(() => {
    const all = recepcionPreview?.candidates ?? [];
    return all.filter((c) => {
      if (!candidateMatchesSelection(c, audienceSelection)) return false;
      if (!forceResend && c.already_sent) return false;
      return true;
    });
  }, [recepcionPreview?.candidates, audienceSelection, forceResend]);

  const previewCounts = useMemo(() => {
    const base = { ok: 0, error: 0, recordatorio: 0, boleta_incorrecta: 0 };
    for (const c of previewRows) {
      if (c.audience === "ok") base.ok += 1;
      else if (c.audience === "error") base.error += 1;
      else if (c.reenvio_tipo === "recordatorio") base.recordatorio += 1;
      else if (c.reenvio_tipo === "boleta_incorrecta") base.boleta_incorrecta += 1;
    }
    return base;
  }, [previewRows]);

  const logs = events.filter((e) => e.type === "log" || e.type === "table");
  const stage0Stats = stageNum === 0 ? parseStage0Stats(events) : null;
  const summary = [...events].reverse().find((e) => e.type === "session.summary");
  const reportReady = [...events].reverse().find((e) => e.type === "report.ready");
  const lastPreview = [...events].reverse().find((e) => e.type === "mail.preview");
  const done = session?.status === "completed" || Boolean(summary);
  const running = isSessionRunning(session?.status);
  const wantsSend = EMAIL_SEND_STAGES.has(stageNum) && Boolean(params.send);
  const sessionSend = Boolean(session) ? sessionSendEnabled : wantsSend;
  const stage5Cta = useMemo(() => {
    if (stageNum !== 5) return STAGE_PRIMARY_CTA[stageNum] ?? `Ejecutar: ${stageTitle}`;
    const parts: string[] = [];
    if (includeOk) parts.push("confirmaciones");
    if (includeError) parts.push("errores de boleta");
    if (includeRecordatorio) parts.push("recordatorios");
    if (includeBoletaIncorrecta) parts.push("boletas incorrectas");
    if (!parts.length) return "Selecciona al menos un grupo";
    if (parts.length === 4) return "Enviar todos los correos de recepción";
    return `Enviar ${parts.join(" + ")}`;
  }, [stageNum, stageTitle, includeOk, includeError, includeRecordatorio, includeBoletaIncorrecta]);
  const primaryCta = stageNum === 5 ? stage5Cta : STAGE_PRIMARY_CTA[stageNum] ?? `Ejecutar: ${stageTitle}`;
  const outlookHealth = OUTLOOK_STAGES.has(stageNum) ? options.data?.outlook_health ?? null : null;
  const outlookBlocks = outlookBlocksStart(outlookHealth, outlookOverride);
  const canOpenReport =
    stageNum === 6 &&
    done &&
    (Boolean(reportReady) || Boolean((summary?.payload as { report_path?: string } | undefined)?.report_path));

  async function handleOpenReport() {
    setOpeningReport(true);
    setLocalError(null);
    try {
      const res = await apiPost<{ ok: boolean; message?: string; path?: string }>(
        baseUrl,
        apiKey,
        "/operations/local/open",
        {
          year: selectedPeriod.year,
          month: selectedPeriod.month_name,
          stage_num: 6,
          filename: "Solicitud.xlsx",
        }
      );
      push(res.message || "Abriendo Excel…", "success");
    } catch (e) {
      const msg =
        typeof e === "object" && e !== null && "message" in e
          ? String((e as { message: unknown }).message)
          : "No se pudo abrir el informe";
      setLocalError(msg);
      push(msg, "error");
    } finally {
      setOpeningReport(false);
    }
  }

  const sheetOptions = useMemo(() => {
    const sheets = options.data?.choices?.solicitud_sheets ?? [];
    return sheets.map((s) => ({ value: s, label: s }));
  }, [options.data?.choices?.solicitud_sheets]);

  function setField(name: string, value: unknown) {
    setParams((p) => ({ ...p, [name]: value }));
    if (name === "send" && !value) setSendConfirm(false);
  }

  async function handleStart() {
    setLocalError(null);
    if (outlookBlocks) {
      setLocalError("Outlook no está listo. Ábrelo o confirma continuar de todos modos.");
      return;
    }
    if (stageNum === 0 && (!maestroFile || !bdFile)) {
      setLocalError("Selecciona archivo maestro y BD docentes.");
      return;
    }
    if (stageNum === 8) {
      const mapVal = String(params.map_csv ?? "").trim();
      if (!mapVal) {
        setLocalError("Indica el CSV de clasificación (map) antes de iniciar el paso 8.");
        return;
      }
    }
    if (wantsSend && !sendConfirm) {
      setLocalError("Confirma el envío real a producción antes de iniciar.");
      return;
    }
    if (stageNum === 5 && !hasAudienceSelection) {
      setLocalError("Elige al menos un grupo: confirmaciones, errores, recordatorios o boletas incorrectas.");
      return;
    }
    if (stageNum === 7 && wantsSend && !String(params.fecha_pago ?? "").trim()) {
      setLocalError("Indica la fecha de pago antes de enviar correos del paso 7.");
      return;
    }
    if (!(await confirmBeforeOperation())) return;
    setStarting(true);
    try {
      const body: Record<string, unknown> = {
        year: selectedPeriod.year,
        month: selectedPeriod.month_name,
        streamlined: true,
        ...params,
      };
      if (stageNum === 5) {
        body.include_ok = includeOk;
        body.include_error = includeError;
        body.include_recordatorio = includeRecordatorio;
        body.include_boleta_incorrecta = includeBoletaIncorrecta;
        body.include_reenvio = includeRecordatorio || includeBoletaIncorrecta;
      }
      if (stageNum === 0) {
        body.maestro_file = maestroFile;
        body.bd_file = bdFile;
      }
      const sheetField = schema.find((f) => f.name === "sheet");
      if (sheetField && !body.sheet) {
        body.sheet =
          options.data?.choices?.solicitud_sheet_auto ??
          sheetOptions[0]?.value ??
          "Solicitud";
      }
      setSessionSendEnabled(Boolean(body.send));
      await startSession(stageNum, body);
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "No se pudo iniciar el paso");
      setSessionSendEnabled(false);
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

  function renderField(field: StageParamField) {
    if (field.type === "select_maestro" && setMaestroFile) {
      const files = options.data?.maestro_files ?? options.data?.choices?.maestro_files ?? [];
      return (
        <label key={field.name} className="block text-sm space-y-1">
          <span>{field.label}</span>
          <Select value={maestroFile ?? ""} onChange={(e) => setMaestroFile(e.target.value)} disabled={Boolean(session) || disabled}>
            <option value="">—</option>
            {files.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </Select>
        </label>
      );
    }
    if (field.type === "select_bd" && setBdFile) {
      const files = options.data?.bd_candidates ?? options.data?.choices?.bd_candidates ?? [];
      return (
        <label key={field.name} className="block text-sm space-y-1">
          <span>{field.label}</span>
          <Select value={bdFile ?? ""} onChange={(e) => setBdFile(e.target.value)} disabled={Boolean(session) || disabled}>
            <option value="">—</option>
            {files.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </Select>
        </label>
      );
    }
    if (field.type === "select_sheet") {
      const val = String(params.sheet ?? options.data?.choices?.solicitud_sheet_auto ?? "");
      return (
        <label key={field.name} className="block text-sm space-y-1">
          <span>{field.label}</span>
          <Select
            value={val}
            onChange={(e) => setField("sheet", e.target.value)}
            disabled={Boolean(session) || disabled}
          >
            {sheetOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        </label>
      );
    }
    if (field.type === "select_path" || field.type === "select") {
      const opts = field.options ?? [];
      return (
        <label key={field.name} className="block text-sm space-y-1">
          <span>{field.label}</span>
          <Select
            value={String(params[field.name] ?? field.default ?? "")}
            onChange={(e) => setField(field.name, e.target.value)}
            disabled={Boolean(session) || disabled}
          >
            {opts.length === 0 ? <option value="">—</option> : null}
            {opts.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
          {field.help ? (
            <span className="block text-xs text-muted-foreground font-normal">{field.help}</span>
          ) : null}
        </label>
      );
    }
    if (field.type === "boolean") {
      return (
        <label key={field.name} className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={Boolean(params[field.name])}
            onChange={(e) => setField(field.name, e.target.checked)}
            disabled={Boolean(session) || disabled}
          />
          <span>
            {field.label}
            {field.help ? (
              <span className="block text-xs text-muted-foreground font-normal">{field.help}</span>
            ) : null}
          </span>
        </label>
      );
    }
    return (
      <label key={field.name} className="block text-sm space-y-1">
        <span>{field.label}</span>
        <input
          type="text"
          className="w-full rounded border border-input bg-background px-2 py-1 text-sm"
          value={String(params[field.name] ?? "")}
          onChange={(e) => setField(field.name, e.target.value)}
          disabled={Boolean(session) || disabled}
          placeholder={field.help}
        />
      </label>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-base">
            {stageNum === 0 ? "Paso 0 — Generar Solicitud" : stageTitle}
          </CardTitle>
          <p className="text-xs text-muted-foreground font-normal">
            {stageNum === 0
              ? "Crea la planilla del mes con maestro y BD docentes. Un solo clic."
              : "Ejecuta el paso con los datos ya elegidos. Confirma solo envíos reales."}
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          {OUTLOOK_STAGES.has(stageNum) && (
            <OutlookHealthBanner
              health={outlookHealth}
              blockStart
              override={outlookOverride}
              onOverrideChange={setOutlookOverride}
            />
          )}
          <p className="text-sm">
            Período:{" "}
            <strong>
              {selectedPeriod.month_name} {selectedPeriod.year}
            </strong>
          </p>
          {stageNum === 0 && (
            <ArrastrePreviewCard
              preview={options.data?.arrastre_preview}
              loading={options.isFetching}
            />
          )}
          {stageNum === 5 && (
            <Stage5AudiencePicker
              includeOk={includeOk}
              includeError={includeError}
              includeRecordatorio={includeRecordatorio}
              includeBoletaIncorrecta={includeBoletaIncorrecta}
              onIncludeOk={setIncludeOk}
              onIncludeError={setIncludeError}
              onIncludeRecordatorio={setIncludeRecordatorio}
              onIncludeBoletaIncorrecta={setIncludeBoletaIncorrecta}
              counts={recepcionPreview?.counts}
              pendingCounts={previewCounts}
              rows={previewRows}
              forceResend={forceResend}
              disabled={Boolean(session) || Boolean(disabled)}
              previewError={recepcionPreview?.error}
            />
          )}
          {schema.map(renderField)}
          {wantsSend && (
            <label className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-900">
              <input
                type="checkbox"
                checked={sendConfirm}
                onChange={(e) => setSendConfirm(e.target.checked)}
                disabled={Boolean(session) || disabled}
              />
              Confirmo envío real a docentes (producción / Outlook)
            </label>
          )}
          {EMAIL_SEND_STAGES.has(stageNum) && !wantsSend && (
            <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              Sin envío real solo se revisa el flujo; no se despachan correos.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              disabled={
                running ||
                disabled ||
                starting ||
                outlookBlocks ||
                (wantsSend && !sendConfirm) ||
                (stageNum === 5 && !hasAudienceSelection)
              }
              onClick={() => void handleStart()}
            >
              {starting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Play className="h-4 w-4 mr-2" />}
              {primaryCta}
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
              {EMAIL_SEND_STAGES.has(stageNum)
                ? sessionSend
                  ? " · envío real"
                  : " · solo preview"
                : ""}
            </p>
          )}
          {(localError || error) && <p className="text-sm text-danger">{localError || error}</p>}
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
          title={
            stageNum === 0
              ? "Solicitud generada"
              : stageNum === 6
                ? "Informe final listo"
                : "Paso listo"
          }
          detail={
            stageNum === 0
              ? stage0Stats
                ? `${stage0Stats.filas} filas en Solicitud (${stage0Stats.maestro} del maestro + ${stage0Stats.prov} PROVISIONADO)${
                    stage0Stats.sinCorreo
                      ? `. Atención: ${stage0Stats.sinCorreo} sin correo válido — completa Docentes (no regeneres el paso 0) antes del envío.`
                      : ". Ya puedes enviar el paso 1."
                  }`
                : "Ya puedes enviar las solicitudes (paso 1)."
              : stageNum === 5 && noRecibidos > 0
                ? `Confirmaciones/observaciones listas. Quedan ${noRecibidos} NO RECIBIDO: envía recordatorios desde el paso 1.`
                : stageNum === 6
                  ? "Se actualizó la hoja «Resumen Boletas» en Solicitud.xlsx. Ábrela aquí o continúa al siguiente paso."
                  : "Revisa el detalle si hace falta."
          }
          openLabel={canOpenReport ? (openingReport ? "Abriendo…" : "Abrir informe en Excel") : undefined}
          onOpen={canOpenReport ? () => void handleOpenReport() : undefined}
          openBusy={openingReport}
          nextLabel={
            onGoToNextStage ? (stageNum === 0 ? "Ir al paso 1" : "Siguiente paso") : undefined
          }
          onNext={onGoToNextStage}
          secondaryLabel={
            stageNum === 5 && noRecibidos > 0 && onGoToReminders
              ? `Paso 1 · solo recordatorios (${noRecibidos})`
              : stageNum === 6 && canOpenReport
                ? "Descargar Solicitud.xlsx"
                : undefined
          }
          onSecondary={
            stageNum === 5 && noRecibidos > 0 && onGoToReminders
              ? onGoToReminders
              : stageNum === 6 && canOpenReport
                ? () => {
                    const url = `${baseUrl}/operations/period/file?year=${selectedPeriod.year}&month=${encodeURIComponent(selectedPeriod.month_name)}&filename=Solicitud.xlsx`;
                    void fetch(url, { headers: { "x-api-key": apiKey } })
                      .then(async (r) => {
                        if (!r.ok) throw new Error(`HTTP ${r.status}`);
                        const blob = await r.blob();
                        const blobUrl = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = blobUrl;
                        a.download = "Solicitud.xlsx";
                        a.click();
                        URL.revokeObjectURL(blobUrl);
                        push("Descarga iniciada", "success");
                      })
                      .catch(() => push("No se pudo descargar el archivo", "error"));
                  }
                : undefined
          }
        />
      )}

      {pendingPrompt &&
        (pendingPrompt.kind === "mail_review" && MAIL_REVIEW_STAGES.has(stageNum) ? (
          <MailReviewPrompt
            pendingPrompt={pendingPrompt}
            lastPreviewEvent={lastPreview}
            onAccept={() => respond("accept")}
            onSkip={() => respond("skip")}
            onCancel={() => respond("cancel")}
            acceptLabel={sessionSend ? "Enviar este correo" : "Continuar (sin enviar)"}
          />
        ) : (
          <Card className="border-warning/30 bg-warning/10">
            <CardHeader className="py-3">
              <CardTitle className="text-sm">{pendingPrompt.title || "Confirmación"}</CardTitle>
              <p className="text-xs text-muted-foreground whitespace-pre-wrap">{pendingPrompt.message}</p>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {pendingPrompt.kind === "choose" ? (
                ((pendingPrompt.payload.options as string[]) ?? []).map((opt) => (
                  <Button
                    key={opt}
                    type="button"
                    variant="outline"
                    className="text-sm h-8"
                    onClick={() => respond("accept", opt)}
                  >
                    {opt}
                  </Button>
                ))
              ) : pendingPrompt.kind === "text" ? (
                <Button
                  type="button"
                  className="text-sm h-8"
                  onClick={() => respond("accept", pendingPrompt.payload.default)}
                >
                  Usar valor por defecto
                </Button>
              ) : (
                <>
                  <Button type="button" className="text-sm h-8" onClick={() => respond("accept")}>
                    Sí
                  </Button>
                  <Button type="button" variant="outline" className="text-sm h-8" onClick={() => respond("reject")}>
                    No
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        ))}

      <details className="rounded-lg border border-border p-3">
        <summary className="text-sm cursor-pointer">Ver detalle técnico</summary>
        <div className="font-mono text-xs max-h-64 overflow-y-auto space-y-0.5 bg-muted/20 rounded p-2 mt-2">
          {logs.length === 0 && <p className="text-muted-foreground">Sin eventos aún.</p>}
          {logs.map((e) => {
            if (e.type === "table") {
              const title = String(e.payload.title ?? "Tabla");
              const rows = (e.payload.rows as Array<[string, string | number]> | undefined) ?? [];
              return (
                <div key={e.seq} className="space-y-0.5 py-1">
                  <p className="font-medium text-foreground">{title}</p>
                  {rows.map(([k, v]) => (
                    <p key={String(k)} className="text-muted-foreground">
                      {k}: {String(v)}
                    </p>
                  ))}
                </div>
              );
            }
            return (
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
            );
          })}
        </div>
      </details>
    </div>
  );
}

function Stage5AudiencePicker({
  includeOk,
  includeError,
  includeRecordatorio,
  includeBoletaIncorrecta,
  onIncludeOk,
  onIncludeError,
  onIncludeRecordatorio,
  onIncludeBoletaIncorrecta,
  counts,
  pendingCounts,
  rows,
  forceResend,
  disabled,
  previewError,
}: {
  includeOk: boolean;
  includeError: boolean;
  includeRecordatorio: boolean;
  includeBoletaIncorrecta: boolean;
  onIncludeOk: (v: boolean) => void;
  onIncludeError: (v: boolean) => void;
  onIncludeRecordatorio: (v: boolean) => void;
  onIncludeBoletaIncorrecta: (v: boolean) => void;
  counts?: {
    ok?: number;
    error?: number;
    reenvio?: number;
    recordatorio?: number;
    boleta_incorrecta?: number;
    ok_pending?: number;
    error_pending?: number;
    reenvio_pending?: number;
    recordatorio_pending?: number;
    boleta_incorrecta_pending?: number;
    already_sent?: number;
  };
  pendingCounts: { ok: number; error: number; recordatorio: number; boleta_incorrecta: number };
  rows: RecepcionPreviewCandidate[];
  forceResend: boolean;
  disabled?: boolean;
  previewError?: string;
}) {
  const totalPending = rows.length;

  return (
    <div className="space-y-3 rounded-lg border border-border bg-muted/20 p-3">
      <div>
        <p className="text-sm font-semibold tracking-tight">¿A quién enviar?</p>
        <p className="text-[0.8125rem] text-muted-foreground">
          Marca los grupos. La lista de abajo se actualiza al instante.
        </p>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <AudienceCheck
          checked={includeOk}
          onChange={onIncludeOk}
          disabled={disabled}
          title="Confirmaciones"
          detail="RECIBIDO — boleta OK"
          count={pendingCounts.ok}
          total={forceResend ? counts?.ok : counts?.ok_pending}
        />
        <AudienceCheck
          checked={includeError}
          onChange={onIncludeError}
          disabled={disabled}
          title="Errores de boleta recibida"
          detail="RECIBIDO CON ERROR o glosa distinta"
          count={pendingCounts.error}
          total={forceResend ? counts?.error : counts?.error_pending}
        />
        <AudienceCheck
          checked={includeRecordatorio}
          onChange={onIncludeRecordatorio}
          disabled={disabled}
          title="Recordatorios"
          detail="NO RECIBIDO — aún no llega boleta"
          count={pendingCounts.recordatorio}
          total={forceResend ? counts?.recordatorio : counts?.recordatorio_pending}
        />
        <AudienceCheck
          checked={includeBoletaIncorrecta}
          onChange={onIncludeBoletaIncorrecta}
          disabled={disabled}
          title="Boleta incorrecta"
          detail="NO RECIBIDO — llegó boleta descartada"
          count={pendingCounts.boleta_incorrecta}
          total={forceResend ? counts?.boleta_incorrecta : counts?.boleta_incorrecta_pending}
        />
      </div>
      {previewError ? (
        <p className="text-sm text-danger">No se pudo armar la vista previa: {previewError}</p>
      ) : (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">
            Previsualización · {totalPending} correo{totalPending === 1 ? "" : "s"}
            {forceResend ? " (incluye ya enviados)" : ""}
          </p>
          <div className="max-h-56 overflow-auto rounded-md border border-border/80 bg-card">
            {rows.length === 0 ? (
              <p className="px-3 py-4 text-sm text-muted-foreground">
                Nadie en estos grupos{forceResend ? "" : " pendiente"}. Cambia la selección o marca
                «Forzar reenvío».
              </p>
            ) : (
              <ul className="divide-y divide-border/70">
                {rows.map((r) => (
                  <li key={`${r.audience}-${r.row}-${r.email}`} className="px-3 py-2 text-sm">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="font-medium">{r.name || "Sin nombre"}</span>
                      <span
                        className={cn(
                          "rounded px-1.5 py-0.5 text-2xs font-semibold",
                          r.audience === "ok" && "bg-success/12 text-success",
                          r.audience === "error" && "bg-danger/12 text-danger",
                          r.reenvio_tipo === "recordatorio" && "bg-blue-500/12 text-blue-700",
                          r.reenvio_tipo === "boleta_incorrecta" && "bg-warning/15 text-warning"
                        )}
                      >
                        {candidateAudienceLabel(r)}
                        {r.already_sent ? " · ya enviado" : ""}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {[r.email, r.emplid, r.monto || "", r.numero_boleta !== "N/A" ? `#${r.numero_boleta}` : ""]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                    {r.problema ? (
                      <p className="mt-0.5 line-clamp-2 text-2xs text-muted-foreground">{r.problema}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function AudienceCheck({
  checked,
  onChange,
  disabled,
  title,
  detail,
  count,
  total,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  title: string;
  detail: string;
  count: number;
  total?: number;
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer flex-col gap-0.5 rounded-md border px-3 py-2 text-sm transition-colors",
        checked ? "border-primary/40 bg-primary/5" : "border-border bg-card",
        disabled && "cursor-not-allowed opacity-60"
      )}
    >
      <span className="flex items-center gap-2 font-medium">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          disabled={disabled}
        />
        {title}
        <span className="ml-auto tabular-nums text-xs text-muted-foreground">{count}</span>
      </span>
      <span className="pl-6 text-2xs text-muted-foreground">
        {detail}
        {typeof total === "number" ? ` · ${total} en Excel` : ""}
      </span>
    </label>
  );
}
