import { useMemo, useState } from "react";
import { Download, Loader2, Play, Square } from "lucide-react";
import type { Period } from "@/shared/api/types";
import { periodDateRange } from "@/shared/lib/period-dates";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { useInteractiveSession } from "./use-interactive-session";

type Props = {
  selectedPeriod: Period;
  baseUrl: string;
  apiKey: string;
  disabled?: boolean;
};

export function Stage2InteractivePanel({
  selectedPeriod,
  baseUrl,
  apiKey,
  disabled,
}: Props) {
  const range = useMemo(() => periodDateRange(selectedPeriod), [selectedPeriod]);
  const { session, events, pendingPrompt, connected, error, startSession, respond, cancelSession } =
    useInteractiveSession(baseUrl, apiKey);
  const [dryRun, setDryRun] = useState(false);
  const [starting, setStarting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const scanReady = [...events].reverse().find((e) => e.type === "scan.ready");
  const duplicates = [...events].reverse().find((e) => e.type === "duplicates.detected");
  const logs = events.filter((e) => e.type === "log");
  const filesSaved = events.filter((e) => e.type === "file.saved").length;

  const choiceOptions =
    (pendingPrompt?.payload?.options as string[] | undefined) ??
    (pendingPrompt?.kind === "choice" ? ["S", "A", "I"] : []);

  async function handleStart() {
    setLocalError(null);
    setStarting(true);
    try {
      await startSession(2, {
        year: selectedPeriod.year,
        month: selectedPeriod.month_name,
        fecha_inicio: range.inicio,
        fecha_fin: range.fin,
        dry_run: dryRun,
      });
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "No se pudo iniciar la sesión");
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card className="border-blue-500/30 bg-blue-500/5">
        <CardHeader className="py-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Download className="h-4 w-4" />
            Extracción supervisada desde Outlook
          </CardTitle>
          <p className="text-xs text-muted-foreground font-normal">
            Misma lógica que la consola. Revisa el escaneo, decide duplicados y ve cada archivo
            guardado en vivo.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm">
            Rango: <strong>{range.inicio}</strong> — <strong>{range.fin}</strong>
          </p>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              disabled={Boolean(session) || disabled}
            />
            Solo simular (dry-run, no guarda archivos)
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
              {filesSaved > 0 ? ` · ${filesSaved} archivo(s) procesado(s)` : ""}
            </p>
          )}
          {(localError || error) && (
            <p className="text-sm text-destructive">{localError || error}</p>
          )}
        </CardContent>
      </Card>

      {scanReady && (
        <Card>
          <CardHeader className="py-2">
            <CardTitle className="text-sm">Escaneo del buzón</CardTitle>
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
        <Card className="border-amber-500/50">
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
                  Sí, continuar
                </Button>
                <Button type="button" className="text-sm h-8" variant="outline" onClick={() => respond("reject")}>
                  No
                </Button>
                <Button type="button" className="text-sm h-8" variant="ghost" onClick={() => respond("cancel")}>
                  Cancelar
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
          <CardTitle className="text-sm">Consola en vivo</CardTitle>
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
