import { useMemo } from "react";
import type { ExecutionHistoryEntry } from "@/shared/api/types";
import { Badge } from "@/shared/ui/badge";
import { cn } from "@/shared/lib/utils";

type Props = {
  entries: ExecutionHistoryEntry[];
  total: number;
  returned: number;
  byMonth: Array<{ period: string; count: number }>;
  isLoading: boolean;
  selectedId: string | null;
  onSelect: (entry: ExecutionHistoryEntry) => void;
};

const STATUS_TONE: Record<string, "default" | "success" | "danger"> = {
  running: "default",
  success: "success",
  failed: "danger",
  unknown: "default",
};

function formatWhen(iso: string | null) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("es-CL", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso.slice(0, 16);
  }
}

export function ExecutionHistoryPanel({
  entries,
  total,
  returned,
  byMonth,
  isLoading,
  selectedId,
  onSelect,
}: Props) {
  const grouped = useMemo(() => {
    const map = new Map<string, ExecutionHistoryEntry[]>();
    for (const e of entries) {
      const key = `${e.month} ${e.year}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(e);
    }
    return [...map.entries()];
  }, [entries]);

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Cargando historial desde logs en disco…</p>;
  }

  if (!entries.length) {
    return (
      <p className="text-sm text-muted-foreground">
        No se encontraron ejecuciones en el rango seleccionado (revisa carpetas logs_* bajo cada mes).
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        {returned} de {total} registros
        {byMonth.length > 0 && (
          <>
            {" "}
            —{" "}
            {byMonth.map((b) => `${b.period}: ${b.count}`).join(" · ")}
          </>
        )}
      </p>
      <div className="max-h-[min(28rem,50vh)] overflow-auto space-y-4 pr-1">
        {grouped.map(([period, items]) => (
          <div key={period}>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1 sticky top-0 bg-card py-1">
              {period}
            </h4>
            <ul className="space-y-1">
              {items.map((entry) => {
                const selected = entry.id === selectedId;
                const tone = STATUS_TONE[entry.status] ?? "default";
                return (
                  <li key={entry.id}>
                    <button
                      type="button"
                      onClick={() => onSelect(entry)}
                      className={cn(
                        "w-full rounded-md border px-3 py-2 text-left text-sm hover:bg-muted",
                        selected ? "border-primary bg-primary/5" : "border-border"
                      )}
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={tone}>{entry.status}</Badge>
                        <span className="text-xs font-medium">Paso {entry.stage_num}</span>
                        {entry.source === "filesystem" && (
                          <span className="text-[10px] uppercase text-muted-foreground">log</span>
                        )}
                        {entry.source === "api" && (
                          <span className="text-[10px] uppercase text-muted-foreground">web</span>
                        )}
                      </div>
                      <p className="mt-0.5 text-xs text-muted-foreground truncate" title={entry.label}>
                        {entry.label}
                      </p>
                      <p className="text-[10px] text-muted-foreground font-mono">{formatWhen(entry.created_at)}</p>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
