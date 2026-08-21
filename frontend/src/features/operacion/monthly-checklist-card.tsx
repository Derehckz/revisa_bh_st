import { useState } from "react";
import { CheckCircle2, AlertTriangle, XCircle, Loader2, Lock, Unlock, ChevronDown } from "lucide-react";
import type { MonthlyChecklistResponse } from "@/shared/api/types";
import { Button } from "@/shared/ui/button";
import { cn } from "@/shared/lib/utils";

type ContabilidadStatus = "ok" | "con_observaciones" | "pendiente";

type Props = {
  checklist?: MonthlyChecklistResponse;
  loading?: boolean;
  closePending?: boolean;
  reopenPending?: boolean;
  contabilidadPending?: boolean;
  /** Compacto por defecto; expandido muestra ítems y Contabilidad. */
  defaultExpanded?: boolean;
  onClose: () => void;
  onReopen: () => void;
  onMarkContabilidad: (status: ContabilidadStatus, notes?: string) => void;
};

function StatusIcon({ status }: { status: string }) {
  if (status === "ok") return <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-green-600" />;
  if (status === "warn") return <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-600" />;
  return <XCircle className="h-3.5 w-3.5 shrink-0 text-danger" />;
}

export function MonthlyChecklistCard({
  checklist,
  loading,
  closePending,
  reopenPending,
  contabilidadPending,
  defaultExpanded = false,
  onClose,
  onReopen,
  onMarkContabilidad,
}: Props) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [notes, setNotes] = useState("");

  if (loading && !checklist) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Checklist…
      </p>
    );
  }
  if (!checklist) return null;

  const informeOk = checklist.items.some((i) => i.id === "informe" && i.status === "ok");
  const contab = (checklist.contabilidad_status || "").toLowerCase();
  const showContabActions = !checklist.closed && informeOk;
  const blocks = checklist.items.filter((i) => i.status === "block");
  const warns = checklist.items.filter((i) => i.status === "warn");
  const summary = checklist.closed
    ? "Cerrado"
    : checklist.can_close
      ? "Listo para cerrar"
      : blocks.length
        ? `${blocks.length} bloqueo(s)`
        : warns.length
          ? `${warns.length} aviso(s)`
          : "En curso";

  return (
    <div className="rounded-lg border border-border/80 bg-card shadow-xs">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2.5">
        <button
          type="button"
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
        >
          <ChevronDown
            className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform", expanded && "rotate-180")}
          />
          <div className="min-w-0">
            <p className="text-sm font-medium tracking-tight">
              Cierre · {checklist.month} {checklist.year}
            </p>
            <p className="truncate text-xs text-muted-foreground">
              {summary}
              {contab === "ok" ? " · Contabilidad OK" : contab === "con_observaciones" ? " · Contabilidad con obs." : informeOk ? " · Contabilidad pendiente" : ""}
            </p>
          </div>
        </button>
        <div className="flex flex-wrap gap-1.5">
          {checklist.closed ? (
            <Button type="button" variant="outline" size="sm" disabled={reopenPending} onClick={onReopen}>
              {reopenPending ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <Unlock className="mr-1 h-3.5 w-3.5" />}
              Reabrir
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              disabled={!checklist.can_close || closePending}
              onClick={onClose}
              title={!checklist.can_close ? "Completa bloqueos antes de cerrar" : "Cerrar y congelar"}
            >
              {closePending ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <Lock className="mr-1 h-3.5 w-3.5" />}
              Cerrar
            </Button>
          )}
        </div>
      </div>

      {expanded ? (
        <div className="space-y-3 border-t border-border/60 px-3 py-3">
          {showContabActions ? (
            <div className="space-y-2 rounded-md border border-border/60 bg-muted/20 p-2.5">
              <p className="text-xs font-medium">Contabilidad (post-informe)</p>
              <input
                className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
                placeholder="Notas opcionales…"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                disabled={contabilidadPending}
              />
              <div className="flex flex-wrap gap-1.5">
                <Button
                  type="button"
                  size="sm"
                  disabled={contabilidadPending || contab === "ok"}
                  onClick={() => onMarkContabilidad("ok", notes.trim() || undefined)}
                >
                  OK Contabilidad
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={contabilidadPending}
                  onClick={() => {
                    const n =
                      notes.trim() ||
                      window.prompt("Observación de Contabilidad (opcional):") ||
                      undefined;
                    onMarkContabilidad("con_observaciones", n);
                  }}
                >
                  Con observaciones
                </Button>
                {contab && contab !== "pendiente" ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    disabled={contabilidadPending}
                    onClick={() => onMarkContabilidad("pendiente")}
                  >
                    Pendiente
                  </Button>
                ) : null}
              </div>
            </div>
          ) : null}

          <ul className="space-y-1.5">
            {checklist.items.map((item) => (
              <li key={item.id} className="flex items-start gap-2 text-[0.8125rem]">
                <StatusIcon status={item.status} />
                <div className="min-w-0 flex-1">
                  <span className={cn("font-medium", item.status === "block" && "text-danger")}>{item.label}</span>
                  {item.message ? (
                    <span className="text-muted-foreground"> — {item.message}</span>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
