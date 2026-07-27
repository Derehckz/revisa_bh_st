export type Period = {
  id: number;
  year: number;
  month_num: number;
  month_name: string;
  status: string;
};

export type DataFreshness = {
  status: "ok" | "degraded" | "unknown" | string;
  message: string;
  details?: Record<string, unknown> | null;
};

export type PeriodSummary = {
  period: {
    id: number;
    year: number;
    month_num: number;
    month_name: string;
    status: string;
  };
  metrics: {
    total_boletas: number;
    total_xml: number;
    xml_coverage_pct: number;
    total_emails: number;
    email_coverage_pct: number;
    recibidos: number;
    no_recibidos: number;
    recibidos_con_error: number;
    emails_enviados: number;
    emails_error: number;
  };
  data_freshness?: DataFreshness | null;
};

export type BoletaItem = {
  id: number;
  boleta_key: string | null;
  emplid: string | null;
  docente_nombre: string | null;
  sede: string | null;
  year?: number | null;
  month_name?: string | null;
  estado_recepcion: string | null;
  observaciones_recepcion: string | null;
  glosa?: string | null;
  monto_bruto: number | null;
  archivo_xml: string | null;
};

export type PaginatedBoletas = {
  pagination: {
    total: number;
    limit: number;
    offset: number;
    returned: number;
  };
  data: BoletaItem[];
};

export type RunsResponse = {
  pagination: {
    total: number;
    limit: number;
    offset: number;
    returned: number;
  };
  data: Array<{
    id: number;
    run_id: string;
    period_label: string | null;
    status: string;
    started_at: string | null;
    finished_at: string | null;
  }>;
};

export type RunStagesResponse = {
  run: {
    id: number;
    run_id: string;
    status: string;
    period_label: string | null;
  };
  stages: Array<{
    id: number;
    stage_num: number;
    stage_name: string;
    correlation_id: string | null;
    status: string;
    rows_read: number | null;
    rows_ok: number | null;
    rows_error: number | null;
    message: string | null;
    started_at: string | null;
    finished_at: string | null;
  }>;
};

export type HealthResponse = {
  status: string;
  ui?: string | null;
};

export type YearStatsResponse = {
  year: number;
  totals: {
    boletas: number;
    xml: number;
    emails: number;
    xml_coverage_pct: number;
    email_coverage_pct: number;
  };
  periods: Array<{
    period_id: number;
    month_num: number;
    month_name: string;
    boletas: number;
    xml: number;
    emails: number;
    xml_coverage_pct: number;
    email_coverage_pct: number;
  }>;
};

export type BoletaDetailResponse = {
  boleta: BoletaItem;
  xml_data: {
    rut_emisor: string | null;
    rut_receptor: string | null;
    numero_boleta: string | null;
    fecha_boleta: string | null;
    total_honorarios: number | null;
    liquido_honorarios: number | null;
    impuesto_honorarios: number | null;
    porcentaje_impuesto: number | null;
    descripcion_linea: string | null;
    observaciones_xml: string | null;
  } | null;
  emails_period_sample: Array<{
    id: number;
    tipo_envio: string;
    to_email: string;
    cc_email: string | null;
    subject: string | null;
    estado: string;
    error_detalle: string | null;
    sent_at: string | null;
  }>;
};

export type PeriodInsightsResponse = {
  period: {
    year: number;
    month: string;
    period_id: number;
  };
  kpis: {
    monto_total: number;
    monto_promedio: number;
    docentes_unicos: number;
    boletas_con_xml: number;
    boletas_sin_xml: number;
  };
  by_sede: Array<{
    sede: string;
    boletas: number;
    monto_total: number;
  }>;
  top_docentes: Array<{
    docente: string;
    boletas: number;
    monto_total: number;
  }>;
};

export type DocenteItem = {
  id: number;
  rut: string;
  nombre_completo: string;
  sede: string | null;
  email_personal: string | null;
  email_dp: string | null;
  boletas_count: number;
  monto_total: number;
};

export type DocenteListResponse = {
  pagination: {
    total: number;
    limit: number;
    offset: number;
    returned: number;
  };
  filters: {
    q?: string | null;
  };
  data: DocenteItem[];
};

export type DocenteProfileResponse = {
  docente: DocenteItem;
  boletas: BoletaItem[];
  period_stats: Array<{
    period_id: number;
    year: number;
    month_num: number;
    month_name: string;
    boletas: number;
    monto_total: number;
  }>;
  email_summary: {
    total: number;
    enviados: number;
    error: number;
    pendientes: number;
    ultimo_envio: string | null;
    tipos: Record<string, number>;
  };
  recent_emails: Array<{
    id: number;
    tipo_envio: string;
    to_email: string;
    cc_email: string | null;
    subject: string | null;
    estado: string;
    error_detalle: string | null;
    periodo_label: string | null;
    sent_at: string | null;
  }>;
};

export type DocenteMetricsResponse = {
  docente: DocenteItem;
  metrics: {
    total_boletas: number;
    recibidas: number;
    con_error: number;
    sin_xml: number;
    monto_total: number;
    monto_promedio: number;
  };
};

export type DocenteEmailsResponse = {
  docente: DocenteItem;
  pagination: {
    total: number;
    limit: number;
    offset: number;
    returned: number;
  };
  filters: {
    tipo?: string | null;
    estado?: string | null;
  };
  data: Array<{
    id: number;
    tipo_envio: string;
    to_email: string;
    cc_email: string | null;
    subject: string | null;
    estado: string;
    error_detalle: string | null;
    periodo_label: string | null;
    sent_at: string | null;
  }>;
};

export type PipelineStageMeta = {
  stage_num: number;
  file: string;
  description: string;
  accepts: "none" | "year_month" | "mes_ano";
  optional_in_full_run: boolean;
  enabled_for_api: boolean;
  is_email_stage?: boolean;
};

export type SelectOption = {
  value: string;
  label: string;
};

export type StageGuideStep = {
  id: string;
  title: string;
  detail: string;
};

export type StageGuide = {
  title: string;
  summary: string;
  steps: StageGuideStep[];
};

export type InteractiveChoices = {
  month_dir: string;
  month_dir_label: string;
  solicitud_file?: string | null;
  solicitud_sheets?: string[];
  solicitud_sheet_auto?: string;
  excel_files_in_month?: string[];
  map_csv_files?: SelectOption[];
  maestro_files?: string[];
  bd_candidates?: string[];
  institucion_options?: SelectOption[];
};

export type StageParamField = {
  name: string;
  type: string;
  label: string;
  cli?: string | null;
  required?: boolean;
  default?: boolean | string | null;
  help?: string;
  options?: SelectOption[];
};

export type StagesListResponse = {
  stages: PipelineStageMeta[];
};

export type StageUiStatus = "READY" | "BLOCKED" | "RUNNING" | "OK" | "ERROR";

export type PrerequisiteItem = {
  id: string;
  label: string;
  ok: boolean;
  blocking?: boolean;
  message?: string;
};

export type StageWarning = {
  code: string;
  message: string;
};

export type EstimatedOutput = {
  id: string;
  label: string;
};

export type PeriodKpis = {
  year: number | string;
  month: string;
  month_dir: string;
  solicitud_exists: boolean;
  total_rows: number;
  recibidos: number;
  no_recibidos: number;
  xml_files_in_month: number;
  pdf_files_in_month: number;
  read_error?: string;
};

export type ExcelAvanceMailCounts = {
  enviado: number;
  omitido: number;
  error: number;
  pendiente: number;
  otro: number;
};

export type ExcelAvanceRow = {
  row: number;
  emplid?: string;
  rut_sin_dv?: string;
  name: string;
  sede: string;
  location?: string;
  email: string;
  email_dp?: string;
  rut_razon?: string;
  nombre_razon?: string;
  direccion_razon?: string;
  glosa?: string;
  estado_recepcion: string;
  correo_enviado: string;
  correo_clase: string;
  recordatorios: string;
  observaciones?: string;
  observacion_descartes?: string;
  archivo_xml: string;
  archivo_xml_usado?: string;
  observaciones_xml: string;
  xml_clase: string;
  numero_boleta_xml?: string;
  fecha_boleta_xml?: string;
  rut_emisor_xml?: string;
  rut_receptor_xml?: string;
  nombre_receptor_xml?: string;
  total_honorarios_xml?: string;
  liquido_honorarios_xml?: string;
  impuesto_honorarios_xml?: string;
  descripcion_xml?: string;
  correo_recepcion_enviado?: string;
  monto: string;
};

export type ExcelAvanceResponse = {
  year: number | string;
  month: string;
  month_dir: string;
  solicitud_path: string;
  solicitud_exists: boolean;
  sheets: string[];
  solicitud_sheet: string | null;
  total_rows: number;
  recepcion: {
    recibido: number;
    recibido_con_error: number;
    no_recibido: number;
    pendiente: number;
    otro: number;
  };
  correo_solicitud: ExcelAvanceMailCounts;
  recordatorios: { con_recordatorio: number; total_envios: number };
  xml_extract: { ok: number; observacion: number; pendiente: number; con_archivo: number };
  archivos_mes: { xml: number; pdf: number };
  pagos: ExcelAvanceMailCounts & {
    sheet_exists: boolean;
    total_rows: number;
    read_error?: string;
  };
  rows: ExcelAvanceRow[];
  rows_truncated: boolean;
  read_error?: string | null;
  mtime?: string | null;
};

export type Step0OptionsResponse = {
  year: number;
  month: string;
  month_dir: string;
  maestro_files: string[];
  bd_candidates: string[];
  stage_num?: number;
  prerequisites?: { ok: boolean; message: string; failed_ids?: string[] };
  checklist?: PrerequisiteItem[];
  warnings?: StageWarning[];
  estimated_outputs?: EstimatedOutput[];
  ui_status?: StageUiStatus;
  period_kpis?: PeriodKpis;
  running_job?: { id: string; stage_num?: number } | null;
  enabled_for_api?: boolean;
  params_schema?: StageParamField[];
  is_email_stage?: boolean;
  guide?: StageGuide;
  choices?: InteractiveChoices;
  outlook_health?: OutlookHealth | null;
};

export type OutlookHealth = {
  ready: boolean;
  process_running: boolean;
  exe_found: boolean;
  com_ok?: boolean | null;
  com_error?: string | null;
  can_auto_launch: boolean;
  message: string;
  required_for_stages?: number[];
};

export type PeriodOverviewStage = PipelineStageMeta & {
  ui_status: StageUiStatus;
  prerequisites: { ok: boolean; message: string; failed_ids?: string[] };
  checklist: PrerequisiteItem[];
  warnings: StageWarning[];
  estimated_outputs: EstimatedOutput[];
  last_job: {
    id: string;
    status: string;
    created_at?: string;
    finished_at?: string | null;
    source?: "api" | "filesystem";
    label?: string;
    log_path?: string | null;
  } | null;
};

export type RecommendationKind =
  | "run"
  | "wait"
  | "fix"
  | "complete"
  | "review"
  | "outbox"
  | "reminders";

export type PeriodRecommendation = {
  kind: RecommendationKind;
  stage_num: number | null;
  title: string;
  message: string;
  action_label?: string;
  params?: { reminders_only?: boolean };
};

export type SyncStatus = {
  status: "ok" | "degraded" | "unknown";
  message: string;
  details?: Record<string, unknown>;
};

export type PeriodOverviewResponse = {
  period: { year: number; month: string; status?: string | null };
  kpis: PeriodKpis;
  stages: PeriodOverviewStage[];
  running_job: { id: string; stage_num?: number; type?: string } | null;
  outbox_stats: Record<string, number>;
  sync_status?: SyncStatus;
  recommendation?: PeriodRecommendation;
};

export type InboxGapItem = {
  rut: string;
  folio: string;
  name: string;
  email: string;
  monto_solicitud?: number | string | null;
  received_time: string;
  subject: string;
  sender: string;
  attachments: string[];
  missing_pdf: boolean;
  missing_xml: boolean;
  suggested_action: string;
};

export type InboxGapsResponse = {
  ok: boolean;
  error?: string;
  message?: string;
  year: number;
  month: string;
  fecha_inicio: string;
  fecha_fin: string;
  carpeta?: string;
  no_recibidos: number;
  emails_scanned: number;
  gaps: InboxGapItem[];
  gap_count: number;
};

export type JobArtifact = {
  id: string;
  label: string;
  path?: string;
  filename: string;
  kind: string;
  exists: boolean;
  size_bytes?: number;
  download_url: string;
};

export type OutboxRow = {
  id: number;
  stage: string;
  item_key: string;
  status: string;
  created_at: string;
  updated_at: string | null;
  attempts: number;
  last_error: string | null;
  payload: string | null;
};

export type OperationJob = {
  id: string;
  stage_num?: number;
  type: string;
  status: "running" | "success" | "failed" | "unknown";
  year: number;
  month: string;
  maestro_file?: string;
  bd_file?: string;
  output_file?: string;
  params?: Record<string, unknown>;
  cmd?: string[];
  created_at: string;
  log_path: string;
  pid: number | null;
  return_code: number | null;
  finished_at: string | null;
  source?: "api" | "filesystem";
  label?: string;
};

export type ExecutionHistoryEntry = {
  id: string;
  source: "api" | "filesystem";
  stage_num: number;
  status: string;
  year: number;
  month: string;
  type: string;
  created_at: string;
  finished_at: string | null;
  log_path: string | null;
  label: string;
  pid: number | null;
  return_code: number | null;
  artifact_path?: string;
};

export type ExecutionHistoryResponse = {
  year: number;
  from_month: string;
  to_month: string;
  total: number;
  returned: number;
  by_month: Array<{ period: string; count: number }>;
  data: ExecutionHistoryEntry[];
};
