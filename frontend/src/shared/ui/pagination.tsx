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
    <div className="flex items-center justify-end gap-2">
      <Button variant="outline" disabled={page <= 1} onClick={onPrev}>
        Anterior
      </Button>
      <span className="text-sm text-muted-foreground">
        Página {page} de {totalPages}
      </span>
      <Button variant="outline" disabled={page >= totalPages} onClick={onNext}>
        Siguiente
      </Button>
    </div>
  );
}
