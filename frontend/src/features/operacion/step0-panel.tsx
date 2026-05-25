import { Loader2 } from "lucide-react";
import { apiPost, mapApiErrorMessage } from "@/shared/api/client";
import type { OperationJob, Period } from "@/shared/api/types";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { ErrorState } from "@/shared/ui/error-state";
import { Select } from "@/shared/ui/select";
import type { UseQueryResult } from "@tanstack/react-query";
import type { Step0OptionsResponse } from "@/shared/api/types";

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
  const prereqOk = options.data?.prerequisites?.ok !== false;

  async function startStep0() {
    if (!selectedPeriod || !maestroFile || !bdFile) {
      onError("Selecciona período, archivo maestro y BD docentes.");
      return;
    }
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
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Paso 0 — Generar Solicitud</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-2">
        <div className="space-y-1 md:col-span-2">
          <p className="text-xs text-muted-foreground">Base a Pago (archivo maestro en carpeta del mes)</p>
          <Select value={maestroFile} onChange={(e) => setMaestroFile(e.target.value)} disabled={!prereqOk}>
            {(options.data?.maestro_files || []).map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1 md:col-span-2">
          <p className="text-xs text-muted-foreground">Base de Docentes</p>
          <Select value={bdFile} onChange={(e) => setBdFile(e.target.value)} disabled={!prereqOk}>
            {(options.data?.bd_candidates || []).map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </Select>
        </div>
        {options.data?.prerequisites && !options.data.prerequisites.ok && (
          <p className="md:col-span-2 text-sm text-amber-800">{options.data.prerequisites.message}</p>
        )}
        <div className="flex items-center gap-2 md:col-span-2">
          <Button onClick={() => void startStep0()} disabled={disabled || isStarting || !prereqOk}>
            {isStarting ? (
              <span className="inline-flex items-center gap-2">
                <Loader2 size={14} className="animate-spin" />
                Iniciando...
              </span>
            ) : (
              "Ejecutar Paso 0"
            )}
          </Button>
        </div>
        {options.isError && (
          <div className="md:col-span-2">
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
