import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { apiPost, mapApiErrorMessage } from "@/shared/api/client";
import type { OperationJob, StageParamField, Step0OptionsResponse } from "@/shared/api/types";
import type { Period } from "@/shared/api/types";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { ErrorState } from "@/shared/ui/error-state";
import type { UseQueryResult } from "@tanstack/react-query";

type Props = {
  stageNum: number;
  stageTitle: string;
  selectedPeriod: Period | undefined;
  options: UseQueryResult<Step0OptionsResponse>;
  isEmailStage?: boolean;
  disabled: boolean;
  onStarted: (job: OperationJob) => void;
  onError: (message: string) => void;
  baseUrl: string;
  apiKey: string;
};

function initialParams(schema: StageParamField[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const f of schema) {
    if (f.type === "boolean") {
      out[f.name] = f.default === true;
    } else if (f.default !== undefined && f.default !== null) {
      out[f.name] = f.default;
    } else {
      out[f.name] = "";
    }
  }
  return out;
}

export function GenericStagePanel({
  stageNum,
  stageTitle,
  selectedPeriod,
  options,
  isEmailStage,
  disabled,
  onStarted,
  onError,
  baseUrl,
  apiKey,
}: Props) {
  const schema = options.data?.params_schema ?? [];
  const [params, setParams] = useState<Record<string, unknown>>(() => initialParams(schema));
  const [isStarting, setIsStarting] = useState(false);
  const [sendConfirm, setSendConfirm] = useState(false);

  useEffect(() => {
    setParams(initialParams(options.data?.params_schema ?? []));
    setSendConfirm(false);
  }, [stageNum, options.data?.params_schema]);

  const prereqOk = options.data?.prerequisites?.ok !== false;
  const wantsSend = Boolean(params.send);

  const canRun = useMemo(() => {
    if (!prereqOk || !selectedPeriod) return false;
    for (const f of schema) {
      if (f.required && !params[f.name]) return false;
    }
    if (isEmailStage && wantsSend && !sendConfirm) return false;
    if (stageNum === 7 && wantsSend && !params.fecha_pago) return false;
    return true;
  }, [isEmailStage, params, prereqOk, schema, selectedPeriod, sendConfirm, stageNum, wantsSend]);

  function setField(name: string, value: unknown) {
    setParams((prev) => ({ ...prev, [name]: value }));
  }

  async function startStage() {
    if (!selectedPeriod) {
      onError("Selecciona un período.");
      return;
    }
    setIsStarting(true);
    try {
      const body: Record<string, unknown> = {
        year: selectedPeriod.year,
        month: selectedPeriod.month_name,
      };
      for (const f of schema) {
        const v = params[f.name];
        if (f.type === "boolean") {
          if (v) body[f.name] = true;
        } else if (v !== "" && v !== undefined && v !== null) {
          body[f.name] = v;
        }
      }
      const job = await apiPost<OperationJob>(baseUrl, apiKey, `/operations/stages/${stageNum}/start`, body);
      onStarted(job);
    } catch (error) {
      onError(mapApiErrorMessage(error as never));
    } finally {
      setIsStarting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Paso {stageNum} — {stageTitle}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {options.data?.prerequisites && !options.data.prerequisites.ok && (
          <p className="text-sm text-amber-800">{options.data.prerequisites.message}</p>
        )}

        {isEmailStage && (
          <p className="rounded-md border border-amber-200 bg-amber-50 p-2 text-sm text-amber-900">
            Etapa de correo: sin marcar &quot;Enviar correos reales&quot; solo se analiza el Excel (equivalente a consola
            con <code className="text-xs">--yes</code> sin <code className="text-xs">--send</code>).
          </p>
        )}

        {schema.map((field) => (
          <div key={field.name} className="space-y-1">
            {field.type === "boolean" ? (
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={Boolean(params[field.name])}
                  onChange={(e) => setField(field.name, e.target.checked)}
                  disabled={!prereqOk}
                />
                <span>{field.label}</span>
              </label>
            ) : (
              <>
                <p className="text-xs text-muted-foreground">
                  {field.label}
                  {field.required ? " *" : ""}
                </p>
                <input
                  className="w-full rounded-md border border-border bg-card px-2 py-1.5 text-sm"
                  value={String(params[field.name] ?? "")}
                  onChange={(e) => setField(field.name, e.target.value)}
                  placeholder={field.help || ""}
                  disabled={!prereqOk}
                />
              </>
            )}
            {field.help && field.type === "boolean" && (
              <p className="text-xs text-muted-foreground">{field.help}</p>
            )}
          </div>
        ))}

        {isEmailStage && wantsSend && (
          <label className="flex items-center gap-2 text-sm font-medium text-red-800">
            <input
              type="checkbox"
              checked={sendConfirm}
              onChange={(e) => setSendConfirm(e.target.checked)}
            />
            Confirmo envío real de correos
          </label>
        )}

        <Button onClick={() => void startStage()} disabled={disabled || isStarting || !canRun}>
          {isStarting ? (
            <span className="inline-flex items-center gap-2">
              <Loader2 size={14} className="animate-spin" />
              Iniciando...
            </span>
          ) : (
            `Ejecutar paso ${stageNum}`
          )}
        </Button>

        {options.isError && (
          <ErrorState
            title="No pudimos cargar opciones"
            description={mapApiErrorMessage(options.error as never)}
            onRetry={() => options.refetch()}
          />
        )}
      </CardContent>
    </Card>
  );
}
