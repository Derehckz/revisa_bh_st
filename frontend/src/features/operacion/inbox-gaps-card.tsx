import { Loader2, MailWarning, Play } from "lucide-react";
import type { InboxGapsResponse } from "@/shared/api/types";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";

type Props = {
  scanning: boolean;
  result: InboxGapsResponse | null;
  error: string | null;
  onScan: () => void;
  onGoToStage2: () => void;
};

export function InboxGapsCard({ scanning, result, error, onScan, onGoToStage2 }: Props) {
  const gaps = result?.gaps ?? [];
  const hasGaps = (result?.gap_count ?? 0) > 0;

  return (
    <Card className={hasGaps ? "border-amber-500/50" : undefined}>
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0 py-3">
        <div className="space-y-1">
          <CardTitle className="flex items-center gap-2 text-sm font-medium tracking-tight">
            <MailWarning className="h-4 w-4 shrink-0" />
            Detector de huecos (correo → carpeta)
          </CardTitle>
          <p className="text-[0.8125rem] font-normal leading-snug text-muted-foreground">
            Busca en Outlook boletas <code className="text-xs">bhe_</code> de filas NO RECIBIDO que
            aún no están en la carpeta del mes (caso Maass).
          </p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={onScan} disabled={scanning}>
          {scanning ? (
            <>
              <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
              Escaneando…
            </>
          ) : (
            "Buscar en correo"
          )}
        </Button>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        {error && <p className="text-sm text-danger">{error}</p>}
        {result && !result.ok && result.error && (
          <p className="text-sm text-danger">{result.error}</p>
        )}
        {result?.ok && (
          <p className="text-sm text-muted-foreground">
            {result.message}{" "}
            <span className="tabular-nums">
              (NO RECIBIDO: {result.no_recibidos} · correos: {result.emails_scanned} · rango:{" "}
              {result.fecha_inicio}–{result.fecha_fin})
            </span>
          </p>
        )}
        {hasGaps && (
          <>
            <ul className="max-h-48 space-y-2 overflow-y-auto text-sm">
              {gaps.map((g) => (
                <li
                  key={`${g.rut}-${g.folio}`}
                  className="rounded-md border border-border/70 bg-muted/20 px-2.5 py-2"
                >
                  <div className="font-medium tracking-tight">
                    {g.name || g.rut} · folio {g.folio}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {g.attachments.join(", ")}
                    {g.received_time ? ` · ${g.received_time}` : ""}
                  </div>
                  {g.subject ? (
                    <div className="truncate text-xs text-muted-foreground">{g.subject}</div>
                  ) : null}
                </li>
              ))}
            </ul>
            <Button type="button" size="sm" onClick={onGoToStage2}>
              <Play className="mr-2 h-3.5 w-3.5" />
              Ir al paso 2 y bajar
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
