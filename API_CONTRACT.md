# API Contract - Boletas Honorarios

## Base URL

- Local: `http://127.0.0.1:8000`

## Authentication

- Header requerido en endpoints de negocio: `x-api-key: <BH_API_KEY>`
- Endpoint público sin key: `GET /health`

## Request Correlation

- Puedes enviar `x-request-id` en la request.
- Si no se envía, el servidor genera uno.
- La respuesta incluye `x-request-id`.

## Error Envelope (estándar)

Todas las respuestas de error usan esta forma:

```json
{
  "code": "STRING_CODE",
  "message": "Mensaje legible",
  "details": {
    "request_id": "...."
  }
}
```

### Códigos relevantes

- `401 UNAUTHORIZED`: key ausente o inválida.
- `422 VALIDATION_ERROR`: parámetros inválidos.
- `429 RATE_LIMIT_EXCEEDED`: límite de requests excedido.
- `503 SECURITY_NOT_CONFIGURED`: servidor sin `BH_API_KEY/BH_API_KEYS`.

## Observabilidad

- Se registra acceso API en JSONL.
- Ruta configurable por `BH_API_ACCESS_LOG_PATH`.
- Si no se define, usa `<BH_RAIZ>/.logs/api_access.jsonl`.

## Endpoints

### Health

- `GET /health`
- Auth: no requerida
- Response:

```json
{
  "status": "ok"
}
```

### Periods

- `GET /periods`
- Auth: requerida
- Response: `PeriodItem[]`

Campos por ítem:
- `id` (int)
- `year` (int)
- `month_num` (int)
- `month_name` (string)
- `status` (string)

### Period Summary

- `GET /period/{year}/{month}`
- Auth: requerida
- Validaciones:
  - `year`: `2000..2100`
  - `month`: texto (`3..20` chars)

Response:
- `period`
- `metrics`:
  - `total_boletas`
  - `total_xml`
  - `xml_coverage_pct`
  - `total_emails`
  - `email_coverage_pct`
  - `recibidos`
  - `no_recibidos`
  - `recibidos_con_error`
  - `emails_enviados`
  - `emails_error`

### Period Boletas

- `GET /period/{year}/{month}/boletas?estado=&limit=&offset=`
- Auth: requerida
- Validaciones:
  - `limit`: `1..500`
  - `offset`: `0..100000`

Response:
- `period`
- `pagination` (`total`, `limit`, `offset`, `returned`)
- `filters`
- `data[]` (`id`, `boleta_key`, `emplid`, `estado_recepcion`, `monto_bruto`, etc.)

### Search Boletas (UI)

- `GET /period/{year}/{month}/search/boletas?q=&limit=&offset=`
- Auth: requerida
- Uso: búsqueda por `emplid`, `boleta_key`, `docente_nombre` y `numero_boleta_xml`.
- Validaciones:
  - `q`: mínimo `2` caracteres
  - `limit`: `1..200`
  - `offset`: `0..100000`

Response:
- `period`
- `pagination`
- `filters` (`q`)
- `data[]`

### Boleta Detail

- `GET /period/{year}/{month}/boletas/{boleta_id}`
- Auth: requerida
- Response:
  - `boleta`
  - `xml_data` (nullable)
  - `emails_period_sample[]`

### Boleta Files

- `GET /period/{year}/{month}/boletas/{boleta_id}/files/{file_type}`
- Auth: requerida
- `file_type`: `xml|pdf`
- Response: archivo binario para abrir en navegador.

### Period Insights

- `GET /period/{year}/{month}/insights`
- Auth: requerida
- Response:
  - `period`
  - `kpis` (`monto_total`, `monto_promedio`, `docentes_unicos`, `boletas_con_xml`, `boletas_sin_xml`)
  - `by_sede[]`
  - `top_docentes[]`

### Period Emails

- `GET /period/{year}/{month}/emails?estado=&tipo=&limit=&offset=`
- Auth: requerida
- Response:
  - `period`
  - `pagination`
  - `filters`
  - `data[]`

### Period XML

- `GET /period/{year}/{month}/xml?limit=&offset=`
- Auth: requerida
- Response:
  - `period`
  - `pagination`
  - `data[]`

### Pipeline Runs

- `GET /runs?limit=&offset=`
- Auth: requerida
- Response:
  - `pagination`
  - `data[]`

### Run Stages

- `GET /runs/{run_id}/stages`
- Auth: requerida
- Response:
  - `run`
  - `stages[]`

### Year Stats

- `GET /stats/year/{year}`
- Auth: requerida
- Response:
  - `year`
  - `totals`
  - `periods[]`

### Docentes

- `GET /docentes?q=&limit=&offset=`
- Auth: requerida
- Response:
  - `pagination`
  - `filters`
  - `data[]` (`id`, `rut`, `nombre_completo`, `sede`, `email_personal`, `email_dp`, `boletas_count`, `monto_total`)

### Docente Profile

- `GET /docentes/{docente_id}?limit=`
- Auth: requerida
- Response:
  - `docente`
  - `boletas[]` (resumen histórico)
  - `period_stats[]`

### Docente Boletas

- `GET /docentes/{docente_id}/boletas?year=&month=&estado=&limit=&offset=`
- Auth: requerida
- Response:
  - `pagination`
  - `filters`
  - `data[]` (boletas asociadas al docente)

### Docente Metrics

- `GET /docentes/{docente_id}/metrics?year=&month=`
- Auth: requerida
- Response:
  - `docente`
  - `metrics` (`total_boletas`, `recibidas`, `con_error`, `sin_xml`, `monto_total`, `monto_promedio`)

## Curl examples

```bash
curl -X GET "http://127.0.0.1:8000/periods" \
  -H "x-api-key: <tu_key>" \
  -H "x-request-id: contrato-test-001"
```

```bash
curl -X GET "http://127.0.0.1:8000/period/2026/Abril" \
  -H "x-api-key: <tu_key>" \
  -H "x-request-id: contrato-test-002"
```
