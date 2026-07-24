import { useEffect, useMemo, useState } from "react";
import { Loader2, Play, Square } from "lucide-react";
import type { Period, StageParamField, Step0OptionsResponse } from "@/shared/api/types";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Select } from "@/shared/ui/select";
import type { UseQueryResult } from "@tanstack/react-query";
import { isSessionRunning, useInteractiveSession } from "./use-interactive-session";
import { usePeriodOperationGuard } from "../period-operation-context";
import { MailReviewPrompt } from "./mail-review-prompt";
import { ActiveSessionCard, SessionDoneCard } from "./session-recovery-cards";
import { OutlookHealthBanner, outlookBlocksStart } from "./outlook-health-banner";

const MAIL_REVIEW_STAGES = new Set([5, 7]);
const EMAIL_SEND_STAGES = new Set([5, 7]);
const OUTLOOK_STAGES = new Set([5, 7]);

const STAGE_PRIMARY_CTA: Record<number, string> = {
  0: "Generar Solicitud del mes",
  5: "Enviar correos de recepción",
  6: "Ejecutar paso 6",
  7: "Enviar correos de pago",
  8: "Ejecutar clasificación",
  9: "Ejecutar paso 9",
  10: "Ejecutar paso 10",
};

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
  }, [stageNum, options.data?.params_schema]);

  const logs = events.filter((e) => e.type === "log");
  const summary = [...events].reverse().find((e) => e.type === "session.summary");
  const lastPreview = [...events].reverse().find((e) => e.type === "mail.preview");
  const done = session?.status === "completed" || Boolean(summary);
  const running = isSessionRunning(session?.status);
  const wantsSend = EMAIL_SEND_STAGES.has(stageNum) && Boolean(params.send);
  const sessionSend = Boolean(session) ? sessionSendEnabled : wantsSend;
  const primaryCta = STAGE_PRIMARY_CTA[stageNum] ?? `Ejecutar: ${stageTitle}`;
  const outlookHealth = OUTLOOK_STAGES.has(stageNum) ? options.data?.outlook_health ?? null : null;
  const outlookBlocks = outlookBlocksStart(outlookHealth, outlookOverride);

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

  const mapOptions = options.data?.choices?.map_csv_files ?? [];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-base">
            {stageNum === 0 ? "Paso 0 — Generar Solicitud" : stageTitle}
          </CardTitle>
          <p className="text-xs text-muted-foreground font-normal">
            {stageNum === 0
              ? "Crea Solicitud.xlsx del mes con maestro y BD docentes. Un solo clic."
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
          {stageNum === 8 && mapOptions.length > 0 && (
            <label className="block text-sm space-y-1">
              <span>CSV clasificación (map)</span>
              <Select
                value={String(params.map_csv ?? "")}
                onChange={(e) => setField("map_csv", e.target.value)}
                disabled={Boolean(session) || disabled}
              >
                <option value="">— elegir —</option>
                {mapOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
            </label>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              disabled={
                running || disabled || starting || outlookBlocks || (wantsSend && !sendConfirm)
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
          title={stageNum === 0 ? "Solicitud generada" : "Paso listo"}
          detail={
            stageNum === 0
              ? "Ya puedes enviar las solicitudes (paso 1)."
              : "Revisa el detalle si hace falta."
          }
          nextLabel={
            onGoToNextStage ? (stageNum === 0 ? "Ir al paso 1" : "Siguiente paso") : undefined
          }
          onNext={onGoToNextStage}
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
