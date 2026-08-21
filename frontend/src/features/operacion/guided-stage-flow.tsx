import { useState, type ReactNode } from "react";
import { CheckCircle2, ChevronLeft, ChevronRight, FolderOpen } from "lucide-react";
import type { InteractiveChoices, PeriodKpis, PrerequisiteItem, StageGuide } from "@/shared/api/types";
import { Button } from "@/shared/ui/button";
import { PrerequisiteChecklist } from "./prerequisite-checklist";
import { cn } from "@/shared/lib/utils";

export type WizardStepId = "review" | "configure" | "confirm";

const WIZARD_STEPS: { id: WizardStepId; label: string }[] = [
  { id: "review", label: "1. Revisar" },
  { id: "configure", label: "2. Elegir opciones" },
  { id: "confirm", label: "3. Confirmar" },
];

type Props = {
  guide: StageGuide;
  choices?: InteractiveChoices;
  kpis?: PeriodKpis;
  checklist?: PrerequisiteItem[];
  prereqOk: boolean;
  configureContent: ReactNode;
  confirmSummary: ReactNode;
  reviewExtra?: ReactNode;
  onExecute: () => void;
  executeDisabled: boolean;
  isExecuting: boolean;
  executeLabel: React.ReactNode;
};

export function GuidedStageFlow({
  guide,
  choices,
  kpis,
  checklist,
  prereqOk,
  configureContent,
  confirmSummary,
  reviewExtra,
  onExecute,
  executeDisabled,
  isExecuting,
  executeLabel,
}: Props) {
  const [step, setStep] = useState<WizardStepId>("review");

  const stepIndex = WIZARD_STEPS.findIndex((s) => s.id === step);

  function goNext() {
    const next = WIZARD_STEPS[stepIndex + 1];
    if (next) setStep(next.id);
  }

  function goBack() {
    const prev = WIZARD_STEPS[stepIndex - 1];
    if (prev) setStep(prev.id);
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-primary/20 bg-primary/5 p-4">
        <h3 className="text-base font-semibold">{guide.title}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{guide.summary}</p>
      </div>

      <nav className="flex flex-wrap gap-2" aria-label="Pasos del asistente">
        {WIZARD_STEPS.map((s, i) => {
          const active = s.id === step;
          const done = i < stepIndex;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => setStep(s.id)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                active && "border-primary bg-primary text-primary-foreground",
                !active && done && "border-border bg-muted/70 text-foreground",
                !active && !done && "border-border bg-card text-muted-foreground hover:bg-muted"
              )}
            >
              {done && <CheckCircle2 className="inline mr-1 h-3 w-3 text-muted-foreground" />}
              {s.label}
            </button>
          );
        })}
      </nav>

      {step === "review" && (
        <div className="space-y-3">
          <ul className="space-y-2 text-sm">
            {guide.steps.map((gs) => (
              <li key={gs.id} className="rounded-md border border-border bg-muted/30 px-3 py-2">
                <p className="font-medium">{gs.title}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{gs.detail}</p>
              </li>
            ))}
          </ul>

          {choices?.month_dir && (
            <div className="flex items-start gap-2 rounded-md border border-border p-3 text-sm">
              <FolderOpen className="h-4 w-4 shrink-0 mt-0.5 text-muted-foreground" />
              <div>
                <p className="font-medium">Carpeta de trabajo</p>
                <p className="text-xs text-muted-foreground break-all">{choices.month_dir}</p>
                <p className="text-xs mt-1">Período: {choices.month_dir_label}</p>
              </div>
            </div>
          )}

          {kpis && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-xs">
              <KpiBox label="Solicitudes" value={(kpis.total_rows ?? 0) > 0 ? String(kpis.total_rows) : "—"} />
              <KpiBox label="Recibidos" value={String(kpis.recibidos)} />
              <KpiBox label="XML en mes" value={String(kpis.xml_files_in_month)} />
              <KpiBox label="PDF en mes" value={String(kpis.pdf_files_in_month)} />
            </div>
          )}

          {checklist && <PrerequisiteChecklist items={checklist} />}

          {reviewExtra}

          {!prereqOk && (
            <p className="text-sm text-amber-800">
              Completa los requisitos en rojo antes de continuar. Si falta un archivo, súbelo a la carpeta del mes.
            </p>
          )}
        </div>
      )}

      {step === "configure" && <div className="space-y-3">{configureContent}</div>}

      {step === "confirm" && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Revisa un último vistazo. Si algo no cuadra, vuelve al paso 2 con «Atrás».
          </p>
          {confirmSummary}
        </div>
      )}

      <div className="flex flex-wrap gap-2 border-t border-border pt-3">
        {stepIndex > 0 && (
          <Button type="button" variant="outline" onClick={goBack}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            Atrás
          </Button>
        )}
        {step !== "confirm" && (
          <Button type="button" onClick={goNext} disabled={step === "review" && !prereqOk}>
            Siguiente
            <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        )}
        {step === "confirm" && (
          <Button type="button" onClick={onExecute} disabled={executeDisabled || isExecuting}>
            {executeLabel}
          </Button>
        )}
      </div>
    </div>
  );
}

function KpiBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-card px-2 py-2">
      <p className="text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  );
}
