import { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { useAppConfig } from "@/app/app-config";
import { apiGet, apiPost, mapApiErrorMessage } from "@/shared/api/client";
import { useOperationJobs, usePeriods, useStep0Options } from "@/shared/api/queries";
import type { OperationJob } from "@/shared/api/types";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { ErrorState } from "@/shared/ui/error-state";
import { Select } from "@/shared/ui/select";
import { Skeleton } from "@/shared/ui/skeleton";
import { useToast } from "@/shared/ui/toast";

export function OperacionPage() {
  const { baseUrl, apiKey } = useAppConfig();
  const { push } = useToast();
  const periods = usePeriods(baseUrl, apiKey);
  const [selectedPeriodKey, setSelectedPeriodKey] = useState("");
  const [maestroFile, setMaestroFile] = useState("");
  const [bdFile, setBdFile] = useState("");
  const [selectedJob, setSelectedJob] = useState<OperationJob | null>(null);
  const [logs, setLogs] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const jobs = useOperationJobs(baseUrl, apiKey, 20);
  const logsRef = useRef<HTMLDivElement | null>(null);
  const prevJobStatusRef = useRef<OperationJob["status"] | null>(null);

  const selectedPeriod = periods.data?.find((p) => `${p.year}-${p.month_name}` === selectedPeriodKey) || periods.data?.[0];
  const options = useStep0Options(baseUrl, apiKey, selectedPeriod?.year, selectedPeriod?.month_name);

  useEffect(() => {
    if (!selectedPeriodKey && periods.data?.length) {
      setSelectedPeriodKey(`${periods.data[0].year}-${periods.data[0].month_name}`);
    }
  }, [periods.data, selectedPeriodKey]);

  useEffect(() => {
    if (options.data?.maestro_files?.length) setMaestroFile(options.data.maestro_files[0]);
    if (options.data?.bd_candidates?.length) setBdFile(options.data.bd_candidates[0]);
  }, [options.data?.maestro_files, options.data?.bd_candidates]);

  useEffect(() => {
    let t: number | undefined;
    if (selectedJob?.id && selectedJob.status === "running") {
      t = window.setInterval(async () => {
        try {
          const fresh = await apiGet<OperationJob>(baseUrl, apiKey, `/operations/jobs/${selectedJob.id}`);
          setSelectedJob(fresh);
          const logPayload = await apiGet<{ job_id: string; logs: string }>(
            baseUrl,
            apiKey,
            `/operations/jobs/${selectedJob.id}/logs`
          );
          setLogs(logPayload.logs);
        } catch {
          // noop
        }
      }, 1500);
    }
    return () => {
      if (t) window.clearInterval(t);
    };
  }, [apiKey, baseUrl, selectedJob?.id, selectedJob?.status]);

  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [logs]);

  useEffect(() => {
    if (!selectedJob) return;
    const prev = prevJobStatusRef.current;
    const next = selectedJob.status;
    if (prev === "running" && next === "success") {
      push("Paso 0 finalizado con éxito ✅", "success");
    }
    if (prev === "running" && next === "failed") {
      push("Paso 0 finalizó con error ❌", "error");
    }
    prevJobStatusRef.current = next;
  }, [push, selectedJob]);

  const runningJobs = useMemo(() => (jobs.data || []).filter((j) => j.status === "running"), [jobs.data]);
  const progress = useMemo(() => parseStepProgress(logs), [logs]);

  async function startStep0() {
    if (!selectedPeriod || !maestroFile || !bdFile) {
      push("Selecciona período, archivo maestro y BD docentes.", "error");
      return;
    }
    try {
      setIsStarting(true);
      const job = await apiPost<OperationJob>(
        baseUrl,
        apiKey,
        `/operations/step0/start?year=${selectedPeriod.year}&month=${selectedPeriod.month_name}&maestro_file=${encodeURIComponent(maestroFile)}&bd_file=${encodeURIComponent(bdFile)}`
      );
      setSelectedJob(job);
      prevJobStatusRef.current = "running";
      setLogs("");
      push("Ejecución Paso 0 iniciada.", "success");
      jobs.refetch();
    } catch (error) {
      push(mapApiErrorMessage(error as never), "error");
    } finally {
      setIsStarting(false);
    }
  }

  async function openProtectedFile(path: string) {
    try {
      const response = await fetch(`${baseUrl}${path}`, {
        headers: {
          "x-api-key": apiKey,
        },
      });
      if (!response.ok) {
        push(`No se pudo abrir archivo (${response.status}).`, "error");
        return;
      }
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      window.open(blobUrl, "_blank", "noopener,noreferrer");
    } catch {
      push("No se pudo abrir archivo.", "error");
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">🛠️ Operación</h1>
      <Card>
        <CardHeader>
          <CardTitle>Paso 0 - Generar Solicitud (modo seguro)</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Período (Mes / Año)</p>
            <Select
              value={selectedPeriod ? `${selectedPeriod.year}-${selectedPeriod.month_name}` : ""}
              onChange={(event) => setSelectedPeriodKey(event.target.value)}
            >
              {(periods.data || []).map((p) => (
                <option key={p.id} value={`${p.year}-${p.month_name}`}>
                  {p.month_name} {p.year}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Base a Pago (archivo maestro)</p>
            <Select value={maestroFile} onChange={(event) => setMaestroFile(event.target.value)}>
              {(options.data?.maestro_files || []).map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Base de Docentes</p>
            <Select value={bdFile} onChange={(event) => setBdFile(event.target.value)}>
              {(options.data?.bd_candidates || []).map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={() => void startStep0()} disabled={runningJobs.length > 0 || isStarting}>
              {isStarting ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 size={14} className="animate-spin" />
                  Iniciando...
                </span>
              ) : (
                "Ejecutar Paso 0"
              )}
            </Button>
            {runningJobs.length > 0 && <span className="text-xs text-muted-foreground">Hay una operación en curso</span>}
          </div>
          {options.isError && (
            <div className="md:col-span-2">
              <ErrorState title="No pudimos cargar opciones del paso 0" description={mapApiErrorMessage(options.error as never)} onRetry={() => options.refetch()} />
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Estado de ejecución</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {!selectedJob && <p className="text-sm text-muted-foreground">Sin ejecución seleccionada.</p>}
          {selectedJob && (
            <>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span>Job: <strong>{selectedJob.id}</strong></span>
                {selectedJob.status === "running" && (
                  <Badge>
                    <span className="inline-flex items-center gap-1">
                      <Loader2 size={12} className="animate-spin" />
                      Ejecutando
                    </span>
                  </Badge>
                )}
                {selectedJob.status === "success" && (
                  <Badge tone="success">
                    <span className="inline-flex items-center gap-1">
                      <CheckCircle2 size={12} />
                      Completado
                    </span>
                  </Badge>
                )}
                {selectedJob.status === "failed" && (
                  <Badge tone="danger">
                    <span className="inline-flex items-center gap-1">
                      <XCircle size={12} />
                      Error
                    </span>
                  </Badge>
                )}
              </div>
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Progreso etapa</span>
                  <span>
                    {progress.current}/{progress.total} ({progress.percent}%)
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-muted">
                  <div className="h-2 rounded-full bg-primary transition-all" style={{ width: `${progress.percent}%` }} />
                </div>
              </div>
              <div ref={logsRef} className="max-h-[340px] overflow-auto rounded-md border border-border bg-muted p-3 text-xs whitespace-pre-wrap">
                {logs || (selectedJob.status === "running" ? <Skeleton className="h-24 w-full" /> : "Sin logs todavía.")}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="outline" onClick={() => void openProtectedFile(`/operations/jobs/${selectedJob.id}/log-file`)}>
                  Descargar log
                </Button>
                {selectedJob.status === "success" && (
                  <Button onClick={() => void openProtectedFile(`/operations/jobs/${selectedJob.id}/output`)}>
                    Abrir Solicitud.xlsx
                  </Button>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Últimos jobs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {(jobs.data || []).map((job) => (
            <button
              key={job.id}
              className="w-full rounded-md border border-border px-3 py-2 text-left text-sm hover:bg-muted"
              onClick={async () => {
                setSelectedJob(job);
                const logPayload = await apiGet<{ job_id: string; logs: string }>(baseUrl, apiKey, `/operations/jobs/${job.id}/logs`);
                setLogs(logPayload.logs);
              }}
            >
              {job.id} | {job.month} {job.year} | {job.status}
            </button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function parseStepProgress(logs: string) {
  const matches = [...logs.matchAll(/\[(\d+)\/(\d+)\]/g)];
  if (!matches.length) return { current: 0, total: 8, percent: 0 };
  const last = matches[matches.length - 1];
  const current = Number(last[1] || 0);
  const total = Number(last[2] || 8) || 8;
  const percent = Math.max(0, Math.min(100, Math.round((current / total) * 100)));
  return { current, total, percent };
}

