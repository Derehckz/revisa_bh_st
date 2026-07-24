import type { OperationJob } from "@/shared/api/types";
import { Badge } from "@/shared/ui/badge";
import { EmptyState } from "@/shared/ui/empty-state";
import { cn } from "@/shared/lib/utils";

type Props = {
  jobs: OperationJob[];
  selectedJobId: string | null;
  onSelect: (job: OperationJob) => void;
};

const STATUS_TONE: Record<string, "default" | "success" | "danger" | "warning"> = {
  running: "warning",
  success: "success",
  failed: "danger",
  unknown: "default",
};

function formatWhen(iso?: string | null) {
  if (!iso) return "Sin fecha";
  try {
    return new Date(iso).toLocaleString("es-CL", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso;
  }
}

export function PeriodJobsList({ jobs, selectedJobId, onSelect }: Props) {
  if (!jobs.length) {
    return (
      <EmptyState
        title="Sin ejecuciones"
        description="Cuando corras un paso, aparecerá aquí."
        className="py-8"
      />
    );
  }

  return (
    <ul className="max-h-56 space-y-1 overflow-auto">
      {jobs.map((job) => {
        const selected = job.id === selectedJobId;
        return (
          <li key={job.id}>
            <button
              type="button"
              onClick={() => onSelect(job)}
              className={cn(
                "w-full rounded-md border px-3 py-2.5 text-left transition-colors",
                selected
                  ? "border-primary/30 bg-primary/5"
                  : "border-border/80 hover:bg-muted/50"
              )}
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={STATUS_TONE[job.status] ?? "default"}>{job.status}</Badge>
                <span className="text-2xs font-medium uppercase tracking-wide text-muted-foreground">
                  Paso {job.stage_num ?? 0}
                </span>
                <span className="ml-auto text-2xs tabular-nums text-muted-foreground">
                  {formatWhen(job.created_at)}
                </span>
              </div>
              {job.label && (
                <p className="mt-1 truncate text-[0.8125rem] text-muted-foreground" title={job.label}>
                  {job.label}
                </p>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
