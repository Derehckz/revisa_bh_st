import { ArrowRight } from "lucide-react";
import type { PeriodRecommendation } from "@/shared/api/types";
import { Button } from "@/shared/ui/button";

type Props = {
  recommendation: PeriodRecommendation;
  onGoToStage: (stageNum: number, opts?: { remindersOnly?: boolean }) => void;
  onGoToSeguimiento: () => void;
  onGoToAvanzado: () => void;
};

export function NextStepCard({ recommendation, onGoToStage, onGoToSeguimiento, onGoToAvanzado }: Props) {
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
      onGoToStage(recommendation.stage_num, {
        remindersOnly:
          recommendation.kind === "reminders" || Boolean(recommendation.params?.reminders_only),
      });
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3 shadow-xs">
      <div className="min-w-0">
        <p className="text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">Siguiente</p>
        <p className="mt-0.5 text-sm font-semibold tracking-tight text-foreground">{recommendation.title}</p>
        <p className="text-[0.8125rem] leading-snug text-muted-foreground line-clamp-2">
          {recommendation.message}
        </p>
      </div>
      <Button type="button" size="sm" onClick={handleAction} className="shrink-0">
        {recommendation.action_label || "Continuar"}
        <ArrowRight size={14} strokeWidth={2} />
      </Button>
    </div>
  );
}
