import { useEffect, useMemo, useState } from "react";
import { Mail, Receipt, Search, UserRound } from "lucide-react";
import { useAppConfig } from "@/app/app-config";
import { useDebouncedValue } from "@/shared/hooks/use-debounced-value";
import { cn, toCurrency } from "@/shared/lib/utils";
import {
  useBoletas,
  useDocenteBoletas,
  useDocenteEmails,
  useDocenteMetrics,
  useDocenteProfile,
  useDocentes,
  usePeriods,
} from "@/shared/api/queries";
import type { DocenteItem } from "@/shared/api/types";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { EmptyState } from "@/shared/ui/empty-state";
import { ErrorState } from "@/shared/ui/error-state";
import { Input } from "@/shared/ui/input";
import { Pagination } from "@/shared/ui/pagination";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import { Skeleton } from "@/shared/ui/skeleton";
import { TD, TH, Table, TableWrapper } from "@/shared/ui/table";
import { useToast } from "@/shared/ui/toast";

const PAGE_SIZE = 20;
const BOLETAS_PAGE_SIZE = 12;
const EMAILS_PAGE_SIZE = 12;

type ListMode = "todos" | "provisionados";
type DetailTab = "resumen" | "boletas" | "correos";

function estadoTone(estado: string | null | undefined): "success" | "warning" | "danger" | "default" {
  const e = (estado || "").toUpperCase();
  if (e === "RECIBIDO" || e === "ENVIADO") return "success";
  if (e.includes("ERROR") || e === "NO RECIBIDO") return e === "NO RECIBIDO" ? "danger" : "warning";
  if (e === "PENDIENTE") return "warning";
  return "default";
}

export function DocentesPage() {
  const { baseUrl, apiKey } = useAppConfig();
  const { push } = useToast();

  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [listMode, setListMode] = useState<ListMode>("todos");
  const [selectedDocenteId, setSelectedDocenteId] = useState<number | undefined>();
  const [gotoEmplid, setGotoEmplid] = useState("");
  const [detailTab, setDetailTab] = useState<DetailTab>("resumen");

  const [periodKey, setPeriodKey] = useState("");
  const [estado, setEstado] = useState("");
  const [boletasPage, setBoletasPage] = useState(1);

  const [emailTipo, setEmailTipo] = useState("");
  const [emailEstado, setEmailEstado] = useState("");
  const [emailsPage, setEmailsPage] = useState(1);

  const debouncedQ = useDebouncedValue(q, 300);
  const periods = usePeriods(baseUrl, apiKey);
  const docentes = useDocentes(baseUrl, apiKey, {
    q: listMode === "todos" ? debouncedQ : "",
    page: listMode === "todos" ? page : 1,
    pageSize: listMode === "todos" ? PAGE_SIZE : 1,
  });
  const lookup = useDocentes(baseUrl, apiKey, { q: gotoEmplid, page: 1, pageSize: 1 });
  const profile = useDocenteProfile(baseUrl, apiKey, selectedDocenteId);

  const selectedPeriod = periods.data?.find((p) => `${p.year}-${p.month_name}` === periodKey) || periods.data?.[0];

  const metrics = useDocenteMetrics(baseUrl, apiKey, {
    docenteId: selectedDocenteId,
    year: selectedPeriod?.year,
    month: selectedPeriod?.month_name,
  });
  const boletas = useDocenteBoletas(baseUrl, apiKey, {
    docenteId: selectedDocenteId,
    year: selectedPeriod?.year,
    month: selectedPeriod?.month_name,
    estado,
    page: boletasPage,
    pageSize: BOLETAS_PAGE_SIZE,
  });
  const docenteEmails = useDocenteEmails(baseUrl, apiKey, {
    docenteId: selectedDocenteId,
    tipo: emailTipo || undefined,
    estado: emailEstado || undefined,
    page: emailsPage,
    pageSize: EMAILS_PAGE_SIZE,
    enabled: detailTab === "correos",
  });

  const provisionadosBoletas = useBoletas(baseUrl, apiKey, {
    year: selectedPeriod?.year,
    month: selectedPeriod?.month_name,
    q: "PROVISIONADO",
    estado: "",
    page: 1,
    pageSize: 200,
    enabled: listMode === "provisionados",
  });

  const provisionadosGroups = useMemo(() => {
    const grouped = new Map<
      string,
      {
        key: string;
        emplid: string;
        docente_nombre: string;
        boletas_count: number;
        monto_total: number;
      }
    >();
    for (const row of provisionadosBoletas.data?.data || []) {
      const docenteNombre = row.docente_nombre?.trim() || "Docente sin nombre";
      const emplid = row.emplid?.trim() || "-";
      const key = `${emplid}::${docenteNombre}`;
      const cur = grouped.get(key);
      if (!cur) {
        grouped.set(key, {
          key,
          emplid,
          docente_nombre: docenteNombre,
          boletas_count: 1,
          monto_total: row.monto_bruto ?? 0,
        });
      } else {
        cur.boletas_count += 1;
        cur.monto_total += row.monto_bruto ?? 0;
      }
    }
    return [...grouped.values()].sort((a, b) => b.boletas_count - a.boletas_count);
  }, [provisionadosBoletas.data?.data]);

  const filteredProvisionados = useMemo(() => {
    const term = debouncedQ.trim().toLowerCase();
    if (!term) return provisionadosGroups;
    return provisionadosGroups.filter(
      (g) =>
        g.docente_nombre.toLowerCase().includes(term) ||
        g.emplid.toLowerCase().includes(term)
    );
  }, [provisionadosGroups, debouncedQ]);

  useEffect(() => {
    if (!periodKey && periods.data?.length) {
      setPeriodKey(`${periods.data[0].year}-${periods.data[0].month_name}`);
    }
  }, [periods.data, periodKey]);

  useEffect(() => {
    if (!gotoEmplid) return;
    const hit = lookup.data?.data?.[0];
    if (!hit) return;
    setSelectedDocenteId(hit.id);
    setGotoEmplid("");
    setDetailTab("resumen");
  }, [lookup.data, gotoEmplid]);

  useEffect(() => {
    setBoletasPage(1);
    setEmailsPage(1);
    setEmailTipo("");
    setEmailEstado("");
    setDetailTab("resumen");
  }, [selectedDocenteId]);

  const totalPages = useMemo(() => {
    const total = docentes.data?.pagination.total || 0;
    return Math.max(1, Math.ceil(total / PAGE_SIZE));
  }, [docentes.data]);
  const boletasTotalPages = useMemo(() => {
    const total = boletas.data?.pagination.total || 0;
    return Math.max(1, Math.ceil(total / BOLETAS_PAGE_SIZE));
  }, [boletas.data]);
  const emailsTotalPages = useMemo(() => {
    const total = docenteEmails.data?.pagination.total || 0;
    return Math.max(1, Math.ceil(total / EMAILS_PAGE_SIZE));
  }, [docenteEmails.data]);

  async function openBoletaFile(
    row: { id: number; year?: number | null; month_name?: string | null },
    fileType: "xml" | "pdf"
  ) {
    if (!row.year || !row.month_name) {
      push("No se pudo determinar el período de la boleta.", "error");
      return;
    }
    const endpoint = `${baseUrl}/period/${row.year}/${row.month_name}/boletas/${row.id}/files/${fileType}`;
    const response = await fetch(endpoint, { headers: { "x-api-key": apiKey } });
    if (!response.ok) {
      push(`No se pudo abrir ${fileType.toUpperCase()} (${response.status}).`, "error");
      return;
    }
    const blob = await response.blob();
    window.open(URL.createObjectURL(blob), "_blank", "noopener,noreferrer");
  }

  function selectFromList(item: DocenteItem) {
    setSelectedDocenteId(item.id);
  }

  function selectProvisionado(emplid: string) {
    setGotoEmplid(emplid);
  }

  const listCount =
    listMode === "todos"
      ? docentes.data?.pagination.total ?? 0
      : filteredProvisionados.length;

  return (
    <div className="flex h-[calc(100vh-4.5rem)] min-h-[520px] flex-col gap-4">
      <PageHeader
        title="Docentes"
        description="Busca un docente y revisa boletas, montos y correos."
        actions={
          <Select
            value={periodKey}
            onChange={(e) => {
              setPeriodKey(e.target.value);
              setBoletasPage(1);
            }}
            className="min-w-[160px]"
            aria-label="Período de contexto"
          >
            {(periods.data || []).map((p) => (
              <option key={p.id} value={`${p.year}-${p.month_name}`}>
                {p.month_name} {p.year}
              </option>
            ))}
          </Select>
        }
      />

      {docentes.isError && (
        <ErrorState
          title="No pudimos cargar docentes"
          description="Revisa conexión o API key e intenta de nuevo."
          onRetry={() => docentes.refetch()}
        />
      )}

      <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[minmax(280px,340px)_1fr]">
        {/* —— Lista —— */}
        <aside className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-border bg-card">
          <div className="space-y-3 border-b border-border p-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setPage(1);
                }}
                placeholder={listMode === "todos" ? "Nombre, RUT o sede…" : "Filtrar provisionados…"}
                className="pl-8"
                aria-label="Buscar docentes"
              />
            </div>
            <div className="flex gap-1 rounded-md bg-muted p-0.5">
              <ModeChip active={listMode === "todos"} onClick={() => setListMode("todos")}>
                Todos
              </ModeChip>
              <ModeChip
                active={listMode === "provisionados"}
                onClick={() => setListMode("provisionados")}
              >
                Provisionados
                {listMode === "provisionados" && provisionadosGroups.length > 0 && (
                  <span className="ml-1 tabular-nums opacity-80">({provisionadosGroups.length})</span>
                )}
              </ModeChip>
            </div>
            <p className="text-xs text-muted-foreground">
              {listMode === "todos" ? (
                <>
                  <strong className="text-foreground">{listCount}</strong> docentes
                </>
              ) : (
                <>
                  <strong className="text-foreground">{listCount}</strong> con glosa PROVISIONADO en{" "}
                  {selectedPeriod?.month_name} {selectedPeriod?.year}
                </>
              )}
            </p>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto">
            {listMode === "todos" && docentes.isLoading && (
              <div className="space-y-2 p-3">
                {Array.from({ length: 8 }).map((_, i) => (
                  <Skeleton key={i} className="h-14 w-full" />
                ))}
              </div>
            )}
            {listMode === "todos" &&
              !docentes.isLoading &&
              (docentes.data?.data || []).map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => selectFromList(item)}
                  className={cn(
                    "flex w-full flex-col gap-0.5 border-b border-border px-3 py-2.5 text-left transition-colors",
                    selectedDocenteId === item.id
                      ? "bg-primary/10 border-l-2 border-l-primary"
                      : "hover:bg-muted/60 border-l-2 border-l-transparent"
                  )}
                >
                  <span className="truncate text-sm font-medium">{item.nombre_completo}</span>
                  <span className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                    <span className="truncate">
                      {item.rut}
                      {item.sede ? ` · ${item.sede}` : ""}
                    </span>
                    <span className="shrink-0 tabular-nums">{item.boletas_count} BH</span>
                  </span>
                </button>
              ))}
            {listMode === "todos" && !docentes.isLoading && (docentes.data?.data.length || 0) === 0 && (
              <div className="p-4">
                <EmptyState title="Sin resultados" description="Prueba otro nombre o RUT." />
              </div>
            )}

            {listMode === "provisionados" && provisionadosBoletas.isLoading && (
              <div className="space-y-2 p-3">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-14 w-full" />
                ))}
              </div>
            )}
            {listMode === "provisionados" && provisionadosBoletas.isError && (
              <div className="p-3">
                <ErrorState
                  title="No se cargaron provisionados"
                  description="Revisa API key o conexión."
                  onRetry={() => provisionadosBoletas.refetch()}
                />
              </div>
            )}
            {listMode === "provisionados" &&
              !provisionadosBoletas.isLoading &&
              filteredProvisionados.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => selectProvisionado(item.emplid)}
                  className="flex w-full flex-col gap-0.5 border-b border-border border-l-2 border-l-transparent px-3 py-2.5 text-left transition-colors hover:bg-muted/60"
                >
                  <span className="truncate text-sm font-medium">{item.docente_nombre}</span>
                  <span className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                    <span className="truncate">{item.emplid}</span>
                    <span className="shrink-0 tabular-nums">
                      {item.boletas_count} · {toCurrency(item.monto_total)}
                    </span>
                  </span>
                </button>
              ))}
            {listMode === "provisionados" &&
              !provisionadosBoletas.isLoading &&
              filteredProvisionados.length === 0 && (
                <div className="p-4">
                  <EmptyState
                    title="Sin provisionados"
                    description={`No hay glosas PROVISIONADO en ${selectedPeriod?.month_name || "este mes"}.`}
                  />
                </div>
              )}
          </div>

          {listMode === "todos" && (
            <div className="border-t border-border p-2">
              <Pagination
                page={page}
                totalPages={totalPages}
                onPrev={() => setPage((p) => p - 1)}
                onNext={() => setPage((p) => p + 1)}
              />
            </div>
          )}
        </aside>

        {/* —— Detalle —— */}
        <section className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-border bg-card">
          {!selectedDocenteId && (
            <div className="flex flex-1 items-center justify-center p-8">
              <EmptyState
                title="Selecciona un docente"
                description="Usa la lista de la izquierda o el modo Provisionados para abrir un perfil."
              />
            </div>
          )}

          {selectedDocenteId && profile.isLoading && (
            <div className="space-y-3 p-4">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-10 w-64" />
              <Skeleton className="h-64 w-full" />
            </div>
          )}

          {selectedDocenteId && profile.isError && (
            <div className="p-4">
              <ErrorState
                title="No pudimos cargar el perfil"
                description="Intenta de nuevo."
                onRetry={() => profile.refetch()}
              />
            </div>
          )}

          {profile.data && (
            <>
              <div className="shrink-0 border-b border-border p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 space-y-1">
                    <div className="flex items-center gap-2">
                      <UserRound className="h-5 w-5 shrink-0 text-muted-foreground" />
                      <h2 className="truncate text-lg font-semibold">{profile.data.docente.nombre_completo}</h2>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {profile.data.docente.rut}
                      {profile.data.docente.sede ? ` · ${profile.data.docente.sede}` : ""}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {profile.data.docente.email_personal || "Sin email personal"}
                      {profile.data.docente.email_dp ? ` · DP: ${profile.data.docente.email_dp}` : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <StatPill label="Boletas" value={String(profile.data.docente.boletas_count)} />
                    <StatPill label="Monto" value={toCurrency(profile.data.docente.monto_total)} />
                    <StatPill
                      label="Correos OK"
                      value={String(profile.data.email_summary?.enviados ?? 0)}
                    />
                    {(profile.data.email_summary?.error ?? 0) > 0 && (
                      <StatPill
                        label="Errores mail"
                        value={String(profile.data.email_summary.error)}
                        danger
                      />
                    )}
                  </div>
                </div>

                <div className="mt-4 flex gap-1 border-b border-transparent">
                  <TabChip
                    active={detailTab === "resumen"}
                    onClick={() => setDetailTab("resumen")}
                    icon={<UserRound className="h-3.5 w-3.5" />}
                  >
                    Resumen
                  </TabChip>
                  <TabChip
                    active={detailTab === "boletas"}
                    onClick={() => setDetailTab("boletas")}
                    icon={<Receipt className="h-3.5 w-3.5" />}
                  >
                    Boletas
                  </TabChip>
                  <TabChip
                    active={detailTab === "correos"}
                    onClick={() => setDetailTab("correos")}
                    icon={<Mail className="h-3.5 w-3.5" />}
                  >
                    Correos
                  </TabChip>
                </div>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto p-4">
                {detailTab === "resumen" && (
                  <div className="space-y-5">
                    <div>
                      <h3 className="mb-2 text-sm font-medium">Actividad de correo</h3>
                      <div className="grid gap-2 sm:grid-cols-4">
                        <MiniMetric label="Enviados" value={profile.data.email_summary?.enviados ?? 0} />
                        <MiniMetric label="Error" value={profile.data.email_summary?.error ?? 0} />
                        <MiniMetric label="Pendientes" value={profile.data.email_summary?.pendientes ?? 0} />
                        <MiniMetric label="Total" value={profile.data.email_summary?.total ?? 0} />
                      </div>
                      <p className="mt-2 text-xs text-muted-foreground">
                        Último envío:{" "}
                        {profile.data.email_summary?.ultimo_envio
                          ? new Date(profile.data.email_summary.ultimo_envio).toLocaleString("es-CL")
                          : "Sin registro"}
                      </p>
                    </div>

                    {metrics.data && (
                      <div>
                        <h3 className="mb-2 text-sm font-medium">
                          Métricas · {selectedPeriod?.month_name} {selectedPeriod?.year}
                        </h3>
                        <div className="grid gap-2 sm:grid-cols-3">
                          <MiniMetric label="Recibidas" value={metrics.data.metrics.recibidas} />
                          <MiniMetric label="Con error" value={metrics.data.metrics.con_error} />
                          <MiniMetric label="Sin XML" value={metrics.data.metrics.sin_xml} />
                        </div>
                      </div>
                    )}

                    <div>
                      <h3 className="mb-2 text-sm font-medium">Por período</h3>
                      {(profile.data.period_stats || []).length === 0 ? (
                        <EmptyState title="Sin períodos" description="Este docente aún no tiene boletas asociadas." />
                      ) : (
                        <TableWrapper>
                          <Table>
                            <thead>
                              <tr>
                                <TH>Período</TH>
                                <TH className="text-right">Boletas</TH>
                                <TH className="text-right">Monto</TH>
                              </tr>
                            </thead>
                            <tbody>
                              {profile.data.period_stats.map((p) => (
                                <tr
                                  key={p.period_id}
                                  className="cursor-pointer hover:bg-muted/50"
                                  onClick={() => {
                                    setPeriodKey(`${p.year}-${p.month_name}`);
                                    setDetailTab("boletas");
                                    setBoletasPage(1);
                                  }}
                                >
                                  <TD>
                                    {p.month_name} {p.year}
                                  </TD>
                                  <TD className="text-right">{p.boletas}</TD>
                                  <TD className="text-right">{toCurrency(p.monto_total)}</TD>
                                </tr>
                              ))}
                            </tbody>
                          </Table>
                        </TableWrapper>
                      )}
                      <p className="mt-1 text-xs text-muted-foreground">
                        Clic en un período para ver sus boletas.
                      </p>
                    </div>

                    <div>
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <h3 className="text-sm font-medium">Últimos correos</h3>
                        <Button variant="ghost" className="h-8 px-2 text-xs" onClick={() => setDetailTab("correos")}>
                          Ver todos
                        </Button>
                      </div>
                      <EmailsTable rows={profile.data.recent_emails ?? []} empty="Sin correos registrados." />
                    </div>
                  </div>
                )}

                {detailTab === "boletas" && (
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-end gap-2">
                      <label className="grid gap-1 text-xs text-muted-foreground">
                        Período
                        <Select
                          value={periodKey}
                          onChange={(e) => {
                            setPeriodKey(e.target.value);
                            setBoletasPage(1);
                          }}
                        >
                          {(periods.data || []).map((p) => (
                            <option key={p.id} value={`${p.year}-${p.month_name}`}>
                              {p.month_name} {p.year}
                            </option>
                          ))}
                        </Select>
                      </label>
                      <label className="grid gap-1 text-xs text-muted-foreground">
                        Estado
                        <Select
                          value={estado}
                          onChange={(e) => {
                            setEstado(e.target.value);
                            setBoletasPage(1);
                          }}
                        >
                          <option value="">Todos</option>
                          <option value="RECIBIDO">RECIBIDO</option>
                          <option value="RECIBIDO CON ERROR">RECIBIDO CON ERROR</option>
                          <option value="NO RECIBIDO">NO RECIBIDO</option>
                        </Select>
                      </label>
                      <p className="pb-2 text-sm text-muted-foreground">
                        <strong className="text-foreground">{boletas.data?.pagination.total ?? 0}</strong> boletas
                      </p>
                    </div>

                    <TableWrapper>
                      <Table>
                        <thead>
                          <tr>
                            <TH>ID</TH>
                            <TH>Período</TH>
                            <TH>Estado</TH>
                            <TH className="text-right">Monto</TH>
                            <TH>Archivos</TH>
                          </tr>
                        </thead>
                        <tbody>
                          {boletas.isLoading &&
                            Array.from({ length: 5 }).map((_, i) => (
                              <tr key={i}>
                                <TD colSpan={5}>
                                  <Skeleton className="h-5 w-full" />
                                </TD>
                              </tr>
                            ))}
                          {!boletas.isLoading &&
                            (boletas.data?.data || []).map((row) => (
                              <tr key={row.id}>
                                <TD className="tabular-nums">{row.id}</TD>
                                <TD>
                                  {row.month_name && row.year ? `${row.month_name} ${row.year}` : "—"}
                                </TD>
                                <TD>
                                  <Badge tone={estadoTone(row.estado_recepcion)}>
                                    {row.estado_recepcion || "—"}
                                  </Badge>
                                </TD>
                                <TD className="text-right tabular-nums">{toCurrency(row.monto_bruto)}</TD>
                                <TD>
                                  {row.archivo_xml ? (
                                    <div className="flex gap-1">
                                      <Button
                                        variant="ghost"
                                        className="h-8 px-2 text-xs"
                                        onClick={() => void openBoletaFile(row, "xml")}
                                      >
                                        XML
                                      </Button>
                                      <Button
                                        variant="ghost"
                                        className="h-8 px-2 text-xs"
                                        onClick={() => void openBoletaFile(row, "pdf")}
                                      >
                                        PDF
                                      </Button>
                                    </div>
                                  ) : (
                                    <span className="text-xs text-muted-foreground">Sin archivo</span>
                                  )}
                                </TD>
                              </tr>
                            ))}
                          {!boletas.isLoading && (boletas.data?.data.length || 0) === 0 && (
                            <tr>
                              <TD colSpan={5}>
                                <EmptyState
                                  title="Sin boletas"
                                  description="Cambia período o estado para ver más resultados."
                                />
                              </TD>
                            </tr>
                          )}
                        </tbody>
                      </Table>
                    </TableWrapper>
                    <Pagination
                      page={boletasPage}
                      totalPages={boletasTotalPages}
                      onPrev={() => setBoletasPage((p) => p - 1)}
                      onNext={() => setBoletasPage((p) => p + 1)}
                    />
                  </div>
                )}

                {detailTab === "correos" && (
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-end gap-2">
                      <label className="grid gap-1 text-xs text-muted-foreground">
                        Tipo
                        <Select
                          value={emailTipo}
                          onChange={(e) => {
                            setEmailTipo(e.target.value);
                            setEmailsPage(1);
                          }}
                        >
                          <option value="">Todos</option>
                          <option value="SOLICITUD">SOLICITUD</option>
                          <option value="RECORDATORIO">RECORDATORIO</option>
                          <option value="RECEPCION">RECEPCION</option>
                          <option value="PAGO">PAGO</option>
                        </Select>
                      </label>
                      <label className="grid gap-1 text-xs text-muted-foreground">
                        Estado
                        <Select
                          value={emailEstado}
                          onChange={(e) => {
                            setEmailEstado(e.target.value);
                            setEmailsPage(1);
                          }}
                        >
                          <option value="">Todos</option>
                          <option value="ENVIADO">ENVIADO</option>
                          <option value="ERROR">ERROR</option>
                          <option value="PENDIENTE">PENDIENTE</option>
                        </Select>
                      </label>
                      <p className="pb-2 text-sm text-muted-foreground">
                        <strong className="text-foreground">{docenteEmails.data?.pagination.total ?? 0}</strong> correos
                      </p>
                    </div>
                    {docenteEmails.isLoading ? (
                      <Skeleton className="h-40 w-full" />
                    ) : (
                      <EmailsTable
                        rows={docenteEmails.data?.data || []}
                        empty="Sin correos para estos filtros."
                      />
                    )}
                    <Pagination
                      page={emailsPage}
                      totalPages={emailsTotalPages}
                      onPrev={() => setEmailsPage((p) => p - 1)}
                      onNext={() => setEmailsPage((p) => p + 1)}
                    />
                  </div>
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function ModeChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition-colors",
        active ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
      )}
    >
      {children}
    </button>
  );
}

function TabChip({
  active,
  onClick,
  icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium transition-colors",
        active
          ? "border-primary text-foreground"
          : "border-transparent text-muted-foreground hover:text-foreground"
      )}
    >
      {icon}
      {children}
    </button>
  );
}

function StatPill({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <div
      className={cn(
        "rounded-md border px-2.5 py-1.5 text-right",
        danger ? "border-red-200 bg-red-50" : "border-border bg-muted/40"
      )}
    >
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={cn("text-sm font-semibold tabular-nums", danger && "text-red-700")}>{value}</p>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function EmailsTable({
  rows,
  empty,
}: {
  rows: Array<{
    id: number;
    sent_at: string | null;
    tipo_envio: string;
    estado: string;
    to_email: string;
    subject: string | null;
  }>;
  empty: string;
}) {
  if (!rows.length) {
    return <EmptyState title="Sin correos" description={empty} />;
  }
  return (
    <TableWrapper>
      <Table>
        <thead>
          <tr>
            <TH>Fecha</TH>
            <TH>Tipo</TH>
            <TH>Estado</TH>
            <TH>Destino</TH>
            <TH>Asunto</TH>
          </tr>
        </thead>
        <tbody>
          {rows.map((mail) => (
            <tr key={mail.id}>
              <TD className="whitespace-nowrap text-xs">
                {mail.sent_at ? new Date(mail.sent_at).toLocaleString("es-CL") : "—"}
              </TD>
              <TD>
                <Badge>{mail.tipo_envio}</Badge>
              </TD>
              <TD>
                <Badge tone={estadoTone(mail.estado)}>{mail.estado}</Badge>
              </TD>
              <TD className="max-w-[140px] truncate text-xs" title={mail.to_email}>
                {mail.to_email}
              </TD>
              <TD className="max-w-[220px] truncate text-xs" title={mail.subject || ""}>
                {mail.subject || "—"}
              </TD>
            </tr>
          ))}
        </tbody>
      </Table>
    </TableWrapper>
  );
}
