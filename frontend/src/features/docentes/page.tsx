import { Fragment, useEffect, useMemo, useState } from "react";
import { useAppConfig } from "@/app/app-config";
import { useDebouncedValue } from "@/shared/hooks/use-debounced-value";
import { toCurrency } from "@/shared/lib/utils";
import {
  useBoletas,
  useDocenteBoletas,
  useDocenteMetrics,
  useDocenteProfile,
  useDocentes,
  usePeriods,
} from "@/shared/api/queries";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { ErrorState } from "@/shared/ui/error-state";
import { Input } from "@/shared/ui/input";
import { Pagination } from "@/shared/ui/pagination";
import { Select } from "@/shared/ui/select";
import { Skeleton } from "@/shared/ui/skeleton";
import { TD, TH, Table, TableWrapper } from "@/shared/ui/table";
import { useToast } from "@/shared/ui/toast";

const PAGE_SIZE = 15;
const BOLETAS_PAGE_SIZE = 10;

export function DocentesPage() {
  const { baseUrl, apiKey } = useAppConfig();
  const { push } = useToast();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [selectedDocenteId, setSelectedDocenteId] = useState<number | undefined>(undefined);
  const [gotoDocenteQuery, setGotoDocenteQuery] = useState("");
  const [selectedPeriodKey, setSelectedPeriodKey] = useState("");
  const [estado, setEstado] = useState("");
  const [boletasPage, setBoletasPage] = useState(1);
  const [provisionadosPeriodKey, setProvisionadosPeriodKey] = useState("");
  const [expandedProvisionadoKey, setExpandedProvisionadoKey] = useState<string | null>(null);
  const debouncedQ = useDebouncedValue(q, 300);
  const periods = usePeriods(baseUrl, apiKey);
  const docentes = useDocentes(baseUrl, apiKey, { q: debouncedQ, page, pageSize: PAGE_SIZE });
  const docenteLookup = useDocentes(baseUrl, apiKey, { q: gotoDocenteQuery, page: 1, pageSize: 1 });
  const profile = useDocenteProfile(baseUrl, apiKey, selectedDocenteId);
  const selectedPeriod = periods.data?.find((p) => `${p.year}-${p.month_name}` === selectedPeriodKey);
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
  const provisionadosPeriod =
    periods.data?.find((p) => `${p.year}-${p.month_name}` === provisionadosPeriodKey) || periods.data?.[0];
  const provisionadosBoletas = useBoletas(baseUrl, apiKey, {
    year: provisionadosPeriod?.year,
    month: provisionadosPeriod?.month_name,
    q: "PROVISIONADO",
    estado: "",
    page: 1,
    pageSize: 200,
  });

  useEffect(() => {
    if (!provisionadosPeriodKey && periods.data?.length) {
      setProvisionadosPeriodKey(`${periods.data[0].year}-${periods.data[0].month_name}`);
    }
  }, [periods.data, provisionadosPeriodKey]);

  const totalPages = useMemo(() => {
    const total = docentes.data?.pagination.total || 0;
    return Math.max(1, Math.ceil(total / PAGE_SIZE));
  }, [docentes.data]);
  const boletasTotalPages = useMemo(() => {
    const total = boletas.data?.pagination.total || 0;
    return Math.max(1, Math.ceil(total / BOLETAS_PAGE_SIZE));
  }, [boletas.data]);
  const provisionadosDocentes = useMemo(() => {
    const grouped = new Map<
      string,
      {
        key: string;
        docente_nombre: string;
        emplid: string;
        boletas_count: number;
        monto_total: number;
        boletas: Array<{
          id: number;
          year?: number | null;
          month_name?: string | null;
          estado: string | null;
          glosa: string | null;
          monto: number | null;
        }>;
      }
    >();
    for (const row of provisionadosBoletas.data?.data || []) {
      const docenteNombre = row.docente_nombre?.trim() || "Docente sin nombre";
      const emplid = row.emplid?.trim() || "-";
      const key = `${emplid}::${docenteNombre}`;
      const current = grouped.get(key);
      if (!current) {
        grouped.set(key, {
          key,
          docente_nombre: docenteNombre,
          emplid,
          boletas_count: 1,
          monto_total: row.monto_bruto ?? 0,
          boletas: [
            {
              id: row.id,
              year: row.year,
              month_name: row.month_name,
              estado: row.estado_recepcion,
              glosa: row.glosa ?? null,
              monto: row.monto_bruto,
            },
          ],
        });
      } else {
        current.boletas_count += 1;
        current.monto_total += row.monto_bruto ?? 0;
        current.boletas.push({
          id: row.id,
          year: row.year,
          month_name: row.month_name,
          estado: row.estado_recepcion,
          glosa: row.glosa ?? null,
          monto: row.monto_bruto,
        });
      }
    }
    return [...grouped.values()].sort((a, b) => b.boletas_count - a.boletas_count);
  }, [provisionadosBoletas.data?.data]);

  useEffect(() => {
    if (!gotoDocenteQuery) return;
    const hit = docenteLookup.data?.data?.[0];
    if (!hit) return;
    setSelectedDocenteId(hit.id);
    setGotoDocenteQuery("");
  }, [docenteLookup.data, gotoDocenteQuery]);

  async function openBoletaFile(row: { id: number; year?: number | null; month_name?: string | null }, fileType: "xml" | "pdf") {
    if (!row.year || !row.month_name) {
      push("No se pudo determinar período de la boleta.", "error");
      return;
    }
    const endpoint = `${baseUrl}/period/${row.year}/${row.month_name}/boletas/${row.id}/files/${fileType}`;
    const response = await fetch(endpoint, { headers: { "x-api-key": apiKey } });
    if (!response.ok) {
      push(`No se pudo abrir ${fileType.toUpperCase()} (${response.status}).`, "error");
      return;
    }
    const blob = await response.blob();
    const blobUrl = URL.createObjectURL(blob);
    window.open(blobUrl, "_blank", "noopener,noreferrer");
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">👤 Perfiles de docentes</h1>
      {docentes.isError && (
        <ErrorState
          title="No pudimos cargar docentes"
          description="Revisa conexión/API key y vuelve a intentar."
          onRetry={() => docentes.refetch()}
        />
      )}
      <Card>
        <CardHeader>
          <CardTitle>🔎 Buscador</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          <Input
            value={q}
            placeholder="Buscar por nombre, RUT o sede"
            onChange={(event) => {
              setQ(event.target.value);
              setPage(1);
            }}
          />
          <div className="text-sm text-muted-foreground md:col-span-2">
            Total: <strong>{docentes.data?.pagination.total ?? 0}</strong>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>🟡 Docentes con glosa "PROVISIONADO"</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 md:grid-cols-3">
            <Select
              value={provisionadosPeriod ? `${provisionadosPeriod.year}-${provisionadosPeriod.month_name}` : ""}
              onChange={(event) => setProvisionadosPeriodKey(event.target.value)}
            >
              {(periods.data || []).map((p) => (
                <option key={p.id} value={`${p.year}-${p.month_name}`}>
                  {p.month_name} {p.year}
                </option>
              ))}
            </Select>
            <div className="text-sm text-muted-foreground md:col-span-2">
              Docentes encontrados: <strong>{provisionadosDocentes.length}</strong> | Boletas con "PROVISIONADO":{" "}
              <strong>{provisionadosBoletas.data?.pagination.total ?? 0}</strong>
            </div>
          </div>
          {provisionadosBoletas.isLoading && <Skeleton className="h-28 w-full" />}
          {provisionadosBoletas.isError && (
            <ErrorState
              title="No pudimos cargar provisionados"
              description="Intenta nuevamente y revisa API key/conexión."
              onRetry={() => provisionadosBoletas.refetch()}
            />
          )}
          {!provisionadosBoletas.isLoading && !provisionadosBoletas.isError && (
            <>
              <TableWrapper>
                <Table>
                  <thead>
                    <tr>
                      <TH>Docente</TH>
                      <TH>EMPLID</TH>
                      <TH className="text-right">Boletas provisionadas</TH>
                      <TH className="text-right">Monto total</TH>
                      <TH>Acciones</TH>
                    </tr>
                  </thead>
                  <tbody>
                    {provisionadosDocentes.map((item) => (
                      <Fragment key={item.key}>
                        <tr key={item.key}>
                          <TD>{item.docente_nombre}</TD>
                          <TD>{item.emplid}</TD>
                          <TD className="text-right">{item.boletas_count}</TD>
                          <TD className="text-right">{toCurrency(item.monto_total)}</TD>
                          <TD>
                            <div className="flex gap-2">
                              <Button
                                variant="ghost"
                                onClick={() =>
                                  setExpandedProvisionadoKey((prev) => (prev === item.key ? null : item.key))
                                }
                              >
                                {expandedProvisionadoKey === item.key ? "Ocultar BH" : "Ver BH"}
                              </Button>
                              <Button
                                variant="ghost"
                                onClick={() => {
                                  setQ(item.emplid);
                                  setPage(1);
                                  setGotoDocenteQuery(item.emplid);
                                }}
                              >
                                Ir al perfil
                              </Button>
                            </div>
                          </TD>
                        </tr>
                        {expandedProvisionadoKey === item.key && (
                          <tr>
                            <TD colSpan={5}>
                              <div className="rounded-md border border-border p-2">
                                <p className="mb-2 text-xs text-muted-foreground">
                                  Boletas provisionadas de {item.docente_nombre}
                                </p>
                                <TableWrapper>
                                  <Table>
                                    <thead>
                                      <tr>
                                        <TH>ID</TH>
                                        <TH>Período</TH>
                                        <TH>Estado</TH>
                                        <TH>Glosa</TH>
                                        <TH className="text-right">Monto</TH>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {item.boletas.map((b) => (
                                        <tr key={`${item.key}-${b.id}`}>
                                          <TD>{b.id}</TD>
                                          <TD>{b.month_name && b.year ? `${b.month_name} ${b.year}` : "-"}</TD>
                                          <TD>{b.estado || "-"}</TD>
                                          <TD>{b.glosa || "-"}</TD>
                                          <TD className="text-right">{toCurrency(b.monto)}</TD>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </Table>
                                </TableWrapper>
                              </div>
                            </TD>
                          </tr>
                        )}
                      </Fragment>
                    ))}
                  </tbody>
                </Table>
              </TableWrapper>
              {provisionadosDocentes.length === 0 && (
                <EmptyState
                  title="Sin docentes provisionados"
                  description='No encontramos boletas con la palabra "PROVISIONADO" en la glosa para el período seleccionado.'
                />
              )}
              {(provisionadosBoletas.data?.pagination.total || 0) > 200 && (
                <p className="text-xs text-amber-700">
                  Mostrando primeros 200 registros de boletas provisionadas. Si necesitas el total completo, conviene
                  habilitar paginación/endpoint dedicado.
                </p>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>📋 Listado</CardTitle>
          </CardHeader>
          <CardContent>
            <TableWrapper>
              <Table>
                <thead>
                  <tr>
                    <TH>Nombre</TH>
                    <TH>RUT</TH>
                    <TH>Sede</TH>
                    <TH className="text-right">Boletas</TH>
                  </tr>
                </thead>
                <tbody>
                  {docentes.isLoading &&
                    Array.from({ length: 8 }).map((_, idx) => (
                      <tr key={`doc-s-${idx}`}>
                        <TD><Skeleton className="h-4 w-32" /></TD>
                        <TD><Skeleton className="h-4 w-20" /></TD>
                        <TD><Skeleton className="h-4 w-16" /></TD>
                        <TD className="text-right"><Skeleton className="ml-auto h-4 w-10" /></TD>
                      </tr>
                    ))}
                  {!docentes.isLoading && docentes.data?.data.map((item) => (
                    <tr
                      key={item.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => setSelectedDocenteId(item.id)}
                    >
                      <TD>{item.nombre_completo}</TD>
                      <TD>{item.rut}</TD>
                      <TD>{item.sede || "-"}</TD>
                      <TD className="text-right">{item.boletas_count}</TD>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </TableWrapper>
            {!docentes.isLoading && (docentes.data?.data.length || 0) === 0 && (
              <EmptyState
                title="Sin docentes para mostrar"
                description="No encontramos docentes con el filtro actual."
              />
            )}
            <Pagination page={page} totalPages={totalPages} onPrev={() => setPage((p) => p - 1)} onNext={() => setPage((p) => p + 1)} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>🪪 Perfil docente</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {!selectedDocenteId && <EmptyState title="Selecciona un docente" description="Haz clic en una fila del listado para ver su perfil." />}
            {profile.isLoading && selectedDocenteId && <Skeleton className="h-56 w-full" />}
            {profile.isError && selectedDocenteId && (
              <ErrorState
                title="No pudimos cargar el perfil"
                description="Intenta nuevamente."
                onRetry={() => profile.refetch()}
              />
            )}
            {profile.data && (
              <>
                <div className="rounded-md border border-border p-3">
                  <p className="text-base font-semibold">{profile.data.docente.nombre_completo}</p>
                  <p className="text-sm text-muted-foreground">{profile.data.docente.rut}</p>
                  <p className="text-sm text-muted-foreground">Sede: {profile.data.docente.sede || "-"}</p>
                  <p className="text-sm text-muted-foreground">Email: {profile.data.docente.email_personal || "-"}</p>
                  <p className="text-sm text-muted-foreground">Email DP: {profile.data.docente.email_dp || "-"}</p>
                  <p className="mt-2 text-sm">Boletas: <strong>{profile.data.docente.boletas_count}</strong></p>
                  <p className="text-sm">Monto total: <strong>{toCurrency(profile.data.docente.monto_total)}</strong></p>
                </div>
                <div className="grid gap-2 md:grid-cols-3">
                  <Select
                    value={selectedPeriodKey}
                    onChange={(event) => {
                      setSelectedPeriodKey(event.target.value);
                      setBoletasPage(1);
                    }}
                  >
                    <option value="">Todos los períodos</option>
                    {(periods.data || []).map((p) => (
                      <option key={p.id} value={`${p.year}-${p.month_name}`}>
                        {p.month_name} {p.year}
                      </option>
                    ))}
                  </Select>
                  <Select
                    value={estado}
                    onChange={(event) => {
                      setEstado(event.target.value);
                      setBoletasPage(1);
                    }}
                  >
                    <option value="">Todos los estados</option>
                    <option value="RECIBIDO">RECIBIDO</option>
                    <option value="RECIBIDO CON ERROR">RECIBIDO CON ERROR</option>
                    <option value="NO RECIBIDO">NO RECIBIDO</option>
                  </Select>
                  <div className="text-sm text-muted-foreground">
                    Total boletas: <strong>{boletas.data?.pagination.total ?? 0}</strong>
                  </div>
                </div>
                {metrics.data && (
                  <div className="grid gap-2 md:grid-cols-3">
                    <div className="rounded-md border border-emerald-500/40 bg-emerald-500/5 p-2 text-xs">✅ Recibidas: <strong>{metrics.data.metrics.recibidas}</strong></div>
                    <div className="rounded-md border border-amber-500/40 bg-amber-500/5 p-2 text-xs">⚠️ Con error: <strong>{metrics.data.metrics.con_error}</strong></div>
                    <div className="rounded-md border border-blue-500/40 bg-blue-500/5 p-2 text-xs">📄 Sin XML: <strong>{metrics.data.metrics.sin_xml}</strong></div>
                  </div>
                )}
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
                        <tr key={p.period_id}>
                          <TD>{p.month_name} {p.year}</TD>
                          <TD className="text-right">{p.boletas}</TD>
                          <TD className="text-right">{toCurrency(p.monto_total)}</TD>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </TableWrapper>
                <div className="rounded-md border border-border p-3">
                  <p className="mb-2 text-sm font-medium">Boletas asociadas</p>
                  <TableWrapper>
                    <Table>
                      <thead>
                        <tr>
                          <TH>ID</TH>
                          <TH>Período</TH>
                          <TH>Estado</TH>
                          <TH className="text-right">Monto</TH>
                          <TH>XML</TH>
                          <TH>PDF</TH>
                        </tr>
                      </thead>
                      <tbody>
                        {boletas.isLoading &&
                          Array.from({ length: 4 }).map((_, idx) => (
                            <tr key={`b-s-${idx}`}>
                              <TD><Skeleton className="h-4 w-8" /></TD>
                              <TD><Skeleton className="h-4 w-20" /></TD>
                              <TD><Skeleton className="h-4 w-16" /></TD>
                              <TD className="text-right"><Skeleton className="ml-auto h-4 w-16" /></TD>
                              <TD><Skeleton className="h-4 w-12" /></TD>
                              <TD><Skeleton className="h-4 w-12" /></TD>
                            </tr>
                          ))}
                        {!boletas.isLoading && (boletas.data?.data || []).map((row) => (
                          <tr key={row.id}>
                            <TD>{row.id}</TD>
                            <TD>{row.month_name && row.year ? `${row.month_name} ${row.year}` : "-"}</TD>
                            <TD>{row.estado_recepcion || "-"}</TD>
                            <TD className="text-right">{toCurrency(row.monto_bruto)}</TD>
                            <TD>
                              {row.archivo_xml ? (
                                <Button variant="ghost" onClick={() => void openBoletaFile(row, "xml")}>Ver XML</Button>
                              ) : "-"}
                            </TD>
                            <TD>
                              {row.archivo_xml ? (
                                <Button variant="ghost" onClick={() => void openBoletaFile(row, "pdf")}>Ver PDF</Button>
                              ) : "-"}
                            </TD>
                          </tr>
                        ))}
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
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

