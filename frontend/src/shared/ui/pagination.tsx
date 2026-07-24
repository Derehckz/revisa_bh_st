import { Button } from "@/shared/ui/button";

export function Pagination({
  page,
  totalPages,
  onPrev,
  onNext,
}: {
  page: number;
  totalPages: number;
  onPrev: () => void;
  onNext: () => void;
}) {
  return (
    <div className="flex items-center justify-end gap-3 pt-1">
      <span className="text-xs tabular-nums text-muted-foreground">
        {page} / {totalPages}
      </span>
      <div className="flex gap-1.5">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={onPrev}>
          Anterior
        </Button>
        <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={onNext}>
          Siguiente
        </Button>
      </div>
    </div>
  );
}
