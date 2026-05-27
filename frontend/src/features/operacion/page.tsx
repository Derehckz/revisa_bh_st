import { useEffect, useMemo, useRef, useState } from "react";
import { useAppConfig } from "@/app/app-config";
import {
  useExecutionHistory,
  useOperationJobs,
  usePeriodOverview,
  usePeriods,
  usePipelineStages,
  useStageOptions,
} from "@/shared/api/queries";
import type { OperationJob } from "@/shared/api/types";
import { useOperationJob } from "@/shared/hooks/use-operation-job";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { useToast } from "@/shared/ui/toast";
import { JobStatusPanel } from "./job-status-panel";
import { OutboxPanel } from "./outbox-panel";
import { PipelineSidebar } from "./pipeline-sidebar";
import { GenericStagePanel } from "./generic-stage-panel";
import { StageArtifactsPanel } from "./stage-artifacts-panel";
import { Step0Panel } from "./step0-panel";
import { ClosePeriodPanel } from "./close-period-panel";
import { PeriodToolbar } from "./period-toolbar";
import { OperacionTabs, type OperacionTab } from "./operacion-tabs";
import { PeriodJobsList } from "./period-jobs-list";
import { ExecutionHistoryPanel } from "./execution-history-panel";
import { StageHeaderBanner } from "./stage-header-banner";
import { NextStepCard } from "./next-step-card";
import { recommendFromOverview } from "@/shared/lib/recommend-next-stage";
import {
  DEFAULT_OPERATION_PERIOD,
  DEFAULT_OPERATION_PERIOD_KEY,
  defaultOperationPeriodKey,
  resolveOperationPeriod,
} from "@/shared/lib/default-period";

export function OperacionPage() {
  const { baseUrl, apiKey } = useAppConfig();
  const { push } = useToast();
  const periods = usePeriods(baseUrl, apiKey);
  const stagesQuery = usePipelineStages(baseUrl, apiKey);
  const [selectedPeriodKey, setSelectedPeriodKey] = useState(DEFAULT_OPERATION_PERIOD_KEY);
  const [activeStage, setActiveStage] = useState(0);
  const [activeTab, setActiveTab] = useState<OperacionTab>("ejecutar");
  const [maestroFile, setMaestroFile] = useState("");
  const [bdFile, setBdFile] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const [enableAutoClose, setEnableAutoClose] = useState(false);
  const prevJobStatusRef = useRef<OperationJob["status"] | null>(null);

  const selectedPeriod = periods.data?.length
    ? resolveOperationPeriod(periods.data, selectedPeriodKey)
    : undefined;

  const jobs = useOperationJobs(baseUrl, apiKey, 50, selectedPeriod?.year, selectedPeriod?.month_name);
  const {
    selectedJob,
    setSelectedJob,
    logs,
    setLogs,
    logsRef,
    selectJob,
    selectHistoryEntry,
    progress,
    refreshJob,
  } = useOperationJob(baseUrl, apiKey);

  const historyRange = { year: 2026, fromMonth: "Enero", toMonth: "Mayo" };
  const executionHistory = useExecutionHistory(
    baseUrl,
    apiKey,
    historyRange.year,
    historyRange.fromMonth,
    historyRange.toMonth
  );

  const overview = usePeriodOverview(baseUrl, apiKey, selectedPeriod?.year, selectedPeriod?.month_name);
  const stageOptions = useStageOptions(baseUrl, apiKey, activeStage, selectedPeriod?.year, selectedPeriod?.month_name);

  const stages = stagesQuery.data?.stages ?? [];
  const activeMeta = stages.find((s) => s.stage_num === activeStage);
  const activeOverviewStage = overview.data?.stages.find((s) => s.stage_num === activeStage);
  const periodBusy = Boolean(overview.data?.running_job);
  const periodJobs = jobs.data ?? [];

  useEffect(() => {
    if (!selectedPeriodKey && periods.data?.length) {
      const key = defaultOperationPeriodKey(periods.data);
      if (key) setSelectedPeriodKey(key);
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
      push(`Paso ${stage} finalizado con éxito`, "success");
      overview.refetch();
      jobs.refetch();
    }
    if (prev === "running" && next === "failed") {
      push(`Paso ${stage} finalizó con error`, "error");
      overview.refetch();
      jobs.refetch();
    }
    prevJobStatusRef.current = next;
  }, [jobs, overview, push, selectedJob]);

  function handleJobStarted(job: OperationJob) {
    setSelectedJob(job);
    prevJobStatusRef.current = "running";
    setLogs("");
    setActiveTab("seguimiento");
    push(`Paso ${job.stage_num ?? 0} en ejecución — revisa la pestaña Seguimiento.`, "success");
    jobs.refetch();
    overview.refetch();
  }

  const runningLabel = useMemo(() => {
    const r = overview.data?.running_job;
    if (!r) return null;
    return `paso ${r.stage_num ?? "?"} (${r.id})`;
  }, [overview.data?.running_job]);

  const recommendation = useMemo(() => {
    if (!overview.data) return null;
    return recommendFromOverview(overview.data);
  }, [overview.data]);

  function handleSelectStage(stageNum: number) {
    setActiveStage(stageNum);
    setActiveTab("ejecutar");
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Operación</h1>
        <p className="mt-1 text-sm text-muted-foreground max-w-3xl">
          Trabaja <strong>un paso a la vez</strong>: elige el mes arriba, selecciona un paso a la izquierda y sigue el
          asistente (Revisar → Elegir archivos/opciones → Confirmar). Después mira el resultado en{" "}
          <strong>Seguimiento</strong>. No hace falta usar la terminal.
        </p>
      </header>

      <PeriodToolbar
        periods={periods.data ?? []}
        selectedPeriod={selectedPeriod}
        selectedPeriodKey={selectedPeriodKey}
        onPeriodChange={setSelectedPeriodKey}
        kpis={overview.data?.kpis}
        runningLabel={periodBusy ? runningLabel : null}
      />

      {recommendation && (
        <NextStepCard
          recommendation={recommendation}
          onGoToStage={handleSelectStage}
          onGoToSeguimiento={() => setActiveTab("seguimiento")}
          onGoToAvanzado={() => setActiveTab("avanzado")}
        />
      )}

      <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
        <aside className="rounded-lg border border-border bg-card p-3 lg:sticky lg:top-4 lg:self-start">
          {stagesQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">Cargando pasos…</p>
          ) : (
            <PipelineSidebar
              stages={stages}
              overviewStages={overview.data?.stages}
              activeStage={activeStage}
              suggestedStageNum={recommendation?.stage_num ?? null}
              onSelect={handleSelectStage}
            />
          )}
        </aside>

        <section className="min-w-0 rounded-lg border border-border bg-card">
          <OperacionTabs
            active={activeTab}
            onChange={setActiveTab}
            hasRunningJob={periodBusy || selectedJob?.status === "running"}
          />

          <div className="p-4 space-y-4">
            {activeTab === "ejecutar" && (
              <>
                <StageHeaderBanner stage={activeOverviewStage} />
                {activeStage === 0 && activeMeta?.enabled_for_api && (
                  <Step0Panel
                    selectedPeriod={selectedPeriod}
                    options={stageOptions}
                    maestroFile={maestroFile}
                    setMaestroFile={setMaestroFile}
                    bdFile={bdFile}
                    setBdFile={setBdFile}
                    disabled={periodBusy}
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
                    disabled={periodBusy}
                    onStarted={handleJobStarted}
                    onError={(msg) => push(msg, "error")}
                    baseUrl={baseUrl}
                    apiKey={apiKey}
                  />
                )}
                {activeStage !== 0 && activeMeta && !activeMeta.enabled_for_api && (
                  <p className="text-sm text-muted-foreground">
                    Este paso solo está disponible por consola (<code className="text-xs">python main.py</code> o script
                    en <code className="text-xs">etapas/</code>).
                  </p>
                )}
              </>
            )}

            {activeTab === "seguimiento" && (
              <div className="space-y-4">
                <Card>
                  <CardHeader className="py-3">
                    <CardTitle className="text-base">
                      Historial completo (Enero–Mayo 2026)
                    </CardTitle>
                    <p className="text-xs text-muted-foreground font-normal mt-1">
                      Incluye ejecuciones por consola (logs en carpetas del mes) y por la web. El período
                      seleccionado arriba solo filtra la lista corta de abajo.
                    </p>
                  </CardHeader>
                  <CardContent>
                    <ExecutionHistoryPanel
                      entries={executionHistory.data?.data ?? []}
                      total={executionHistory.data?.total ?? 0}
                      returned={executionHistory.data?.returned ?? 0}
                      byMonth={executionHistory.data?.by_month ?? []}
                      isLoading={executionHistory.isLoading}
                      selectedId={selectedJob?.id ?? null}
                      onSelect={(entry) =>
                        void selectHistoryEntry(entry, historyRange)
                      }
                    />
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="py-3">
                    <CardTitle className="text-base">
                      Jobs del período seleccionado
                      {selectedPeriod ? ` (${selectedPeriod.month_name} ${selectedPeriod.year})` : ""}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <PeriodJobsList
                      jobs={periodJobs}
                      selectedJobId={selectedJob?.id ?? null}
                      onSelect={(job) => void selectJob(job)}
                    />
                  </CardContent>
                </Card>
                <div className="grid gap-4 xl:grid-cols-2">
                  <JobStatusPanel
                    baseUrl={baseUrl}
                    apiKey={apiKey}
                    selectedJob={selectedJob}
                    logs={logs}
                    logsRef={logsRef}
                    progress={progress}
                  />
                  <StageArtifactsPanel baseUrl={baseUrl} apiKey={apiKey} selectedJob={selectedJob} />
                </div>
                {!selectedJob && (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    Selecciona un job de la lista o ejecuta un paso para ver logs y archivos.
                  </p>
                )}
              </div>
            )}

            {activeTab === "avanzado" && (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  Modo recomendado: ejecutar cada paso manualmente desde la pestaña Ejecutar. Las
                  herramientas automáticas quedan deshabilitadas por defecto para evitar ejecuciones no deseadas.
                </p>
                <label className="inline-flex items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-1.5 text-xs">
                  <input
                    type="checkbox"
                    checked={enableAutoClose}
                    onChange={(e) => setEnableAutoClose(e.target.checked)}
                  />
                  Habilitar cierre automático 2→10 (solo si realmente lo necesitas)
                </label>
                {enableAutoClose && (
                  <ClosePeriodPanel
                    selectedPeriod={selectedPeriod}
                    disabled={periodBusy}
                    baseUrl={baseUrl}
                    apiKey={apiKey}
                    onJobUpdate={(job) => {
                      setSelectedJob(job);
                      setActiveTab("seguimiento");
                      if (job.status === "running") {
                        void refreshJob(job.id).catch(() => undefined);
                      }
                    }}
                    onFinished={() => {
                      overview.refetch();
                      jobs.refetch();
                    }}
                  />
                )}
                <OutboxPanel baseUrl={baseUrl} apiKey={apiKey} />
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
