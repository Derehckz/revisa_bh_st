export type Period = {
  id: number;
  year: number;
  month_num: number;
  month_name: string;
  status: string;
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

export type RecommendationKind = "run" | "wait" | "fix" | "complete" | "review" | "outbox";

export type PeriodRecommendation = {
  kind: RecommendationKind;
  stage_num: number | null;
  title: string;
  message: string;
  action_label?: string;
};

export type PeriodOverviewResponse = {
  period: { year: number; month: string };
  kpis: PeriodKpis;
  stages: PeriodOverviewStage[];
  running_job: { id: string; stage_num?: number; type?: string } | null;
  outbox_stats: Record<string, number>;
  recommendation?: PeriodRecommendation;
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
