import { Activity, AlertTriangle, CheckCircle2, Clock3, FileText, Mail, Receipt, UserCircle2 } from "lucide-react";
import { motion } from "framer-motion";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar } from "recharts";
import { useAppConfig } from "@/app/app-config";
import { mapApiErrorMessage } from "@/shared/api/client";
import { usePeriodInsights, usePeriodSummary, usePeriods, useRuns, useYearStats } from "@/shared/api/queries";
import {
  defaultOperationPeriodKey,
  monthsForYear,
  periodKey,
  resolveOperationPeriod,
  yearsFromPeriods,
} from "@/shared/lib/default-period";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { ErrorState } from "@/shared/ui/error-state";
import { Badge } from "@/shared/ui/badge";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import { Skeleton } from "@/shared/ui/skeleton";
import { cn, toCurrency } from "@/shared/lib/utils";
import { useEffect, useMemo, useState } from "react";

type Scope = "mes" | "ytd" | "anio";

export function DashboardPage() {
  const { baseUrl, apiKey } = useAppConfig();
  const [selectedPeriodKey, setSelectedPeriodKey] = useState("");
  const [scope, setScope] = useState<Scope>("mes");
  const periods = usePeriods(baseUrl, apiKey);
  const runs = useRuns(baseUrl, apiKey);

  useEffect(() => {
    if (!periods.data?.length) return;
    const exists = periods.data.some((p) => periodKey(p.year, p.month_name) === selectedPeriodKey);
    if (!selectedPeriodKey || !exists) {
      setSelectedPeriodKey(defaultOperationPeriodKey(periods.data) || "");
    }
  }, [periods.data, selectedPeriodKey]);

  const selectedPeriod = resolveOperationPeriod(periods.data ?? [], selectedPeriodKey);
  const year = selectedPeriod?.year;
  const month = selectedPeriod?.month_name;
  const years = useMemo(() => yearsFromPeriods(periods.data ?? []), [periods.data]);
  const monthsInYear = useMemo(
    () => (year ? monthsForYear(periods.data ?? [], year) : []),
    [periods.data, year]
  );

  const periodSummary = usePeriodSummary(baseUrl, apiKey, year, month);
  const periodInsights = usePeriodInsights(baseUrl, apiKey, year, month);
  const yearStats = useYearStats(baseUrl, apiKey, year);

  const ytd = useMemo(() => {
    if (!yearStats.data || !selectedPeriod) return null;
    const items = yearStats.data.periods.filter((p) => p.month_num <= selectedPeriod.month_num);
    const boletas = items.reduce((acc, p) => acc + p.boletas, 0);
    const xml = items.reduce((acc, p) => acc + p.xml, 0);
    const emails = items.reduce((acc, p) => acc + p.emails, 0);
    const monto = items.reduce((acc, p) => acc + (p.monto_total ?? 0), 0);
    return {
      boletas,
      xml,
      emails,
      monto,
      xmlCoverage: boletas ? Number(((xml / boletas) * 100).toFixed(2)) : 0,
      emailCoverage: boletas ? Number(((emails / boletas) * 100).toFixed(2)) : 0,
      throughMonth: selectedPeriod.month_name,
    };
  }, [yearStats.data, selectedPeriod]);

  const yearTotals = yearStats.data?.totals;

  const focus = useMemo(() => {
    if (scope === "anio" && yearTotals) {
      return {
        title: `Año ${year}`,
        boletas: yearTotals.boletas,
        xml: yearTotals.xml,
        emails: yearTotals.emails,
        monto: yearTotals.monto_total ?? 0,
        xmlPct: yearTotals.xml_coverage_pct,
        emailPct: yearTotals.email_coverage_pct,
      };
    }
    if (scope === "ytd" && ytd) {
      return {
        title: `Acumulado Ene–${ytd.throughMonth} ${year}`,
        boletas: ytd.boletas,
        xml: ytd.xml,
        emails: ytd.emails,
        monto: ytd.monto,
        xmlPct: ytd.xmlCoverage,
        emailPct: ytd.emailCoverage,
      };
    }
    return {
      title: month && year ? `${month} ${year}` : "Mes",
      boletas: periodSummary.data?.metrics.total_boletas ?? 0,
      xml: periodSummary.data?.metrics.total_xml ?? 0,
      emails: periodSummary.data?.metrics.total_emails ?? 0,
      monto: periodInsights.data?.kpis.monto_total ?? 0,
      xmlPct: periodSummary.data?.metrics.xml_coverage_pct ?? 0,
      emailPct:
        periodSummary.data?.metrics.total_boletas
          ? Number(
              (
                ((periodSummary.data.metrics.total_emails || 0) /
                  periodSummary.data.metrics.total_boletas) *
                100
              ).toFixed(2)
            )
          : 0,
    };
  }, [scope, yearTotals, ytd, year, month, periodSummary.data, periodInsights.data]);

  const cards = [
    {
      icon: Receipt,
      label: scope === "mes" ? "Boletas del mes" : "Boletas",
      value: focus.boletas,
      subtitle: focus.title,
    },
    {
      icon: FileText,
      label: "Monto honorarios",
      value: toCurrency(focus.monto),
      subtitle: scope === "mes" ? "Bruto del período" : "Acumulado",
    },
    {
      icon: Mail,
      label: "Cobertura XML",
      value: `${focus.xmlPct}%`,
      subtitle: `${focus.xml} XML`,
    },
    {
      icon: Activity,
      label: "Correos / runs",
      value: scope === "mes" ? (runs.data?.data.length ?? 0) : focus.emails,
      subtitle: scope === "mes" ? "Runs recientes" : "Emails acumulados",
    },
  ];

  const monthlyHealth = [
    { label: "Recibidas", value: periodSummary.data?.metrics.recibidos ?? 0, icon: CheckCircle2, tone: "text-success" },
    { label: "Con error", value: periodSummary.data?.metrics.recibidos_con_error ?? 0, icon: AlertTriangle, tone: "text-warning" },
    { label: "No recibidas", value: periodSummary.data?.metrics.no_recibidos ?? 0, icon: Clock3, tone: "text-danger" },
  ];

  function onYearChange(nextYear: number) {
    const months = monthsForYear(periods.data ?? [], nextYear);
    const pick = months[0];
    if (pick) setSelectedPeriodKey(periodKey(pick.year, pick.month_name));
  }

  function onMonthChange(monthName: string) {
    if (!year) return;
    setSelectedPeriodKey(periodKey(year, monthName));
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Resumen del mes en foco y acumulado del año. Por defecto abre el último mes."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
              Año
              <Select
                className="min-w-[96px]"
                value={year ? String(year) : ""}
                onChange={(e) => onYearChange(Number(e.target.value))}
                aria-label="Año"
              >
                {years.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </Select>
            </label>
            <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
              Mes
              <Select
                className="min-w-[140px]"
                value={month || ""}
                onChange={(e) => onMonthChange(e.target.value)}
                aria-label="Mes"
              >
                {monthsInYear.map((p) => (
                  <option key={p.id} value={p.month_name}>
                    {p.month_name}
                    {p.status === "cerrado" ? " (cerrado)" : ""}
                  </option>
                ))}
              </Select>
            </label>
            <div className="inline-flex rounded-md border border-border p-0.5">
              {(
                [
                  ["mes", "Mes"],
                  ["ytd", "Acumulado"],
                  ["anio", "Año completo"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setScope(id)}
                  className={cn(
                    "rounded px-2.5 py-1.5 text-xs font-medium",
                    scope === id ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
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
                {periods.isLoading || runs.isLoading || periodSummary.isLoading || yearStats.isLoading ? (
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

      <Card>
        <CardHeader>
          <CardTitle>Acumulado del año {year || "—"}</CardTitle>
          <p className="text-xs font-normal text-muted-foreground">
            Hasta {ytd?.throughMonth || month || "—"} (YTD) vs año completo.
          </p>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <AccStat label="Boletas YTD" value={String(ytd?.boletas ?? 0)} />
          <AccStat label="Monto YTD" value={toCurrency(ytd?.monto ?? 0)} />
          <AccStat label="XML YTD" value={`${ytd?.xmlCoverage ?? 0}%`} />
          <AccStat label="Boletas año" value={String(yearTotals?.boletas ?? 0)} />
          <AccStat label="Monto año" value={toCurrency(yearTotals?.monto_total ?? 0)} />
          <AccStat label="Emails año" value={String(yearTotals?.emails ?? 0)} />
        </CardContent>
      </Card>

      {scope === "mes" ? (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Estado del mes</CardTitle>
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
              <CardTitle>Monto del mes</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <p className="text-xs text-muted-foreground">Total del período activo</p>
              <p className="text-xl font-semibold">
                {periodInsights.isLoading ? (
                  <Skeleton className="h-7 w-28" />
                ) : (
                  toCurrency(periodInsights.data?.kpis.monto_total)
                )}
              </p>
              <p className="text-xs text-muted-foreground">Promedio por boleta</p>
              <p className="text-base font-medium">
                {periodInsights.isLoading ? (
                  <Skeleton className="h-5 w-24" />
                ) : (
                  toCurrency(periodInsights.data?.kpis.monto_promedio)
                )}
              </p>
              <div className="pt-1">
                <Badge>{`Docentes únicos: ${periodInsights.data?.kpis.docentes_unicos ?? 0}`}</Badge>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Actividad reciente</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {runs.data?.data.slice(0, 8).map((r) => (
              <div key={r.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2">
                <span className="font-medium">{r.run_id}</span>
                <Badge tone={r.status === "OK" ? "success" : r.status === "ERROR" ? "danger" : "default"}>
                  {r.status}
                </Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tendencia {year || ""}</CardTitle>
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
                <Area type="monotone" dataKey="boletas" stroke="#2563eb" fill="url(#colorBoletas)" name="Boletas" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {scope === "mes" ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Distribución por sede</CardTitle>
            </CardHeader>
            <CardContent className="h-72">
              {periodInsights.isLoading && <Skeleton className="h-full w-full" />}
              {!periodInsights.isLoading && (periodInsights.data?.by_sede.length || 0) === 0 && (
                <EmptyState
                  title="Sin distribución por sede"
                  description="No hay datos para graficar sedes en este período."
                />
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
                <div
                  key={item.docente}
                  className="flex items-center justify-between rounded-md border border-border px-3 py-2"
                >
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
                <EmptyState
                  title="Sin top de docentes"
                  description="No hay datos suficientes para construir el ranking."
                />
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}

function AccStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold tabular-nums tracking-tight">{value}</p>
    </div>
  );
}
