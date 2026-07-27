import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAppConfig } from "@/app/app-config";
import {
  invalidatePeriodViews,
  useExecutionHistory,
  useOperationJobs,
  usePeriodOverview,
  usePeriodSyncRefresh,
  usePeriods,
  usePipelineStages,
  useStageOptions,
  useInboxGapsScan,
} from "@/shared/api/queries";
import type { InboxGapsResponse, OperationJob } from "@/shared/api/types";
import { useOperationJob } from "@/shared/hooks/use-operation-job";
import { useToast } from "@/shared/ui/toast";
import { JobStatusPanel } from "./job-status-panel";
import { OutboxPanel } from "./outbox-panel";
import { PipelineSidebar } from "./pipeline-sidebar";
import { StageArtifactsPanel } from "./stage-artifacts-panel";
import { BridgedInteractivePanel } from "./interactive/bridged-interactive-panel";
import { Stage1InteractivePanel } from "./interactive/stage1-interactive-panel";
import { Stage2InteractivePanel } from "./interactive/stage2-interactive-panel";
import { Stage3InteractivePanel } from "./interactive/stage3-interactive-panel";
import { Stage4InteractivePanel } from "./interactive/stage4-interactive-panel";
import { ClosePeriodPanel } from "./close-period-panel";
import { PageHeader } from "@/shared/ui/page-header";
import { PeriodToolbar } from "./period-toolbar";
import { OperacionTabs, type OperacionTab } from "./operacion-tabs";
import { ExcelAvancePanel } from "./excel-avance-panel";
import { PeriodJobsList } from "./period-jobs-list";
import { ExecutionHistoryPanel } from "./execution-history-panel";
import { NextStepCard } from "./next-step-card";
import { InboxGapsCard } from "./inbox-gaps-card";
import { recommendForOperation } from "@/shared/lib/recommend-next-stage";
import { periodDateRange } from "@/shared/lib/period-dates";
import {
  defaultOperationPeriodKey,
  periodKey,
  resolveOperationPeriod,
} from "@/shared/lib/default-period";
import { PeriodOperationProvider } from "./period-operation-context";
import { PeriodOperationBanner } from "./period-operation-banner";
import { isPeriodClosed } from "@/shared/lib/period-operation-guard";

export function OperacionPage() {
  const { baseUrl, apiKey } = useAppConfig();
  const queryClient = useQueryClient();
  const { push } = useToast();
  const periods = usePeriods(baseUrl, apiKey);
  const stagesQuery = usePipelineStages(baseUrl, apiKey);
  const syncRefresh = usePeriodSyncRefresh(baseUrl, apiKey);
  const [selectedPeriodKey, setSelectedPeriodKey] = useState("");
  const [activeStage, setActiveStage] = useState(0);
  const [stage1RemindersOnly, setStage1RemindersOnly] = useState(false);
  const [activeTab, setActiveTab] = useState<OperacionTab>("ejecutar");
  const [maestroFile, setMaestroFile] = useState("");
  const [bdFile, setBdFile] = useState("");
  const [enableAutoClose, setEnableAutoClose] = useState(false);
  const [inboxGapsResult, setInboxGapsResult] = useState<InboxGapsResponse | null>(null);
  const [inboxGapsError, setInboxGapsError] = useState<string | null>(null);
  const prevJobStatusRef = useRef<OperationJob["status"] | null>(null);
  const inboxGaps = useInboxGapsScan(baseUrl, apiKey);

  const selectedPeriod = periods.data?.length
    ? resolveOperationPeriod(periods.data, selectedPeriodKey)
    : undefined;

  useEffect(() => {
    setInboxGapsResult(null);
    setInboxGapsError(null);
  }, [selectedPeriod?.year, selectedPeriod?.month_name]);

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
  const stageOptions = useStageOptions(
    baseUrl,
    apiKey,
    activeStage,
    selectedPeriod?.year,
    selectedPeriod?.month_name
  );

  const stages = stagesQuery.data?.stages ?? [];
  const activeMeta = stages.find((s) => s.stage_num === activeStage);
  const periodBusy = Boolean(overview.data?.running_job);
  const periodJobs = jobs.data ?? [];

  useEffect(() => {
    if (!periods.data?.length) return;
    const exists = periods.data.some(
      (p) => periodKey(p.year, p.month_name) === selectedPeriodKey
    );
    if (!selectedPeriodKey || !exists) {
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
      invalidatePeriodViews(queryClient);
    }
    if (prev === "running" && next === "failed") {
      push(`Paso ${stage} finalizó con error`, "error");
      invalidatePeriodViews(queryClient);
    }
    prevJobStatusRef.current = next;
  }, [push, queryClient, selectedJob]);

  const runningLabel = useMemo(() => {
    const r = overview.data?.running_job;
    if (!r) return null;
    return `paso ${r.stage_num ?? "?"}`;
  }, [overview.data?.running_job]);

  const recommendation = useMemo(() => {
    return recommendForOperation(overview.data, selectedPeriod);
  }, [overview.data, selectedPeriod]);

  function handleSelectStage(stageNum: number, opts?: { remindersOnly?: boolean }) {
    setActiveStage(stageNum);
    setStage1RemindersOnly(stageNum === 1 ? Boolean(opts?.remindersOnly) : false);
    setActiveTab("ejecutar");
  }

  let stagePanel: React.ReactNode = null;
  if (selectedPeriod && activeMeta?.enabled_for_api) {
    if (activeStage === 0) {
      stagePanel = (
        <BridgedInteractivePanel
          stageNum={0}
          stageTitle={activeMeta.description}
          selectedPeriod={selectedPeriod}
          options={stageOptions}
          maestroFile={maestroFile}
          setMaestroFile={setMaestroFile}
          bdFile={bdFile}
          setBdFile={setBdFile}
          baseUrl={baseUrl}
          apiKey={apiKey}
          disabled={periodBusy}
          onGoToNextStage={() => handleSelectStage(1)}
        />
      );
    } else if (activeStage === 1) {
      stagePanel = (
        <Stage1InteractivePanel
          selectedPeriod={selectedPeriod}
          options={stageOptions}
          baseUrl={baseUrl}
          apiKey={apiKey}
          disabled={periodBusy}
          remindersOnlyInitial={stage1RemindersOnly}
          onGoToNextStage={() => handleSelectStage(2)}
        />
      );
    } else if (activeStage === 2) {
      stagePanel = (
        <Stage2InteractivePanel
          selectedPeriod={selectedPeriod}
          options={stageOptions}
          baseUrl={baseUrl}
          apiKey={apiKey}
          disabled={periodBusy}
          onGoToNextStage={() => handleSelectStage(3)}
        />
      );
    } else if (activeStage === 3) {
      stagePanel = (
        <Stage3InteractivePanel
          selectedPeriod={selectedPeriod}
          options={stageOptions}
          baseUrl={baseUrl}
          apiKey={apiKey}
          disabled={periodBusy}
          noRecibidos={overview.data?.kpis?.no_recibidos ?? 0}
          onGoToNextStage={() => handleSelectStage(4)}
          onGoToReminders={() => handleSelectStage(1, { remindersOnly: true })}
        />
      );
    } else if (activeStage === 4) {
      stagePanel = (
        <Stage4InteractivePanel
          selectedPeriod={selectedPeriod}
          options={stageOptions}
          baseUrl={baseUrl}
          apiKey={apiKey}
          disabled={periodBusy}
          onGoToNextStage={() => handleSelectStage(5)}
        />
      );
    } else if ([5, 6, 7, 8, 9, 10].includes(activeStage)) {
      stagePanel = (
        <BridgedInteractivePanel
          stageNum={activeStage}
          stageTitle={activeMeta.description}
          selectedPeriod={selectedPeriod}
          options={stageOptions}
          baseUrl={baseUrl}
          apiKey={apiKey}
          disabled={periodBusy}
          noRecibidos={overview.data?.kpis?.no_recibidos ?? 0}
          onGoToNextStage={() => handleSelectStage(Math.min(activeStage + 1, 10))}
          onGoToReminders={
            activeStage === 5
              ? () => handleSelectStage(1, { remindersOnly: true })
              : undefined
          }
        />
      );
    }
  } else if (activeMeta && !activeMeta.enabled_for_api) {
    stagePanel = <p className="text-sm text-muted-foreground">Este paso se ejecuta solo por consola.</p>;
  }

  return (
    <PeriodOperationProvider period={selectedPeriod}>
      <div className="space-y-5">
        <PageHeader
          title="Operación"
          description="Mes → paso → un botón. Ejecución supervisada del pipeline."
        />

        <PeriodToolbar
          periods={periods.data ?? []}
          selectedPeriod={selectedPeriod}
          selectedPeriodKey={selectedPeriodKey}
          onPeriodChange={setSelectedPeriodKey}
          kpis={overview.data?.kpis}
          runningLabel={periodBusy ? runningLabel : null}
          syncStatus={overview.data?.sync_status}
          resyncPending={syncRefresh.isPending}
          onResync={() => {
            if (!selectedPeriod) return;
            syncRefresh.mutate(
              { year: selectedPeriod.year, month: selectedPeriod.month_name },
              {
                onSuccess: (res) => {
                  push(
                    `Re-sync: ${res.message || res.status}`,
                    res.status === "ok" ? "success" : "info"
                  );
                },
                onError: (err) => {
                  push(err instanceof Error ? err.message : "Re-sync falló", "error");
                },
              }
            );
          }}
        />

        <PeriodOperationBanner />

        {recommendation && (
          <NextStepCard
            recommendation={recommendation}
            onGoToStage={handleSelectStage}
            onGoToSeguimiento={() => setActiveTab("seguimiento")}
            onGoToAvanzado={() => setActiveTab("avanzado")}
          />
        )}

        {selectedPeriod && !isPeriodClosed(selectedPeriod) && (
          <InboxGapsCard
            scanning={inboxGaps.isPending}
            result={inboxGapsResult}
            error={inboxGapsError}
            onScan={() => {
              setInboxGapsError(null);
              const range = periodDateRange(selectedPeriod);
              inboxGaps.mutate(
                {
                  year: selectedPeriod.year,
                  month: selectedPeriod.month_name,
                  fecha_inicio: range.inicio,
                  fecha_fin: range.fin,
                },
                {
                  onSuccess: (res) => {
                    setInboxGapsResult(res);
                    if (res.gap_count > 0) {
                      push(`${res.gap_count} hueco(s) en correo sin bajar`, "info");
                    } else if (res.ok) {
                      push(res.message || "Sin huecos", "success");
                    }
                  },
                  onError: (err) => {
                    const msg =
                      typeof err === "object" && err !== null && "message" in err
                        ? String((err as { message: unknown }).message)
                        : "No se pudo escanear Outlook";
                    setInboxGapsError(msg);
                    push(msg, "error");
                  },
                }
              );
            }}
            onGoToStage2={() => handleSelectStage(2)}
          />
        )}

        <div className={activeTab === "avance" ? "min-h-[480px]" : "grid min-h-[480px] gap-3 lg:grid-cols-[220px_1fr]"}>
          {activeTab !== "avance" && (
          <aside className="rounded-lg border border-border/80 bg-muted/30 p-2 lg:sticky lg:top-16 lg:self-start">
            {stagesQuery.isLoading ? (
              <p className="p-2 text-sm text-muted-foreground">Cargando…</p>
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
          )}

          <section className="min-w-0 overflow-hidden rounded-lg border border-border/80 bg-card shadow-xs">
            <OperacionTabs
              active={activeTab}
              onChange={setActiveTab}
              hasRunningJob={periodBusy || selectedJob?.status === "running"}
            />

            <div className="space-y-4 p-4 md:p-5">
              {activeTab === "ejecutar" && stagePanel}

              {activeTab === "avance" && (
                <ExcelAvancePanel
                  baseUrl={baseUrl}
                  apiKey={apiKey}
                  year={selectedPeriod?.year}
                  month={selectedPeriod?.month_name}
                  layout="full"
                />
              )}

              {activeTab === "seguimiento" && (
                <div className="space-y-4">
                  <div>
                    <p className="mb-2 text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">
                      Ejecuciones del mes
                    </p>
                    <PeriodJobsList
                      jobs={periodJobs}
                      selectedJobId={selectedJob?.id ?? null}
                      onSelect={(job) => void selectJob(job)}
                    />
                  </div>
                  {selectedJob && (
                    <StageArtifactsPanel baseUrl={baseUrl} apiKey={apiKey} selectedJob={selectedJob} />
                  )}
                  <details className="rounded-lg border border-border/80 bg-muted/20 open:bg-card">
                    <summary className="cursor-pointer px-3 py-2.5 text-[0.8125rem] font-medium tracking-tight text-muted-foreground hover:text-foreground">
                      Bitácora
                    </summary>
                    <div className="border-t border-border/80 p-3">
                      <JobStatusPanel
                        baseUrl={baseUrl}
                        apiKey={apiKey}
                        selectedJob={selectedJob}
                        logs={logs}
                        logsRef={logsRef}
                        progress={progress}
                      />
                    </div>
                  </details>
                  <details className="rounded-lg border border-border/80 bg-muted/20 open:bg-card">
                    <summary className="cursor-pointer px-3 py-2.5 text-[0.8125rem] font-medium tracking-tight text-muted-foreground hover:text-foreground">
                      Historial Enero–Mayo 2026
                    </summary>
                    <div className="border-t border-border/80 p-3">
                      <ExecutionHistoryPanel
                        entries={executionHistory.data?.data ?? []}
                        total={executionHistory.data?.total ?? 0}
                        returned={executionHistory.data?.returned ?? 0}
                        byMonth={executionHistory.data?.by_month ?? []}
                        isLoading={executionHistory.isLoading}
                        selectedId={selectedJob?.id ?? null}
                        onSelect={(entry) => void selectHistoryEntry(entry, historyRange)}
                      />
                    </div>
                  </details>
                </div>
              )}

              {activeTab === "avanzado" && (
                <div className="space-y-4">
                  <p className="text-[0.8125rem] leading-snug text-muted-foreground">
                    Solo si necesitas cierre automático o recuperar la bandeja de envíos.
                  </p>
                  <label className="inline-flex items-center gap-2 text-sm tracking-tight">
                    <input
                      type="checkbox"
                      className="rounded border-border"
                      checked={enableAutoClose}
                      onChange={(e) => setEnableAutoClose(e.target.checked)}
                    />
                    Mostrar cierre automático (pasos 2–10)
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
                      onFinished={() => invalidatePeriodViews(queryClient)}
                    />
                  )}
                  <OutboxPanel
                    baseUrl={baseUrl}
                    apiKey={apiKey}
                    disabled={selectedPeriod ? isPeriodClosed(selectedPeriod) : false}
                  />
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </PeriodOperationProvider>
  );
}
