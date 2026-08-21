import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import type {
  BoletaDetailResponse,
  DocenteItem,
  DocenteEmailsResponse,
  DocenteMetricsResponse,
  DocenteListResponse,
  DocenteProfileResponse,
  DocenteUpsertPayload,
  DirectorListResponse,
  DirectorPrograma,
  DirectorUpsertPayload,
  HealthResponse,
  JobArtifact,
  ExecutionHistoryResponse,
  OperationJob,
  OutboxRow,
  PaginatedBoletas,
  Period,
  PeriodOverviewResponse,
  ExcelAvanceResponse,
  FinalReportResponse,
  PagosReportResponse,
  PeriodBackfillResponse,
  MonthlyChecklistResponse,
  MaestroValidationResponse,
  AuditEvent,
  DbBackupItem,
  InboxGapsResponse,
  PeriodInsightsResponse,
  PeriodSummary,
  PeriodSetupResponse,
  MissingMonthsResponse,
  CreatePeriodResponse,
  DbConsistencyResponse,
  DbMigrateResponse,
  PeriodUploadResponse,
  PagosImportResult,
  PagosPreviewResponse,
  PeriodVerifyResponse,
  ServerRestartResponse,
  RunStagesResponse,
  RunsResponse,
  StagesListResponse,
  Step0OptionsResponse,
  SyncStatus,
  YearStatsResponse,
} from "@/shared/api/types";
import { apiGet, apiPost, apiRequest, apiUpload } from "@/shared/api/client";

/** Invalida datos de período/operación para que la UI se actualice sin F5. */
export function invalidatePeriodViews(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: ["period-overview"] });
  void queryClient.invalidateQueries({ queryKey: ["excel-avance"] });
  void queryClient.invalidateQueries({ queryKey: ["operations-jobs"] });
  void queryClient.invalidateQueries({ queryKey: ["stage-options"] });
  void queryClient.invalidateQueries({ queryKey: ["periods"] });
  void queryClient.invalidateQueries({ queryKey: ["operations-history"] });
  void queryClient.invalidateQueries({ queryKey: ["boletas"] });
  void queryClient.invalidateQueries({ queryKey: ["summary"] });
  void queryClient.invalidateQueries({ queryKey: ["period-insights"] });
  void queryClient.invalidateQueries({ queryKey: ["outbox-stats"] });
  void queryClient.invalidateQueries({ queryKey: ["outbox-rows"] });
  void queryClient.invalidateQueries({ queryKey: ["period-setup"] });
  void queryClient.invalidateQueries({ queryKey: ["periods-missing"] });
}

export function usePeriods(baseUrl: string, apiKey: string) {
  return useQuery({
    queryKey: ["periods", baseUrl, apiKey],
    queryFn: () => apiGet<Period[]>(baseUrl, apiKey, "/periods"),
    refetchInterval: 30_000,
  });
}

export function usePeriodSummary(baseUrl: string, apiKey: string, year?: number, month?: string) {
  return useQuery({
    queryKey: ["summary", baseUrl, apiKey, year, month],
    enabled: Boolean(year && month),
    queryFn: () => apiGet<PeriodSummary>(baseUrl, apiKey, `/period/${year}/${month}`),
    refetchInterval: 15_000,
  });
}

export function usePeriodInsights(baseUrl: string, apiKey: string, year?: number, month?: string) {
  return useQuery({
    queryKey: ["period-insights", baseUrl, apiKey, year, month],
    enabled: Boolean(year && month),
    queryFn: () => apiGet<PeriodInsightsResponse>(baseUrl, apiKey, `/period/${year}/${month}/insights`),
    refetchInterval: 15_000,
  });
}

export function useBoletas(
  baseUrl: string,
  apiKey: string,
  params: {
    year?: number;
    month?: string;
    estado?: string;
    q?: string;
    page: number;
    pageSize: number;
    enabled?: boolean;
  }
) {
  const { year, month, estado, q, page, pageSize, enabled = true } = params;
  return useQuery({
    queryKey: ["boletas", baseUrl, apiKey, year, month, estado, q, page, pageSize],
    enabled: Boolean(enabled && year && month),
    refetchInterval: 15_000,
    queryFn: () => {
      const offset = (page - 1) * pageSize;
      if (q && q.trim().length >= 2) {
        return apiGet<PaginatedBoletas>(
          baseUrl,
          apiKey,
          `/period/${year}/${month}/search/boletas?q=${encodeURIComponent(q.trim())}&limit=${pageSize}&offset=${offset}`
        );
      }
      const estadoPart = estado ? `&estado=${encodeURIComponent(estado)}` : "";
      return apiGet<PaginatedBoletas>(
        baseUrl,
        apiKey,
        `/period/${year}/${month}/boletas?limit=${pageSize}&offset=${offset}${estadoPart}`
      );
    },
  });
}

export function useRuns(baseUrl: string, apiKey: string, params: { page?: number; pageSize?: number } = {}) {
  const { page = 1, pageSize = 20 } = params;
  return useQuery({
    queryKey: ["runs", baseUrl, apiKey, page, pageSize],
    queryFn: () => apiGet<RunsResponse>(baseUrl, apiKey, `/runs?limit=${pageSize}&offset=${(page - 1) * pageSize}`),
  });
}

export function useRunStages(baseUrl: string, apiKey: string, runId?: string, enabled = true) {
  return useQuery({
    queryKey: ["run-stages", baseUrl, apiKey, runId],
    enabled: Boolean(enabled && runId),
    queryFn: () => apiGet<RunStagesResponse>(baseUrl, apiKey, `/runs/${runId}/stages`),
  });
}

export function useYearStats(baseUrl: string, apiKey: string, year?: number) {
  return useQuery({
    queryKey: ["year-stats", baseUrl, apiKey, year],
    enabled: Boolean(year),
    queryFn: () => apiGet<YearStatsResponse>(baseUrl, apiKey, `/stats/year/${year}`),
  });
}

export function useBoletaDetail(
  baseUrl: string,
  apiKey: string,
  params: { year?: number; month?: string; boletaId?: number; enabled?: boolean }
) {
  const { year, month, boletaId, enabled = true } = params;
  return useQuery({
    queryKey: ["boleta-detail", baseUrl, apiKey, year, month, boletaId],
    enabled: Boolean(enabled && year && month && boletaId),
    queryFn: () =>
      apiGet<BoletaDetailResponse>(baseUrl, apiKey, `/period/${year}/${month}/boletas/${boletaId}`),
  });
}

export function useHealth(baseUrl: string) {
  return useQuery({
    queryKey: ["health", baseUrl],
    queryFn: () => apiGet<HealthResponse>(baseUrl, "", "/health"),
  });
}

export function useDocentes(baseUrl: string, apiKey: string, params: { q?: string; page: number; pageSize: number }) {
  const { q, page, pageSize } = params;
  return useQuery({
    queryKey: ["docentes", baseUrl, apiKey, q, page, pageSize],
    queryFn: () => {
      const offset = (page - 1) * pageSize;
      const qPart = q && q.trim().length >= 2 ? `&q=${encodeURIComponent(q.trim())}` : "";
      return apiGet<DocenteListResponse>(baseUrl, apiKey, `/docentes?limit=${pageSize}&offset=${offset}${qPart}`);
    },
  });
}

export function useDocenteProfile(baseUrl: string, apiKey: string, docenteId?: number) {
  return useQuery({
    queryKey: ["docente-profile", baseUrl, apiKey, docenteId],
    enabled: Boolean(docenteId),
    queryFn: () => apiGet<DocenteProfileResponse>(baseUrl, apiKey, `/docentes/${docenteId}?limit=300`),
  });
}

export function useDocenteBoletas(
  baseUrl: string,
  apiKey: string,
  params: { docenteId?: number; year?: number; month?: string; estado?: string; page: number; pageSize: number }
) {
  const { docenteId, year, month, estado, page, pageSize } = params;
  return useQuery({
    queryKey: ["docente-boletas", baseUrl, apiKey, docenteId, year, month, estado, page, pageSize],
    enabled: Boolean(docenteId),
    queryFn: () => {
      const offset = (page - 1) * pageSize;
      const yearPart = year ? `&year=${year}` : "";
      const monthPart = month ? `&month=${encodeURIComponent(month)}` : "";
      const estadoPart = estado ? `&estado=${encodeURIComponent(estado)}` : "";
      return apiGet<PaginatedBoletas>(
        baseUrl,
        apiKey,
        `/docentes/${docenteId}/boletas?limit=${pageSize}&offset=${offset}${yearPart}${monthPart}${estadoPart}`
      );
    },
  });
}

export function useDocenteMetrics(
  baseUrl: string,
  apiKey: string,
  params: { docenteId?: number; year?: number; month?: string }
) {
  const { docenteId, year, month } = params;
  return useQuery({
    queryKey: ["docente-metrics", baseUrl, apiKey, docenteId, year, month],
    enabled: Boolean(docenteId),
    queryFn: () => {
      const yearPart = year ? `?year=${year}` : "";
      const monthPart = month ? `${yearPart ? "&" : "?"}month=${encodeURIComponent(month)}` : "";
      return apiGet<DocenteMetricsResponse>(baseUrl, apiKey, `/docentes/${docenteId}/metrics${yearPart}${monthPart}`);
    },
  });
}

export function useDocenteEmails(
  baseUrl: string,
  apiKey: string,
  params: { docenteId?: number; tipo?: string; estado?: string; page: number; pageSize: number; enabled?: boolean }
) {
  const { docenteId, tipo, estado, page, pageSize, enabled = true } = params;
  return useQuery({
    queryKey: ["docente-emails", baseUrl, apiKey, docenteId, tipo, estado, page, pageSize],
    enabled: Boolean(enabled && docenteId),
    queryFn: () => {
      const offset = (page - 1) * pageSize;
      const tipoPart = tipo ? `&tipo=${encodeURIComponent(tipo)}` : "";
      const estadoPart = estado ? `&estado=${encodeURIComponent(estado)}` : "";
      return apiGet<DocenteEmailsResponse>(
        baseUrl,
        apiKey,
        `/docentes/${docenteId}/emails?limit=${pageSize}&offset=${offset}${tipoPart}${estadoPart}`
      );
    },
  });
}

export function useCreateDocente(baseUrl: string, apiKey: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: DocenteUpsertPayload) =>
      apiPost<{ ok: boolean; docente: DocenteItem; solicitud_actualizada?: string[] }>(
        baseUrl,
        apiKey,
        "/docentes",
        payload
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["docentes"] });
      void qc.invalidateQueries({ queryKey: ["excel-avance"] });
      void qc.invalidateQueries({ queryKey: ["monthly-checklist"] });
    },
  });
}

export function useUpdateDocente(baseUrl: string, apiKey: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ docenteId, payload }: { docenteId: number; payload: DocenteUpsertPayload }) =>
      apiRequest<{ ok: boolean; docente: DocenteItem; solicitud_actualizada?: string[] }>(
        baseUrl,
        apiKey,
        `/docentes/${docenteId}`,
        "PUT",
        payload
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["docentes"] });
      void qc.invalidateQueries({ queryKey: ["docente-profile"] });
      void qc.invalidateQueries({ queryKey: ["excel-avance"] });
      void qc.invalidateQueries({ queryKey: ["monthly-checklist"] });
    },
  });
}

export function useDisableDocente(baseUrl: string, apiKey: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (docenteId: number) =>
      apiPost<{ ok: boolean; docente: DocenteItem }>(baseUrl, apiKey, `/docentes/${docenteId}/disable`, {}),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["docentes"] });
      void qc.invalidateQueries({ queryKey: ["docente-profile"] });
    },
  });
}

export function useDeleteDocente(baseUrl: string, apiKey: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (docenteId: number) =>
      apiRequest<{ ok: boolean; docente: DocenteItem }>(baseUrl, apiKey, `/docentes/${docenteId}`, "DELETE"),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["docentes"] });
      void qc.invalidateQueries({ queryKey: ["docente-profile"] });
    },
  });
}

export function useDirectores(baseUrl: string, apiKey: string) {
  return useQuery({
    queryKey: ["directores", baseUrl, apiKey],
    queryFn: () => apiGet<DirectorListResponse>(baseUrl, apiKey, "/directores"),
  });
}

export function useCreateDirector(baseUrl: string, apiKey: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: DirectorUpsertPayload) =>
      apiPost<{ ok: boolean; director: DirectorPrograma }>(baseUrl, apiKey, "/directores", payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["directores"] });
      void qc.invalidateQueries({ queryKey: ["docentes"] });
    },
  });
}

export function useUpdateDirector(baseUrl: string, apiKey: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ directorId, payload }: { directorId: number; payload: DirectorUpsertPayload }) =>
      apiRequest<{ ok: boolean; director: DirectorPrograma }>(
        baseUrl,
        apiKey,
        `/directores/${directorId}`,
        "PUT",
        payload
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["directores"] });
      void qc.invalidateQueries({ queryKey: ["docentes"] });
    },
  });
}

export function useDeleteDirector(baseUrl: string, apiKey: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (directorId: number) =>
      apiRequest<{ ok: boolean }>(baseUrl, apiKey, `/directores/${directorId}`, "DELETE"),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["directores"] });
    },
  });
}

export function useSeedDirectores(baseUrl: string, apiKey: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiPost<{ ok: boolean; created: number; sedes: number; mapping: number }>(
        baseUrl,
        apiKey,
        "/directores/seed-from-excel",
        {}
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["directores"] });
    },
  });
}

export function usePipelineStages(baseUrl: string, apiKey: string) {
  return useQuery({
    queryKey: ["pipeline-stages", baseUrl, apiKey],
    queryFn: () => apiGet<StagesListResponse>(baseUrl, apiKey, "/operations/stages"),
  });
}

export function useStageOptions(
  baseUrl: string,
  apiKey: string,
  stageNum: number,
  year?: number,
  month?: string
) {
  return useQuery({
    queryKey: ["stage-options", baseUrl, apiKey, stageNum, year, month],
    enabled: Boolean(year && month),
    refetchInterval: 20_000,
    queryFn: () =>
      apiGet<Step0OptionsResponse>(
        baseUrl,
        apiKey,
        `/operations/stages/${stageNum}/options?year=${year}&month=${encodeURIComponent(month || "")}`
      ),
  });
}

/** @deprecated Use useStageOptions(baseUrl, apiKey, 0, year, month) */
export function useStep0Options(baseUrl: string, apiKey: string, year?: number, month?: string) {
  return useStageOptions(baseUrl, apiKey, 0, year, month);
}

export function usePeriodOverview(baseUrl: string, apiKey: string, year?: number, month?: string) {
  return useQuery({
    queryKey: ["period-overview", baseUrl, apiKey, year, month],
    enabled: Boolean(year && month),
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.running_job ? 3000 : 10_000;
    },
    queryFn: () =>
      apiGet<PeriodOverviewResponse>(
        baseUrl,
        apiKey,
        `/operations/period/overview?year=${year}&month=${encodeURIComponent(month || "")}`
      ),
  });
}

export function useExcelAvance(baseUrl: string, apiKey: string, year?: number, month?: string) {
  return useQuery({
    queryKey: ["excel-avance", baseUrl, apiKey, year, month],
    enabled: Boolean(year && month),
    staleTime: 0,
    refetchInterval: 10_000,
    refetchOnMount: "always",
    queryFn: () =>
      apiGet<ExcelAvanceResponse>(
        baseUrl,
        apiKey,
        `/operations/period/excel-avance?year=${year}&month=${encodeURIComponent(month || "")}`
      ),
  });
}

export function useFinalReport(baseUrl: string, apiKey: string, year?: number, month?: string) {
  return useQuery({
    queryKey: ["final-report", baseUrl, apiKey, year, month],
    enabled: Boolean(year && month),
    queryFn: () =>
      apiGet<FinalReportResponse>(
        baseUrl,
        apiKey,
        `/operations/period/final-report?year=${year}&month=${encodeURIComponent(month || "")}`
      ),
  });
}

export function usePagosReport(baseUrl: string, apiKey: string, year?: number, month?: string) {
  return useQuery({
    queryKey: ["pagos-report", baseUrl, apiKey, year, month],
    enabled: Boolean(year && month),
    queryFn: () =>
      apiGet<PagosReportResponse>(
        baseUrl,
        apiKey,
        `/operations/period/pagos-report?year=${year}&month=${encodeURIComponent(month || "")}`
      ),
  });
}

export function useMonthlyChecklist(baseUrl: string, apiKey: string, year?: number, month?: string) {
  return useQuery({
    queryKey: ["monthly-checklist", baseUrl, apiKey, year, month],
    enabled: Boolean(year && month),
    refetchInterval: 15_000,
    queryFn: () =>
      apiGet<MonthlyChecklistResponse>(
        baseUrl,
        apiKey,
        `/operations/period/monthly-checklist?year=${year}&month=${encodeURIComponent(month || "")}`
      ),
  });
}

export function useValidateMaestro(
  baseUrl: string,
  apiKey: string,
  year?: number,
  month?: string,
  filename?: string
) {
  return useQuery({
    queryKey: ["validate-maestro", baseUrl, apiKey, year, month, filename],
    enabled: Boolean(year && month && filename),
    queryFn: () => {
      const qs = new URLSearchParams({
        year: String(year),
        month: month || "",
        filename: filename || "",
      });
      return apiGet<MaestroValidationResponse>(
        baseUrl,
        apiKey,
        `/operations/period/validate-maestro?${qs.toString()}`
      );
    },
  });
}

export function useClosePeriod(baseUrl: string, apiKey: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { year: number; month: string; force?: boolean }) =>
      apiPost(baseUrl, apiKey, "/operations/period/close", vars),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["monthly-checklist"] });
      void qc.invalidateQueries({ queryKey: ["periods"] });
      void qc.invalidateQueries({ queryKey: ["final-report"] });
      void qc.invalidateQueries({ queryKey: ["period-overview"] });
    },
  });
}

export function useReopenPeriod(baseUrl: string, apiKey: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { year: number; month: string }) =>
      apiPost(baseUrl, apiKey, "/operations/period/reopen", vars),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["monthly-checklist"] });
      void qc.invalidateQueries({ queryKey: ["periods"] });
      void qc.invalidateQueries({ queryKey: ["final-report"] });
      void qc.invalidateQueries({ queryKey: ["period-overview"] });
    },
  });
}

export function useMarkContabilidad(baseUrl: string, apiKey: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: {
      year: number;
      month: string;
      status: "ok" | "con_observaciones" | "pendiente";
      notes?: string;
    }) => apiPost(baseUrl, apiKey, "/operations/period/contabilidad-validate", vars),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["monthly-checklist"] });
      void qc.invalidateQueries({ queryKey: ["period-overview"] });
    },
  });
}

export function useDbBackup(baseUrl: string, apiKey: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<{ ok: boolean; message: string; path?: string }>(baseUrl, apiKey, "/operations/db/backup"),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["db-backups"] }),
  });
}

export function useDbBackups(baseUrl: string, apiKey: string) {
  return useQuery({
    queryKey: ["db-backups", baseUrl, apiKey],
    enabled: Boolean(apiKey),
    queryFn: () => apiGet<{ backups_dir: string; backups: DbBackupItem[] }>(baseUrl, apiKey, "/operations/db/backups"),
  });
}

export function useAuditEvents(baseUrl: string, apiKey: string, year?: number, month?: string) {
  return useQuery({
    queryKey: ["audit-events", baseUrl, apiKey, year, month],
    enabled: Boolean(apiKey),
    queryFn: () => {
      const qs = new URLSearchParams({ limit: "50" });
      if (year) qs.set("year", String(year));
      if (month) qs.set("month", month);
      return apiGet<{ events: AuditEvent[] }>(baseUrl, apiKey, `/audit/events?${qs.toString()}`);
    },
  });
}

/** On-demand: cruza Inbox Outlook vs carpeta para NO RECIBIDO (puede tardar). */
export function useInboxGapsScan(baseUrl: string, apiKey: string) {
  return useMutation({
    mutationFn: (vars: {
      year: number;
      month: string;
      fecha_inicio?: string;
      fecha_fin?: string;
    }) => {
      const qs = new URLSearchParams({
        year: String(vars.year),
        month: vars.month,
      });
      if (vars.fecha_inicio) qs.set("fecha_inicio", vars.fecha_inicio);
      if (vars.fecha_fin) qs.set("fecha_fin", vars.fecha_fin);
      return apiGet<InboxGapsResponse>(
        baseUrl,
        apiKey,
        `/operations/period/inbox-gaps?${qs.toString()}`
      );
    },
  });
}

/** E11: re-sync Excel↔PG vía SyncProjector (refresh=true). */
export function usePeriodSyncRefresh(baseUrl: string, apiKey: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ year, month }: { year: number; month: string }) =>
      apiGet<SyncStatus & { ok?: boolean; periods_created?: number }>(
        baseUrl,
        apiKey,
        `/operations/period/sync-status?year=${year}&month=${encodeURIComponent(month)}&refresh=true`
      ),
    onSuccess: (_data, vars) => {
      void qc.invalidateQueries({ queryKey: ["period-overview", baseUrl, apiKey, vars.year, vars.month] });
      void qc.invalidateQueries({ queryKey: ["summary", baseUrl, apiKey, vars.year, vars.month] });
    },
  });
}

export function usePeriodVerify(baseUrl: string, apiKey: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      year,
      month,
      runMigrations = true,
      runConsistency = true,
    }: {
      year: number;
      month: string;
      runMigrations?: boolean;
      runConsistency?: boolean;
    }) =>
      apiPost<PeriodVerifyResponse>(baseUrl, apiKey, "/operations/period/verify", {
        year,
        month,
        run_migrations: runMigrations,
        run_consistency: runConsistency,
      }),
    onSuccess: (_data, vars) => {
      void qc.invalidateQueries({ queryKey: ["period-overview", baseUrl, apiKey, vars.year, vars.month] });
      void qc.invalidateQueries({ queryKey: ["excel-avance", baseUrl, apiKey, vars.year, vars.month] });
      void qc.invalidateQueries({ queryKey: ["summary", baseUrl, apiKey, vars.year, vars.month] });
      void qc.invalidateQueries({ queryKey: ["final-report", baseUrl, apiKey, vars.year, vars.month] });
      void qc.invalidateQueries({ queryKey: ["pagos-report", baseUrl, apiKey, vars.year, vars.month] });
    },
  });
}

export function usePeriodBackfill(baseUrl: string, apiKey: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      year,
      month,
      runMigrations = true,
    }: {
      year: number;
      month?: string;
      runMigrations?: boolean;
    }) =>
      apiPost<PeriodBackfillResponse>(baseUrl, apiKey, "/operations/period/backfill", {
        year,
        month: month || null,
        run_migrations: runMigrations,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["periods", baseUrl, apiKey] });
      void qc.invalidateQueries({ queryKey: ["excel-avance", baseUrl, apiKey] });
      void qc.invalidateQueries({ queryKey: ["final-report", baseUrl, apiKey] });
      void qc.invalidateQueries({ queryKey: ["pagos-report", baseUrl, apiKey] });
    },
  });
}

export function useDbMigrate(baseUrl: string, apiKey: string) {
  return useMutation({
    mutationFn: () => apiPost<DbMigrateResponse>(baseUrl, apiKey, "/operations/db/migrate", {}),
  });
}

export function useDbConsistencyCheck(baseUrl: string, apiKey: string) {
  return useMutation<DbConsistencyResponse, Error, number>({
    mutationFn: (limit) =>
      apiPost<DbConsistencyResponse>(baseUrl, apiKey, "/operations/db/consistency-check", { limit }),
  });
}

export function useServerRestart(baseUrl: string, apiKey: string) {
  return useMutation<ServerRestartResponse, Error, number | undefined>({
    mutationFn: (port = 8000) =>
      apiPost<ServerRestartResponse>(baseUrl, apiKey, "/operations/server/restart", { port }),
  });
}

export function useJobArtifacts(baseUrl: string, apiKey: string, jobId: string | null) {
  const isApiJob = Boolean(jobId && !jobId.startsWith("hist_"));
  return useQuery({
    queryKey: ["job-artifacts", baseUrl, apiKey, jobId],
    enabled: isApiJob,
    queryFn: () =>
      apiGet<{ job_id: string; artifacts: JobArtifact[] }>(
        baseUrl,
        apiKey,
        `/operations/jobs/${jobId}/artifacts`
      ),
  });
}

export function useOutboxStats(baseUrl: string, apiKey: string) {
  return useQuery({
    queryKey: ["outbox-stats", baseUrl, apiKey],
    queryFn: () => apiGet<{ by_status: Record<string, number> }>(baseUrl, apiKey, "/operations/outbox/stats"),
    refetchInterval: 15000,
  });
}

export function useOutboxRows(baseUrl: string, apiKey: string, status?: string, limit = 50) {
  return useQuery({
    queryKey: ["outbox-rows", baseUrl, apiKey, status, limit],
    queryFn: () =>
      apiGet<{ data: OutboxRow[] }>(
        baseUrl,
        apiKey,
        `/operations/outbox/rows?limit=${limit}${status ? `&status=${encodeURIComponent(status)}` : ""}`
      ),
  });
}

export function useOperationJobs(
  baseUrl: string,
  apiKey: string,
  limit = 50,
  year?: number,
  month?: string
) {
  return useQuery({
    queryKey: ["operations-jobs", baseUrl, apiKey, limit, year, month],
    refetchInterval: 10_000,
    queryFn: async () => {
      const q = new URLSearchParams({ limit: String(limit) });
      if (year != null) q.set("year", String(year));
      if (month) q.set("month", month);
      const payload = await apiGet<{ data: OperationJob[] }>(
        baseUrl,
        apiKey,
        `/operations/jobs?${q.toString()}`
      );
      return payload.data;
    },
  });
}

export function useExecutionHistory(
  baseUrl: string,
  apiKey: string,
  year: number,
  fromMonth: string,
  toMonth: string,
  limit = 500
) {
  return useQuery({
    queryKey: ["operations-history", baseUrl, apiKey, year, fromMonth, toMonth, limit],
    queryFn: () =>
      apiGet<ExecutionHistoryResponse>(
        baseUrl,
        apiKey,
        `/operations/history?year=${year}&from_month=${encodeURIComponent(fromMonth)}&to_month=${encodeURIComponent(toMonth)}&limit=${limit}`
      ),
    staleTime: 60_000,
  });
}

export function usePeriodSetup(baseUrl: string, apiKey: string, year?: number, month?: string) {
  return useQuery({
    queryKey: ["period-setup", baseUrl, apiKey, year, month],
    enabled: Boolean(year && month),
    queryFn: () =>
      apiGet<PeriodSetupResponse>(
        baseUrl,
        apiKey,
        `/operations/period/setup?year=${year}&month=${encodeURIComponent(month!)}`
      ),
    refetchInterval: 15_000,
  });
}

export function useMissingMonths(baseUrl: string, apiKey: string, year: number, enabled = true) {
  return useQuery({
    queryKey: ["periods-missing", baseUrl, apiKey, year],
    enabled: Boolean(enabled && year),
    queryFn: () =>
      apiGet<MissingMonthsResponse>(baseUrl, apiKey, `/operations/periods/missing?year=${year}`),
  });
}

export function useCreatePeriod(baseUrl: string, apiKey: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { year: number; month_name: string }) =>
      apiPost<CreatePeriodResponse>(baseUrl, apiKey, "/operations/periods", body),
    onSuccess: () => {
      invalidatePeriodViews(queryClient);
    },
  });
}

export function usePeriodUpload(baseUrl: string, apiKey: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (args: {
      year: number;
      month: string;
      kind: "maestro" | "bd" | "adjunto" | "pagos";
      file: File;
    }) => {
      const form = new FormData();
      form.append("year", String(args.year));
      form.append("month", args.month);
      form.append("kind", args.kind);
      form.append("file", args.file);
      return apiUpload<PeriodUploadResponse>(baseUrl, apiKey, "/operations/period/upload", form);
    },
    onSuccess: () => {
      invalidatePeriodViews(queryClient);
    },
  });
}

export function useStage7ImportPagos(baseUrl: string, apiKey: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (args: { year: number; month: string; paste?: string; file?: File }) => {
      const form = new FormData();
      form.append("year", String(args.year));
      form.append("month", args.month);
      if (args.paste?.trim()) form.append("paste", args.paste.trim());
      if (args.file) form.append("file", args.file);
      return apiUpload<PagosImportResult & Partial<PeriodUploadResponse>>(
        baseUrl,
        apiKey,
        "/operations/stages/7/import-pagos",
        form
      );
    },
    onSuccess: () => {
      invalidatePeriodViews(queryClient);
    },
  });
}

export function useStage7PreviewPagos(baseUrl: string, apiKey: string) {
  return useMutation({
    mutationFn: (body: { year: number; month: string; fecha_pago: string; force_resend?: boolean }) =>
      apiPost<PagosPreviewResponse>(baseUrl, apiKey, "/operations/stages/7/preview-pagos", body),
  });
}
