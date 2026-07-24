import { useMemo, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import type { ExcelAvanceRow } from "@/shared/api/types";
import { useExcelAvance } from "@/shared/api/queries";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { cn } from "@/shared/lib/utils";

type Props = {
  baseUrl: string;
  apiKey: string;
  year?: number;
  month?: string;
};

type FilterKey = "todos" | "pendiente_recepcion" | "con_error" | "sin_correo" | "sin_xml";

const FILTERS: { id: FilterKey; label: string }[] = [
  { id: "todos", label: "Todos" },
  { id: "pendiente_recepcion", label: "Sin recepción" },
  { id: "con_error", label: "Con error" },
  { id: "sin_correo", label: "Sin correo" },
  { id: "sin_xml", label: "Sin XML" },
];

function pct(part: number, total: number): number {
  if (!total) return 0;
  return Math.round((part / total) * 100);
}

function matchesFilter(row: ExcelAvanceRow, filter: FilterKey): boolean {
  const estado = row.estado_recepcion.trim().toUpperCase();
  if (filter === "todos") return true;
  if (filter === "pendiente_recepcion") return !estado || estado === "NO RECIBIDO";
  if (filter === "con_error") {
    return (
      estado === "RECIBIDO CON ERROR" || row.correo_clase === "error" || row.xml_clase === "observacion"
    );
  }
  if (filter === "sin_correo") return row.correo_clase === "pendiente";
  if (filter === "sin_xml") return row.xml_clase === "pendiente" && !row.archivo_xml;
  return true;
}

export function ExcelAvancePanel({ baseUrl, apiKey, year, month }: Props) {
  const q = useExcelAvance(baseUrl, apiKey, year, month);
  const [filter, setFilter] = useState<FilterKey>("todos");
  const [qtext, setQtext] = useState("");

  const data = q.data;
  const filtered = useMemo(() => {
    const rows = data?.rows ?? [];
    const needle = qtext.trim().toLowerCase();
    return rows.filter((r) => {
      if (!matchesFilter(r, filter)) return false;
      if (!needle) return true;
      return [r.name, r.sede, r.email, r.estado_recepcion, r.correo_enviado, r.observaciones_xml]
        .join(" ")
        .toLowerCase()
        .includes(needle);
    });
  }, [data?.rows, filter, qtext]);

  if (!year || !month) {
    return <p className="text-sm text-muted-foreground">Elige un mes para ver el avance del Excel.</p>;
  }

  if (q.isLoading && !data) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Leyendo Solicitud.xlsx…
      </p>
    );
  }

  if (!data?.solicitud_exists) {
    return (
      <div className="space-y-2 text-sm">
        <p className="text-muted-foreground">
          Aún no hay <strong>Solicitud.xlsx</strong> en este mes.
        </p>
        <p className="text-xs text-muted-foreground">{data?.month_dir}</p>
      </div>
    );
  }

  if (data.read_error) {
    return <p className="text-sm text-danger">No se pudo leer el Excel: {data.read_error}</p>;
  }

  const total = data.total_rows;
  const recOk = data.recepcion.recibido;
  const recErr = data.recepcion.recibido_con_error;
  const recibidos = recOk + recErr;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Avance de Solicitud.xlsx</h2>
          <p className="text-xs text-muted-foreground">
            {month} {year}
            {data.mtime ? ` · actualizado ${data.mtime}` : ""}
            {" · "}
            {total} fila{total === 1 ? "" : "s"}
            {data.rows_truncated ? " (tabla limitada)" : ""}
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => void q.refetch()}
          disabled={q.isFetching}
        >
          {q.isFetching ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <RefreshCw className="h-4 w-4 mr-2" />
          )}
          Actualizar
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <ProgressBlock
          title="Recepción"
          primary={`${recibidos}/${total}`}
          percent={pct(recibidos, total)}
          lines={[
            `OK ${recOk}`,
            `Con error ${recErr}`,
            `No recibido ${data.recepcion.no_recibido}`,
            `Sin marcar ${data.recepcion.pendiente}`,
          ]}
        />
        <ProgressBlock
          title="Correo solicitud"
          primary={`${data.correo_solicitud.enviado}/${total}`}
          percent={pct(data.correo_solicitud.enviado, total)}
          lines={[
            `Enviados ${data.correo_solicitud.enviado}`,
            `Pendientes ${data.correo_solicitud.pendiente}`,
            `Errores ${data.correo_solicitud.error}`,
            `Omitidos ${data.correo_solicitud.omitido}`,
            data.recordatorios.con_recordatorio
              ? `Con recordatorio ${data.recordatorios.con_recordatorio}`
              : null,
          ]}
        />
        <ProgressBlock
          title="Extracción XML"
          primary={`${data.xml_extract.ok}/${total}`}
          percent={pct(data.xml_extract.ok, total)}
          lines={[
            `OK ${data.xml_extract.ok}`,
            `Con obs. ${data.xml_extract.observacion}`,
            `Pendiente ${data.xml_extract.pendiente}`,
            `Con archivo ${data.xml_extract.con_archivo}`,
            `Carpeta XML ${data.archivos_mes.xml} · PDF ${data.archivos_mes.pdf}`,
          ]}
        />
        <ProgressBlock
          title="Pagos (hoja)"
          primary={data.pagos.sheet_exists ? `${data.pagos.enviado}/${data.pagos.total_rows}` : "—"}
          percent={data.pagos.sheet_exists ? pct(data.pagos.enviado, data.pagos.total_rows || 1) : 0}
          lines={
            data.pagos.sheet_exists
              ? [
                  `Filas ${data.pagos.total_rows}`,
                  `Enviados ${data.pagos.enviado}`,
                  `Pendientes ${data.pagos.pendiente}`,
                  `Errores ${data.pagos.error}`,
                ]
              : ["Hoja Pagos aún no existe"]
          }
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex flex-wrap gap-0.5 rounded-lg bg-muted/70 p-0.5">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setFilter(f.id)}
            className={cn(
              "rounded-md px-2.5 py-1 text-xs font-medium tracking-tight transition-colors",
              filter === f.id
                ? "bg-card text-foreground shadow-xs"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {f.label}
          </button>
        ))}
        </div>
        <Input
          type="search"
          value={qtext}
          onChange={(e) => setQtext(e.target.value)}
          placeholder="Buscar docente, sede, email…"
          className="ml-auto min-w-[180px] flex-1"
        />
      </div>

      <div className="overflow-x-auto rounded-lg border border-border/80">
        <table className="w-full min-w-[720px] text-left text-sm tracking-tight">
          <thead className="border-b border-border bg-muted/50 text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">
            <tr>
              <th className="px-2.5 py-2.5">#</th>
              <th className="px-2.5 py-2.5">Docente</th>
              <th className="px-2.5 py-2.5">Sede</th>
              <th className="px-2.5 py-2.5">Recepción</th>
              <th className="px-2.5 py-2.5">Correo</th>
              <th className="px-2.5 py-2.5">XML</th>
              <th className="px-2.5 py-2.5">Monto</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-2 py-6 text-center text-muted-foreground">
                  Sin filas para este filtro.
                </td>
              </tr>
            ) : (
              filtered.map((r) => (
                <tr key={r.row} className="border-b border-border/70 last:border-0">
                  <td className="px-2 py-1.5 text-xs text-muted-foreground">{r.row}</td>
                  <td className="px-2 py-1.5">
                    <div className="font-medium">{r.name || "—"}</div>
                    {r.email && <div className="text-xs text-muted-foreground">{r.email}</div>}
                  </td>
                  <td className="px-2 py-1.5 text-xs">{r.sede || "—"}</td>
                  <td className="px-2 py-1.5">
                    <StatusPill value={r.estado_recepcion || "Pendiente"} kind={recepcionKind(r)} />
                  </td>
                  <td className="px-2 py-1.5">
                    <StatusPill value={shortMail(r.correo_enviado) || "Pendiente"} kind={r.correo_clase} />
                  </td>
                  <td className="px-2 py-1.5">
                    <StatusPill
                      value={shortXml(r) || "Pendiente"}
                      kind={
                        r.xml_clase === "ok"
                          ? "enviado"
                          : r.xml_clase === "observacion"
                            ? "error"
                            : "pendiente"
                      }
                    />
                  </td>
                  <td className="px-2 py-1.5 text-xs tabular-nums">{r.monto || "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-muted-foreground">
        Lee el archivo en disco (no hace falta abrirlo). Se refresca solo cada 15 s.
      </p>
    </div>
  );
}

function recepcionKind(r: ExcelAvanceRow): string {
  const e = r.estado_recepcion.trim().toUpperCase();
  if (e === "RECIBIDO") return "enviado";
  if (e === "RECIBIDO CON ERROR") return "error";
  if (e === "NO RECIBIDO") return "omitido";
  return "pendiente";
}

function shortMail(value: string): string {
  if (!value) return "";
  if (value.length <= 42) return value;
  return `${value.slice(0, 40)}…`;
}

function shortXml(r: ExcelAvanceRow): string {
  if (r.xml_clase === "ok") return "OK";
  if (r.observaciones_xml) return shortMail(r.observaciones_xml);
  if (r.archivo_xml) return "Archivo ligado";
  return "";
}

function ProgressBlock({
  title,
  primary,
  percent,
  lines,
}: {
  title: string;
  primary: string;
  percent: number;
  lines: Array<string | null>;
}) {
  return (
    <div className="rounded-lg border border-border/80 px-3 py-3">
      <p className="text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">{title}</p>
      <p className="mt-1 text-xl font-semibold tracking-tight tabular-nums">{primary}</p>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${Math.min(100, percent)}%` }}
        />
      </div>
      <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground">
        {lines.filter(Boolean).map((line) => (
          <li key={line as string}>{line}</li>
        ))}
      </ul>
    </div>
  );
}

function StatusPill({ value, kind }: { value: string; kind: string }) {
  return (
    <span
      className={cn(
        "inline-block max-w-[180px] truncate rounded-md px-1.5 py-0.5 text-2xs font-semibold",
        kind === "enviado" && "bg-success/12 text-success",
        kind === "error" && "bg-danger/12 text-danger",
        kind === "omitido" && "bg-warning/12 text-warning",
        kind === "pendiente" && "bg-muted text-muted-foreground",
        kind === "otro" && "bg-muted text-muted-foreground",
        kind === "ok" && "bg-success/12 text-success",
        kind === "observacion" && "bg-warning/12 text-warning"
      )}
      title={value}
    >
      {value}
    </span>
  );
}
