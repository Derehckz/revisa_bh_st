import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { apiPost, mapApiErrorMessage } from "@/shared/api/client";
import type { OperationJob, StageParamField, Step0OptionsResponse } from "@/shared/api/types";
import type { Period } from "@/shared/api/types";
import { defaultDateParamsForStage } from "@/shared/lib/period-dates";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { ErrorState } from "@/shared/ui/error-state";
import type { UseQueryResult } from "@tanstack/react-query";
import { GuidedStageFlow } from "./guided-stage-flow";
import { StageParamFields, buildConfirmSummary } from "./stage-param-fields";

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
    } else if (f.type === "select_path" && f.options?.length) {
      out[f.name] = f.options[0].value;
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
    const base = initialParams(options.data?.params_schema ?? []);
    if (stageNum === 8 && selectedPeriod) {
      base.map_csv = `${selectedPeriod.year}/${selectedPeriod.month_name}/map_ip_cft.csv`;
      base.no_interactive = true;
      base.dry_run = false;
      base.mover = true;
    }
    if (selectedPeriod) {
      Object.assign(base, defaultDateParamsForStage(stageNum, selectedPeriod));
    }
    const sheetField = (options.data?.params_schema ?? []).find((f) => f.name === "sheet");
    if (sheetField?.default) {
      base.sheet = sheetField.default;
    } else if (options.data?.choices?.solicitud_sheet_auto) {
      base.sheet = options.data.choices.solicitud_sheet_auto;
    }
    setParams(base);
    setSendConfirm(false);
  }, [stageNum, options.data?.params_schema, selectedPeriod]);

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
        if (f.name.startsWith("_ui_")) continue;
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

  const guide = options.data?.guide ?? {
    title: `Paso ${stageNum}`,
    summary: stageTitle,
    steps: [],
  };
  const confirmRows = buildConfirmSummary(schema, params);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Paso {stageNum}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <GuidedStageFlow
          guide={guide}
          choices={options.data?.choices}
          kpis={options.data?.period_kpis}
          checklist={options.data?.checklist}
          prereqOk={prereqOk}
          executeDisabled={disabled || !canRun}
          isExecuting={isStarting}
          executeLabel={
            isStarting ? (
              <span className="inline-flex items-center gap-2">
                <Loader2 size={14} className="animate-spin" />
                Iniciando…
              </span>
            ) : (
              `Ejecutar paso ${stageNum}`
            )
          }
          onExecute={() => void startStage()}
          configureContent={
            <>
              {isEmailStage && !wantsSend && (
                <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                  Sin marcar «Enviar correos reales» el sistema <strong>no envía</strong> correos (solo prepara el
                  proceso, igual que en consola sin --send).
                </p>
              )}
              <StageParamFields
                schema={schema}
                params={params}
                setField={setField}
                disabled={!prereqOk}
                selectedPeriod={selectedPeriod}
              />
              {isEmailStage && wantsSend && (
                <label className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-900">
                  <input
                    type="checkbox"
                    checked={sendConfirm}
                    onChange={(e) => setSendConfirm(e.target.checked)}
                  />
                  Confirmo que quiero enviar correos reales desde Outlook
                </label>
              )}
            </>
          }
          confirmSummary={
            <ul className="rounded-md border border-border divide-y text-sm">
              <li className="px-3 py-2 flex justify-between gap-2">
                <span className="text-muted-foreground">Período</span>
                <span className="font-medium">
                  {selectedPeriod?.month_name} {selectedPeriod?.year}
                </span>
              </li>
              {confirmRows.map((row) => (
                <li key={row.label} className="px-3 py-2 flex justify-between gap-2">
                  <span className="text-muted-foreground">{row.label}</span>
                  <span className="font-medium text-right">{row.value}</span>
                </li>
              ))}
              {confirmRows.length === 0 && (
                <li className="px-3 py-2 text-muted-foreground">Sin opciones adicionales para este paso.</li>
              )}
            </ul>
          }
        />

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
