import type { PeriodKpis } from "@/shared/api/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";

type Props = {
  kpis: PeriodKpis | undefined;
  outboxStats?: Record<string, number>;
};

export function PeriodSummaryCard({ kpis, outboxStats }: Props) {
  if (!kpis) return null;

  const pending = outboxStats?.pending ?? 0;
  const failed = outboxStats?.failed ?? 0;
  const sent = outboxStats?.sent ?? 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Resumen — {kpis.month} {kpis.year}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Solicitudes" value={(kpis.total_rows ?? 0) > 0 ? String(kpis.total_rows) : "—"} />
          <Stat label="Recibidos" value={(kpis.total_rows ?? 0) > 0 ? String(kpis.recibidos) : "—"} />
          <Stat label="No recibidos" value={(kpis.total_rows ?? 0) > 0 ? String(kpis.no_recibidos) : "—"} />
          <Stat label="XML en carpeta" value={String(kpis.xml_files_in_month)} />
          <Stat label="PDF en carpeta" value={String(kpis.pdf_files_in_month)} />
          <Stat label="Outbox pending" value={String(pending)} />
          <Stat label="Outbox sent" value={String(sent)} />
          <Stat label="Outbox failed" value={String(failed)} />
        </div>
        {kpis.read_error && (
          <p className="mt-2 text-xs text-amber-800">No se pudo cargar el resumen: {kpis.read_error}</p>
        )}
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  );
}
