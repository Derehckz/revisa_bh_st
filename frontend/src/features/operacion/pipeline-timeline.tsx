import type { PeriodOverviewStage, PipelineStageMeta, StageUiStatus } from "@/shared/api/types";
import { Badge } from "@/shared/ui/badge";

type Props = {
  stages: PipelineStageMeta[];
  overviewStages?: PeriodOverviewStage[];
  activeStage: number;
  onSelect: (stageNum: number) => void;
};

const STATUS_LABEL: Record<StageUiStatus, string> = {
  READY: "Listo",
  BLOCKED: "Bloqueado",
  RUNNING: "Ejecutando",
  OK: "OK",
  ERROR: "Error",
};

const STATUS_TONE: Record<StageUiStatus, "default" | "success" | "danger" | "warning"> = {
  READY: "default",
  BLOCKED: "warning",
  RUNNING: "warning",
  OK: "success",
  ERROR: "danger",
};

export function PipelineTimeline({ stages, overviewStages, activeStage, onSelect }: Props) {
  const statusByNum = new Map(overviewStages?.map((s) => [s.stage_num, s.ui_status]) ?? []);
  const sorted = [...stages].sort((a, b) => a.stage_num - b.stage_num);

  return (
    <div className="flex flex-wrap gap-2">
      {sorted.map((s) => {
        const isActive = s.stage_num === activeStage;
        const enabled = s.enabled_for_api;
        const uiStatus = statusByNum.get(s.stage_num);
        return (
          <button
            key={s.stage_num}
            type="button"
            onClick={() => onSelect(s.stage_num)}
            className={`rounded-md border px-3 py-2 text-left text-xs transition-colors ${
              isActive ? "border-primary bg-primary/10" : "border-border hover:bg-muted"
            }`}
          >
            <div className="flex flex-wrap items-center gap-1">
              <span className="font-semibold">Paso {s.stage_num}</span>
              {uiStatus && (
                <Badge tone={STATUS_TONE[uiStatus]}>{STATUS_LABEL[uiStatus]}</Badge>
              )}
              {enabled ? (
                <Badge tone="success">API</Badge>
              ) : (
                <Badge tone="default">Consola</Badge>
              )}
            </div>
            <p className="mt-1 max-w-[140px] text-muted-foreground line-clamp-2">{s.description}</p>
          </button>
        );
      })}
    </div>
  );
}
