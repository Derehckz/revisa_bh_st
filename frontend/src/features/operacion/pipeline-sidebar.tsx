import type { PeriodOverviewStage, PipelineStageMeta, StageUiStatus } from "@/shared/api/types";
import { cn } from "@/shared/lib/utils";

type Props = {
  stages: PipelineStageMeta[];
  overviewStages?: PeriodOverviewStage[];
  activeStage: number;
  suggestedStageNum?: number | null;
  onSelect: (stageNum: number) => void;
};

const SHORT: Record<number, string> = {
  0: "Generar Solicitud",
  1: "Enviar correos",
  2: "Bajar boletas",
  3: "Marcar recibidos",
  4: "Completar datos",
  5: "Correo recepción",
  6: "Informe final",
  7: "Pagos / correo",
  8: "Clasificar",
  9: "Nómina",
  10: "Revisar carpetas",
};

const STATUS_DOT: Record<StageUiStatus, string> = {
  READY: "bg-muted-foreground/35",
  BLOCKED: "bg-warning",
  RUNNING: "bg-primary animate-pulse",
  OK: "bg-success",
  ERROR: "bg-danger",
};

export function PipelineSidebar({ stages, overviewStages, activeStage, suggestedStageNum, onSelect }: Props) {
  const overviewByNum = new Map(overviewStages?.map((s) => [s.stage_num, s]) ?? []);
  const sorted = [...stages].sort((a, b) => a.stage_num - b.stage_num);

  return (
    <nav className="space-y-0.5" aria-label="Pasos">
      <p className="mb-2 px-2 text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">
        Pasos
      </p>
      {sorted.map((s) => {
        const ov = overviewByNum.get(s.stage_num);
        const uiStatus = ov?.ui_status ?? (s.enabled_for_api ? "READY" : "BLOCKED");
        const isActive = s.stage_num === activeStage;
        const isSuggested = suggestedStageNum != null && s.stage_num === suggestedStageNum;
        const label = SHORT[s.stage_num] ?? s.description;
        return (
          <button
            key={s.stage_num}
            type="button"
            onClick={() => onSelect(s.stage_num)}
            className={cn(
              "flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-[0.8125rem] font-medium tracking-tight transition-colors",
              isActive
                ? "bg-card text-foreground shadow-xs"
                : "text-muted-foreground hover:bg-card/70 hover:text-foreground",
              isSuggested && !isActive && "ring-1 ring-primary/25"
            )}
          >
            <span
              className={cn("h-1.5 w-1.5 shrink-0 rounded-full", STATUS_DOT[uiStatus])}
              aria-hidden
            />
            <span className="min-w-0 flex-1 truncate">
              <span className="tabular-nums text-muted-foreground">{s.stage_num}</span>
              <span className="mx-1 text-border">·</span>
              {label}
            </span>
            {uiStatus === "OK" && (
              <span className="text-2xs font-semibold text-success">OK</span>
            )}
            {uiStatus === "ERROR" && (
              <span className="text-2xs font-semibold text-danger">Error</span>
            )}
          </button>
        );
      })}
    </nav>
  );
}
