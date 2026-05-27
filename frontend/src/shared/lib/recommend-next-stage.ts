import type { PeriodOverviewResponse, PeriodRecommendation } from "@/shared/api/types";

/** Fallback si la API aún no envía `recommendation` (uvicorn viejo). */
export function recommendFromOverview(overview: PeriodOverviewResponse): PeriodRecommendation {
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

  if (!kpis.solicitud_exists) {
    return {
      kind: "run",
      stage_num: 0,
      title: "Generar Solicitud",
      message: "No hay Solicitud.xlsx en el mes.",
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
