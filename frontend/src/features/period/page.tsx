import { useEffect, useMemo, useState } from "react";
import { useAppConfig } from "@/app/app-config";
import { mapApiErrorMessage } from "@/shared/api/client";
import { usePeriodInsights, usePeriodSummary, usePeriods } from "@/shared/api/queries";
import { defaultOperationPeriodKey, periodKey, resolveOperationPeriod } from "@/shared/lib/default-period";
import { toCurrency } from "@/shared/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { ErrorState } from "@/shared/ui/error-state";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import { Skeleton } from "@/shared/ui/skeleton";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function PeriodPage() {
  const { baseUrl, apiKey } = useAppConfig();
  const periods = usePeriods(baseUrl, apiKey);
  const [selectedPeriodKey, setSelectedPeriodKey] = useState("");
  const selected = resolveOperationPeriod(periods.data ?? [], selectedPeriodKey);
  const year = selected?.year;
  const month = selected?.month_name;
  const summary = usePeriodSummary(baseUrl, apiKey, year, month);
  const insights = usePeriodInsights(baseUrl, apiKey, year, month);

  useEffect(() => {
    if (!periods.data?.length) return;
    const exists = periods.data.some((p) => periodKey(p.year, p.month_name) === selectedPeriodKey);
    if (!selectedPeriodKey || !exists) {
      setSelectedPeriodKey(defaultOperationPeriodKey(periods.data) || "");
    }
  }, [periods.data, selectedPeriodKey]);

  const breakdown = useMemo<Array<{ label: string; value: number }>>(() => {
    if (!summary.data) return [];
    return [
      { label: "Recibidos", value: summary.data.metrics.recibidos },
      { label: "No recibidos", value: summary.data.metrics.no_recibidos },
      { label: "Con error", value: summary.data.metrics.recibidos_con_error },
      { label: "XML", value: summary.data.metrics.total_xml },
      { label: "Emails", value: summary.data.metrics.total_emails }
    ];
  }, [summary.data]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Período"
        description="Indicadores y desglose del mes seleccionado."
        actions={
          <Select
            className="min-w-[180px]"
            value={selected ? `${selected.year}-${selected.month_name}` : ""}
            onChange={(e) => setSelectedPeriodKey(e.target.value)}
            aria-label="Período"
          >
            {(periods.data || []).map((p) => (
              <option key={p.id} value={`${p.year}-${p.month_name}`}>
                {p.month_name} {p.year}
              </option>
            ))}
          </Select>
        }
      />
      {(periods.isError || summary.isError || insights.isError) && (
        <ErrorState
          title="No pudimos cargar el resumen del período"
          description={mapApiErrorMessage((periods.error || summary.error || insights.error) as never)}
          onRetry={() => {
            periods.refetch();
            summary.refetch();
            insights.refetch();
          }}
        />
      )}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {(summary.isLoading ? Array.from({ length: 5 }, (_, i) => ({ label: `loading-${i}`, value: 0 })) : breakdown).map((item, idx) => (
          <Card key={idx}>
            <CardHeader>
              <CardTitle className="text-muted-foreground">{summary.isLoading ? "Cargando…" : item.label}</CardTitle>
            </CardHeader>
            <CardContent className="text-[1.75rem] font-semibold tracking-tight tabular-nums">
              {summary.isLoading ? <Skeleton className="h-8 w-12" /> : item.value}
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <Card>
          <CardHeader><CardTitle className="text-muted-foreground">Monto total</CardTitle></CardHeader>
          <CardContent className="text-xl font-semibold tracking-tight tabular-nums">
            {insights.isLoading ? <Skeleton className="h-8 w-28" /> : toCurrency(insights.data?.kpis.monto_total)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-muted-foreground">Monto promedio</CardTitle></CardHeader>
          <CardContent className="text-xl font-semibold">
            {insights.isLoading ? <Skeleton className="h-8 w-28" /> : toCurrency(insights.data?.kpis.monto_promedio)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-muted-foreground">Docentes únicos</CardTitle></CardHeader>
          <CardContent className="text-xl font-semibold tracking-tight tabular-nums">
            {insights.isLoading ? <Skeleton className="h-8 w-16" /> : insights.data?.kpis.docentes_unicos ?? 0}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-muted-foreground">Con XML</CardTitle></CardHeader>
          <CardContent className="text-xl font-semibold tracking-tight tabular-nums">
            {insights.isLoading ? <Skeleton className="h-8 w-16" /> : insights.data?.kpis.boletas_con_xml ?? 0}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-muted-foreground">Sin XML</CardTitle></CardHeader>
          <CardContent className="text-xl font-semibold tracking-tight tabular-nums">
            {insights.isLoading ? <Skeleton className="h-8 w-16" /> : insights.data?.kpis.boletas_sin_xml ?? 0}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="min-w-0 overflow-hidden">
          <CardHeader>
            <CardTitle>Boletas por sede</CardTitle>
          </CardHeader>
          <CardContent className="h-[320px] min-w-0">
            {insights.isLoading ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                <BarChart data={insights.data?.by_sede || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="sede" hide />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="boletas" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
        <Card className="min-w-0 overflow-hidden">
          <CardHeader>
            <CardTitle>Top docentes</CardTitle>
          </CardHeader>
          <CardContent className="h-[320px] min-w-0">
            {insights.isLoading ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                <BarChart data={insights.data?.top_docentes || []}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="docente" hide />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="boletas" fill="#0d9488" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
      {!summary.isLoading && breakdown.length === 0 && (
        <Card>
          <CardContent>
            <EmptyState
              title="Sin resumen para mostrar"
              description="No hay métricas de período disponibles con la configuración actual."
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
