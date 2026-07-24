import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { apiPost, mapApiErrorMessage } from "@/shared/api/client";
import type { OperationJob, Period } from "@/shared/api/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { ErrorState } from "@/shared/ui/error-state";
import { Select } from "@/shared/ui/select";
import type { UseQueryResult } from "@tanstack/react-query";
import type { Step0OptionsResponse } from "@/shared/api/types";
import { GuidedStageFlow } from "./guided-stage-flow";
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
  const canRun = prereqOk && Boolean(maestroFile && bdFile && selectedPeriod);

  async function startStep0() {
    if (!selectedPeriod || !maestroFile || !bdFile) {
      onError("Selecciona período, archivo maestro y BD docentes.");
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
              "Generar Solicitud.xlsx"
            )
          }
          onExecute={() => void startStep0()}
          configureContent={
            <div className="space-y-4">
              <div className="space-y-1">
                <p className="text-sm font-medium">Archivo maestro del mes *</p>
                <p className="text-xs text-muted-foreground">
                  Es el Excel de «Base a Pago» que subes a la carpeta del mes (como en consola).
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
            </div>
          }
          confirmSummary={
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
            </ul>
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
