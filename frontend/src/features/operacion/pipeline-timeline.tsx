import type { PipelineStageMeta } from "@/shared/api/types";
import { Badge } from "@/shared/ui/badge";

type Props = {
  stages: PipelineStageMeta[];
  activeStage: number;
  onSelect: (stageNum: number) => void;
};

export function PipelineTimeline({ stages, activeStage, onSelect }: Props) {
  const sorted = [...stages].sort((a, b) => a.stage_num - b.stage_num);

  return (
    <div className="flex flex-wrap gap-2">
      {sorted.map((s) => {
        const isActive = s.stage_num === activeStage;
        const enabled = s.enabled_for_api;
        return (
          <button
            key={s.stage_num}
            type="button"
            onClick={() => onSelect(s.stage_num)}
            className={`rounded-md border px-3 py-2 text-left text-xs transition-colors ${
              isActive ? "border-primary bg-primary/10" : "border-border hover:bg-muted"
            }`}
          >
            <div className="flex items-center gap-2">
              <span className="font-semibold">Paso {s.stage_num}</span>
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
