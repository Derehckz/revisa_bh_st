import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Expand, Loader2, RefreshCw, X, AlertTriangle } from "lucide-react";
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
  | "normales"
  | "provisionados"
  | "pendiente_recepcion"
  | "con_error"
  | "boleta_descartada"
  | "sin_correo"
  | "sin_xml"
  | "con_recordatorio";

const FILTERS: { id: FilterKey; label: string }[] = [
  { id: "todos", label: "Todos" },
  { id: "normales", label: "Normales" },
  { id: "provisionados", label: "Provisionados" },
  { id: "pendiente_recepcion", label: "Sin recepción" },
  { id: "boleta_descartada", label: "Boleta no tomada" },
  { id: "con_error", label: "Con error" },
  { id: "sin_correo", label: "Sin correo" },
  { id: "sin_xml", label: "Sin XML" },
  { id: "con_recordatorio", label: "Con recordatorio" },
];

function isProvisionado(row: ExcelAvanceRow): boolean {
  if (typeof row.provisionado === "boolean") return row.provisionado;
  const glosa = (row.glosa || "").toLowerCase();
  return glosa.includes("provisionado") || glosa.includes("provisonado") || glosa.includes("provs");
}

function effectiveEstadoRecepcion(row: ExcelAvanceRow): string {
  return (row.estado_recepcion_efectivo || row.estado_recepcion || "").trim();
}

function recepcionStatusLabel(row: ExcelAvanceRow): string {
  const raw = (row.estado_recepcion || "").trim();
  const eff = effectiveEstadoRecepcion(row);
  if (raw && eff && raw !== eff) return `${raw} -> ${eff}`;
  return eff || raw;
}

function hasXmlEvidence(row: ExcelAvanceRow): boolean {
  return Boolean(
    row.archivo_xml?.trim() ||
      row.archivo_xml_usado?.trim() ||
      row.numero_boleta_xml?.trim() ||
      row.descripcion_xml?.trim()
  );
}

function hasGlosaDistinta(row: ExcelAvanceRow): boolean {
  return row.glosa_xml_coincide === false && hasXmlEvidence(row) && recepcionFinalizada(row);
}

function hasGlosaNormalizada(row: ExcelAvanceRow): boolean {
  return row.glosa_xml_coincide === true && row.glosa_match_mode === "prefijo_omitido";
}

function hasBoletaDescartada(row: ExcelAvanceRow): boolean {
  const estado = effectiveEstadoRecepcion(row).toUpperCase();
  return Boolean(row.observacion_descartes?.trim()) && (estado === "NO RECIBIDO" || estado === "RECIBIDO CON ERROR");
}

function recepcionFinalizada(row: ExcelAvanceRow): boolean {
  const estado = effectiveEstadoRecepcion(row).toUpperCase();
  return estado === "RECIBIDO" || estado === "RECIBIDO CON ERROR";
}

function recordatoriosNum(row: ExcelAvanceRow): number {
  return Number(String(row.recordatorios || "").replace(/[^\d]/g, "") || "0");
}

function recordatoriosLabel(row: ExcelAvanceRow): string {
  const n = recordatoriosNum(row);
  if (n <= 0) return "0";
  if (recepcionFinalizada(row)) return `${n} (hist.)`;
  return String(n);
}

/** Resumen corto para chip en listado (detalle completo en title / panel). */
function discardAlertLabel(descartes: string): string {
  const d = descartes.toLowerCase();
  if (
    d.includes("provisionado") ||
    d.includes("glosa/provisión") ||
    d.includes("glosa/provision")
  ) {
    return "Glosa PROVISIONADO";
  }
  if (d.includes("ya quedó asociada") || d.includes("ya asignada") || d.includes("otra solicitud")) {
    return "Asignada a otra solicitud";
  }
  if (d.includes("monto") && (d.includes("distinto") || d.includes("pero esta solicitud") || d.includes("por $"))) {
    return "Monto distinto";
  }
  if (d.includes("razón social") || d.includes("rut receptor") || d.includes("razón")) {
    return "Razón social distinta";
  }
  if (d.includes("rut emisor")) return "RUT emisor distinto";
  return "Boleta no tomada";
}

function matchesFilter(row: ExcelAvanceRow, filter: FilterKey): boolean {
  const estado = effectiveEstadoRecepcion(row).toUpperCase();
  if (filter === "todos") return true;
  if (filter === "normales") return !isProvisionado(row);
  if (filter === "provisionados") return isProvisionado(row);
  if (filter === "pendiente_recepcion") return !estado || estado === "NO RECIBIDO";
  if (filter === "boleta_descartada") return hasBoletaDescartada(row);
  if (filter === "con_error") {
    return (
      estado === "RECIBIDO CON ERROR" ||
      hasGlosaDistinta(row) ||
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

function pct(part: number, total: number): number {
  if (!total) return 0;
  return Math.round((part / total) * 100);
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
        isProvisionado(r) ? "provisionado" : "normal",
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
    return <p className="text-sm text-muted-foreground">Elige un mes para ver el avance del período.</p>;
  }

  if (q.isLoading && !data) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Cargando avance del período…
      </p>
    );
  }

  if (!data || ((data.total_rows ?? 0) === 0 && !data.solicitud_exists)) {
    return (
      <div className="space-y-2 text-sm">
        <p className="text-muted-foreground">
          Aún no hay solicitudes registradas en este período.
        </p>
        <p className="text-xs text-muted-foreground">{data?.month_dir}</p>
      </div>
    );
  }

  if (data.read_error) {
    return <p className="text-sm text-danger">No se pudo cargar el avance: {data.read_error}</p>;
  }

  const total = data.total_rows;
  const recOk = data.recepcion.recibido;
  const recErr = data.recepcion.recibido_con_error;
  const recibidos = recOk + recErr;
  const isFull = layout === "full";
  const updatedAgo = formatUpdatedAgo(q.dataUpdatedAt);

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
            <h2 className="text-base font-semibold tracking-tight">Avance del período</h2>
          )}
          <p className={cn("text-xs text-muted-foreground", isFull && "md:text-[0.8125rem]")}>
            {month} {year}
            {updatedAgo ? ` · actualizado ${updatedAgo}` : ""}
            {" · "}
            {filtered.length}/{total} fila{total === 1 ? "" : "s"}
            {data.rows_truncated ? " (tabla limitada)" : ""}
            {" · "}
            XML {data.archivos_mes.xml} · PDF {data.archivos_mes.pdf}
          </p>
          <p className="text-2xs text-muted-foreground/90">
            Se actualiza al vuelo (cada ~10 s). El paso 2 solo guarda archivos en la carpeta; recepción y
            XML se actualizan con los pasos 3 y 4.
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
        {data ? (
          <span className="text-xs text-muted-foreground">
            {countForFilter(data.rows, "normales")} normales · {countForFilter(data.rows, "provisionados")}{" "}
            provisionadas
          </span>
        ) : null}
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
                <th className="px-2.5 py-2">Tipo</th>
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
                  <td colSpan={10} className="px-2 py-6 text-center text-muted-foreground">
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
                      <td className="px-2 py-1.5">
                        {isProvisionado(r) ? (
                          <span
                            className="inline-flex rounded-md bg-amber-500/15 px-1.5 py-0.5 text-2xs font-semibold text-amber-800"
                            title={r.glosa || "Arrastre de mes anterior (PROVISIONADO)"}
                          >
                            Provisionado
                          </span>
                        ) : (
                          <span
                            className="inline-flex rounded-md bg-muted px-1.5 py-0.5 text-2xs font-medium text-muted-foreground"
                            title={r.glosa || "Boleta del mes (maestro)"}
                          >
                            Normal
                          </span>
                        )}
                      </td>
                      <td className="px-2 py-1.5 font-mono text-xs">{r.emplid || "—"}</td>
                      <td className="px-2 py-1.5 text-xs">
                        <div className="max-w-[160px] truncate" title={r.nombre_razon}>
                          {r.nombre_razon || "—"}
                        </div>
                        <div className="font-mono text-2xs text-muted-foreground">{r.rut_razon || ""}</div>
                      </td>
                      <td className="px-2 py-1.5">
                        <div className="flex flex-col items-start gap-1">
                          <StatusPill value={recepcionStatusLabel(r) || "Pendiente"} kind={recepcionKind(r)} />
                          {hasGlosaDistinta(r) ? (
                            <span
                              className="inline-flex max-w-[200px] items-center gap-1 truncate rounded-md bg-warning/15 px-1.5 py-0.5 text-2xs font-semibold text-warning"
                              title="La glosa del XML no coincide con la solicitada"
                            >
                              <AlertTriangle className="h-3 w-3 shrink-0" />
                              Glosa distinta
                            </span>
                          ) : null}
                          {hasGlosaNormalizada(r) ? (
                            <span
                              className="inline-flex max-w-[220px] items-center gap-1 truncate rounded-md bg-blue-500/12 px-1.5 py-0.5 text-2xs font-semibold text-blue-700"
                              title="La glosa coincide por normalización (prefijo institucional omitido en XML)"
                            >
                              Glosa normalizada
                            </span>
                          ) : null}
                          {hasBoletaDescartada(r) ? (
                            <span
                              className="inline-flex max-w-[200px] items-center gap-1 truncate rounded-md bg-warning/15 px-1.5 py-0.5 text-2xs font-semibold text-warning"
                              title={r.observacion_descartes}
                            >
                              <AlertTriangle className="h-3 w-3 shrink-0" />
                              {discardAlertLabel(r.observacion_descartes || "")}
                            </span>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-2 py-1.5">
                        <StatusPill value={shortMail(r.correo_enviado) || "Pendiente"} kind={r.correo_clase} />
                      </td>
                      <td
                        className={cn(
                          "px-2 py-1.5 text-xs tabular-nums",
                          recepcionFinalizada(r) && recordatoriosNum(r) > 0 && "text-muted-foreground"
                        )}
                        title={
                          recepcionFinalizada(r) && recordatoriosNum(r) > 0
                            ? "Recordatorios enviados antes de marcar recepción."
                            : undefined
                        }
                      >
                        {recordatoriosLabel(r)}
                      </td>
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
        {hasBoletaDescartada(row) ? (
          <div
            className="rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-[0.8125rem] text-foreground"
            role="status"
          >
            <p className="font-semibold tracking-tight text-warning">
              Boleta en carpeta pero no tomada para esta fila
            </p>
            <p className="mt-1 leading-snug text-muted-foreground">
              {row.observaciones?.trim() ||
                "Hay archivo(s) del docente que no cuadran con esta línea de la solicitud."}
            </p>
            {row.observacion_descartes?.trim() ? (
              <p className="mt-1.5 break-words font-mono text-2xs text-muted-foreground">
                {row.observacion_descartes}
              </p>
            ) : null}
          </div>
        ) : null}
        <DetailSection title="Identificación">
          <DetailKV label="EMPLID" value={row.emplid} mono />
          <DetailKV label="RUT sin DV" value={row.rut_sin_dv} mono />
          <DetailKV label="Sede" value={row.sede} />
          <DetailKV label="Location" value={row.location} />
          <DetailKV label="Tipo" value={isProvisionado(row) ? "Provisionado (arrastre)" : "Normal (maestro del mes)"} />
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
          <DetailKV label="Estado recepción (vista)" value={recepcionStatusLabel(row) || "Pendiente"} />
          {row.estado_recepcion && row.estado_recepcion !== effectiveEstadoRecepcion(row) ? (
            <DetailKV label="Estado en Excel" value={row.estado_recepcion} />
          ) : null}
          {hasGlosaDistinta(row) ? (
            <p className="rounded-md border border-warning/30 bg-warning/10 px-2 py-1.5 text-xs text-warning">
              La glosa del XML no coincide con la pedida en la solicitud. Esta fila se trata como error
              aunque en Excel quede \"RECIBIDO\".
            </p>
          ) : null}
          {hasGlosaNormalizada(row) ? (
            <p className="rounded-md border border-blue-300/50 bg-blue-50 px-2 py-1.5 text-xs text-blue-700">
              Coincidencia válida por normalización: el XML omite el prefijo institucional (IPST/CFTST),
              pero el resto de la glosa coincide.
            </p>
          ) : null}
          <DetailKV label="Correo enviado" value={row.correo_enviado || "—"} />
          <DetailKV label="Recordatorios" value={recordatoriosLabel(row)} />
          {recepcionFinalizada(row) && recordatoriosNum(row) > 0 ? (
            <p className="rounded-md border border-blue-300/50 bg-blue-50 px-2 py-1.5 text-xs text-blue-700">
              Estos recordatorios son históricos: se enviaron antes de que la boleta quedara recepcionada.
            </p>
          ) : null}
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
  const e = effectiveEstadoRecepcion(r).toUpperCase();
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
  // «Glosa no coincide» solo con recepción finalizada + XML asociado.
  if (hasGlosaDistinta(r)) return "Glosa no coincide";
  const estado = effectiveEstadoRecepcion(r).toUpperCase();
  // Sin boleta válida recibida: alinear con Observaciones («aún no recibimos…»).
  if (!estado || estado === "NO RECIBIDO") return "XML no recibido";
  if (r.numero_boleta_xml) return `Boleta ${r.numero_boleta_xml}`;
  if (!hasXmlEvidence(r)) return "Pendiente";
  if (r.xml_clase === "ok") return "OK";
  if (r.observaciones_xml) return shortMail(r.observaciones_xml);
  if (r.archivo_xml) return "Archivo ligado";
  return "Pendiente";
}

function formatUpdatedAgo(dataUpdatedAt: number): string {
  if (!dataUpdatedAt) return "";
  const sec = Math.max(0, Math.round((Date.now() - dataUpdatedAt) / 1000));
  if (sec < 5) return "actualizados ahora";
  if (sec < 60) return `actualizados hace ${sec} s`;
  const min = Math.round(sec / 60);
  return `actualizados hace ${min} min`;
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
