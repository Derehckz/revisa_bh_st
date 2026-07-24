import { AlertCircle } from "lucide-react";
import { Button } from "@/shared/ui/button";

export function ErrorState({
  title,
  description,
  onRetry,
}: {
  title: string;
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-danger/25 bg-danger/5 px-4 py-3">
      <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-danger" strokeWidth={1.75} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold tracking-tight text-foreground">{title}</p>
        {description ? <p className="mt-0.5 text-sm text-muted-foreground">{description}</p> : null}
        {onRetry ? (
          <Button variant="outline" size="sm" className="mt-2" onClick={onRetry}>
            Reintentar
          </Button>
        ) : null}
      </div>
    </div>
  );
}
