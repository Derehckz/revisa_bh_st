import { useMemo, useState } from "react";
import { Loader2, Play, Square } from "lucide-react";
import type { Period, StageParamField, Step0OptionsResponse } from "@/shared/api/types";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Select } from "@/shared/ui/select";
import type { UseQueryResult } from "@tanstack/react-query";
import { useInteractiveSession } from "./use-interactive-session";

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
};

function initialParams(schema: StageParamField[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const f of schema) {
    if (f.type === "boolean") {
      out[f.name] = Boolean(f.default);
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
}: Props) {
  const schema = options.data?.params_schema ?? [];
  const [params, setParams] = useState<Record<string, unknown>>(() => initialParams(schema));
  const [starting, setStarting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const { session, events, pendingPrompt, connected, error, startSession, respond, cancelSession } =
    useInteractiveSession(baseUrl, apiKey);

  const logs = events.filter((e) => e.type === "log");
  const summary = [...events].reverse().find((e) => e.type === "session.summary");

  const sheetOptions = useMemo(() => {
    const sheets = options.data?.choices?.solicitud_sheets ?? [];
    return sheets.map((s) => ({ value: s, label: s }));
  }, [options.data?.choices?.solicitud_sheets]);

  function setField(name: string, value: unknown) {
    setParams((p) => ({ ...p, [name]: value }));
  }

  async function handleStart() {
    setLocalError(null);
    if (stageNum === 0 && (!maestroFile || !bdFile)) {
      setLocalError("Selecciona archivo maestro y BD docentes.");
      return;
    }
    setStarting(true);
    try {
      const body: Record<string, unknown> = {
        year: selectedPeriod.year,
        month: selectedPeriod.month_name,
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
      await startSession(stageNum, body);
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "No se pudo iniciar la sesión");
    } finally {
      setStarting(false);
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
      <Card className="border-primary/30 bg-primary/5">
        <CardHeader className="py-3">
          <CardTitle className="text-base">{stageTitle} (supervisada)</CardTitle>
          <p className="text-xs text-muted-foreground font-normal">
            Misma lógica que la consola; confirma cada paso desde el navegador.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm">
            Período:{" "}
            <strong>
              {selectedPeriod.month_name} {selectedPeriod.year}
            </strong>
          </p>
          {schema.map(renderField)}
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
            <Button type="button" disabled={Boolean(session) || disabled || starting} onClick={() => void handleStart()}>
              {starting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Play className="h-4 w-4 mr-2" />}
              Iniciar sesión
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
          {(localError || error) && <p className="text-sm text-destructive">{localError || error}</p>}
          {summary && (
            <p className="text-sm">
              Resultado:{" "}
              <strong>{(summary.payload as { ok?: boolean }).ok ? "OK" : "con errores"}</strong>
            </p>
          )}
        </CardContent>
      </Card>

      {pendingPrompt && (
        <Card className="border-amber-500/50">
          <CardHeader className="py-3">
            <CardTitle className="text-sm">{pendingPrompt.title || "Confirmación"}</CardTitle>
            <p className="text-xs text-muted-foreground whitespace-pre-wrap">{pendingPrompt.message}</p>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {pendingPrompt.kind === "choose" ? (
              ((pendingPrompt.payload.options as string[]) ?? []).map((opt) => (
                <Button key={opt} type="button" variant="outline" className="text-sm h-8" onClick={() => respond("accept", opt)}>
                  {opt}
                </Button>
              ))
            ) : pendingPrompt.kind === "text" ? (
              <Button type="button" className="text-sm h-8" onClick={() => respond("accept", pendingPrompt.payload.default)}>
                Usar valor por defecto
              </Button>
            ) : (
              <>
                <Button type="button" className="text-sm h-8" onClick={() => respond("accept")}>
                  Sí / Continuar
                </Button>
                <Button type="button" variant="outline" className="text-sm h-8" onClick={() => respond("reject")}>
                  No / Cancelar
                </Button>
              </>
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
