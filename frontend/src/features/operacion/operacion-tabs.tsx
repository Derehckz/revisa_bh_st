import { cn } from "@/shared/lib/utils";

export type OperacionTab = "ejecutar" | "avance" | "cierre" | "seguimiento" | "avanzado";

type Props = {
  active: OperacionTab;
  onChange: (tab: OperacionTab) => void;
  hasRunningJob: boolean;
  cierreNeedsAttention?: boolean;
};

const TABS: { id: OperacionTab; label: string }[] = [
  { id: "ejecutar", label: "Ejecutar" },
  { id: "avance", label: "Avance" },
  { id: "cierre", label: "Cierre" },
  { id: "seguimiento", label: "Resultados" },
  { id: "avanzado", label: "Más" },
];

export function OperacionTabs({ active, onChange, hasRunningJob, cierreNeedsAttention }: Props) {
  return (
    <div className="border-b border-border/80 px-3 pt-3" role="tablist" aria-label="Secciones de operación">
      <div className="inline-flex max-w-full gap-0.5 overflow-x-auto rounded-lg bg-muted/70 p-0.5">
        {TABS.map((tab) => {
          const isActive = active === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => onChange(tab.id)}
              className={cn(
                "relative shrink-0 rounded-md px-3 py-1.5 text-[0.8125rem] font-medium tracking-tight transition-colors",
                isActive
                  ? "bg-card text-foreground shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {tab.label}
              {tab.id === "seguimiento" && hasRunningJob && (
                <span
                  className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-primary"
                  aria-label="Hay una tarea en curso"
                />
              )}
              {tab.id === "cierre" && cierreNeedsAttention && !isActive && (
                <span
                  className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-amber-500"
                  aria-label="Cierre pendiente"
                />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
