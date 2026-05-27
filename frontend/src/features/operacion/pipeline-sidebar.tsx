import type { PeriodOverviewStage, PipelineStageMeta, StageUiStatus } from "@/shared/api/types";
import { cn } from "@/shared/lib/utils";

type Props = {
  stages: PipelineStageMeta[];
  overviewStages?: PeriodOverviewStage[];
  activeStage: number;
  suggestedStageNum?: number | null;
  onSelect: (stageNum: number) => void;
};

const STATUS_DOT: Record<StageUiStatus, string> = {
  READY: "bg-slate-400",
  BLOCKED: "bg-amber-500",
  RUNNING: "bg-blue-500 animate-pulse",
  OK: "bg-green-600",
  ERROR: "bg-red-600",
};

const STATUS_LABEL: Record<StageUiStatus, string> = {
  READY: "Listo",
  BLOCKED: "Bloqueado",
  RUNNING: "En curso",
  OK: "Hecho",
  ERROR: "Error",
};

function shortDescription(desc: string, max = 42) {
  if (desc.length <= max) return desc;
  return `${desc.slice(0, max)}…`;
}

export function PipelineSidebar({ stages, overviewStages, activeStage, suggestedStageNum, onSelect }: Props) {
  const overviewByNum = new Map(overviewStages?.map((s) => [s.stage_num, s]) ?? []);
  const sorted = [...stages].sort((a, b) => a.stage_num - b.stage_num);

  return (
    <nav className="space-y-1" aria-label="Pasos del pipeline">
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Pasos 0–10</p>
      {sorted.map((s) => {
        const ov = overviewByNum.get(s.stage_num);
        const uiStatus = ov?.ui_status ?? (s.enabled_for_api ? "READY" : "BLOCKED");
        const isActive = s.stage_num === activeStage;
        const isSuggested = suggestedStageNum != null && s.stage_num === suggestedStageNum;
        return (
          <button
            key={s.stage_num}
            type="button"
            onClick={() => onSelect(s.stage_num)}
            className={cn(
              "flex w-full items-start gap-2 rounded-md border px-2 py-2 text-left text-sm transition-colors",
              isActive ? "border-primary bg-primary/10" : "border-transparent hover:bg-muted",
              isSuggested && !isActive && "ring-1 ring-primary/50"
            )}
          >
            <span
              className={cn("mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full", STATUS_DOT[uiStatus])}
              title={STATUS_LABEL[uiStatus]}
            />
            <span className="min-w-0 flex-1">
              <span className="flex items-center justify-between gap-1">
                <span className="font-medium">Paso {s.stage_num}</span>
                {uiStatus === "OK" && (
                  <span className="text-[10px] font-medium text-green-700 shrink-0">OK</span>
                )}
                {uiStatus === "ERROR" && (
                  <span className="text-[10px] font-medium text-red-700 shrink-0">Error</span>
                )}
              </span>
              <span className="block text-xs text-muted-foreground line-clamp-2">
                {shortDescription(s.description)}
              </span>
              {ov?.last_job && (uiStatus === "OK" || uiStatus === "ERROR") && (
                <span className="block text-[10px] text-muted-foreground truncate" title={ov.last_job.label}>
                  {ov.last_job.source === "filesystem" ? "Consola" : "Web"}
                  {ov.last_job.created_at
                    ? ` · ${new Date(ov.last_job.created_at).toLocaleDateString("es-CL")}`
                    : ""}
                </span>
              )}
            </span>
          </button>
        );
      })}
      <div className="mt-3 space-y-1 border-t border-border pt-2 text-[11px] text-muted-foreground">
        <p className="font-medium">Leyenda</p>
        <LegendItem color={STATUS_DOT.READY} label="Listo para ejecutar" />
        <LegendItem color={STATUS_DOT.BLOCKED} label="Faltan requisitos" />
        <LegendItem color={STATUS_DOT.OK} label="Última ejecución OK" />
        <LegendItem color={STATUS_DOT.ERROR} label="Última ejecución falló" />
      </div>
    </nav>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={cn("h-2 w-2 rounded-full", color)} />
      {label}
    </span>
  );
}
