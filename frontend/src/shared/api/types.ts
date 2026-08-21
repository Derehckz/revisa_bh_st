export type Period = {
  id: number;
  year: number;
  month_num: number;
  month_name: string;
  status: string;
  closed_at?: string | null;
  closed_by?: string | null;
  informe_frozen_at?: string | null;
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
  has_xml_file?: boolean | null;
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
  capabilities_version?: number | null;
  capabilities?: Record<string, boolean> | null;
  read_from_db?: boolean | null;
  started_at?: string | null;
};

export type YearStatsResponse = {
  year: number;
  totals: {
    boletas: number;
    xml: number;
    emails: number;
    monto_total?: number;
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
    monto_total?: number;
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
  activo?: string | null;
  boletas_count: number;
  monto_total: number;
};

export type DocenteUpsertPayload = {
  rut: string;
  rut_sin_dv?: string | null;
  nombre_completo: string;
  email_personal?: string | null;
  email_dp?: string | null;
  telefono?: string | null;
  direccion?: string | null;
  sede?: string | null;
  activo?: string | null;
};

export type DirectorPrograma = {
  id: number;
  nombre: string | null;
  email: string;
  activo?: string | null;
  sedes: string[];
};

export type DirectorListResponse = {
  data: DirectorPrograma[];
};

export type DirectorUpsertPayload = {
  nombre?: string | null;
  email: string;
  sedes: string[];
  activo?: string | null;
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

export type RecepcionAudience = "ok" | "error" | "reenvio";
export type ReenvioTipo = "recordatorio" | "boleta_incorrecta";

export type RecepcionPreviewCandidate = {
  row: number;
  index?: number;
  audience: RecepcionAudience;
  reenvio_tipo?: ReenvioTipo;
  kind: "ok" | "problema";
  name: string;
  email: string;
  emplid: string;
  estado_recepcion: string;
  numero_boleta: string;
  monto: string;
  problema: string;
  already_sent: boolean;
  correo_recepcion?: string;
};

export type RecepcionPreview = {
  candidates: RecepcionPreviewCandidate[];
  counts: {
    ok?: number;
    error?: number;
    reenvio?: number;
    recordatorio?: number;
    boleta_incorrecta?: number;
    ok_pending?: number;
    error_pending?: number;
    reenvio_pending?: number;
    recordatorio_pending?: number;
    boleta_incorrecta_pending?: number;
    already_sent?: number;
  };
  error?: string;
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
  recepcion_preview?: RecepcionPreview;
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
  /** Fila de arrastre (GLOSA con PROVISIONADO), aparte de la boleta normal del mes. */
  provisionado?: boolean;
  estado_recepcion: string;
  /** Si el Excel dice RECIBIDO pero la glosa XML no cuadra, refleja RECIBIDO CON ERROR. */
  estado_recepcion_efectivo?: string;
  glosa_xml_coincide?: boolean;
  /** exacta | prefijo_omitido | distinta */
  glosa_match_mode?: string;
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
  arrastre_preview?: ArrastrePreview;
};

export type ArrastrePreviewRow = {
  emplid: string;
  name: string;
  institucion: string;
  location?: number | string | null;
  rut_razon: string;
  monto: number;
  glosa: string;
  email: string;
};

export type ArrastrePreview = {
  year: number;
  month: string;
  lookback: Array<{ month: string; year: number; closed: boolean; has_solicitud: boolean }>;
  previous_closed: boolean;
  count: number;
  total_monto: number;
  rows: ArrastrePreviewRow[];
  message: string;
  error?: string;
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

export type PeriodVerifyResponse = {
  ok: boolean;
  year: number;
  month: string;
  solicitud: string;
  sheet: string;
  migration?: { ok: boolean; message: string } | null;
  import_stats: Record<string, unknown>;
  projection: { projected: number; failed: number };
  compare: { rows_compared: number; differences: number; alignment_pct: number };
  period_check?: {
    ok: boolean;
    total_boletas?: number;
    message?: string;
  };
  consistency?: {
    ok: boolean;
    critical_count: number;
    warning_count: number;
    findings: Array<{ name: string; severity: string; count: number }>;
  } | null;
  snapshots?: Record<string, unknown> | null;
};

export type PeriodBackfillResponse = {
  ok: boolean;
  year: number;
  months: string[];
  ok_count: number;
  total: number;
  migration?: { ok: boolean; message: string } | null;
  results: Array<{
    month: string;
    ok: boolean;
    error?: string;
    verify?: PeriodVerifyResponse;
    snapshots?: Record<string, unknown>;
  }>;
};

export type DbMigrateResponse = {
  ok: boolean;
  message: string;
};

export type DbConsistencyResponse = {
  ok: boolean;
  total_boletas: number;
  total_xml: number;
  total_emails: number;
  email_coverage_pct: number;
  critical_count: number;
  warning_count: number;
  findings: Array<{ name: string; severity: string; count: number }>;
  samples?: Record<string, string[]>;
};

export type ServerRestartResponse = {
  ok: boolean;
  message: string;
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

export type FinalReportRow = {
  rut: string;
  nombre_docente: string;
  reg_empleo: string;
  location: string;
  ins: string;
  nombre_sede: string;
  numero_boleta: string;
  tipo_doc: string;
  tipo_pago: string;
  fecha_emision: string;
  monto_bruto: number | string;
};

export type FinalReportResponse = {
  year: number;
  month: string;
  exists: boolean;
  frozen?: boolean;
  frozen_at?: string | null;
  frozen_by?: string | null;
  generated_at: string | null;
  generated_at_source: string | null;
  sheet_name: string | null;
  source_file: string | null;
  source?: string | null;
  total_rows: number;
  total_monto: number;
  rows: FinalReportRow[];
  read_error?: string | null;
  period_status?: string | null;
  sha256?: string | null;
};

export type PagosReportRow = Record<string, string | number | null | undefined>;

export type PagosReportItem = {
  rut: string;
  rut_digits?: string;
  nombre: string;
  boleta: string;
  empresa: string;
  sede: string;
  mail: string;
  banco: string;
  tipo_cuenta: string;
  nro_cuenta: string;
  descripcion: string;
  estado_boleta: string;
  fecha_emision: string;
  tipo_documento: string;
  bruto: number;
  retencion: number;
  liquido: number;
  retencion_pct: number | null;
  mail_status: "enviado" | "pendiente" | "error" | "omitido" | "otro" | string;
  mail_status_label: string;
  mail_raw: string;
  docente_id?: number | null;
  docente_nombre?: string;
  raw?: PagosReportRow;
};

export type PagosReportResponse = {
  year: number;
  month: string;
  exists: boolean;
  frozen?: boolean;
  frozen_at?: string | null;
  generated_at?: string | null;
  source?: string | null;
  source_kind?: string | null;
  total_rows: number;
  rows: PagosReportRow[];
  items?: PagosReportItem[];
  counts?: {
    enviado: number;
    pendiente: number;
    error: number;
    omitido: number;
    otro: number;
  };
  totals?: {
    bruto: number;
    retencion: number;
    liquido: number;
    rows: number;
  };
  read_error?: string | null;
  period_status?: string | null;
};

export type MonthlyChecklistItem = {
  id: string;
  label: string;
  status: "ok" | "warn" | "block" | string;
  blocking: boolean;
  message?: string;
};

export type MonthlyChecklistResponse = {
  year: number;
  month: string;
  closed: boolean;
  closed_at?: string | null;
  closed_by?: string | null;
  informe_frozen_at?: string | null;
  contabilidad_status?: string | null;
  contabilidad_validated_at?: string | null;
  contabilidad_validated_by?: string | null;
  contabilidad_notes?: string | null;
  can_close: boolean;
  blocking_count: number;
  warn_count: number;
  items: MonthlyChecklistItem[];
};

export type AuditEvent = {
  id: number;
  ts: string | null;
  operator: string | null;
  action: string;
  period_year: number | null;
  period_month: string | null;
  entity: string | null;
  entity_id: string | null;
  detail: Record<string, unknown>;
};

export type MaestroValidationResponse = {
  ok: boolean;
  path?: string;
  filename?: string;
  row_count: number;
  missing_columns: string[];
  errors: string[];
  warnings: string[];
  empty_emplid?: number;
  zero_monto?: number;
};

export type DbBackupItem = {
  filename: string;
  path: string;
  size_bytes: number;
  mtime: number;
};

export type PeriodSetupItem = {
  id: string;
  label: string;
  ok: boolean;
  blocking: boolean;
  message?: string;
  kind?: "maestro" | "bd" | "adjunto" | null;
  files?: string[];
  path?: string;
  outlook?: Record<string, unknown>;
};

export type PeriodSetupResponse = {
  year: number;
  month: string;
  month_num: number;
  month_dir: string;
  items: PeriodSetupItem[];
  ready_for_step0: boolean;
  setup_complete: boolean;
  solicitud_exists: boolean;
  needs_setup_panel: boolean;
};

export type MissingMonthsResponse = {
  year: number;
  missing: { month_num: number; month_name: string }[];
  existing_count: number;
};

export type CreatePeriodResponse = {
  ok: boolean;
  created: boolean;
  period: Period;
  month_dir: string;
  message: string;
};

export type PeriodUploadResponse = {
  ok: boolean;
  kind: string;
  path: string;
  filename: string;
  size_bytes: number;
  message: string;
  setup: PeriodSetupResponse;
  pagos_import?: PagosImportResult;
};

export type PagosImportSampleRow = {
  id: string;
  nombre: string;
  sede: string;
  mail: string;
  liquido: number | string | null;
  cuenta: string;
};

export type PagosCruzadoRow = {
  rut: string;
  boleta: string;
  nombre?: string;
};

export type PagosCruzadoMismatch = {
  rut: string;
  boleta: string;
  field: string;
  expected: number | number[] | null;
  got: number | number[] | null;
  diff?: number | null;
  source?: string;
};

export type PagosCruzadoWarning = {
  rut?: string;
  boleta?: string;
  field?: string;
  message: string;
};

export type PagosCruzadoResult = {
  ok: boolean;
  message?: string;
  matched: number;
  informe_rows?: number;
  pagos_rows?: number;
  only_in_informe: PagosCruzadoRow[];
  only_in_pagos: PagosCruzadoRow[];
  amount_mismatches: PagosCruzadoMismatch[];
  pct_mismatches: PagosCruzadoMismatch[];
  warnings: PagosCruzadoWarning[];
  totals?: {
    informe_bruto?: number;
    pagos_bruto?: number;
    bruto_diff?: number;
    informe_liquido?: number;
    pagos_liquido?: number;
    liquido_diff?: number;
    informe_count?: number;
    pagos_count?: number;
    count_diff?: number;
  };
  errors_count: number;
  warnings_count: number;
};

export type PagosImportResult = {
  ok: boolean;
  year: number;
  month: string;
  source?: string;
  solicitud?: string;
  rows: number;
  missing_mail: number;
  missing_sede?: number;
  missing_liquido: number;
  written?: boolean;
  message?: string;
  sample?: PagosImportSampleRow[];
  cruzado?: PagosCruzadoResult;
};

export type PagosPreviewCandidate = {
  index: number;
  nombre: string;
  mail: string;
  sede: string;
  ubicacion?: string;
  id: string;
  boleta: string;
  descripcion?: string;
  bruto?: number;
  bruto_txt?: string;
  retencion?: number;
  retencion_txt?: string;
  pct_retencion?: number | null;
  monto: number;
  monto_txt: string;
  banco: string;
  cuenta: string;
  forma_pago: string;
  tipo_documento?: string;
  fecha_pago?: string;
  subject: string;
  html_body: string;
  idempotency_key: string;
};

export type PagosPreviewResponse = {
  ok: boolean;
  year: number;
  month: string;
  fecha_pago: string;
  total_rows: number;
  ready: number;
  skipped_no_mail: number;
  skipped_already: number;
  candidates: PagosPreviewCandidate[];
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
