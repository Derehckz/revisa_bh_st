import type { Period, PeriodOverviewResponse, PeriodRecommendation } from "@/shared/api/types";
import { isPeriodClosed } from "@/shared/lib/period-operation-guard";

function isClosedOverviewStatus(status?: string | null): boolean {
  return (status ?? "").trim().toLowerCase().includes("cerrad");
}

/** Fallback si la API aún no envía `recommendation` (uvicorn viejo). */
export function recommendFromOverview(overview: PeriodOverviewResponse): PeriodRecommendation {
  const periodStatus = overview.period?.status;
  if (isClosedOverviewStatus(periodStatus)) {
    const label = `${overview.period.month} ${overview.period.year}`;
    return {
      kind: "review",
      stage_num: null,
      title: "Período cerrado",
      message: `El período ${label} está cerrado en BD. La API no permite jobs ni sesiones. Cambia a un mes abierto o usa la consola.`,
      action_label: "Cambiar período",
    };
  }

  if (overview.recommendation) return overview.recommendation;

  const { stages, kpis, running_job } = overview;
  const sorted = [...stages].sort((a, b) => a.stage_num - b.stage_num);

  if (running_job) {
    const sn = running_job.stage_num ?? 0;
    return {
      kind: "wait",
      stage_num: sn,
      title: "Job en ejecución",
      message: `Espera a que termine el paso ${sn}.`,
      action_label: "Ver seguimiento",
    };
  }

  const failed = sorted.find((s) => s.ui_status === "ERROR" && s.enabled_for_api);
  if (failed) {
    return {
      kind: "run",
      stage_num: failed.stage_num,
      title: `Reintentar paso ${failed.stage_num}`,
      message: "La última ejecución falló.",
      action_label: `Ir a paso ${failed.stage_num}`,
    };
  }

  if (!kpis.total_rows) {
    return {
      kind: "run",
      stage_num: 0,
      title: "Generar Solicitud",
      message: "Aún no hay solicitudes en este período.",
      action_label: "Ir a paso 0",
    };
  }

  const blocked = sorted.find((s) => s.ui_status === "BLOCKED");
  if (blocked) {
    return {
      kind: "fix",
      stage_num: blocked.stage_num,
      title: `Desbloquear paso ${blocked.stage_num}`,
      message: blocked.prerequisites.message || "Revisa requisitos.",
      action_label: `Ir a paso ${blocked.stage_num}`,
    };
  }

  const ready = sorted.find((s) => s.ui_status === "READY" && s.enabled_for_api);
  const noRecibidos = overview.kpis?.no_recibidos ?? 0;
  const stage3Ok = sorted.some((s) => s.stage_num === 3 && s.ui_status === "OK");
  const inboundReady =
    ready != null && [2, 3, 4, 5].includes(ready.stage_num) && ready.enabled_for_api;

  if (noRecibidos > 0 && stage3Ok && !inboundReady) {
    return {
      kind: "reminders",
      stage_num: 1,
      title: "Recordatorios a pendientes",
      message: `Hay ${noRecibidos} fila(s) NO RECIBIDO. Vuelve al paso 1 en modo solo recordatorios.`,
      action_label: "Paso 1 · solo recordatorios",
      params: { reminders_only: true },
    };
  }

  if (ready) {
    return {
      kind: "run",
      stage_num: ready.stage_num,
      title: `Siguiente: paso ${ready.stage_num}`,
      message: ready.description,
      action_label: `Ir a paso ${ready.stage_num}`,
    };
  }

  return {
    kind: "complete",
    stage_num: null,
    title: "Pipeline al día",
    message: "Pasos API con última ejecución OK.",
    action_label: "Ver paso 10",
  };
}

/** Combina recomendación API con estado del período seleccionado en el toolbar. */
export function recommendForOperation(
  overview: PeriodOverviewResponse | undefined,
  selectedPeriod?: Period
): PeriodRecommendation | null {
  if (!overview) return null;
  if (selectedPeriod && isPeriodClosed(selectedPeriod)) {
    const label = `${selectedPeriod.month_name} ${selectedPeriod.year}`;
    return {
      kind: "review",
      stage_num: null,
      title: "Período cerrado",
      message: `Has seleccionado ${label}, que está cerrado. Cambia el mes arriba antes de ejecutar pasos.`,
      action_label: "Cambiar período",
    };
  }
  return recommendFromOverview(overview);
}
