import { ArrowRight, Clock, PlayCircle, Wrench } from "lucide-react";
import type { PeriodRecommendation } from "@/shared/api/types";
import { Button } from "@/shared/ui/button";
import { cn } from "@/shared/lib/utils";

type Props = {
  recommendation: PeriodRecommendation;
  onGoToStage: (stageNum: number) => void;
  onGoToSeguimiento: () => void;
  onGoToAvanzado: () => void;
};

const KIND_STYLE: Record<
  PeriodRecommendation["kind"],
  { border: string; bg: string; Icon: typeof PlayCircle }
> = {
  run: { border: "border-primary/40", bg: "bg-primary/5", Icon: PlayCircle },
  wait: { border: "border-amber-300", bg: "bg-amber-50", Icon: Clock },
  fix: { border: "border-amber-400", bg: "bg-amber-50", Icon: Wrench },
  complete: { border: "border-green-300", bg: "bg-green-50", Icon: PlayCircle },
  review: { border: "border-border", bg: "bg-muted/40", Icon: PlayCircle },
  outbox: { border: "border-blue-300", bg: "bg-blue-50", Icon: Wrench },
};

export function NextStepCard({ recommendation, onGoToStage, onGoToSeguimiento, onGoToAvanzado }: Props) {
  const style = KIND_STYLE[recommendation.kind];
  const Icon = style.Icon;

  function handleAction() {
    if (recommendation.kind === "wait") {
      onGoToSeguimiento();
      return;
    }
    if (recommendation.kind === "outbox") {
      onGoToAvanzado();
      return;
    }
    if (recommendation.stage_num != null) {
      onGoToStage(recommendation.stage_num);
    }
  }

  return (
    <div className={cn("rounded-lg border p-4", style.border, style.bg)}>
      <div className="flex flex-wrap items-start gap-3">
        <Icon className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden />
        <div className="min-w-0 flex-1 space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Siguiente paso sugerido
          </p>
          <p className="font-semibold">{recommendation.title}</p>
          <p className="text-sm text-muted-foreground">{recommendation.message}</p>
        </div>
        <Button type="button" onClick={handleAction} className="shrink-0">
          <span className="inline-flex items-center gap-1">
            {recommendation.action_label || "Continuar"}
            <ArrowRight size={14} />
          </span>
        </Button>
      </div>
    </div>
  );
}
