import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Expand, Loader2, RefreshCw, X } from "lucide-react";
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
  /** Pantalla completa (sin sidebar de Operación). */
  layout?: "embedded" | "full";
};

type FilterKey =
  | "todos"
  | "pendiente_recepcion"
  | "con_error"
  | "sin_correo"
  | "sin_xml"
  | "con_recordatorio";

const FILTERS: { id: FilterKey; label: string }[] = [
  { id: "todos", label: "Todos" },
  { id: "pendiente_recepcion", label: "Sin recepción" },
  { id: "con_error", label: "Con error" },
  { id: "sin_correo", label: "Sin correo" },
  { id: "sin_xml", label: "Sin XML" },
  { id: "con_recordatorio", label: "Con recordatorio" },
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
      estado === "RECIBIDO CON ERROR" ||
      row.correo_clase === "error" ||
      row.xml_clase === "observacion" ||
      Boolean(row.observacion_descartes?.trim())
    );
  }
  if (filter === "sin_correo") return row.correo_clase === "pendiente";
  if (filter === "sin_xml") return row.xml_clase === "pendiente" && !row.archivo_xml;
  if (filter === "con_recordatorio") {
    const n = Number(String(row.recordatorios || "").replace(/[^\d]/g, "") || "0");
    return n > 0 || /recordatorio/i.test(row.correo_enviado || "");
  }
  return true;
}

export function ExcelAvancePanel({ baseUrl, apiKey, year, month, layout = "embedded" }: Props) {
  const q = useExcelAvance(baseUrl, apiKey, year, month);
  const [filter, setFilter] = useState<FilterKey>("todos");
  const [qtext, setQtext] = useState("");
  const [selectedRow, setSelectedRow] = useState<number | null>(null);

  const data = q.data;
  const filtered = useMemo(() => {
    const rows = data?.rows ?? [];
    const needle = qtext.trim().toLowerCase();
    return rows.filter((r) => {
      if (!matchesFilter(r, filter)) return false;
      if (!needle) return true;
      return [
        r.name,
        r.sede,
        r.email,
        r.emplid,
        r.rut_razon,
        r.nombre_razon,
        r.estado_recepcion,
        r.correo_enviado,
        r.observaciones_xml,
        r.observaciones,
        r.observacion_descartes,
        r.numero_boleta_xml,
        r.glosa,
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle);
    });
  }, [data?.rows, filter, qtext]);

  const selected = useMemo(
    () => filtered.find((r) => r.row === selectedRow) ?? data?.rows.find((r) => r.row === selectedRow) ?? null,
    [filtered, data?.rows, selectedRow]
  );

  useEffect(() => {
    if (selectedRow != null && !filtered.some((r) => r.row === selectedRow)) {
      // Mantener selección si la fila existe en data pero no en filtro actual
      if (!(data?.rows ?? []).some((r) => r.row === selectedRow)) {
        setSelectedRow(null);
      }
    }
  }, [filtered, selectedRow, data?.rows]);

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
  const isFull = layout === "full";

  return (
    <div
      className={cn(
        isFull
          ? "flex min-h-0 flex-1 flex-col gap-3 p-3 md:p-4"
          : "space-y-4"
      )}
    >
      <div className="flex shrink-0 flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          {!isFull && (
            <h2 className="text-base font-semibold tracking-tight">Avance de Solicitud.xlsx</h2>
          )}
          <p className={cn("text-xs text-muted-foreground", isFull && "md:text-[0.8125rem]")}>
            {month} {year}
            {data.mtime ? ` · ${formatMtime(data.mtime)}` : ""}
            {" · "}
            {filtered.length}/{total} fila{total === 1 ? "" : "s"}
            {data.rows_truncated ? " (tabla limitada)" : ""}
            {" · "}
            XML {data.archivos_mes.xml} · PDF {data.archivos_mes.pdf}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {layout === "embedded" && (
            <Link
              to="/avance"
              className="inline-flex h-8 items-center justify-center gap-1.5 rounded-md border border-border bg-card px-3 text-xs font-medium tracking-tight text-foreground hover:bg-muted/80"
            >
              <Expand className="h-4 w-4" />
              Vista completa
            </Link>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void q.refetch()}
            disabled={q.isFetching}
          >
            {q.isFetching ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            Actualizar
          </Button>
        </div>
      </div>

      <div
        className={cn(
          "grid shrink-0 gap-2",
          isFull ? "grid-cols-2 lg:grid-cols-4" : "sm:grid-cols-2 xl:grid-cols-4 gap-3"
        )}
      >
        <ProgressBlock
          compact={isFull}
          title="Recepción"
          primary={`${recibidos}/${total}`}
          percent={pct(recibidos, total)}
          active={filter === "pendiente_recepcion" || filter === "con_error"}
          onClick={() =>
            setFilter((f) => (f === "pendiente_recepcion" ? "todos" : "pendiente_recepcion"))
          }
          lines={
            isFull
              ? [`OK ${recOk} · Err ${recErr} · No rec. ${data.recepcion.no_recibido}`]
              : [
                  `OK ${recOk}`,
                  `Con error ${recErr}`,
                  `No recibido ${data.recepcion.no_recibido}`,
                  `Sin marcar ${data.recepcion.pendiente}`,
                ]
          }
        />
        <ProgressBlock
          compact={isFull}
          title="Correo solicitud"
          primary={`${data.correo_solicitud.enviado}/${total}`}
          percent={pct(data.correo_solicitud.enviado, total)}
          active={filter === "sin_correo" || filter === "con_recordatorio"}
          onClick={() => setFilter((f) => (f === "sin_correo" ? "todos" : "sin_correo"))}
          lines={
            isFull
              ? [
                  `Pend. ${data.correo_solicitud.pendiente} · Rec. ${data.recordatorios.con_recordatorio || 0}`,
                ]
              : [
                  `Enviados ${data.correo_solicitud.enviado}`,
                  `Pendientes ${data.correo_solicitud.pendiente}`,
                  `Errores ${data.correo_solicitud.error}`,
                  `Omitidos ${data.correo_solicitud.omitido}`,
                  data.recordatorios.con_recordatorio
                    ? `Con recordatorio ${data.recordatorios.con_recordatorio}`
                    : null,
                ]
          }
        />
        <ProgressBlock
          compact={isFull}
          title="Extracción XML"
          primary={`${data.xml_extract.ok}/${total}`}
          percent={pct(data.xml_extract.ok, total)}
          active={filter === "sin_xml"}
          onClick={() => setFilter((f) => (f === "sin_xml" ? "todos" : "sin_xml"))}
          lines={
            isFull
              ? [`Obs. ${data.xml_extract.observacion} · Pend. ${data.xml_extract.pendiente}`]
              : [
                  `OK ${data.xml_extract.ok}`,
                  `Con obs. ${data.xml_extract.observacion}`,
                  `Pendiente ${data.xml_extract.pendiente}`,
                  `Con archivo ${data.xml_extract.con_archivo}`,
                  `Carpeta XML ${data.archivos_mes.xml} · PDF ${data.archivos_mes.pdf}`,
                ]
          }
        />
        <ProgressBlock
          compact={isFull}
          title="Pagos (hoja)"
          primary={data.pagos.sheet_exists ? `${data.pagos.enviado}/${data.pagos.total_rows}` : "—"}
          percent={data.pagos.sheet_exists ? pct(data.pagos.enviado, data.pagos.total_rows || 1) : 0}
          lines={
            data.pagos.sheet_exists
              ? isFull
                ? [`Pend. ${data.pagos.pendiente} · Err ${data.pagos.error}`]
                : [
                    `Filas ${data.pagos.total_rows}`,
                    `Enviados ${data.pagos.enviado}`,
                    `Pendientes ${data.pagos.pendiente}`,
                    `Errores ${data.pagos.error}`,
                  ]
              : ["Hoja Pagos aún no existe"]
          }
        />
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-2">
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
              {f.id !== "todos" && data ? (
                <span className="ml-1 tabular-nums text-muted-foreground">
                  {countForFilter(data.rows, f.id)}
                </span>
              ) : null}
            </button>
          ))}
        </div>
        <Input
          type="search"
          value={qtext}
          onChange={(e) => setQtext(e.target.value)}
          placeholder="Buscar nombre, RUT, email, boleta, glosa…"
          className="ml-auto min-w-[200px] max-w-md flex-1"
        />
      </div>

      <div
        className={cn(
          "grid min-h-0 gap-3",
          isFull ? "flex-1" : "",
          selected
            ? isFull
              ? "lg:grid-cols-[minmax(0,1fr)_minmax(340px,28%)]"
              : "lg:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]"
            : "grid-cols-1"
        )}
      >
        <div
          className={cn(
            "min-h-0 overflow-auto rounded-lg border border-border/80",
            isFull ? "h-full min-h-[420px]" : "max-h-[min(52vh,560px)]"
          )}
        >
          <table className="w-full min-w-[960px] text-left text-sm tracking-tight">
            <thead className="sticky top-0 z-[1] border-b border-border bg-muted/95 text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground backdrop-blur">
              <tr>
                <th className="px-2.5 py-2">#</th>
                <th className="px-2.5 py-2">Docente</th>
                <th className="px-2.5 py-2">EMPLID</th>
                <th className="px-2.5 py-2">Razón</th>
                <th className="px-2.5 py-2">Recepción</th>
                <th className="px-2.5 py-2">Correo</th>
                <th className="px-2.5 py-2">Rec.</th>
                <th className="px-2.5 py-2">XML / boleta</th>
                <th className="px-2.5 py-2">Monto</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-2 py-6 text-center text-muted-foreground">
                    Sin filas para este filtro.
                  </td>
                </tr>
              ) : (
                filtered.map((r) => {
                  const active = r.row === selectedRow;
                  return (
                    <tr
                      key={r.row}
                      tabIndex={0}
                      onClick={() => setSelectedRow(r.row)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelectedRow(r.row);
                        }
                      }}
                      className={cn(
                        "cursor-pointer border-b border-border/70 last:border-0 outline-none transition-colors",
                        active ? "bg-primary/8" : "hover:bg-muted/40"
                      )}
                    >
                      <td className="px-2 py-1.5 text-xs text-muted-foreground">{r.row}</td>
                      <td className="px-2 py-1.5">
                        <div className="font-medium">{r.name || "—"}</div>
                        <div className="text-xs text-muted-foreground">
                          {[r.sede, r.email].filter(Boolean).join(" · ") || "—"}
                        </div>
                      </td>
                      <td className="px-2 py-1.5 font-mono text-xs">{r.emplid || "—"}</td>
                      <td className="px-2 py-1.5 text-xs">
                        <div className="max-w-[160px] truncate" title={r.nombre_razon}>
                          {r.nombre_razon || "—"}
                        </div>
                        <div className="font-mono text-2xs text-muted-foreground">{r.rut_razon || ""}</div>
                      </td>
                      <td className="px-2 py-1.5">
                        <StatusPill value={r.estado_recepcion || "Pendiente"} kind={recepcionKind(r)} />
                      </td>
                      <td className="px-2 py-1.5">
                        <StatusPill value={shortMail(r.correo_enviado) || "Pendiente"} kind={r.correo_clase} />
                      </td>
                      <td className="px-2 py-1.5 text-xs tabular-nums">{r.recordatorios || "0"}</td>
                      <td className="px-2 py-1.5">
                        <StatusPill
                          value={xmlSummary(r)}
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
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {selected && (
          <RowDetailPanel
            row={selected}
            monthDir={data.month_dir}
            onClose={() => setSelectedRow(null)}
            fillHeight={isFull}
          />
        )}
      </div>

      {!isFull && (
        <p className="text-xs text-muted-foreground">
          Clic en una fila para ver el detalle completo. Lee el Excel en disco (se refresca cada 15 s).
        </p>
      )}
    </div>
  );
}

function countForFilter(rows: ExcelAvanceRow[], filter: FilterKey): number {
  return rows.filter((r) => matchesFilter(r, filter)).length;
}

function RowDetailPanel({
  row,
  monthDir,
  onClose,
  fillHeight = false,
}: {
  row: ExcelAvanceRow;
  monthDir: string;
  onClose: () => void;
  fillHeight?: boolean;
}) {
  return (
    <aside
      className={cn(
        "flex flex-col overflow-hidden rounded-lg border border-border/80 bg-muted/20 shadow-xs",
        fillHeight ? "h-full min-h-[420px]" : "max-h-[min(70vh,780px)]"
      )}
    >
      <div className="flex items-start justify-between gap-2 border-b border-border/80 px-3 py-2.5">
        <div className="min-w-0">
          <p className="text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">
            Fila {row.row}
          </p>
          <h3 className="truncate text-[0.9375rem] font-semibold tracking-tight">{row.name || "Sin nombre"}</h3>
          <p className="truncate text-xs text-muted-foreground">{row.email || "Sin email"}</p>
        </div>
        <Button type="button" variant="ghost" size="sm" className="h-8 w-8 shrink-0 p-0" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-3">
        <DetailSection title="Identificación">
          <DetailKV label="EMPLID" value={row.emplid} mono />
          <DetailKV label="RUT sin DV" value={row.rut_sin_dv} mono />
          <DetailKV label="Sede" value={row.sede} />
          <DetailKV label="Location" value={row.location} />
          <DetailKV label="Email DP" value={row.email_dp} />
        </DetailSection>
        <DetailSection title="Razón social">
          <DetailKV label="RUT razón" value={row.rut_razon} mono />
          <DetailKV label="Nombre" value={row.nombre_razon} />
          <DetailKV label="Dirección" value={row.direccion_razon} />
          <DetailKV label="Glosa" value={row.glosa} />
          <DetailKV label="Monto esperado" value={row.monto} />
        </DetailSection>
        <DetailSection title="Correo y recepción">
          <DetailKV label="Estado recepción" value={row.estado_recepcion || "Pendiente"} />
          <DetailKV label="Correo enviado" value={row.correo_enviado || "—"} />
          <DetailKV label="Recordatorios" value={row.recordatorios || "0"} />
          <DetailKV label="Correo recepción" value={row.correo_recepcion_enviado || "—"} />
          <DetailKV label="Observaciones" value={row.observaciones || "—"} />
          <DetailKV label="Obs. descartes" value={row.observacion_descartes || "—"} />
        </DetailSection>
        <DetailSection title="XML / boleta">
          <DetailKV label="Estado XML" value={xmlSummary(row)} />
          <DetailKV label="Observaciones XML" value={row.observaciones_xml || "—"} />
          <DetailKV label="Archivo XML" value={row.archivo_xml || "—"} mono />
          <DetailKV label="XML usado" value={row.archivo_xml_usado || "—"} mono />
          <DetailKV label="Nº boleta" value={row.numero_boleta_xml || "—"} />
          <DetailKV label="Fecha boleta" value={row.fecha_boleta_xml || "—"} />
          <DetailKV label="Emisor XML" value={row.rut_emisor_xml || "—"} mono />
          <DetailKV label="Receptor XML" value={row.rut_receptor_xml || "—"} mono />
          <DetailKV label="Nombre receptor" value={row.nombre_receptor_xml || "—"} />
          <DetailKV label="Total XML" value={row.total_honorarios_xml || "—"} />
          <DetailKV label="Líquido XML" value={row.liquido_honorarios_xml || "—"} />
          <DetailKV label="Impuesto XML" value={row.impuesto_honorarios_xml || "—"} />
          <DetailKV label="Descripción XML" value={row.descripcion_xml || "—"} />
        </DetailSection>
        <p className="break-all text-2xs text-muted-foreground">Carpeta: {monthDir}</p>
      </div>
    </aside>
  );
}

function DetailSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-1.5">
      <h4 className="text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">{title}</h4>
      <dl className="space-y-1.5">{children}</dl>
    </section>
  );
}

function DetailKV({ label, value, mono }: { label: string; value?: string | null; mono?: boolean }) {
  const v = (value ?? "").trim() || "—";
  return (
    <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-2 text-[0.8125rem]">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={cn("break-words text-foreground", mono && "font-mono text-xs")}>{v}</dd>
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

function xmlSummary(r: ExcelAvanceRow): string {
  if (r.numero_boleta_xml) return `Boleta ${r.numero_boleta_xml}`;
  if (r.xml_clase === "ok") return "OK";
  if (r.observaciones_xml) return shortMail(r.observaciones_xml);
  if (r.archivo_xml) return "Archivo ligado";
  return "Pendiente";
}

function formatMtime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("es-CL", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso;
  }
}

function ProgressBlock({
  title,
  primary,
  percent,
  lines,
  compact = false,
  onClick,
  active = false,
}: {
  title: string;
  primary: string;
  percent: number;
  lines: Array<string | null>;
  compact?: boolean;
  onClick?: () => void;
  active?: boolean;
}) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      {...(onClick ? { type: "button" as const } : {})}
      onClick={onClick}
      className={cn(
        "rounded-lg border border-border/80 text-left",
        compact ? "px-2.5 py-2" : "px-3 py-3",
        onClick && "cursor-pointer transition-colors hover:bg-muted/40",
        active && "border-primary/40 bg-primary/5"
      )}
    >
      <p className="text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">{title}</p>
      <p
        className={cn(
          "mt-0.5 font-semibold tracking-tight tabular-nums",
          compact ? "text-lg" : "mt-1 text-xl"
        )}
      >
        {primary}
      </p>
      <div className={cn("overflow-hidden rounded-full bg-muted", compact ? "mt-1.5 h-1" : "mt-2 h-1.5")}>
        <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, percent)}%` }} />
      </div>
      <ul className={cn("text-xs text-muted-foreground", compact ? "mt-1" : "mt-2 space-y-0.5")}>
        {lines.filter(Boolean).map((line) => (
          <li key={line as string}>{line}</li>
        ))}
      </ul>
    </Tag>
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
