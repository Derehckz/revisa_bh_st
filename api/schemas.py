"""Contratos Pydantic para respuestas de la API."""
from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict


class PeriodItem(BaseModel):
    id: int
    year: int
    month_num: int
    month_name: str
    status: str


class Pagination(BaseModel):
    total: int
    limit: int
    offset: int
    returned: int


class PeriodRef(BaseModel):
    year: int
    month: str
    period_id: int


class PeriodSummaryMetrics(BaseModel):
    total_boletas: int
    total_xml: int
    xml_coverage_pct: float
    total_emails: int
    email_coverage_pct: float
    recibidos: int
    no_recibidos: int
    recibidos_con_error: int
    emails_enviados: int
    emails_error: int


class DataFreshness(BaseModel):
    """E11: frescura Excel↔PG para pantallas de consulta."""

    status: str  # ok | degraded | unknown
    message: str = ""
    details: dict | None = None


class PeriodSummaryResponse(BaseModel):
    period: PeriodItem
    metrics: PeriodSummaryMetrics
    data_freshness: DataFreshness | None = None


class BoletaListItem(BaseModel):
    id: int
    boleta_key: str | None
    emplid: str | None
    docente_nombre: str | None = None
    sede: str | None = None
    year: int | None = None
    month_name: str | None = None
    estado_recepcion: str | None
    observaciones_recepcion: str | None
    glosa: str | None = None
    monto_bruto: float | None
    archivo_xml: str | None


class BoletaListResponse(BaseModel):
    period: PeriodRef
    pagination: Pagination
    filters: dict
    data: list[BoletaListItem]


class BoletaSearchResponse(BaseModel):
    period: PeriodRef
    pagination: Pagination
    filters: dict
    data: list[BoletaListItem]


class BoletaXmlDetail(BaseModel):
    rut_emisor: str | None
    rut_receptor: str | None
    numero_boleta: str | None
    fecha_boleta: str | None
    total_honorarios: float | None
    liquido_honorarios: float | None
    impuesto_honorarios: float | None
    porcentaje_impuesto: float | None
    descripcion_linea: str | None
    observaciones_xml: str | None


class EmailItem(BaseModel):
    id: int
    tipo_envio: str
    to_email: str
    cc_email: str | None
    subject: str | None
    estado: str
    error_detalle: str | None
    periodo_label: str | None = None
    sent_at: str | None


class BoletaDetailResponse(BaseModel):
    boleta: BoletaListItem
    xml_data: BoletaXmlDetail | None
    emails_period_sample: list[EmailItem]


class PeriodXmlItem(BaseModel):
    xml_id: int
    boleta_id: int
    emplid: str | None
    numero_boleta: str | None
    rut_emisor: str | None
    rut_receptor: str | None
    total_honorarios: float | None
    observaciones_xml: str | None


class PeriodXmlResponse(BaseModel):
    period: PeriodRef
    pagination: Pagination
    data: list[PeriodXmlItem]


class PeriodEmailsResponse(BaseModel):
    period: PeriodRef
    pagination: Pagination
    filters: dict
    data: list[EmailItem]


class RunItem(BaseModel):
    id: int
    run_id: str
    period_label: str | None
    triggered_by: str | None
    mode: str
    status: str
    started_at: str | None
    finished_at: str | None


class RunsResponse(BaseModel):
    pagination: Pagination
    data: list[RunItem]


class StageItem(BaseModel):
    id: int
    stage_num: int
    stage_name: str
    correlation_id: str | None
    status: str
    rows_read: int | None
    rows_ok: int | None
    rows_error: int | None
    message: str | None
    started_at: str | None
    finished_at: str | None


class RunStagesResponse(BaseModel):
    run: dict
    stages: list[StageItem]


class YearPeriodStats(BaseModel):
    period_id: int
    month_num: int
    month_name: str
    boletas: int
    xml: int
    emails: int
    xml_coverage_pct: float
    email_coverage_pct: float


class YearStatsResponse(BaseModel):
    year: int
    totals: dict
    periods: list[YearPeriodStats]


class PeriodSedeInsight(BaseModel):
    sede: str
    boletas: int
    monto_total: float


class PeriodDocenteInsight(BaseModel):
    docente: str
    boletas: int
    monto_total: float


class PeriodInsightsKpis(BaseModel):
    monto_total: float
    monto_promedio: float
    docentes_unicos: int
    boletas_con_xml: int
    boletas_sin_xml: int


class PeriodInsightsResponse(BaseModel):
    period: PeriodRef
    kpis: PeriodInsightsKpis
    by_sede: list[PeriodSedeInsight]
    top_docentes: list[PeriodDocenteInsight]


class DocenteItem(BaseModel):
    id: int
    rut: str
    nombre_completo: str
    sede: str | None
    email_personal: str | None
    email_dp: str | None
    boletas_count: int
    monto_total: float


class DocenteListResponse(BaseModel):
    pagination: Pagination
    filters: dict
    data: list[DocenteItem]


class DocentePeriodStat(BaseModel):
    period_id: int
    year: int
    month_num: int
    month_name: str
    boletas: int
    monto_total: float


class DocenteEmailSummary(BaseModel):
    total: int
    enviados: int
    error: int
    pendientes: int
    ultimo_envio: str | None
    tipos: dict[str, int]


class DocenteProfileResponse(BaseModel):
    docente: DocenteItem
    boletas: list[BoletaListItem]
    period_stats: list[DocentePeriodStat]
    email_summary: DocenteEmailSummary
    recent_emails: list[EmailItem]


class DocenteMetricsResponse(BaseModel):
    docente: DocenteItem
    metrics: dict


class DocenteEmailsResponse(BaseModel):
    docente: DocenteItem
    pagination: Pagination
    filters: dict
    data: list[EmailItem]


class StageStartRequest(BaseModel):
    year: int
    month: str
    # Paso 0
    maestro_file: str | None = None
    bd_file: str | None = None
    output_file: str | None = None
    csv_nuevos_docentes: str | None = None
    # Común / varios pasos
    strict: bool | None = None
    send: bool | None = None
    force_resend: bool | None = None
    dry_run: bool | None = None
    # Paso 2
    fecha_inicio: str | None = None
    fecha_fin: str | None = None
    # Paso 7
    fecha_pago: str | None = None
    # Paso 8
    mover: bool | None = None
    map_csv: str | None = None
    no_interactive: bool | None = None
    # Paso 9
    agrupar_archivos: bool | None = None
    # Paso 10
    institucion: str | None = None
    force: bool | None = None
