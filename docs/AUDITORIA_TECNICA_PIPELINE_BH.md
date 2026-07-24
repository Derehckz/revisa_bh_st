# Pipeline BH — pendientes y changelog

Documento operativo: **qué falta** y **qué cambió** en el código reciente.

### Layout del repositorio

| Carpeta | Contenido |
|---------|-----------|
| **`lib/`** | Módulos compartidos: `config`, `utils`, `bh_*`, `email_*`, `outlook_utils`, `pipeline_stages`, `outbox_com_dispatch`. El paquete **`db/`** sigue en la raíz; los scripts `db/*.py` ejecutables añaden `lib/` + raíz al `sys.path`. |
| **`etapas/`** | Scripts numerados **0–10** del pipeline; cada uno hace `import _sys_path` para añadir `lib/` al path. |
| **`herramientas/`** | CLIs operativos: `outbox_worker.py`, `runs_report.py`, `bh_doctor.py`. |
| **Raíz** | `main.py`, `api/`, `alembic/`, datos por año (`2024/`…), `BD-DOCENTES.xlsx`, PDF de ejemplo, `requirements.txt`, etc. |

Ejecutar siempre **`main.py`** y las herramientas **desde la raíz del repo** (`cd` al directorio que contiene `lib/`).

---

## Pendientes

### Arquitectura

| Tema | Qué falta |
|------|-----------|
| Outlook COM | Pulir parámetros de backoff por entorno; métricas más ricas (contadores / export) si hace falta; `outbox_com_dispatch` sigue invocando 1/5/7. |
| Excel + scripts monolíticos | Reutilizar `bh_excel_workbook` en otros scripts (3/4/6/10…) donde hoy se duplica el patrón read-modify-atomic; más servicios de negocio. |
| Riesgo sistémico | Sigue la dependencia de Outlook; la lógica COM/HTML quedó centralizada en `bh_outlook_mail` para 1/5/7. |

### Por script

| Script | Pendiente o riesgo |
|--------|-------------------|
| `etapas/1.-envia_correo_mensual_bh.py` | Más dominio reusable fuera del script (envío / políticas). |
| `etapas/2.-extrae_xml_correo.py` | Filtros Outlook/COM y heurística de adjuntos; sin `--year`/`--month` (rango de fechas). |
| `etapas/3.-revisa_solicitud_VS_recibidas.py` | Casos borde: montos, archivos sin prefijo `bhe_`, nombres fuera de lo ya tolerado. |
| `etapas/4.-extrae_datos_xml_al_excel.py` | Más códigos `[BH-*]` en errores por tipo de fila si hace falta en operación. |
| `etapas/5.-Enviar_Correo_Recepcion.py` | Segunda confirmación opcional para alto volumen. |
| `etapas/7.-Envia_mail_pagos.py` | Plantillas adicionales por banco si el negocio lo exige. |
| `etapas/9.-agrupa_por_docente.py` | `--agrupar-archivos` solo copia BH en raíz del mes; ampliar si hay otras convenciones de ruta. |
| `etapas/10.-revisa_carpetas_ip_cft.py` | OCR opcional no determinista; control de recursos en paralelismo. |

### Outbox / dispatch COM

- **`dispatch-com`** solo enruta `stage` conocidos: `script1.mail_send.*`, `script5.recepcion_send`, `script7.pago_send`. Otros `stage` → se marcan `failed` con mensaje explícito.
- Reintentos **script 7**: el `payload` debe incluir **`fecha_pago`**. Filas antiguas en `pending` sin ese campo no pueden armar el correo; conviene un envío normal con `--fecha-pago` o limpiar la fila en sqlite.

### UX / CLI

- Extender `[BH-*]` / `bh_errors.format_bh` al resto de scripts con el mismo criterio.
- Opcional: entrypoint único tipo `python -m bh_tools` (`runs_report`, `outbox_worker`, `bh_doctor`, etc.).

### Prioridades (recomendaciones)

**Media:** más dominio de correo fuera de scripts 1/5/7; `runs_report` con duración por etapa u otras columnas si hace falta.

**Baja:** rendimiento en validaciones masivas (`os.scandir`, lotes); entrypoint único `bh_tools`.

---

## Changelog (reciente)

| Área | Cambio |
|------|--------|
| COM unificado | **`bh_outlook_mail.py`**: `send_html_mail_once`, `send_html_mail_with_backoff` (backoff exponencial, logs `[bh-outlook] metric=…`). Usado en scripts **1, 5 y 7**. |
| Excel servicio | **`bh_excel_workbook.py`**: `replace_sheet_atomically`; usado en **1** (guardado final), **5**, **7** y **`outbox_com_dispatch`** (script 1). |
| Período CLI | `utils.resolve_año_mes`, `register_period_args`: `--year` / `--month` en scripts **3–9**; `main.py` pasa período con `accepts: year_month`. |
| Errores | `bh_errors.py` (`format_bh`); `[BH-*]` en período y fallos de guardado Excel en script **4**. |
| Outbox + COM | `email_outbox`: `fetch_pending_rows`, `get_row_status`; **`lib/outbox_com_dispatch.py`**: reintento COM solo para filas `pending`; **`herramientas/outbox_worker.py`**: `dispatch-com`, `watch-dispatch` (además de `stats`, `list`, `reopen-failed`, `watch --exec-cmd`). |
| Scripts correo | **1**: `outbox_ids_by_index` para reutilizar id pending; **5/7**: `dispatch_outbox` + `dispatch_only_indices` e índice fila normalizado (`int`); **7**: payload outbox con `fecha_pago`. |
| Runs | **`herramientas/runs_report.py`**: `--table` (etapas en tabla texto), resumen JSON por defecto, `--list`, `--last N`, `--path`. |
| Doctor | **`herramientas/bh_doctor.py`**: checklist RAIZ, adjunto paso 1, sqlite outbox, `.state/runs`, opcional `--year`/`--month` + `Solicitud.xlsx`. |
| Orquestación | **`lib/pipeline_stages.py`**: `SCRIPTS` consumido por `main.py`. |
| Carpetas | **`lib/`**, **`etapas/`**, **`herramientas/`**: código agrupado; `main.py` inserta `lib/` en `sys.path`; tests y API hacen lo mismo al arrancar. |
| Script 3 | Emparejamiento PDF/XML: RUT con ceros, `bhe_` + EMPLID, sufijo `-`/`_`, `except` más acotados. |
| Script 4 | Menos `except` amplios; errores Excel etiquetados; no interactivo sin pisar filas “Datos extraídos OK” sin confirmación. |
| Script 9 | **`--agrupar-archivos`**: copia PDF/XML `bhe_*` desde raíz del mes a cada carpeta docente. |
| Script 0 | **`--csv-nuevos-docentes`** batch; `--yes` sin CSV con faltantes → `[BH-NUEVOS_DOCENTES_BATCH]`. |
| Tests | `test_bh_errors_resolve.py`; `test_email_outbox` incluye `fetch_pending_rows` / `get_row_status`; resto (schema, idempotencia, `reminder_policy`). |

### Referencia rápida (CLI)

```text
python herramientas/bh_doctor.py [--year AÑO --month MES]
python herramientas/outbox_worker.py stats | list | reopen-failed
python herramientas/outbox_worker.py dispatch-com [--limit N] [--dry-run]
python herramientas/outbox_worker.py watch-dispatch [--interval SEG] [--limit N]
python herramientas/runs_report.py [--table] [--list] [--last N] [--path RUTA.json]
```

**Archivos relevantes (rutas actuales):** `lib/bh_outlook_mail.py`, `lib/bh_excel_workbook.py`, `lib/bh_errors.py`, `lib/outbox_com_dispatch.py`, `lib/email_outbox.py`, `lib/pipeline_stages.py`, `lib/utils.py`, `herramientas/bh_doctor.py`, `herramientas/outbox_worker.py`, `herramientas/runs_report.py`, `etapas/*.py`, `main.py`, `tests/`.
