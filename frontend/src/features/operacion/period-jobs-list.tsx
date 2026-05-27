import type { OperationJob } from "@/shared/api/types";
import { Badge } from "@/shared/ui/badge";
import { cn } from "@/shared/lib/utils";

type Props = {
  jobs: OperationJob[];
  selectedJobId: string | null;
  onSelect: (job: OperationJob) => void;
};

const STATUS_TONE: Record<string, "default" | "success" | "danger"> = {
  running: "default",
  success: "success",
  failed: "danger",
  unknown: "default",
};

export function PeriodJobsList({ jobs, selectedJobId, onSelect }: Props) {
  if (!jobs.length) {
    return <p className="text-sm text-muted-foreground">Aún no hay ejecuciones para este período.</p>;
  }

  return (
    <ul className="space-y-1 max-h-48 overflow-auto">
      {jobs.map((job) => {
        const selected = job.id === selectedJobId;
        return (
          <li key={job.id}>
            <button
              type="button"
              onClick={() => onSelect(job)}
              className={cn(
                "w-full rounded-md border px-3 py-2 text-left text-sm hover:bg-muted",
                selected ? "border-primary bg-primary/5" : "border-border"
              )}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs">{job.id}</span>
                <Badge tone={STATUS_TONE[job.status] ?? "default"}>{job.status}</Badge>
                <span className="text-xs text-muted-foreground">Paso {job.stage_num ?? 0}</span>
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
