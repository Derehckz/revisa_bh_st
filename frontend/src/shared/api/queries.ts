import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/shared/api/client";
import type {
  BoletaDetailResponse,
  DocenteMetricsResponse,
  DocenteListResponse,
  DocenteProfileResponse,
  HealthResponse,
  JobArtifact,
  ExecutionHistoryResponse,
  OperationJob,
  OutboxRow,
  PaginatedBoletas,
  Period,
  PeriodOverviewResponse,
  PeriodInsightsResponse,
  PeriodSummary,
  RunStagesResponse,
  RunsResponse,
  StagesListResponse,
  Step0OptionsResponse,
  YearStatsResponse,
} from "@/shared/api/types";

export function usePeriods(baseUrl: string, apiKey: string) {
  return useQuery({
    queryKey: ["periods", baseUrl],
    queryFn: () => apiGet<Period[]>(baseUrl, apiKey, "/periods"),
  });
}

export function usePeriodSummary(baseUrl: string, apiKey: string, year?: number, month?: string) {
  return useQuery({
    queryKey: ["summary", baseUrl, year, month],
    enabled: Boolean(year && month),
    queryFn: () => apiGet<PeriodSummary>(baseUrl, apiKey, `/period/${year}/${month}`),
  });
}

export function usePeriodInsights(baseUrl: string, apiKey: string, year?: number, month?: string) {
  return useQuery({
    queryKey: ["period-insights", baseUrl, year, month],
    enabled: Boolean(year && month),
    queryFn: () => apiGet<PeriodInsightsResponse>(baseUrl, apiKey, `/period/${year}/${month}/insights`),
  });
}

export function useBoletas(
  baseUrl: string,
  apiKey: string,
  params: { year?: number; month?: string; estado?: string; q?: string; page: number; pageSize: number }
) {
  const { year, month, estado, q, page, pageSize } = params;
  return useQuery({
    queryKey: ["boletas", baseUrl, year, month, estado, q, page, pageSize],
    enabled: Boolean(year && month),
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
    queryKey: ["runs", baseUrl, page, pageSize],
    queryFn: () => apiGet<RunsResponse>(baseUrl, apiKey, `/runs?limit=${pageSize}&offset=${(page - 1) * pageSize}`),
  });
}

export function useRunStages(baseUrl: string, apiKey: string, runId?: string, enabled = true) {
  return useQuery({
    queryKey: ["run-stages", baseUrl, runId],
    enabled: Boolean(enabled && runId),
    queryFn: () => apiGet<RunStagesResponse>(baseUrl, apiKey, `/runs/${runId}/stages`),
  });
}

export function useYearStats(baseUrl: string, apiKey: string, year?: number) {
  return useQuery({
    queryKey: ["year-stats", baseUrl, year],
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
    queryKey: ["boleta-detail", baseUrl, year, month, boletaId],
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
    queryKey: ["docentes", baseUrl, q, page, pageSize],
    queryFn: () => {
      const offset = (page - 1) * pageSize;
      const qPart = q && q.trim().length >= 2 ? `&q=${encodeURIComponent(q.trim())}` : "";
      return apiGet<DocenteListResponse>(baseUrl, apiKey, `/docentes?limit=${pageSize}&offset=${offset}${qPart}`);
    },
  });
}

export function useDocenteProfile(baseUrl: string, apiKey: string, docenteId?: number) {
  return useQuery({
    queryKey: ["docente-profile", baseUrl, docenteId],
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
    queryKey: ["docente-boletas", baseUrl, docenteId, year, month, estado, page, pageSize],
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
    queryKey: ["docente-metrics", baseUrl, docenteId, year, month],
    enabled: Boolean(docenteId),
    queryFn: () => {
      const yearPart = year ? `?year=${year}` : "";
      const monthPart = month ? `${yearPart ? "&" : "?"}month=${encodeURIComponent(month)}` : "";
      return apiGet<DocenteMetricsResponse>(baseUrl, apiKey, `/docentes/${docenteId}/metrics${yearPart}${monthPart}`);
    },
  });
}

export function usePipelineStages(baseUrl: string, apiKey: string) {
  return useQuery({
    queryKey: ["pipeline-stages", baseUrl],
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
    queryKey: ["stage-options", baseUrl, stageNum, year, month],
    enabled: Boolean(year && month),
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
    queryKey: ["period-overview", baseUrl, year, month],
    enabled: Boolean(year && month),
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.running_job ? 3000 : false;
    },
    queryFn: () =>
      apiGet<PeriodOverviewResponse>(
        baseUrl,
        apiKey,
        `/operations/period/overview?year=${year}&month=${encodeURIComponent(month || "")}`
      ),
  });
}

export function useJobArtifacts(baseUrl: string, apiKey: string, jobId: string | null) {
  const isApiJob = Boolean(jobId && !jobId.startsWith("hist_"));
  return useQuery({
    queryKey: ["job-artifacts", baseUrl, jobId],
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
    queryKey: ["outbox-stats", baseUrl],
    queryFn: () => apiGet<{ by_status: Record<string, number> }>(baseUrl, apiKey, "/operations/outbox/stats"),
    refetchInterval: 15000,
  });
}

export function useOutboxRows(baseUrl: string, apiKey: string, status?: string, limit = 50) {
  return useQuery({
    queryKey: ["outbox-rows", baseUrl, status, limit],
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
    queryKey: ["operations-jobs", baseUrl, limit, year, month],
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
    queryKey: ["operations-history", baseUrl, year, fromMonth, toMonth, limit],
    queryFn: () =>
      apiGet<ExecutionHistoryResponse>(
        baseUrl,
        apiKey,
        `/operations/history?year=${year}&from_month=${encodeURIComponent(fromMonth)}&to_month=${encodeURIComponent(toMonth)}&limit=${limit}`
      ),
    staleTime: 60_000,
  });
}
