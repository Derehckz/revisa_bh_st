import { cn } from "@/shared/lib/utils";

export type OperacionTab = "ejecutar" | "seguimiento" | "avanzado";

type Props = {
  active: OperacionTab;
  onChange: (tab: OperacionTab) => void;
  hasRunningJob: boolean;
};

const TABS: { id: OperacionTab; label: string; hint: string }[] = [
  { id: "ejecutar", label: "1. Ejecutar paso", hint: "Formulario del paso seleccionado" },
  { id: "seguimiento", label: "2. Seguimiento", hint: "Logs, archivos y historial" },
  { id: "avanzado", label: "3. Avanzado", hint: "Cierre batch y outbox" },
];

export function OperacionTabs({ active, onChange, hasRunningJob }: Props) {
  return (
    <div className="border-b border-border">
      <div className="flex flex-wrap gap-1" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active === tab.id}
            onClick={() => onChange(tab.id)}
            className={cn(
              "rounded-t-md px-4 py-2 text-sm font-medium transition-colors",
              active === tab.id
                ? "border border-b-0 border-border bg-card text-foreground"
                : "text-muted-foreground hover:bg-muted/60"
            )}
          >
            {tab.label}
            {tab.id === "seguimiento" && hasRunningJob && (
              <span className="ml-1.5 inline-block h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
            )}
          </button>
        ))}
      </div>
      <p className="bg-card px-4 py-2 text-xs text-muted-foreground border-x border-border">
        {TABS.find((t) => t.id === active)?.hint}
      </p>
    </div>
  );
}
