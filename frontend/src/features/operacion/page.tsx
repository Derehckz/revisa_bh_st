import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAppConfig } from "@/app/app-config";
import {
  invalidatePeriodViews,
  useExecutionHistory,
  useOperationJobs,
  usePeriodOverview,
  usePeriods,
  usePipelineStages,
  useStageOptions,
  usePeriodSetup,
  useMonthlyChecklist,
  useClosePeriod,
  useReopenPeriod,
  useMarkContabilidad,
} from "@/shared/api/queries";
import type { OperationJob } from "@/shared/api/types";
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
import { Stage7InteractivePanel } from "./interactive/stage7-interactive-panel";
import { ClosePeriodPanel } from "./close-period-panel";
import { MonthlyChecklistCard } from "./monthly-checklist-card";
import { PageHeader } from "@/shared/ui/page-header";
import { PeriodToolbar } from "./period-toolbar";
import { PeriodSetupCard } from "./period-setup-card";
import { OperacionTabs, type OperacionTab } from "./operacion-tabs";
import { ExcelAvancePanel } from "./excel-avance-panel";
import { PeriodJobsList } from "./period-jobs-list";
import { ExecutionHistoryPanel } from "./execution-history-panel";
import { NextStepCard } from "./next-step-card";
import { recommendForOperation } from "@/shared/lib/recommend-next-stage";
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
  const [selectedPeriodKey, setSelectedPeriodKey] = useState("");
  const [activeStage, setActiveStage] = useState(0);
  const [stage1RemindersOnly, setStage1RemindersOnly] = useState(false);
  const [activeTab, setActiveTab] = useState<OperacionTab>("ejecutar");
  const [maestroFile, setMaestroFile] = useState("");
  const [bdFile, setBdFile] = useState("");
  const [enableAutoClose, setEnableAutoClose] = useState(false);
  const [downloadDbPending, setDownloadDbPending] = useState(false);
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
  const periodSetup = usePeriodSetup(baseUrl, apiKey, selectedPeriod?.year, selectedPeriod?.month_name);
  const monthlyChecklist = useMonthlyChecklist(
    baseUrl,
    apiKey,
    selectedPeriod?.year,
    selectedPeriod?.month_name
  );
  const closePeriod = useClosePeriod(baseUrl, apiKey);
  const reopenPeriod = useReopenPeriod(baseUrl, apiKey);
  const markContabilidad = useMarkContabilidad(baseUrl, apiKey);
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

  async function handleDownloadDbSnapshot() {
    if (!selectedPeriod || !apiKey) return;
    setDownloadDbPending(true);
    try {
      const url = `${baseUrl}/operations/period/export-db?year=${selectedPeriod.year}&month=${encodeURIComponent(selectedPeriod.month_name)}`;
      const response = await fetch(url, {
        headers: {
          "x-api-key": apiKey,
        },
      });
      if (!response.ok) {
        throw new Error("No se pudo exportar Solicitud desde BD");
      }
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = `Solicitud_${selectedPeriod.year}_${selectedPeriod.month_name}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(blobUrl);
      push("Exportación lista", "success");
    } catch (e) {
      push(e instanceof Error ? e.message : "No se pudo descargar snapshot BD", "error");
    } finally {
      setDownloadDbPending(false);
    }
  }

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

  useEffect(() => {
    if (activeTab === "avance" && selectedPeriod) {
      invalidatePeriodViews(queryClient);
    }
  }, [activeTab, queryClient, selectedPeriod?.month_name, selectedPeriod?.year]);

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
    } else if (activeStage === 7) {
      stagePanel = (
        <Stage7InteractivePanel
          selectedPeriod={selectedPeriod}
          options={stageOptions}
          baseUrl={baseUrl}
          apiKey={apiKey}
          disabled={periodBusy}
          onGoToNextStage={() => handleSelectStage(8)}
        />
      );
    } else if ([5, 6, 8, 9, 10].includes(activeStage)) {
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
      <div className="space-y-3">
        <PageHeader title="Operación" description="Elige el mes y ejecuta el paso." />

        <PeriodToolbar
          periods={periods.data ?? []}
          selectedPeriod={selectedPeriod}
          selectedPeriodKey={selectedPeriodKey}
          onPeriodChange={setSelectedPeriodKey}
          kpis={overview.data?.kpis}
          runningLabel={periodBusy ? runningLabel : null}
          baseUrl={baseUrl}
          apiKey={apiKey}
          onExportPeriod={() => void handleDownloadDbSnapshot()}
          exportPending={downloadDbPending}
        />

        <PeriodOperationBanner />

        {periodSetup.data?.needs_setup_panel && (
          <PeriodSetupCard
            setup={periodSetup.data}
            onGoToStep0={() => handleSelectStage(0)}
          />
        )}

        {recommendation && (recommendation.kind === "wait" || recommendation.kind === "outbox") && (
          <NextStepCard
            recommendation={recommendation}
            onGoToStage={handleSelectStage}
            onGoToSeguimiento={() => setActiveTab("seguimiento")}
            onGoToAvanzado={() => setActiveTab("avanzado")}
          />
        )}

        <div className={activeTab === "avance" || activeTab === "cierre" ? "min-h-[320px]" : "grid min-h-[420px] gap-3 lg:grid-cols-[200px_1fr]"}>
          {activeTab !== "avance" && activeTab !== "cierre" && (
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
              cierreNeedsAttention={Boolean(
                monthlyChecklist.data &&
                  !monthlyChecklist.data.closed &&
                  !monthlyChecklist.data.can_close &&
                  (monthlyChecklist.data.blocking_count ?? 0) > 0
              )}
            />

            <div className="space-y-4 p-4 md:p-5">
              {activeTab === "ejecutar" && (
                <div className="space-y-3">
                  {recommendation &&
                    recommendation.kind !== "wait" &&
                    recommendation.kind !== "outbox" && (
                      <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border/60 bg-muted/20 px-3 py-2 text-sm">
                        <p className="min-w-0 text-muted-foreground">
                          <span className="font-medium text-foreground">Siguiente:</span>{" "}
                          {recommendation.title}
                        </p>
                        {recommendation.stage_num != null && (
                          <button
                            type="button"
                            className="shrink-0 text-xs font-medium text-primary hover:underline"
                            onClick={() =>
                              handleSelectStage(recommendation.stage_num!, {
                                remindersOnly:
                                  recommendation.kind === "reminders" ||
                                  Boolean(recommendation.params?.reminders_only),
                              })
                            }
                          >
                            Ir al paso {recommendation.stage_num}
                          </button>
                        )}
                      </div>
                    )}
                  {stagePanel}
                </div>
              )}

              {activeTab === "avance" && (
                <ExcelAvancePanel
                  baseUrl={baseUrl}
                  apiKey={apiKey}
                  year={selectedPeriod?.year}
                  month={selectedPeriod?.month_name}
                  layout="full"
                />
              )}

              {activeTab === "cierre" && selectedPeriod && (
                <div className="mx-auto max-w-2xl space-y-3">
                  <p className="text-sm text-muted-foreground">
                    Tras el informe: Contabilidad valida → marcas OK aquí → cierras el mes. El paso 5 solo confirma
                    recepción técnica. Los pagos de Contabilidad se cargan en el{" "}
                    <button
                      type="button"
                      className="underline underline-offset-2"
                      onClick={() => handleSelectStage(7)}
                    >
                      paso 7
                    </button>{" "}
                    (pegar tabla del correo → fecha → enviar).
                  </p>
                  <MonthlyChecklistCard
                    checklist={monthlyChecklist.data}
                    loading={monthlyChecklist.isLoading}
                    defaultExpanded
                    closePending={closePeriod.isPending}
                    reopenPending={reopenPeriod.isPending}
                    contabilidadPending={markContabilidad.isPending}
                    onClose={() => {
                      if (
                        !window.confirm(
                          "¿Cerrar el período? Se congelará el informe y no se podrán ejecutar pasos."
                        )
                      ) {
                        return;
                      }
                      void closePeriod.mutateAsync(
                        { year: selectedPeriod.year, month: selectedPeriod.month_name },
                        {
                          onSuccess: () => push("Período cerrado e informe congelado", "success"),
                          onError: (err) =>
                            push(
                              err instanceof Error ? err.message : "No se pudo cerrar el período",
                              "error"
                            ),
                        }
                      );
                    }}
                    onReopen={() => {
                      if (!window.confirm("¿Reabrir el período? Podrás volver a ejecutar pasos.")) return;
                      void reopenPeriod.mutateAsync(
                        { year: selectedPeriod.year, month: selectedPeriod.month_name },
                        {
                          onSuccess: () => push("Período reabierto", "success"),
                          onError: (err) =>
                            push(err instanceof Error ? err.message : "No se pudo reabrir", "error"),
                        }
                      );
                    }}
                    onMarkContabilidad={(status, notes) => {
                      void markContabilidad.mutateAsync(
                        {
                          year: selectedPeriod.year,
                          month: selectedPeriod.month_name,
                          status,
                          notes,
                        },
                        {
                          onSuccess: () => {
                            if (status === "ok") push("Contabilidad marcada OK", "success");
                            else if (status === "con_observaciones")
                              push("Contabilidad con observaciones — rectifica antes de cerrar", "info");
                            else push("Validación Contabilidad en pendiente", "success");
                          },
                          onError: (err) =>
                            push(
                              err instanceof Error ? err.message : "No se pudo marcar Contabilidad",
                              "error"
                            ),
                        }
                      );
                    }}
                  />
                </div>
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
                      Historial de ejecuciones
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
                    Solo si necesitas encadenar pendientes o recuperar la bandeja de envíos.
                  </p>
                  <label className="inline-flex items-center gap-2 text-sm tracking-tight">
                    <input
                      type="checkbox"
                      className="rounded border-border"
                      checked={enableAutoClose}
                      onChange={(e) => setEnableAutoClose(e.target.checked)}
                    />
                    Mostrar encadenar pasos 2–10 (no cierra el mes)
                  </label>
                  {enableAutoClose && (
                    <ClosePeriodPanel
                      selectedPeriod={selectedPeriod}
                      disabled={periodBusy}
                      baseUrl={baseUrl}
                      apiKey={apiKey}
                      checklistWarn={
                        monthlyChecklist.data?.items?.find((i) => i.id === "informe" && i.status !== "ok")
                          ?.message ||
                        (monthlyChecklist.data && !monthlyChecklist.data.can_close
                          ? "El checklist aún tiene ítems pendientes; revisa en la pestaña Cierre."
                          : null)
                      }
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
