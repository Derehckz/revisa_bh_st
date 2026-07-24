import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowDownAZ, ArrowUpAZ, Search, SlidersHorizontal } from "lucide-react";
import { useAppConfig } from "@/app/app-config";
import { useBoletas, usePeriods } from "@/shared/api/queries";
import type { BoletaItem } from "@/shared/api/types";
import { useDebouncedValue } from "@/shared/hooks/use-debounced-value";
import { toCurrency } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { ErrorState } from "@/shared/ui/error-state";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { Pagination } from "@/shared/ui/pagination";
import { Select } from "@/shared/ui/select";
import { Skeleton } from "@/shared/ui/skeleton";
import { TD, TH, Table, TableWrapper } from "@/shared/ui/table";
import { useToast } from "@/shared/ui/toast";
import { BoletaDetailDrawer } from "@/features/boletas/boleta-detail-drawer";

const PAGE_SIZE = 20;
type SortKey = "id" | "emplid" | "docente_nombre" | "estado_recepcion" | "monto_bruto";

export function BoletasPage() {
  const { baseUrl, apiKey } = useAppConfig();
  const { push } = useToast();
  const periods = usePeriods(baseUrl, apiKey);
  const [selectedPeriodKey, setSelectedPeriodKey] = useState<string>("");
  const selected =
    periods.data?.find((p) => `${p.year}-${p.month_name}` === selectedPeriodKey) || periods.data?.[0];
  const [estado, setEstado] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [xmlFilter, setXmlFilter] = useState<"all" | "with_xml" | "without_xml">("all");
  const [montoMin, setMontoMin] = useState<string>("");
  const [montoMax, setMontoMax] = useState<string>("");
  const [sortKey, setSortKey] = useState<SortKey>("id");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [selectedBoletaId, setSelectedBoletaId] = useState<number | undefined>(undefined);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const debouncedQ = useDebouncedValue(q, 300);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!selectedPeriodKey && periods.data?.length) {
      setSelectedPeriodKey(`${periods.data[0].year}-${periods.data[0].month_name}`);
    }
  }, [periods.data, selectedPeriodKey]);

  const query = useBoletas(baseUrl, apiKey, {
    year: selected?.year,
    month: selected?.month_name,
    estado,
    q: debouncedQ,
    page,
    pageSize: PAGE_SIZE,
  });

  const totalPages = useMemo(() => {
    const total = query.data?.pagination.total || 0;
    return Math.max(1, Math.ceil(total / PAGE_SIZE));
  }, [query.data]);

  const sortedRows = useMemo(() => {
    const rows = [...(query.data?.data || [])].filter((row) => {
      if (xmlFilter === "with_xml" && !row.archivo_xml) return false;
      if (xmlFilter === "without_xml" && row.archivo_xml) return false;
      const monto = row.monto_bruto ?? 0;
      const min = montoMin ? Number(montoMin) : null;
      const max = montoMax ? Number(montoMax) : null;
      if (min !== null && monto < min) return false;
      if (max !== null && monto > max) return false;
      return true;
    });
    rows.sort((a, b) => compareValues(a, b, sortKey, sortDir));
    return rows;
  }, [query.data?.data, sortDir, sortKey, xmlFilter, montoMin, montoMax]);

  function toggleSort(nextKey: SortKey) {
    if (sortKey === nextKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(nextKey);
      setSortDir("asc");
    }
  }

  function sortIcon(nextKey: SortKey) {
    if (sortKey !== nextKey) return <ArrowDownAZ size={12} className="opacity-40" />;
    return sortDir === "asc" ? <ArrowDownAZ size={12} /> : <ArrowUpAZ size={12} />;
  }

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "/" && !event.ctrlKey && !event.metaKey && !event.altKey) {
        const tag = (event.target as HTMLElement | null)?.tagName?.toLowerCase();
        if (tag === "input" || tag === "textarea") return;
        event.preventDefault();
        searchInputRef.current?.focus();
      }
      if (event.key === "Escape" && (estado || q || xmlFilter !== "all" || montoMin || montoMax)) {
        setEstado("");
        setQ("");
        setXmlFilter("all");
        setMontoMin("");
        setMontoMax("");
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [estado, q, xmlFilter, montoMin, montoMax]);

  async function openBoletaFile(boletaId: number, fileType: "xml" | "pdf") {
    if (!selected?.year || !selected?.month_name) return;
    const endpoint = `${baseUrl}/period/${selected.year}/${selected.month_name}/boletas/${boletaId}/files/${fileType}`;
    const response = await fetch(endpoint, {
      headers: {
        "x-api-key": apiKey,
      },
    });
    if (!response.ok) {
      push(`No se pudo abrir ${fileType.toUpperCase()} (${response.status}).`, "error");
      return;
    }
    const blob = await response.blob();
    const blobUrl = URL.createObjectURL(blob);
    window.open(blobUrl, "_blank", "noopener,noreferrer");
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Boletas"
        description="Consulta, filtra y abre XML/PDF del período."
      />
      {query.isError && (
        <ErrorState
          title="No pudimos cargar boletas"
          description="Revisa filtros, conectividad API o autenticación."
          onRetry={() => query.refetch()}
        />
      )}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Filtros</CardTitle>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <SlidersHorizontal size={14} />
            <span>{debouncedQ ? "Búsqueda activa" : "Sin búsqueda"}</span>
          </div>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-4">
          <Select
            value={selected ? `${selected.year}-${selected.month_name}` : ""}
            onChange={(e) => {
              setSelectedPeriodKey(e.target.value);
              setPage(1);
            }}
          >
            {(periods.data || []).map((p) => (
              <option key={p.id} value={`${p.year}-${p.month_name}`}>
                {p.month_name} {p.year}
              </option>
            ))}
          </Select>
          <Select value={estado} onChange={(e) => setEstado(e.target.value)}>
            <option value="">Todos los estados</option>
            <option value="RECIBIDO">RECIBIDO</option>
            <option value="RECIBIDO CON ERROR">RECIBIDO CON ERROR</option>
            <option value="NO RECIBIDO">NO RECIBIDO</option>
          </Select>
          <div className="relative">
            <Search className="absolute left-2 top-2.5 text-muted-foreground" size={14} />
            <Input
              ref={searchInputRef}
              className="pl-8"
              placeholder="Buscar emplid o boleta_key"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <div className="text-sm text-muted-foreground">
            Total: <strong>{query.data?.pagination.total ?? 0}</strong>
          </div>
          <Select value={xmlFilter} onChange={(e) => setXmlFilter(e.target.value as typeof xmlFilter)}>
            <option value="all">XML: Todos</option>
            <option value="with_xml">XML: Con XML</option>
            <option value="without_xml">XML: Sin XML</option>
          </Select>
          <Input
            placeholder="Monto mínimo"
            value={montoMin}
            onChange={(e) => setMontoMin(e.target.value.replace(/[^\d]/g, ""))}
          />
          <Input
            placeholder="Monto máximo"
            value={montoMax}
            onChange={(e) => setMontoMax(e.target.value.replace(/[^\d]/g, ""))}
          />
          <div className="rounded-md border border-dashed border-border px-3 py-2 text-xs text-muted-foreground md:col-span-2">
            Filtro por email por boleta quedará habilitado cuando exista endpoint de vínculo boleta-email directo.
          </div>
          {(estado || debouncedQ || xmlFilter !== "all" || montoMin || montoMax) && (
            <div className="md:col-span-4 flex flex-wrap items-center gap-2">
              {estado && <Badge>{estado}</Badge>}
              {debouncedQ && <Badge>{`q: ${debouncedQ}`}</Badge>}
              {xmlFilter !== "all" && <Badge>{xmlFilter === "with_xml" ? "con XML" : "sin XML"}</Badge>}
              {montoMin && <Badge>{`min: ${montoMin}`}</Badge>}
              {montoMax && <Badge>{`max: ${montoMax}`}</Badge>}
              <Button
                variant="ghost"
                onClick={() => {
                  setEstado("");
                  setQ("");
                  setXmlFilter("all");
                  setMontoMin("");
                  setMontoMax("");
                  setPage(1);
                }}
              >
                Limpiar filtros
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <TableWrapper>
        <Table>
          <thead>
            <tr>
              <TH>
                <button aria-label="Ordenar por ID" className="inline-flex items-center gap-1" onClick={() => toggleSort("id")}>
                  ID {sortIcon("id")}
                </button>
              </TH>
              <TH>
                <button aria-label="Ordenar por EMPLID" className="inline-flex items-center gap-1" onClick={() => toggleSort("emplid")}>
                  EMPLID {sortIcon("emplid")}
                </button>
              </TH>
              <TH>
                <button aria-label="Ordenar por Docente" className="inline-flex items-center gap-1" onClick={() => toggleSort("docente_nombre")}>
                  Nombre {sortIcon("docente_nombre")}
                </button>
              </TH>
              <TH>
                <button aria-label="Ordenar por Estado" className="inline-flex items-center gap-1" onClick={() => toggleSort("estado_recepcion")}>
                  Estado {sortIcon("estado_recepcion")}
                </button>
              </TH>
              <TH className="text-right">
                <button aria-label="Ordenar por Monto" className="inline-flex items-center gap-1" onClick={() => toggleSort("monto_bruto")}>
                  Monto {sortIcon("monto_bruto")}
                </button>
              </TH>
              <TH>XML</TH>
              <TH>PDF</TH>
            </tr>
          </thead>
          <tbody>
            {query.isLoading &&
              Array.from({ length: 8 }).map((_, idx) => (
                <tr key={`s-${idx}`}>
                  <TD><Skeleton className="h-4 w-10" /></TD>
                  <TD><Skeleton className="h-4 w-24" /></TD>
                  <TD><Skeleton className="h-4 w-40" /></TD>
                  <TD><Skeleton className="h-6 w-24 rounded-full" /></TD>
                  <TD className="text-right"><Skeleton className="ml-auto h-4 w-16" /></TD>
                  <TD><Skeleton className="h-4 w-28" /></TD>
                  <TD><Skeleton className="h-4 w-24" /></TD>
                </tr>
              ))}
            {!query.isLoading && sortedRows.map((row) => (
              <tr
                key={row.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => {
                  setSelectedBoletaId(row.id);
                  setDrawerOpen(true);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelectedBoletaId(row.id);
                    setDrawerOpen(true);
                  }
                }}
                tabIndex={0}
              >
                <TD>{row.id}</TD>
                <TD>{row.emplid || "-"}</TD>
                <TD>{row.docente_nombre || "-"}</TD>
                <TD>
                  <Badge tone={row.estado_recepcion?.includes("ERROR") ? "warning" : row.estado_recepcion === "NO RECIBIDO" ? "danger" : "success"}>
                    {row.estado_recepcion === "RECIBIDO"
                      ? "✅ RECIBIDO"
                      : row.estado_recepcion === "RECIBIDO CON ERROR"
                        ? "⚠️ RECIBIDO CON ERROR"
                        : row.estado_recepcion === "NO RECIBIDO"
                          ? "❌ NO RECIBIDO"
                          : "-"}
                  </Badge>
                </TD>
                <TD className="text-right">{toCurrency(row.monto_bruto)}</TD>
                <TD className="text-xs">
                  {row.archivo_xml ? (
                    <Button
                      variant="ghost"
                      onClick={(event) => {
                        event.stopPropagation();
                        void openBoletaFile(row.id, "xml");
                      }}
                    >
                      Ver XML
                    </Button>
                  ) : "-"}
                </TD>
                <TD className="text-xs text-muted-foreground">
                  {inferPdfName(row.archivo_xml) !== "-" ? (
                    <Button
                      variant="ghost"
                      onClick={(event) => {
                        event.stopPropagation();
                        void openBoletaFile(row.id, "pdf");
                      }}
                    >
                      Ver PDF
                    </Button>
                  ) : "-"}
                </TD>
              </tr>
            ))}
            {!query.isLoading && sortedRows.length === 0 && (
              <tr>
                <TD colSpan={7} className="py-10 text-center text-muted-foreground">
                  <EmptyState
                    title="Sin resultados"
                    description="No encontramos boletas para este período con los filtros actuales."
                  />
                </TD>
              </tr>
            )}
          </tbody>
        </Table>
      </TableWrapper>

      <Pagination page={page} totalPages={totalPages} onPrev={() => setPage((p) => p - 1)} onNext={() => setPage((p) => p + 1)} />
      <div className="rounded-md border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">
        Leyenda rápida: ✅ recibido | ⚠️ recibido con error | ❌ no recibido.
      </div>
      <BoletaDetailDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        year={selected?.year}
        month={selected?.month_name}
        boletaId={selectedBoletaId}
      />
    </div>
  );
}

function compareValues(a: BoletaItem, b: BoletaItem, key: SortKey, dir: "asc" | "desc") {
  const dirFactor = dir === "asc" ? 1 : -1;
  const av = a[key];
  const bv = b[key];
  if (key === "id" || key === "monto_bruto") {
    const na = typeof av === "number" ? av : Number(av ?? 0);
    const nb = typeof bv === "number" ? bv : Number(bv ?? 0);
    return (na - nb) * dirFactor;
  }
  return String(av ?? "").localeCompare(String(bv ?? ""), "es") * dirFactor;
}

function inferPdfName(xmlName: string | null) {
  if (!xmlName) return "-";
  if (!xmlName.toLowerCase().endsWith(".xml")) return "-";
  return xmlName.replace(/\.xml$/i, ".pdf");
}
