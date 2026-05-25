import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet } from "@/shared/api/client";
import type { OperationJob } from "@/shared/api/types";

const POLL_MS = 1500;

export function parseStepProgress(logs: string) {
  const matches = [...logs.matchAll(/\[(\d+)\/(\d+)\]/g)];
  if (!matches.length) return { current: 0, total: 8, percent: 0 };
  const last = matches[matches.length - 1];
  const current = Number(last[1] || 0);
  const total = Number(last[2] || 8) || 8;
  const percent = Math.max(0, Math.min(100, Math.round((current / total) * 100)));
  return { current, total, percent };
}

export function useOperationJob(baseUrl: string, apiKey: string) {
  const [selectedJob, setSelectedJob] = useState<OperationJob | null>(null);
  const [logs, setLogs] = useState("");
  const logsRef = useRef<HTMLDivElement | null>(null);

  const refreshJob = useCallback(
    async (jobId: string) => {
      const fresh = await apiGet<OperationJob>(baseUrl, apiKey, `/operations/jobs/${jobId}`);
      setSelectedJob(fresh);
      const logPayload = await apiGet<{ job_id: string; logs: string }>(
        baseUrl,
        apiKey,
        `/operations/jobs/${jobId}/logs`
      );
      setLogs(logPayload.logs);
      return fresh;
    },
    [apiKey, baseUrl]
  );

  const selectJob = useCallback(
    async (job: OperationJob) => {
      setSelectedJob(job);
      try {
        await refreshJob(job.id);
      } catch {
        setLogs("");
      }
    },
    [refreshJob]
  );

  useEffect(() => {
    let t: number | undefined;
    if (selectedJob?.id && selectedJob.status === "running") {
      t = window.setInterval(() => {
        void refreshJob(selectedJob.id).catch(() => undefined);
      }, POLL_MS);
    }
    return () => {
      if (t) window.clearInterval(t);
    };
  }, [refreshJob, selectedJob?.id, selectedJob?.status]);

  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [logs]);

  return {
    selectedJob,
    setSelectedJob,
    logs,
    setLogs,
    logsRef,
    refreshJob,
    selectJob,
    progress: parseStepProgress(logs),
  };
}
