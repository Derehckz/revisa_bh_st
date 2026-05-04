import { AlertTriangle } from "lucide-react";
import { Button } from "@/shared/ui/button";

export function ErrorState({
  title,
  description,
  onRetry,
}: {
  title: string;
  description: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-8 text-center">
      <div className="rounded-full bg-red-100 p-2">
        <AlertTriangle size={18} className="text-red-600" />
      </div>
      <p className="font-semibold text-red-900">{title}</p>
      <p className="max-w-xl text-sm text-red-800">{description}</p>
      {onRetry && (
        <Button variant="outline" onClick={onRetry}>
          Reintentar
        </Button>
      )}
    </div>
  );
}
