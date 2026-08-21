import { useEffect, useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { apiPost, mapApiErrorMessage } from "@/shared/api/client";
import type { OperationJob, Period } from "@/shared/api/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { ErrorState } from "@/shared/ui/error-state";
import { Select } from "@/shared/ui/select";
import type { UseQueryResult } from "@tanstack/react-query";
import type { Step0OptionsResponse } from "@/shared/api/types";
import { useValidateMaestro } from "@/shared/api/queries";
import { GuidedStageFlow } from "./guided-stage-flow";
import { ArrastrePreviewCard } from "./arrastre-preview-card";
import { usePeriodOperationGuard } from "./period-operation-context";

type Props = {
  selectedPeriod: Period | undefined;
  options: UseQueryResult<Step0OptionsResponse>;
  maestroFile: string;
  setMaestroFile: (v: string) => void;
  bdFile: string;
  setBdFile: (v: string) => void;
  disabled: boolean;
  isStarting: boolean;
  setIsStarting: (v: boolean) => void;
  onStarted: (job: OperationJob) => void;
  onError: (message: string) => void;
  baseUrl: string;
  apiKey: string;
};

export function Step0Panel({
  selectedPeriod,
  options,
  maestroFile,
  setMaestroFile,
  bdFile,
  setBdFile,
  disabled,
  isStarting,
  setIsStarting,
  onStarted,
  onError,
  baseUrl,
  apiKey,
}: Props) {
  const { confirmBeforeOperation } = usePeriodOperationGuard();
  const prereqOk = options.data?.prerequisites?.ok !== false;
  const validation = useValidateMaestro(
    baseUrl,
    apiKey,
    selectedPeriod?.year,
    selectedPeriod?.month_name,
    maestroFile || undefined
  );
  const maestroOk = validation.data?.ok !== false;
  const arrastre = options.data?.arrastre_preview;
  const canRun =
    prereqOk &&
    Boolean(maestroFile && bdFile && selectedPeriod) &&
    maestroOk &&
    !validation.isFetching;

  async function startStep0() {
    if (!selectedPeriod || !maestroFile || !bdFile) {
      onError("Selecciona período, archivo maestro y BD docentes.");
      return;
    }
    if (validation.data && !validation.data.ok) {
      onError(validation.data.errors?.join("; ") || "El maestro no es válido.");
      return;
    }
    if (!(await confirmBeforeOperation())) return;
    setIsStarting(true);
    try {
      const job = await apiPost<OperationJob>(baseUrl, apiKey, "/operations/stages/0/start", {
        year: selectedPeriod.year,
        month: selectedPeriod.month_name,
        maestro_file: maestroFile,
        bd_file: bdFile,
      });
      onStarted(job);
    } catch (error) {
      onError(mapApiErrorMessage(error as never));
    } finally {
      setIsStarting(false);
    }
  }

  const guide = options.data?.guide ?? {
    title: "Crear Solicitud",
    summary: "Genera la planilla del mes.",
    steps: [],
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Paso 0 — Planilla del mes</CardTitle>
      </CardHeader>
      <CardContent>
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
                Generando…
              </span>
            ) : (
              "Generar Solicitud"
            )
          }
          onExecute={() => void startStep0()}
          reviewExtra={<ArrastrePreviewCard preview={arrastre} compact loading={options.isFetching} />}
          configureContent={
            <div className="space-y-4">
              <div className="space-y-1">
                <p className="text-sm font-medium">Archivo maestro del mes *</p>
                <p className="text-xs text-muted-foreground">
                  Excel de «Base a Pago» en la carpeta del mes. Se valida antes de generar.
                </p>
                <Select value={maestroFile} onChange={(e) => setMaestroFile(e.target.value)} disabled={!prereqOk}>
                  {(options.data?.maestro_files || []).map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium">Base de docentes (BD) *</p>
                <p className="text-xs text-muted-foreground">Normalmente BD-DOCENTES.xlsx en la raíz del proyecto.</p>
                <Select value={bdFile} onChange={(e) => setBdFile(e.target.value)} disabled={!prereqOk}>
                  {(options.data?.bd_candidates || []).map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </Select>
              </div>
              {validation.isFetching && (
                <p className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Validando maestro…
                </p>
              )}
              {validation.data && !validation.data.ok && (
                <div className="rounded-md border border-danger/40 bg-danger/5 px-3 py-2 text-sm">
                  <p className="mb-1 flex items-center gap-1.5 font-medium text-danger">
                    <AlertTriangle className="h-4 w-4" /> Maestro inválido — no se puede generar
                  </p>
                  <ul className="list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">
                    {(validation.data.errors || []).map((e) => (
                      <li key={e}>{e}</li>
                    ))}
                  </ul>
                </div>
              )}
              {validation.data?.ok && (validation.data.warnings?.length ?? 0) > 0 && (
                <div className="rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs text-muted-foreground">
                  <p className="mb-1 font-medium text-amber-700">Avisos ({validation.data.row_count} filas)</p>
                  <ul className="list-disc space-y-0.5 pl-5">
                    {validation.data.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
              <ArrastrePreviewCard preview={arrastre} loading={options.isFetching} />
            </div>
          }
          confirmSummary={
            <div className="space-y-3">
            <ul className="rounded-md border border-border divide-y text-sm">
              <li className="px-3 py-2 flex justify-between gap-2">
                <span className="text-muted-foreground">Período</span>
                <span className="font-medium">
                  {selectedPeriod?.month_name} {selectedPeriod?.year}
                </span>
              </li>
              <li className="px-3 py-2 flex justify-between gap-2">
                <span className="text-muted-foreground">Maestro</span>
                <span className="font-medium">{maestroFile || "—"}</span>
              </li>
              <li className="px-3 py-2 flex justify-between gap-2">
                <span className="text-muted-foreground">BD docentes</span>
                <span className="font-medium">{bdFile || "—"}</span>
              </li>
              <li className="px-3 py-2 flex justify-between gap-2">
                <span className="text-muted-foreground">Validación</span>
                <span className="font-medium">
                  {validation.isFetching
                    ? "…"
                    : validation.data?.ok
                      ? `OK (${validation.data.row_count} filas)`
                      : "Fallida"}
                </span>
              </li>
              <li className="px-3 py-2 flex justify-between gap-2">
                <span className="text-muted-foreground">Provisionados</span>
                <span className="font-medium">
                  {arrastre
                    ? arrastre.count > 0
                      ? `${arrastre.count} filas`
                      : "Ninguno"
                    : "…"}
                </span>
              </li>
            </ul>
            {arrastre && arrastre.count > 0 && (
              <ArrastrePreviewCard preview={arrastre} />
            )}
            </div>
          }
        />

        {options.isError && (
          <div className="mt-3">
            <ErrorState
              title="No pudimos cargar opciones del paso 0"
              description={mapApiErrorMessage(options.error as never)}
              onRetry={() => options.refetch()}
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
