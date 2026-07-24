import type { PeriodOverviewStage, StageUiStatus } from "@/shared/api/types";
import { Badge } from "@/shared/ui/badge";

const STATUS_LABEL: Record<StageUiStatus, string> = {
  READY: "Listo",
  BLOCKED: "Bloqueado",
  RUNNING: "Ejecutando",
  OK: "Completado",
  ERROR: "Falló",
};

const STATUS_TONE: Record<StageUiStatus, "default" | "success" | "danger" | "warning"> = {
  READY: "default",
  BLOCKED: "warning",
  RUNNING: "warning",
  OK: "success",
  ERROR: "danger",
};

type Props = {
  stage?: PeriodOverviewStage;
};

export function StageHeaderBanner({ stage }: Props) {
  if (!stage) return null;

  const last = stage.last_job;

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-border/80 bg-muted/40 px-3 py-2 text-[0.8125rem]">
      <span className="text-muted-foreground">Estado</span>
      <Badge tone={STATUS_TONE[stage.ui_status]}>{STATUS_LABEL[stage.ui_status]}</Badge>
      {last && (
        <span className="text-muted-foreground">
          Última ({last.source === "filesystem" ? "consola" : "web"}):{" "}
          <span className="font-medium text-foreground" title={last.label ?? last.id}>
            {last.label ?? last.id}
          </span>
          {last.status === "success" || last.status === "unknown" ? " · OK" : ` · ${last.status}`}
          {(last.finished_at || last.created_at) &&
            ` · ${new Date(last.finished_at ?? last.created_at!).toLocaleString("es-CL")}`}
        </span>
      )}
      {!stage.prerequisites.ok && (
        <span className="w-full text-warning sm:w-auto">{stage.prerequisites.message}</span>
      )}
    </div>
  );
}
