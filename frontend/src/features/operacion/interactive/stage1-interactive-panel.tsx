import { useState } from "react";
import { Loader2, Mail, Play, Square } from "lucide-react";
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

export function Stage1InteractivePanel({
  selectedPeriod,
  options,
  baseUrl,
  apiKey,
  disabled,
}: Props) {
  const { session, events, pendingPrompt, connected, error, startSession, respond, cancelSession } =
    useInteractiveSession(baseUrl, apiKey);
  const [sendReal, setSendReal] = useState(false);
  const [forceResend, setForceResend] = useState(false);
  const [starting, setStarting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const sheetDefault =
    options.data?.params_schema?.find((f) => f.name === "sheet")?.default ??
    options.data?.choices?.solicitud_sheet_auto ??
    "Solicitud";

  async function handleStart() {
    setLocalError(null);
    setStarting(true);
    try {
      await startSession(1, {
        year: selectedPeriod.year,
        month: selectedPeriod.month_name,
        sheet: sheetDefault,
        send: sendReal,
        force_resend: forceResend,
        strict: false,
        supervision_mode: "per_mail",
      });
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "No se pudo iniciar la sesión");
    } finally {
      setStarting(false);
    }
  }

  const logs = events.filter((e) => e.type === "log");
  const lastPreview = [...events].reverse().find((e) => e.type === "mail.preview");

  return (
    <div className="space-y-4">
      <Card className="border-cyan-500/30 bg-cyan-500/5">
        <CardHeader className="py-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Mail className="h-4 w-4" />
            Envío supervisado (tiempo real)
          </CardTitle>
          <p className="text-xs text-muted-foreground font-normal">
            Misma lógica que la consola. Confirma cada correo antes de enviar. Requiere API y Outlook en
            este equipo.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={sendReal}
              onChange={(e) => setSendReal(e.target.checked)}
              disabled={Boolean(session) || disabled}
            />
            Enviar correos reales (sin marcar: solo análisis y vistas previas)
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={forceResend}
              onChange={(e) => setForceResend(e.target.checked)}
              disabled={Boolean(session) || disabled}
            />
            Forzar reenvío (ignorar idempotencia)
          </label>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              onClick={() => void handleStart()}
              disabled={disabled || starting || Boolean(session)}
            >
              {starting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Play className="h-4 w-4 mr-2" />}
              Iniciar sesión supervisada
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
              {connected ? " · conectado" : " · reconectando…"}
            </p>
          )}
          {(localError || error) && (
            <p className="text-sm text-destructive">{localError || error}</p>
          )}
        </CardContent>
      </Card>

      {pendingPrompt && (
        <Card className="border-amber-500/50">
          <CardHeader className="py-3">
            <CardTitle className="text-sm">{pendingPrompt.title}</CardTitle>
            <p className="text-xs text-muted-foreground">{pendingPrompt.message}</p>
          </CardHeader>
          <CardContent className="space-y-3">
            {pendingPrompt.kind === "mail_review" && lastPreview && (
              <div className="rounded border bg-muted/30 p-2 max-h-48 overflow-auto text-xs">
                <p className="font-medium mb-1">
                  {(lastPreview.payload as { mail?: { subject?: string } }).mail?.subject}
                </p>
                <iframe
                  title="Vista previa correo"
                  className="w-full h-40 bg-white rounded"
                  sandbox=""
                  srcDoc={String(
                    (lastPreview.payload as { mail?: { html_body?: string } }).mail?.html_body ?? ""
                  )}
                />
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              <Button type="button" className="text-sm h-8 px-3" onClick={() => respond("accept")}>
                Enviar
              </Button>
              <Button type="button" className="text-sm h-8 px-3" variant="ghost" onClick={() => respond("skip")}>
                Omitir
              </Button>
              <Button type="button" className="text-sm h-8 px-3" variant="outline" onClick={() => respond("cancel")}>
                Cancelar todo
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm">Consola en vivo</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="font-mono text-xs max-h-64 overflow-y-auto space-y-0.5 bg-muted/20 rounded p-2">
            {logs.length === 0 && <p className="text-muted-foreground">Sin eventos aún.</p>}
            {logs.map((e) => (
              <div
                key={e.seq}
                className={
                  (e.payload.level as string) === "error"
                    ? "text-destructive"
                    : (e.payload.level as string) === "success"
                      ? "text-green-600"
                      : ""
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
