import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Search, X } from "lucide-react";
import type { PagosReportItem, PagosReportResponse } from "@/shared/api/types";
import { formatRutCl } from "@/shared/lib/display-format";
import { cn, toCurrency } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Input } from "@/shared/ui/input";
import { TD, TH, Table, TableWrapper } from "@/shared/ui/table";

type MailFilter = "todos" | "enviado" | "pendiente" | "error" | "omitido";

function mailTone(status: string): "success" | "warning" | "danger" | "default" {
  if (status === "enviado") return "success";
  if (status === "pendiente" || status === "omitido") return "warning";
  if (status === "error") return "danger";
  return "default";
}

function formatName(name: string): string {
  const s = name.trim();
  if (!s.includes(",")) return s;
  const [a, b] = s.split(",", 2);
  return `${(b || "").trim()} ${(a || "").trim()}`.trim() || s;
}

type Props = {
  data: PagosReportResponse;
  year: number;
  month: string;
  sourceLabel: string;
};

export function PagosReportPanel({ data, year, month, sourceLabel }: Props) {
  const [q, setQ] = useState("");
  const [mailFilter, setMailFilter] = useState<MailFilter>("todos");
  const [selected, setSelected] = useState<PagosReportItem | null>(null);

  const items = useMemo(() => {
    if (data.items?.length) return data.items;
    // Fallback mínimo si API vieja sin items
    return (data.rows || []).map((r) => ({
      rut: String(r.ID || r.RUT || ""),
      nombre: String(r.Nombre || r.NOMBRE || ""),
      boleta: String(r["Número Boleta"] || r.BOLETA || ""),
      empresa: String(r.Empr || ""),
      sede: String(r.SEDE || ""),
      mail: String(r.MAIL || ""),
      banco: String(r.BANCO || ""),
      tipo_cuenta: String(r["FORMA PAGO"] || ""),
      nro_cuenta: String(r["NªCUENTA"] || ""),
      descripcion: String(r.Descripción || r.Descripcion || ""),
      estado_boleta: String(r["Estado Boleta"] || ""),
      fecha_emision: String(r["Fecha Emisión"] || ""),
      tipo_documento: String(r["Tipo Documento"] || ""),
      bruto: Number(r["Bruto $"] || 0),
      retencion: Number(r.RETENCIÓN || r.RETENCION || 0),
      liquido: Number(r.LÍQUIDO || r.LIQUIDO || 0),
      retencion_pct: null,
      mail_status: "pendiente",
      mail_status_label: String(r["Correo Enviado"] || "Pendiente"),
      mail_raw: String(r["Correo Enviado"] || ""),
      docente_id: null,
      raw: r,
    })) as PagosReportItem[];
  }, [data.items, data.rows]);

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    return items.filter((it) => {
      if (mailFilter !== "todos" && it.mail_status !== mailFilter) return false;
      if (!term) return true;
      const hay = [
        it.nombre,
        it.rut,
        it.mail,
        it.sede,
        it.boleta,
        it.empresa,
        it.banco,
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(term);
    });
  }, [items, mailFilter, q]);

  const totals = data.totals || {
    bruto: items.reduce((a, i) => a + (i.bruto || 0), 0),
    retencion: items.reduce((a, i) => a + (i.retencion || 0), 0),
    liquido: items.reduce((a, i) => a + (i.liquido || 0), 0),
    rows: items.length,
  };

  const counts = data.counts || {
    enviado: 0,
    pendiente: 0,
    error: 0,
    omitido: 0,
    otro: 0,
  };

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Pagos" value={String(totals.rows)} hint={`${counts.enviado} enviados · ${counts.pendiente} pendientes`} />
        <Metric label="Total bruto" value={toCurrency(totals.bruto)} hint="Honorarios brutos del mes" />
        <Metric label="Retención" value={toCurrency(totals.retencion)} hint="Descuento / retención" />
        <Metric label="Total líquido" value={toCurrency(totals.liquido)} hint="A depositar" accent />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-8"
            placeholder="Buscar docente, RUT, sede, boleta…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        {(
          [
            ["todos", "Todos"],
            ["enviado", "Enviados"],
            ["pendiente", "Pendientes"],
            ["omitido", "Omitidos"],
            ["error", "Error"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setMailFilter(id)}
            className={cn(
              "rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors",
              mailFilter === id
                ? "border-foreground/20 bg-muted text-foreground"
                : "border-border text-muted-foreground hover:text-foreground"
            )}
          >
            {label}
            {id !== "todos" ? (
              <span className="ml-1 tabular-nums text-muted-foreground">
                {counts[id as keyof typeof counts] ?? 0}
              </span>
            ) : null}
          </button>
        ))}
      </div>

      <p className="text-xs text-muted-foreground">
        {sourceLabel}. Montos en pesos chilenos. Clic en un docente para ver el detalle del pago.
        {filtered.length !== items.length ? ` · Mostrando ${filtered.length} de ${items.length}` : ""}
      </p>

      <div className={cn("grid gap-4", selected ? "lg:grid-cols-[1fr_340px]" : "")}>
        <TableWrapper>
          <Table>
            <thead>
              <tr>
                <TH>Docente</TH>
                <TH>Boleta</TH>
                <TH>Sede</TH>
                <TH className="text-right">Bruto</TH>
                <TH className="text-right">Retención</TH>
                <TH className="text-right">Líquido</TH>
                <TH>Correo</TH>
              </tr>
            </thead>
            <tbody>
              {filtered.map((it) => {
                const active =
                  selected &&
                  selected.rut === it.rut &&
                  selected.boleta === it.boleta &&
                  selected.liquido === it.liquido;
                return (
                  <tr
                    key={`${it.rut}-${it.boleta}-${it.liquido}-${it.mail}`}
                    className={cn(
                      "cursor-pointer transition-colors hover:bg-muted/40",
                      active && "bg-muted/60"
                    )}
                    onClick={() => setSelected(it)}
                  >
                    <TD>
                      <div className="min-w-0">
                        <p className="truncate font-medium tracking-tight text-foreground">
                          {formatName(it.nombre)}
                        </p>
                        <p className="font-mono text-2xs text-muted-foreground">
                          {formatRutCl(it.rut) || it.rut}
                          {it.empresa ? ` · ${it.empresa}` : ""}
                        </p>
                      </div>
                    </TD>
                    <TD className="tabular-nums">{it.boleta || "—"}</TD>
                    <TD className="max-w-[120px] truncate text-xs">{it.sede || "—"}</TD>
                    <TD className="text-right tabular-nums text-xs">{toCurrency(it.bruto)}</TD>
                    <TD className="text-right tabular-nums text-xs">
                      <span>{toCurrency(it.retencion)}</span>
                      {it.retencion_pct != null ? (
                        <span className="ml-1 text-2xs text-muted-foreground">{it.retencion_pct}%</span>
                      ) : null}
                    </TD>
                    <TD className="text-right tabular-nums text-sm font-semibold">{toCurrency(it.liquido)}</TD>
                    <TD>
                      <Badge tone={mailTone(it.mail_status)}>{it.mail_status_label}</Badge>
                    </TD>
                  </tr>
                );
              })}
              {!filtered.length ? (
                <tr>
                  <TD colSpan={7} className="py-8 text-center text-sm text-muted-foreground">
                    Sin resultados para este filtro.
                  </TD>
                </tr>
              ) : null}
            </tbody>
          </Table>
        </TableWrapper>

        {selected ? (
          <aside className="rounded-lg border border-border/80 bg-card p-4 shadow-xs">
            <div className="mb-3 flex items-start justify-between gap-2">
              <div>
                <p className="text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">
                  Detalle del pago
                </p>
                <h3 className="mt-1 text-base font-semibold tracking-tight">
                  {formatName(selected.nombre)}
                </h3>
                <p className="font-mono text-xs text-muted-foreground">
                  {formatRutCl(selected.rut) || selected.rut}
                </p>
              </div>
              <button
                type="button"
                className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                onClick={() => setSelected(null)}
                aria-label="Cerrar detalle"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mb-4 grid grid-cols-3 gap-2">
              <MiniStat label="Bruto" value={toCurrency(selected.bruto)} />
              <MiniStat
                label="Retención"
                value={toCurrency(selected.retencion)}
                hint={selected.retencion_pct != null ? `${selected.retencion_pct}%` : undefined}
              />
              <MiniStat label="Líquido" value={toCurrency(selected.liquido)} accent />
            </div>

            <dl className="space-y-2 text-sm">
              <DetailRow label="Boleta" value={selected.boleta || "—"} />
              <DetailRow label="Estado boleta" value={selected.estado_boleta || "—"} />
              <DetailRow label="Fecha emisión" value={selected.fecha_emision || "—"} />
              <DetailRow label="Empresa" value={selected.empresa || "—"} />
              <DetailRow label="Sede" value={selected.sede || "—"} />
              <DetailRow label="Correo" value={selected.mail || "—"} />
              <DetailRow label="Banco" value={selected.banco || "—"} />
              <DetailRow
                label="Cuenta"
                value={
                  [selected.tipo_cuenta, selected.nro_cuenta].filter(Boolean).join(" · ") || "—"
                }
              />
              <DetailRow label="Descripción" value={selected.descripcion || "—"} />
              <DetailRow label="Aviso de pago" value={selected.mail_status_label} />
              {selected.mail_raw && selected.mail_raw !== selected.mail_status_label ? (
                <DetailRow label="Detalle correo" value={selected.mail_raw} />
              ) : null}
            </dl>

            <div className="mt-4 flex flex-col gap-2">
              {selected.docente_id ? (
                <Link
                  to={`/docentes?id=${selected.docente_id}&year=${year}&month=${encodeURIComponent(month)}`}
                  className="inline-flex h-9 w-full items-center justify-between gap-1.5 rounded-md bg-primary px-3.5 text-sm font-medium tracking-tight text-primary-foreground hover:brightness-110"
                >
                  Ver perfil del docente
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
              ) : (
                <Link
                  to={`/docentes?q=${encodeURIComponent(selected.rut || selected.nombre)}`}
                  className="inline-flex h-9 w-full items-center justify-between gap-1.5 rounded-md border border-border bg-card px-3.5 text-sm font-medium tracking-tight text-foreground hover:bg-muted/80"
                >
                  Buscar en docentes
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
              )}
              <p className="text-2xs text-muted-foreground">
                El perfil muestra boletas y correos del docente en este y otros períodos.
              </p>
            </div>
          </aside>
        ) : null}
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string;
  hint?: string;
  accent?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border/80 bg-card px-4 py-3 shadow-xs",
        accent && "border-foreground/15"
      )}
    >
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("mt-1 text-lg font-semibold tracking-tight tabular-nums", accent && "text-foreground")}>
        {value}
      </p>
      {hint ? <p className="mt-0.5 text-2xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

function MiniStat({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string;
  hint?: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-md bg-muted/40 px-2 py-2 text-center">
      <p className="text-2xs text-muted-foreground">{label}</p>
      <p className={cn("text-sm font-semibold tabular-nums", accent && "text-foreground")}>{value}</p>
      {hint ? <p className="text-2xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-border/50 pb-2 last:border-0">
      <dt className="shrink-0 text-xs text-muted-foreground">{label}</dt>
      <dd className="text-right text-xs font-medium leading-snug text-foreground break-all">{value}</dd>
    </div>
  );
}
