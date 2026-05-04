import { useEffect, useMemo, useState } from "react";
import { useAppConfig } from "@/app/app-config";
import { mapApiErrorMessage } from "@/shared/api/client";
import { usePeriodInsights, usePeriodSummary, usePeriods } from "@/shared/api/queries";
import { toCurrency } from "@/shared/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { ErrorState } from "@/shared/ui/error-state";
import { Select } from "@/shared/ui/select";
import { Skeleton } from "@/shared/ui/skeleton";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function PeriodPage() {
  const { baseUrl, apiKey } = useAppConfig();
  const periods = usePeriods(baseUrl, apiKey);
  const [selectedPeriodKey, setSelectedPeriodKey] = useState("");
  const selected =
    periods.data?.find((p) => `${p.year}-${p.month_name}` === selectedPeriodKey) || periods.data?.[0];
  const year = selected?.year;
  const month = selected?.month_name;
  const summary = usePeriodSummary(baseUrl, apiKey, year, month);
  const insights = usePeriodInsights(baseUrl, apiKey, year, month);

  useEffect(() => {
    if (!selectedPeriodKey && periods.data?.length) {
      setSelectedPeriodKey(`${periods.data[0].year}-${periods.data[0].month_name}`);
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
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">📅 Vista de período</h1>
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
      <Card>
        <CardHeader>
          <CardTitle>🗂️ Período activo</CardTitle>
        </CardHeader>
        <CardContent>
          <Select
            value={selected ? `${selected.year}-${selected.month_name}` : ""}
            onChange={(event) => setSelectedPeriodKey(event.target.value)}
          >
            {(periods.data || []).map((p) => (
              <option key={p.id} value={`${p.year}-${p.month_name}`}>
                {p.month_name} {p.year}
              </option>
            ))}
          </Select>
        </CardContent>
      </Card>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {(summary.isLoading ? Array.from({ length: 5 }, (_, i) => ({ label: `loading-${i}`, value: 0 })) : breakdown).map((item, idx) => (
          <Card key={idx} className="border-l-4 border-l-primary/50">
            <CardHeader>
              <CardTitle>{summary.isLoading ? "⏳ Cargando..." : item.label}</CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-semibold">
              {summary.isLoading ? <Skeleton className="h-8 w-12" /> : item.value}
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <Card className="bg-emerald-500/5 border-emerald-500/30">
          <CardHeader><CardTitle>💰 Monto total</CardTitle></CardHeader>
          <CardContent className="text-xl font-semibold">
            {insights.isLoading ? <Skeleton className="h-8 w-28" /> : toCurrency(insights.data?.kpis.monto_total)}
          </CardContent>
        </Card>
        <Card className="bg-cyan-500/5 border-cyan-500/30">
          <CardHeader><CardTitle>📊 Monto promedio</CardTitle></CardHeader>
          <CardContent className="text-xl font-semibold">
            {insights.isLoading ? <Skeleton className="h-8 w-28" /> : toCurrency(insights.data?.kpis.monto_promedio)}
          </CardContent>
        </Card>
        <Card className="bg-violet-500/5 border-violet-500/30">
          <CardHeader><CardTitle>👩‍🏫 Docentes únicos</CardTitle></CardHeader>
          <CardContent className="text-xl font-semibold">
            {insights.isLoading ? <Skeleton className="h-8 w-16" /> : insights.data?.kpis.docentes_unicos ?? 0}
          </CardContent>
        </Card>
        <Card className="bg-blue-500/5 border-blue-500/30">
          <CardHeader><CardTitle>✅ Boletas con XML</CardTitle></CardHeader>
          <CardContent className="text-xl font-semibold">
            {insights.isLoading ? <Skeleton className="h-8 w-16" /> : insights.data?.kpis.boletas_con_xml ?? 0}
          </CardContent>
        </Card>
        <Card className="bg-amber-500/5 border-amber-500/30">
          <CardHeader><CardTitle>⚠️ Boletas sin XML</CardTitle></CardHeader>
          <CardContent className="text-xl font-semibold">
            {insights.isLoading ? <Skeleton className="h-8 w-16" /> : insights.data?.kpis.boletas_sin_xml ?? 0}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="min-w-0 overflow-hidden">
          <CardHeader>
            <CardTitle>🏢 Boletas por sede</CardTitle>
          </CardHeader>
          <CardContent className="h-[320px] min-w-0">
            {insights.isLoading ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                <BarChart data={insights.data?.by_sede || []}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="sede" hide />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="boletas" fill="#2563eb" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
        <Card className="min-w-0 overflow-hidden">
          <CardHeader>
            <CardTitle>🏆 Top docentes por boletas</CardTitle>
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
