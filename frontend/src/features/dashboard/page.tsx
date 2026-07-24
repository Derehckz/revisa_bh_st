import { Activity, AlertTriangle, CheckCircle2, Clock3, FileText, Mail, Receipt, UserCircle2 } from "lucide-react";
import { motion } from "framer-motion";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar } from "recharts";
import { useAppConfig } from "@/app/app-config";
import { mapApiErrorMessage } from "@/shared/api/client";
import { usePeriodInsights, usePeriodSummary, usePeriods, useRuns, useYearStats } from "@/shared/api/queries";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { ErrorState } from "@/shared/ui/error-state";
import { Badge } from "@/shared/ui/badge";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import { Skeleton } from "@/shared/ui/skeleton";
import { toCurrency } from "@/shared/lib/utils";
import { useEffect, useMemo, useState } from "react";

export function DashboardPage() {
  const { baseUrl, apiKey } = useAppConfig();
  const [selectedPeriodKey, setSelectedPeriodKey] = useState("");
  const periods = usePeriods(baseUrl, apiKey);
  const runs = useRuns(baseUrl, apiKey);
  const selectedPeriod =
    periods.data?.find((p) => `${p.year}-${p.month_name}` === selectedPeriodKey) || periods.data?.[0];
  const year = selectedPeriod?.year;
  const month = selectedPeriod?.month_name;
  const periodSummary = usePeriodSummary(baseUrl, apiKey, year, month);
  const periodInsights = usePeriodInsights(baseUrl, apiKey, year, month);
  const yearStats = useYearStats(baseUrl, apiKey, year);
  useEffect(() => {
    if (!selectedPeriodKey && periods.data?.length) {
      setSelectedPeriodKey(`${periods.data[0].year}-${periods.data[0].month_name}`);
    }
  }, [periods.data, selectedPeriodKey]);
  const ytd = useMemo(() => {
    if (!yearStats.data || !selectedPeriod) return null;
    const items = yearStats.data.periods.filter((p) => p.month_num <= selectedPeriod.month_num);
    const boletas = items.reduce((acc, p) => acc + p.boletas, 0);
    const xml = items.reduce((acc, p) => acc + p.xml, 0);
    const emails = items.reduce((acc, p) => acc + p.emails, 0);
    return {
      boletas,
      xml,
      emails,
      xmlCoverage: boletas ? Number(((xml / boletas) * 100).toFixed(2)) : 0,
      emailCoverage: boletas ? Number(((emails / boletas) * 100).toFixed(2)) : 0,
    };
  }, [yearStats.data, selectedPeriod]);

  const cards = [
    {
      icon: Receipt,
      label: "Boletas del mes",
      value: periodSummary.data?.metrics.total_boletas ?? 0,
      subtitle: month && year ? `${month} ${year}` : "Sin período",
    },
    {
      icon: Mail,
      label: "Cobertura XML",
      value: `${periodSummary.data?.metrics.xml_coverage_pct ?? 0}%`,
      subtitle: "Recepción mensual",
    },
    {
      icon: Activity,
      label: "Runs recientes",
      value: runs.data?.data.length ?? 0,
      subtitle: "Últimos 20",
    },
    {
      icon: FileText,
      label: "Boletas del año",
      value: yearStats.data?.totals.boletas ?? 0,
      subtitle: year ? `Año ${year}` : "Sin año",
    },
  ];
  const monthlyHealth = [
    { label: "Recibidas", value: periodSummary.data?.metrics.recibidos ?? 0, icon: CheckCircle2, tone: "text-success" },
    { label: "Con error", value: periodSummary.data?.metrics.recibidos_con_error ?? 0, icon: AlertTriangle, tone: "text-warning" },
    { label: "No recibidas", value: periodSummary.data?.metrics.no_recibidos ?? 0, icon: Clock3, tone: "text-danger" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Resumen del período en foco y salud operativa."
        actions={
          <Select
            className="min-w-[180px]"
            value={selectedPeriod ? `${selectedPeriod.year}-${selectedPeriod.month_name}` : ""}
            onChange={(event) => setSelectedPeriodKey(event.target.value)}
            aria-label="Período en foco"
          >
            {(periods.data || []).map((p) => (
              <option key={p.id} value={`${p.year}-${p.month_name}`}>
                {p.month_name} {p.year}
              </option>
            ))}
          </Select>
        }
      />
      {periodSummary.data?.data_freshness && periodSummary.data.data_freshness.status !== "ok" && (
        <p
          className={
            "rounded-md border px-3 py-2 text-sm " +
            (periodSummary.data.data_freshness.status === "degraded"
              ? "border-warning/30 bg-warning/10 text-warning"
              : "border-border bg-muted text-muted-foreground")
          }
          title={periodSummary.data.data_freshness.message}
        >
          Frescura: {periodSummary.data.data_freshness.message}
        </p>
      )}
      {(periods.isError || periodSummary.isError || periodInsights.isError || yearStats.isError || runs.isError) && (
        <ErrorState
          title="No pudimos cargar datos del dashboard"
          description={
            mapApiErrorMessage(
              (periods.error || periodSummary.error || periodInsights.error || yearStats.error || runs.error) as never
            )
          }
          onRetry={() => {
            periods.refetch();
            periodSummary.refetch();
            periodInsights.refetch();
            yearStats.refetch();
            runs.refetch();
          }}
        />
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((c, idx) => (
          <motion.div
            key={c.label}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.04 }}
            whileHover={{ y: -2 }}
          >
          <Card className="transition-shadow hover:shadow-card">
            <CardHeader className="flex flex-row items-center justify-between pb-1">
              <CardTitle className="text-muted-foreground">{c.label}</CardTitle>
              <c.icon size={16} strokeWidth={1.75} className="text-muted-foreground" />
            </CardHeader>
            <CardContent className="text-[1.75rem] font-semibold tracking-tight tabular-nums">
              {(periods.isLoading || runs.isLoading || periodSummary.isLoading || yearStats.isLoading) ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                c.value
              )}
              <p className="mt-1 text-xs font-normal tracking-normal text-muted-foreground">{c.subtitle}</p>
            </CardContent>
          </Card>
          </motion.div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Estado mensual</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-3">
            {monthlyHealth.map((item) => (
              <div key={item.label} className="rounded-md border border-border p-3">
                <div className="mb-1 flex items-center gap-2">
                  <item.icon size={15} className={item.tone} />
                  <span className="text-xs text-muted-foreground">{item.label}</span>
                </div>
                <p className="text-2xl font-semibold">{item.value}</p>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Monto del período</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-xs text-muted-foreground">Total del período activo</p>
            <p className="text-xl font-semibold">
              {periodInsights.isLoading ? <Skeleton className="h-7 w-28" /> : toCurrency(periodInsights.data?.kpis.monto_total)}
            </p>
            <p className="text-xs text-muted-foreground">Promedio por boleta</p>
            <p className="text-base font-medium">
              {periodInsights.isLoading ? <Skeleton className="h-5 w-24" /> : toCurrency(periodInsights.data?.kpis.monto_promedio)}
            </p>
            <div className="pt-1">
              <Badge>{`Docentes únicos: ${periodInsights.data?.kpis.docentes_unicos ?? 0}`}</Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Actividad reciente</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {runs.data?.data.slice(0, 8).map((r) => (
              <div key={r.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2">
                <span className="font-medium">{r.run_id}</span>
                <Badge tone={r.status === "OK" ? "success" : r.status === "ERROR" ? "danger" : "default"}>{r.status}</Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Acumulado año a la fecha</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-5">
          <div className="rounded-md border border-border p-3">
            <p className="text-xs text-muted-foreground">Boletas acumuladas</p>
            <p className="text-xl font-semibold">{ytd?.boletas ?? 0}</p>
          </div>
          <div className="rounded-md border border-border p-3">
            <p className="text-xs text-muted-foreground">XML acumulados</p>
            <p className="text-xl font-semibold">{ytd?.xml ?? 0}</p>
          </div>
          <div className="rounded-md border border-border p-3">
            <p className="text-xs text-muted-foreground">Emails acumulados</p>
            <p className="text-xl font-semibold">{ytd?.emails ?? 0}</p>
          </div>
          <div className="rounded-md border border-border p-3">
            <p className="text-xs text-muted-foreground">Cobertura XML YTD</p>
            <p className="text-xl font-semibold">{ytd?.xmlCoverage ?? 0}%</p>
          </div>
          <div className="rounded-md border border-border p-3">
            <p className="text-xs text-muted-foreground">Cobertura Email YTD</p>
            <p className="text-xl font-semibold">{ytd?.emailCoverage ?? 0}%</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tendencia anual</CardTitle>
        </CardHeader>
        <CardContent className="h-72">
          {yearStats.isLoading && <Skeleton className="h-full w-full" />}
          {!yearStats.isLoading && (yearStats.data?.periods.length || 0) === 0 && (
            <EmptyState title="Sin tendencia disponible" description="No hay datos anuales para graficar." />
          )}
          {(yearStats.data?.periods.length || 0) > 0 && (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={yearStats.data?.periods}>
                <defs>
                  <linearGradient id="colorBoletas" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.2} />
                <XAxis dataKey="month_name" />
                <YAxis />
                <Tooltip />
                <Area type="monotone" dataKey="boletas" stroke="#2563eb" fill="url(#colorBoletas)" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Distribución por sede</CardTitle>
        </CardHeader>
        <CardContent className="h-72">
          {periodInsights.isLoading && <Skeleton className="h-full w-full" />}
          {!periodInsights.isLoading && (periodInsights.data?.by_sede.length || 0) === 0 && (
            <EmptyState title="Sin distribución por sede" description="No hay datos para graficar sedes en este período." />
          )}
          {(periodInsights.data?.by_sede.length || 0) > 0 && (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={periodInsights.data?.by_sede}>
                <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.2} />
                <XAxis dataKey="sede" hide />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="boletas" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Top docentes</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {(periodInsights.data?.top_docentes || []).slice(0, 8).map((item) => (
            <div key={item.docente} className="flex items-center justify-between rounded-md border border-border px-3 py-2">
              <div className="flex items-center gap-2">
                <UserCircle2 size={16} className="text-muted-foreground" />
                <span className="text-sm">{item.docente}</span>
              </div>
              <div className="text-right text-xs text-muted-foreground">
                <div>{item.boletas} boletas</div>
                <div>{toCurrency(item.monto_total)}</div>
              </div>
            </div>
          ))}
          {!periodInsights.isLoading && (periodInsights.data?.top_docentes.length || 0) === 0 && (
            <EmptyState title="Sin top de docentes" description="No hay datos suficientes para construir el ranking." />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
