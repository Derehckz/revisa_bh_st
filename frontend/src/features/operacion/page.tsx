import { useEffect, useMemo, useRef, useState } from "react";
import { useAppConfig } from "@/app/app-config";
import { useOperationJobs, usePeriods, usePipelineStages, useStageOptions } from "@/shared/api/queries";
import type { OperationJob } from "@/shared/api/types";
import { useOperationJob } from "@/shared/hooks/use-operation-job";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Select } from "@/shared/ui/select";
import { useToast } from "@/shared/ui/toast";
import { JobStatusPanel } from "./job-status-panel";
import { PipelineTimeline } from "./pipeline-timeline";
import { GenericStagePanel } from "./generic-stage-panel";
import { Step0Panel } from "./step0-panel";

export function OperacionPage() {
  const { baseUrl, apiKey } = useAppConfig();
  const { push } = useToast();
  const periods = usePeriods(baseUrl, apiKey);
  const stagesQuery = usePipelineStages(baseUrl, apiKey);
  const [selectedPeriodKey, setSelectedPeriodKey] = useState("");
  const [activeStage, setActiveStage] = useState(0);
  const [maestroFile, setMaestroFile] = useState("");
  const [bdFile, setBdFile] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const jobs = useOperationJobs(baseUrl, apiKey, 20);
  const { selectedJob, setSelectedJob, logs, setLogs, logsRef, selectJob, progress } = useOperationJob(
    baseUrl,
    apiKey
  );
  const prevJobStatusRef = useRef<OperationJob["status"] | null>(null);

  const selectedPeriod =
    periods.data?.find((p) => `${p.year}-${p.month_name}` === selectedPeriodKey) || periods.data?.[0];
  const stageOptions = useStageOptions(baseUrl, apiKey, activeStage, selectedPeriod?.year, selectedPeriod?.month_name);

  const stages = stagesQuery.data?.stages ?? [];
  const activeMeta = stages.find((s) => s.stage_num === activeStage);
  const runningJobs = useMemo(() => (jobs.data || []).filter((j) => j.status === "running"), [jobs.data]);

  useEffect(() => {
    if (!selectedPeriodKey && periods.data?.length) {
      setSelectedPeriodKey(`${periods.data[0].year}-${periods.data[0].month_name}`);
    }
  }, [periods.data, selectedPeriodKey]);

  useEffect(() => {
    if (stageOptions.data?.maestro_files?.length) setMaestroFile(stageOptions.data.maestro_files[0]);
    if (stageOptions.data?.bd_candidates?.length) setBdFile(stageOptions.data.bd_candidates[0]);
  }, [stageOptions.data?.maestro_files, stageOptions.data?.bd_candidates]);

  useEffect(() => {
    if (!selectedJob) return;
    const prev = prevJobStatusRef.current;
    const next = selectedJob.status;
    const stage = selectedJob.stage_num ?? 0;
    if (prev === "running" && next === "success") {
      push(`Paso ${stage} finalizado con éxito ✅`, "success");
    }
    if (prev === "running" && next === "failed") {
      push(`Paso ${stage} finalizó con error ❌`, "error");
    }
    prevJobStatusRef.current = next;
  }, [push, selectedJob]);

  function handleJobStarted(job: typeof selectedJob) {
    if (!job) return;
    setSelectedJob(job);
    prevJobStatusRef.current = "running";
    setLogs("");
    push(`Ejecución paso ${job.stage_num ?? 0} iniciada.`, "success");
    jobs.refetch();
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Operación</h1>
      <p className="text-sm text-muted-foreground">
        Ejecuta etapas 0–10 desde la web (mismo comando que consola con <code className="text-xs">--yes</code>).
        En pasos de correo (1, 5, 7) marca explícitamente envío real. La consola sigue disponible con{" "}
        <code className="text-xs">python main.py</code> o scripts en <code className="text-xs">etapas/</code>.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Período</CardTitle>
        </CardHeader>
        <CardContent>
          <Select
            value={selectedPeriod ? `${selectedPeriod.year}-${selectedPeriod.month_name}` : ""}
            onChange={(e) => setSelectedPeriodKey(e.target.value)}
          >
            {(periods.data || []).map((p) => (
              <option key={p.id} value={`${p.year}-${p.month_name}`}>
                {p.month_name} {p.year}
              </option>
            ))}
          </Select>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Pipeline (pasos 0–10)</CardTitle>
        </CardHeader>
        <CardContent>
          {stagesQuery.isLoading && <p className="text-sm text-muted-foreground">Cargando etapas…</p>}
          {stages.length > 0 && (
            <PipelineTimeline stages={stages} activeStage={activeStage} onSelect={setActiveStage} />
          )}
        </CardContent>
      </Card>

      {activeStage === 0 && activeMeta?.enabled_for_api && (
        <Step0Panel
          selectedPeriod={selectedPeriod}
          options={stageOptions}
          maestroFile={maestroFile}
          setMaestroFile={setMaestroFile}
          bdFile={bdFile}
          setBdFile={setBdFile}
          disabled={runningJobs.length > 0}
          isStarting={isStarting}
          setIsStarting={setIsStarting}
          onStarted={handleJobStarted}
          onError={(msg) => push(msg, "error")}
          baseUrl={baseUrl}
          apiKey={apiKey}
        />
      )}

      {activeStage !== 0 && activeMeta?.enabled_for_api && (
        <GenericStagePanel
          stageNum={activeStage}
          stageTitle={activeMeta.description}
          selectedPeriod={selectedPeriod}
          options={stageOptions}
          isEmailStage={activeMeta.is_email_stage}
          disabled={runningJobs.length > 0}
          onStarted={handleJobStarted}
          onError={(msg) => push(msg, "error")}
          baseUrl={baseUrl}
          apiKey={apiKey}
        />
      )}

      {activeStage !== 0 && activeMeta && !activeMeta.enabled_for_api && (
        <Card>
          <CardHeader>
            <CardTitle>
              Paso {activeStage} — {activeMeta.description}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Etapa no habilitada en API. Usa consola.
          </CardContent>
        </Card>
      )}

      {runningJobs.length > 0 && (
        <p className="text-xs text-muted-foreground">Hay una operación en curso; espera a que termine antes de iniciar otra.</p>
      )}

      <JobStatusPanel
        baseUrl={baseUrl}
        apiKey={apiKey}
        selectedJob={selectedJob}
        logs={logs}
        logsRef={logsRef}
        progress={progress}
      />

      <Card>
        <CardHeader>
          <CardTitle>Últimos jobs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {(jobs.data || []).map((job) => (
            <button
              key={job.id}
              type="button"
              className="w-full rounded-md border border-border px-3 py-2 text-left text-sm hover:bg-muted"
              onClick={() => {
                void selectJob(job);
              }}
            >
              {job.id} | paso {job.stage_num ?? 0} | {job.month} {job.year} | {job.status}
            </button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
