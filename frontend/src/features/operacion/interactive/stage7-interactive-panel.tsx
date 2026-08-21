import { useRef, useState } from "react";
import { Loader2, Play, Square, Upload } from "lucide-react";
import type {
  Period,
  PagosCruzadoResult,
  PagosImportResult,
  PagosPreviewResponse,
  Step0OptionsResponse,
} from "@/shared/api/types";
import { useStage7ImportPagos, useStage7PreviewPagos } from "@/shared/api/queries";
import { mapApiErrorMessage, type ApiError } from "@/shared/api/client";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { cn } from "@/shared/lib/utils";
import type { UseQueryResult } from "@tanstack/react-query";
import { isSessionRunning, useInteractiveSession } from "./use-interactive-session";
import { usePeriodOperationGuard } from "../period-operation-context";
import { ActiveSessionCard, SessionDoneCard } from "./session-recovery-cards";
import { OutlookHealthBanner, outlookBlocksStart } from "./outlook-health-banner";

type Props = {
  selectedPeriod: Period;
  options: UseQueryResult<Step0OptionsResponse>;
  baseUrl: string;
  apiKey: string;
  disabled?: boolean;
  onGoToNextStage?: () => void;
};

function importPayload(res: PagosImportResult & { pagos_import?: PagosImportResult }): PagosImportResult {
  if (res.pagos_import) return res.pagos_import;
  return res;
}

function money(n?: number | null) {
  if (n == null || Number.isNaN(n)) return "—";
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

function CruzadoReport({ cruzado }: { cruzado: PagosCruzadoResult }) {
  const totals = cruzado.totals;
  return (
    <div
      className={cn(
        "mt-3 space-y-2 rounded-md border p-3 text-[0.8125rem]",
        cruzado.ok ? "border-success/30 bg-success/10" : "border-danger/30 bg-danger/10"
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={cn(
            "rounded-md px-2 py-0.5 text-2xs font-semibold",
            cruzado.ok ? "bg-success/20 text-success" : "bg-danger/20 text-danger"
          )}
        >
          {cruzado.ok ? "Coincide con informe" : "Hay diferencias"}
        </span>
        <span className="text-muted-foreground">
          Match {cruzado.matched} · errores {cruzado.errors_count} · avisos {cruzado.warnings_count}
        </span>
      </div>
      {cruzado.message ? <p>{cruzado.message}</p> : null}
      {totals ? (
        <p className="text-2xs text-muted-foreground">
          Bruto informe {money(totals.informe_bruto)} vs Contabilidad {money(totals.pagos_bruto)}
          {totals.bruto_diff ? ` (Δ ${money(totals.bruto_diff)})` : ""}
          {" · "}
          Líquido {money(totals.informe_liquido)} vs {money(totals.pagos_liquido)}
          {" · "}
          Filas {totals.informe_count ?? "—"} / {totals.pagos_count ?? "—"}
        </p>
      ) : null}

      {cruzado.only_in_informe.length > 0 ? (
        <div>
          <p className="font-medium">Solo en informe ({cruzado.only_in_informe.length})</p>
          <ul className="mt-1 max-h-24 overflow-auto text-2xs">
            {cruzado.only_in_informe.slice(0, 20).map((r) => (
              <li key={`inf-${r.rut}-${r.boleta}`}>
                {r.nombre || r.rut} · boleta {r.boleta || "—"} · {r.rut}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {cruzado.only_in_pagos.length > 0 ? (
        <div>
          <p className="font-medium">Solo en Contabilidad ({cruzado.only_in_pagos.length})</p>
          <ul className="mt-1 max-h-24 overflow-auto text-2xs">
            {cruzado.only_in_pagos.slice(0, 20).map((r) => (
              <li key={`pag-${r.rut}-${r.boleta}`}>
                {r.nombre || r.rut} · boleta {r.boleta || "—"} · {r.rut}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {cruzado.amount_mismatches.length > 0 ? (
        <div>
          <p className="font-medium">Montos distintos ({cruzado.amount_mismatches.length})</p>
          <ul className="mt-1 max-h-28 overflow-auto text-2xs">
            {cruzado.amount_mismatches.slice(0, 30).map((m) => (
              <li key={`amt-${m.rut}-${m.boleta}-${m.field}`}>
                {m.rut} boleta {m.boleta}: {m.field} informe {money(m.expected as number | null)} vs
                Contabilidad {money(m.got as number | null)}
                {m.diff != null ? ` (Δ ${money(m.diff)})` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {cruzado.pct_mismatches.length > 0 ? (
        <div>
          <p className="font-medium">% retención distinto ({cruzado.pct_mismatches.length})</p>
          <ul className="mt-1 max-h-24 overflow-auto text-2xs">
            {cruzado.pct_mismatches.slice(0, 20).map((m) => (
              <li key={`pct-${m.rut}-${m.boleta}`}>
                {m.rut} boleta {m.boleta}: {String(m.expected)}% vs {String(m.got)}%
                {m.source ? ` (${m.source})` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {cruzado.warnings.length > 0 ? (
        <div>
          <p className="font-medium text-muted-foreground">Advertencias ({cruzado.warnings.length})</p>
          <ul className="mt-1 max-h-20 overflow-auto text-2xs text-muted-foreground">
            {cruzado.warnings.slice(0, 15).map((w, i) => (
              <li key={`w-${i}`}>
                {w.rut ? `${w.rut} ` : ""}
                {w.boleta ? `boleta ${w.boleta}: ` : ""}
                {w.message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export function Stage7InteractivePanel({
  selectedPeriod,
  options,
  baseUrl,
  apiKey,
  disabled,
  onGoToNextStage,
}: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const { confirmBeforeOperation } = usePeriodOperationGuard();
  const importPagos = useStage7ImportPagos(baseUrl, apiKey);
  const previewPagos = useStage7PreviewPagos(baseUrl, apiKey);

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

  const [paste, setPaste] = useState("");
  const [importResult, setImportResult] = useState<PagosImportResult | null>(null);
  const [fechaPago, setFechaPago] = useState("");
  const [forceResend, setForceResend] = useState(false);
  const [preview, setPreview] = useState<PagosPreviewResponse | null>(null);
  const [sendConfirm, setSendConfirm] = useState(false);
  const [cruzadoOverride, setCruzadoOverride] = useState(false);
  const [outlookOverride, setOutlookOverride] = useState(false);
  const [starting, setStarting] = useState(false);
  const [resolvingActive, setResolvingActive] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const summary = [...events].reverse().find((e) => e.type === "session.summary");
  const logs = events.filter((e) => e.type === "log");
  const done = session?.status === "completed" || Boolean(summary);
  const running = isSessionRunning(session?.status);
  const outlookHealth = options.data?.outlook_health;
  const outlookBlocks = outlookBlocksStart(outlookHealth, outlookOverride);
  const busy = Boolean(disabled || running || starting || importPagos.isPending || previewPagos.isPending);
  const cruzado = importResult?.cruzado;
  const cruzadoBlocks = Boolean(cruzado && !cruzado.ok && !cruzadoOverride);

  async function handleImport(file?: File) {
    setLocalError(null);
    setPreview(null);
    setCruzadoOverride(false);
    if (!file && !paste.trim()) {
      setLocalError("Pegá la tabla del correo de Contabilidad o subí un CSV/Excel.");
      return;
    }
    try {
      const res = await importPagos.mutateAsync({
        year: selectedPeriod.year,
        month: selectedPeriod.month_name,
        paste: file ? undefined : paste,
        file,
      });
      const payload = importPayload(res as PagosImportResult & { pagos_import?: PagosImportResult });
      setImportResult(payload);
    } catch (e) {
      setLocalError(mapApiErrorMessage(e as ApiError) || "No se pudo importar pagos");
    }
  }

  async function handlePreview() {
    setLocalError(null);
    if (cruzadoBlocks) {
      setLocalError("Hay diferencias con el informe. Corrigelas o marca «Continuar pese a diferencias».");
      return;
    }
    if (!fechaPago.trim()) {
      setLocalError("Indica la fecha de pago (dd/mm/aaaa).");
      return;
    }
    try {
      const res = await previewPagos.mutateAsync({
        year: selectedPeriod.year,
        month: selectedPeriod.month_name,
        fecha_pago: fechaPago.trim(),
        force_resend: forceResend,
      });
      setPreview(res);
    } catch (e) {
      setLocalError(mapApiErrorMessage(e as ApiError) || "No se pudo previsualizar");
    }
  }

  async function handleSend() {
    setLocalError(null);
    if (cruzadoBlocks) {
      setLocalError("Hay diferencias con el informe. Corrigelas o marca «Continuar pese a diferencias».");
      return;
    }
    if (outlookBlocks) {
      setLocalError("Outlook no está listo. Ábrelo o confirma continuar de todos modos.");
      return;
    }
    if (!fechaPago.trim()) {
      setLocalError("Indica la fecha de pago.");
      return;
    }
    if (!preview || preview.ready < 1) {
      setLocalError("Primero genera la previsualización con al menos un correo listo.");
      return;
    }
    if (!sendConfirm) {
      setLocalError("Confirma el envío real antes de despachar.");
      return;
    }
    if (!(await confirmBeforeOperation())) return;
    setStarting(true);
    try {
      await startSession(7, {
        year: selectedPeriod.year,
        month: selectedPeriod.month_name,
        send: true,
        fecha_pago: fechaPago.trim(),
        force_resend: forceResend,
        supervision_mode: "batch",
        streamlined: true,
      });
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "No se pudo iniciar el envío");
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

  return (
    <div className="space-y-3">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Paso 7 — Pagos Contabilidad y correos</CardTitle>
          <p className="text-[0.8125rem] font-normal leading-snug text-muted-foreground">
            Contabilidad manda la tabla en el correo: subí el <strong>.eml</strong> o el{" "}
            <strong>.csv</strong> (evitá un .xlsx vacío). Completamos MAIL/SEDE, cruzamos con el
            informe, pedimos fecha, previsualizamos y enviamos.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <OutlookHealthBanner
            health={outlookHealth}
            blockStart
            allowOverride
            override={outlookOverride}
            onOverrideChange={setOutlookOverride}
          />

          {activeSessionId && !running && !done ? (
            <ActiveSessionCard
              sessionId={activeSessionId}
              busy={resolvingActive}
              onResume={() => void handleResumeActive()}
              onCancel={() => void cancelSessionById(activeSessionId)}
            />
          ) : null}

          <section className="space-y-2">
            <p className="text-sm font-medium tracking-tight">1. Tabla de Contabilidad</p>
            <textarea
              className="min-h-[120px] w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              placeholder="Copiá la tabla del correo de Contabilidad y pégala aquí (celdas o HTML)…"
              value={paste}
              disabled={busy}
              onChange={(e) => setPaste(e.target.value)}
            />
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                disabled={busy || !paste.trim()}
                onClick={() => void handleImport()}
              >
                {importPagos.isPending ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                ) : null}
                Cargar pegado → hoja Pagos
              </Button>
              <input
                ref={fileRef}
                type="file"
                className="hidden"
                accept=".xlsx,.xlsm,.csv,.eml,.html,.htm,text/csv,text/html,message/rfc822,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.target.value = "";
                  if (file) void handleImport(file);
                }}
              />
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() => fileRef.current?.click()}
              >
                <Upload className="mr-1.5 h-3.5 w-3.5" />
                Subir .eml / CSV / Excel
              </Button>
            </div>
            {importResult ? (
              <div className="rounded-md border border-border/80 bg-muted/20 p-3 text-[0.8125rem]">
                <p>
                  {importResult.message ||
                    `${importResult.rows} fila(s) en Pagos · sin MAIL ${importResult.missing_mail} · sin SEDE ${importResult.missing_sede ?? 0}`}
                </p>
                {importResult.sample && importResult.sample.length > 0 ? (
                  <div className="mt-2 overflow-x-auto">
                    <table className="w-full text-left text-2xs">
                      <thead>
                        <tr className="text-muted-foreground">
                          <th className="py-1 pr-2">Nombre</th>
                          <th className="py-1 pr-2">SEDE</th>
                          <th className="py-1 pr-2">MAIL</th>
                          <th className="py-1 pr-2">Líquido</th>
                        </tr>
                      </thead>
                      <tbody>
                        {importResult.sample.map((r) => (
                          <tr key={`${r.id}-${r.mail}`} className="border-t border-border/60">
                            <td className="py-1 pr-2">{r.nombre || r.id}</td>
                            <td className="py-1 pr-2">{r.sede || "—"}</td>
                            <td className="py-1 pr-2">{r.mail || "—"}</td>
                            <td className="py-1 pr-2">{String(r.liquido ?? "—")}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
                {cruzado ? <CruzadoReport cruzado={cruzado} /> : null}
                {cruzado && !cruzado.ok ? (
                  <label className="mt-2 flex items-center gap-2 text-[0.8125rem]">
                    <input
                      type="checkbox"
                      className="rounded border-border"
                      checked={cruzadoOverride}
                      disabled={busy}
                      onChange={(e) => setCruzadoOverride(e.target.checked)}
                    />
                    Continuar pese a diferencias (no recomendado)
                  </label>
                ) : null}
              </div>
            ) : null}
          </section>

          <section className="space-y-2">
            <p className="text-sm font-medium tracking-tight">2. Fecha de pago</p>
            <div className="flex flex-wrap items-end gap-3">
              <label className="space-y-1 text-[0.8125rem]">
                <span className="text-muted-foreground">dd/mm/aaaa</span>
                <Input
                  value={fechaPago}
                  disabled={busy}
                  placeholder="31/07/2026"
                  className="w-40"
                  onChange={(e) => {
                    setFechaPago(e.target.value);
                    setPreview(null);
                  }}
                />
              </label>
              <label className="flex items-center gap-2 text-[0.8125rem]">
                <input
                  type="checkbox"
                  className="rounded border-border"
                  checked={forceResend}
                  disabled={busy}
                  onChange={(e) => {
                    setForceResend(e.target.checked);
                    setPreview(null);
                  }}
                />
                Forzar reenvío
              </label>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={busy || cruzadoBlocks}
                onClick={() => void handlePreview()}
              >
                {previewPagos.isPending ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                ) : null}
                Previsualizar correos
              </Button>
            </div>
            {cruzadoBlocks ? (
              <p className="text-2xs text-danger">
                Previsualización bloqueada hasta corregir el cruzado o marcar override.
              </p>
            ) : null}
          </section>

          {preview ? (
            <section className="space-y-2">
              <p className="text-sm font-medium tracking-tight">3. Previsualización</p>
              <p className="text-[0.8125rem] text-muted-foreground">
                Listos {preview.ready} · sin mail {preview.skipped_no_mail} · ya enviados{" "}
                {preview.skipped_already} · filas hoja {preview.total_rows}
              </p>
              <div className="max-h-80 overflow-auto rounded-md border border-border">
                <table className="w-full text-left text-[0.8125rem]">
                  <thead className="sticky top-0 bg-muted/80 text-muted-foreground">
                    <tr>
                      <th className="px-2 py-1.5">Docente</th>
                      <th className="px-2 py-1.5">Boleta</th>
                      <th className="px-2 py-1.5">Bruto</th>
                      <th className="px-2 py-1.5">Ret. / %</th>
                      <th className="px-2 py-1.5">Líquido</th>
                      <th className="px-2 py-1.5">Correo</th>
                      <th className="px-2 py-1.5">Depósito</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.candidates.map((c) => (
                      <tr key={c.idempotency_key} className="border-t border-border/70 align-top">
                        <td className="px-2 py-1.5">
                          <div className="font-medium">{c.nombre}</div>
                          <div className="text-2xs text-muted-foreground">
                            {c.id} · {c.sede || "—"}
                            {c.ubicacion ? ` · ubi ${c.ubicacion}` : ""}
                          </div>
                          {c.descripcion ? (
                            <div className="text-2xs text-muted-foreground">{c.descripcion}</div>
                          ) : null}
                        </td>
                        <td className="px-2 py-1.5 tabular-nums">{c.boleta || "—"}</td>
                        <td className="px-2 py-1.5 tabular-nums">{c.bruto_txt || "—"}</td>
                        <td className="px-2 py-1.5 tabular-nums text-2xs">
                          {c.retencion_txt || "—"}
                          {c.pct_retencion != null ? (
                            <div className="text-muted-foreground">{c.pct_retencion}%</div>
                          ) : null}
                        </td>
                        <td className="px-2 py-1.5 font-medium tabular-nums">{c.monto_txt}</td>
                        <td className="px-2 py-1.5 text-2xs">{c.mail}</td>
                        <td className="px-2 py-1.5 text-2xs">
                          {c.banco || "—"} · {c.forma_pago || "—"}
                          <br />
                          {c.cuenta || "—"}
                          {c.tipo_documento ? (
                            <>
                              <br />
                              {c.tipo_documento}
                            </>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {preview.candidates[0]?.subject ? (
                <p className="text-2xs text-muted-foreground">
                  Asunto ejemplo: {preview.candidates[0].subject}
                </p>
              ) : null}
            </section>
          ) : null}

          <section className="space-y-2 border-t border-border/70 pt-3">
            <label className="flex items-center gap-2 text-[0.8125rem]">
              <input
                type="checkbox"
                className="rounded border-border"
                checked={sendConfirm}
                disabled={busy || !preview || preview.ready < 1 || cruzadoBlocks}
                onChange={(e) => setSendConfirm(e.target.checked)}
              />
              Confirmo envío real a los docentes listados
            </label>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={busy || outlookBlocks || cruzadoBlocks || !preview || preview.ready < 1}
                onClick={() => void handleSend()}
              >
                {starting || running ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Play className="mr-1.5 h-3.5 w-3.5" />
                )}
                Enviar correos de pago
              </Button>
              {running ? (
                <Button type="button" size="sm" variant="outline" onClick={() => void cancelSession()}>
                  <Square className="mr-1.5 h-3.5 w-3.5" />
                  Cancelar
                </Button>
              ) : null}
            </div>
          </section>

          {(localError || error) && (
            <p className="text-sm text-danger">{localError || error}</p>
          )}
          {connected && running ? (
            <p className="text-2xs text-muted-foreground">Sesión conectada…</p>
          ) : null}
        </CardContent>
      </Card>

      {pendingPrompt ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{pendingPrompt.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-sm text-muted-foreground">{pendingPrompt.message}</p>
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" onClick={() => void respond(pendingPrompt.prompt_id, "confirm")}>
                Confirmar
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => void respond(pendingPrompt.prompt_id, "skip")}
              >
                Omitir
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => void respond(pendingPrompt.prompt_id, "cancel")}
              >
                Cancelar
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {logs.length > 0 ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Registro</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="max-h-40 space-y-1 overflow-auto text-[0.8125rem] text-muted-foreground">
              {logs.slice(-40).map((e) => (
                <li key={e.seq}>{String((e.payload as { message?: string }).message ?? e.type)}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {done ? (
        <SessionDoneCard
          title="Paso 7 listo"
          detail="Correos de pago procesados. La hoja Pagos y el estado en BD quedan actualizados."
          nextLabel="Ir al paso 8"
          onNext={onGoToNextStage}
        />
      ) : null}
    </div>
  );
}
