import { motion } from "framer-motion";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useMemo, useState } from "react";
import { useAppConfig } from "@/app/app-config";
import { mapApiErrorMessage } from "@/shared/api/client";
import { useRunStages, useRuns } from "@/shared/api/queries";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { ErrorState } from "@/shared/ui/error-state";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { Skeleton } from "@/shared/ui/skeleton";

export function RunsPage() {
  const { baseUrl, apiKey } = useAppConfig();
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;
  const runs = useRuns(baseUrl, apiKey, { page, pageSize: PAGE_SIZE });
  const [expandedRunId, setExpandedRunId] = useState<string | undefined>(undefined);
  const [search, setSearch] = useState("");
  const stages = useRunStages(baseUrl, apiKey, expandedRunId, Boolean(expandedRunId));
  const filteredRuns = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return runs.data?.data || [];
    return (runs.data?.data || []).filter(
      (r) =>
        r.run_id.toLowerCase().includes(q) ||
        (r.period_label || "").toLowerCase().includes(q) ||
        r.status.toLowerCase().includes(q)
    );
  }, [runs.data?.data, search]);
  const kpis = useMemo(() => {
    const items = runs.data?.data || [];
    const ok = items.filter((r) => r.status === "OK").length;
    const error = items.filter((r) => r.status === "ERROR").length;
    const running = items.filter((r) => r.status === "RUNNING").length;
    return { total: items.length, ok, error, running };
  }, [runs.data?.data]);
  const totalPages = useMemo(() => {
    const total = runs.data?.pagination.total || 0;
    return Math.max(1, Math.ceil(total / PAGE_SIZE));
  }, [runs.data]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Runs"
        description="Historial de ejecuciones y detalle por etapa."
      />
      {runs.isError && (
        <ErrorState
          title="No pudimos cargar runs"
          description={mapApiErrorMessage(runs.error as never)}
          onRetry={() => runs.refetch()}
        />
      )}
      <div className="grid gap-3 md:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <p className="text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">Total</p>
            <p className="mt-1 text-xl font-semibold tracking-tight tabular-nums">{kpis.total}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">OK</p>
            <p className="mt-1 text-xl font-semibold tracking-tight tabular-nums text-success">{kpis.ok}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">Error</p>
            <p className="mt-1 text-xl font-semibold tracking-tight tabular-nums text-danger">{kpis.error}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">En curso</p>
            <p className="mt-1 text-xl font-semibold tracking-tight tabular-nums">{kpis.running}</p>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader className="space-y-2">
          <CardTitle>Timeline de ejecuciones</CardTitle>
          <Input
            placeholder="Buscar run_id, período o estado"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </CardHeader>
        <CardContent className="space-y-3">
          {runs.isLoading &&
            Array.from({ length: 5 }).map((_, idx) => <Skeleton key={idx} className="h-14 w-full" />)}
          {filteredRuns.map((run, i) => (
            <motion.div key={run.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.02 }}>
              <div className="rounded-md border border-border p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{run.run_id}</p>
                    <p className="text-xs text-muted-foreground">{run.period_label || "Sin período"}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone={run.status === "OK" ? "success" : run.status === "ERROR" ? "danger" : "default"}>
                      {run.status}
                    </Badge>
                    <Button
                      variant="ghost"
                      onClick={() => setExpandedRunId((prev) => (prev === run.run_id ? undefined : run.run_id))}
                    >
                      {expandedRunId === run.run_id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </Button>
                  </div>
                </div>
                {expandedRunId === run.run_id && (
                  <div className="mt-3 rounded-md bg-muted/50 p-2">
                    {stages.isLoading && <Skeleton className="h-20 w-full" />}
                    {!stages.isLoading && (
                      <div className="space-y-2">
                        {stages.data?.stages.map((stage) => (
                          <div key={stage.id} className="flex items-center justify-between rounded border border-border bg-card px-2 py-1.5 text-xs">
                            <span>
                              #{stage.stage_num} {stage.stage_name}
                            </span>
                            <span className="text-muted-foreground">
                              {stage.status} | ok:{stage.rows_ok ?? 0} err:{stage.rows_error ?? 0}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </motion.div>
          ))}
          {!runs.isLoading && filteredRuns.length === 0 && (
            <EmptyState title="Sin actividad reciente" description="No existen runs registrados para mostrar en la línea de tiempo." />
          )}
          <div className="flex items-center justify-end gap-2">
            <Button variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Anterior
            </Button>
            <span className="text-xs text-muted-foreground">Página {page} de {totalPages}</span>
            <Button variant="outline" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Siguiente
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
