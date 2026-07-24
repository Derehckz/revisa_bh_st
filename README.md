# Boletas de Honorarios

Sistema interno para el **cierre mensual de boletas de honorarios de docentes**: solicitar la boleta por correo, recibir PDF/XML desde Outlook, validar y completar `Solicitud.xlsx`, informar recepción/pago y archivar por IP/CFT.

Opera en tres capas que conviven:

| Capa | Rol |
|------|-----|
| **Pipeline CLI** (`main.py` + `etapas/`) | Vía operativa oficial (informática / consola). No depende de la web. |
| **API FastAPI** (`api/`) | Lectura (dashboard, boletas, docentes) + operaciones (jobs, sesiones interactivas, outbox, avance Excel). |
| **Frontend React** (`frontend/`) | Monitoreo y sala de control **Operación** para usuario de oficina. |

Excel (`Solicitud.xlsx`) sigue siendo la **fuente operativa del mes**. PostgreSQL recibe dual-write / snapshot para trazabilidad y pantallas de consulta. Outlook (COM, Windows) envía y descarga correos.

---

## Tabla de contenidos

1. [Qué problema resuelve](#qué-problema-resuelve)
2. [Estado actual](#estado-actual)
3. [Arquitectura](#arquitectura)
4. [Pipeline de etapas (0–10)](#pipeline-de-etapas-010)
5. [Artefactos por mes](#artefactos-por-mes)
6. [Solicitud.xlsx (columnas clave)](#solicitudxlsx-columnas-clave)
7. [Frontend (pantallas)](#frontend-pantallas)
8. [API (endpoints)](#api-endpoints)
9. [Requisitos e instalación](#requisitos-e-instalación)
10. [Configuración (`.env`)](#configuración-env)
11. [Ejecución](#ejecución)
12. [Herramientas auxiliares](#herramientas-auxiliares)
13. [Estado local (`.state/`)](#estado-local-state)
14. [Calidad y tests](#calidad-y-tests)
15. [Documentación relacionada](#documentación-relacionada)
16. [Estructura del repositorio](#estructura-del-repositorio)
17. [Principios de evolución (CLI-first)](#principios-de-evolución-cli-first)

---

## Qué problema resuelve

Cada mes hay que:

1. Armar la planilla de docentes que deben emitir boleta.
2. Pedirles la boleta por correo (y recordatorios).
3. Bajar los adjuntos (PDF + XML con prefijo `bhe_`) desde Outlook.
4. Cruzar lo recibido con la planilla (`Estado_Recepcion`).
5. Extraer datos del XML a columnas del Excel.
6. Confirmar recepción, generar informe, avisar pagos.
7. Separar y revisar carpetas IP / CFT.

Sin este sistema el trabajo se hace a mano abriendo Excel y Outlook. Con él, el mismo flujo corre por **consola** o por la **web Operación**, con logs, outbox, idempotencia de correos y vista de avance sin abrir el archivo.

---

## Estado actual

- Pipeline productivo 0–10 (`main.py` + `etapas/`).
- Lógica de negocio migrando a `lib/stages/` (servicios + adaptadores CLI/Web).
- PostgreSQL + SQLAlchemy + Alembic (consulta / dual-write).
- API con `x-api-key`, CORS, `x-request-id`, rate limit.
- Frontend: Dashboard, Período, Boletas, Docentes, **Operación**, Runs, Configuración.
- Operación web:
  - pasos **0–4** (y bridges) con sesión interactiva WebSocket;
  - flujo *streamlined* (menos confirms; auto-guardado Excel en 3/4);
  - pestaña **Avance Excel** (lee `Solicitud.xlsx` en vivo);
  - Outlook se puede **abrir solo** si está cerrado al conectar COM;
  - outbox de correos (SQLite) + dispatch COM.
- CLI **siempre vigente** e independiente de uvicorn/React. Ver [`docs/CLI_FIRST.md`](docs/CLI_FIRST.md).

---

## Arquitectura

```text
┌─────────────────────────────────────────────────────────────────┐
│  Usuario oficina (web)     │  Informática (consola)              │
│  frontend/ :5173           │  main.py / etapas/*.py              │
└──────────────┬─────────────┴──────────────┬──────────────────────┘
               │ HTTP / WS                  │ argparse + CLIAdapter
               ▼                            ▼
┌──────────────────────────┐    ┌──────────────────────────────┐
│  api/ (FastAPI :8000)    │    │  lib/stages/* / scripts       │
│  jobs · interactive ·    │───▶│  misma lógica de negocio      │
│  overview · excel-avance │    └──────────────┬───────────────┘
└────────────┬─────────────┘                   │
             │                                 │
             ▼                                 ▼
      PostgreSQL                    Excel + Outlook COM
      (consulta / runs)             ({BH_RAIZ}/{año}/{Mes}/)
                                           │
                                           ▼
                                    .state/ (outbox, jobs,
                                     sesiones, idempotencia)
```

### Capas

| Capa | Ubicación | Notas |
|------|-----------|--------|
| Orquestación CLI | `main.py`, `lib/pipeline_stages.py` | Tramos `--start-from` / `--end-at` |
| Scripts etapa | `etapas/N.-*.py` | Entrypoints oficiales; `--help` estable |
| Servicios | `lib/stages/stageN/` | Negocio compartido CLI + web |
| Interacción | `lib/interaction/` | `CLIAdapter`, `WebAdapter`, `RecordingAdapter`, `SessionBus` |
| Excel | `lib/bh_excel_workbook.py`, `schema_validator.py` | Escritura atómica / esquema canónico |
| Outlook | `lib/outlook_utils.py`, `bh_outlook_mail.py` | COM; auto-lanzar si está cerrado |
| Correos | `email_outbox`, plantillas, idempotencia | Outbox SQLite + flags en Excel |
| API | `api/app.py`, `api/operations.py`, `api/interactive/` | Lectura + operación |
| DB | `db/`, `alembic/` | Modelos, repos, migraciones |
| UI | `frontend/src/features/*` | React + Vite + TanStack Query |

---

## Pipeline de etapas (0–10)

Fuente de verdad: `lib/pipeline_stages.py`.

| # | Script | Descripción | Entrada típica | Resultado |
|---|--------|-------------|----------------|-----------|
| **0** | `0.-generar_solicitud.py` | Genera/actualiza planilla del mes | Maestro + BD docentes | `Solicitud.xlsx` |
| **1** | `1.-envia_correo_mensual_bh.py` | Pide emitir boleta | Excel + Outlook | Columna `Correo Enviado` / recordatorios |
| **2** | `2.-extrae_xml_correo.py` | Baja adjuntos del buzón | Outlook (rango fechas) | `bhe_*.pdf` / `bhe_*.xml` en carpeta mes |
| **3** | `3.-revisa_solicitud_VS_recibidas.py` | Cruza solicitud vs XML | Excel + carpeta | `Estado_Recepcion`, observaciones, `archivo_xml` |
| **4** | `4.-extrae_datos_xml_al_excel.py` | Parsea XML → columnas | Excel + XML | `*_XML`, `Observaciones_XML` |
| **5** | `5.-Enviar_Correo_Recepcion.py` | Confirma recepción | Filas RECIBIDO | Correos + flags |
| **6** | `6.-Informe_final_boletas.py` | Informe consolidado | Excel | Hojas/informe en Solicitud |
| **7** | `7.-Envia_mail_pagos.py` | Detalle de depósito | Hoja `Pagos` | Correos de pago |
| **8** | `8.-separa_bh_ip_cft.py` | Separa archivos | Prefijo `bhe_` | Carpetas `IP/` y `CFT/` |
| **9** | `9.-agrupa_por_docente.py` | Agrupa por persona | IP/CFT | Subcarpetas por docente |
| **10** | `10.-revisa_carpetas_ip_cft.py` | Valida estructura | Carpetas | `revision_carpetas.xlsx` |

### Cómo se ejecutan en web vs consola

| Etapas | Consola | Web Operación |
|--------|---------|---------------|
| **1–4** | Script + `CLIAdapter` | Sesión interactiva WebSocket (`lib/stages` + `WebAdapter`) |
| **5, 7** | Script; envío real con `--send` | Misma lógica / bridge; política de envío según contrato CLI-first |
| **0, 6, 8–10** | Script legacy | Bridge supervisado por WebSocket o job subprocess |
| Cualquiera | `python main.py …` | Job: `POST /operations/stages/{n}/start` (modo avanzado) |

Detalle de producto web (CTAs, streamlined): [`docs/PLAN_OPERACION_WEB.md`](docs/PLAN_OPERACION_WEB.md).

### Orquestación CLI

```bash
# Mes completo (según flags de main.py)
python main.py --year 2026 --month Julio

# Solo un tramo
python main.py --year 2026 --month Julio --start-from 3 --end-at 5

# Una etapa suelta
python etapas/2.-extrae_xml_correo.py --help
```

El paso **0** puede ser opcional en corrida completa (`optional_in_full_run` en el catálogo).

---

## Artefactos por mes

Raíz operativa: `BH_RAIZ` (por defecto la raíz del repo).

```text
{BH_RAIZ}/
  2026/
    Julio/
      Solicitud.xlsx              # planilla operativa del mes
      Solicitud_arrastre*.xlsx    # variantes / backups (no son el canónico de KPIs)
      bhe_{rut}-{n}.pdf
      bhe_{rut}-{n}.xml
      logs_envios/                # paso 1
      logs_extraccion/            # paso 2
      logs_revision/              # paso 3
      reporte_avance/             # reportes texto paso 3
      logs_extraccion_xml_excel/  # paso 4
      logs_agrupa/                # paso 9
      IP/                         # pasos 8–10
      CFT/
      revision_carpetas.xlsx      # paso 10
  .state/                         # ver sección Estado local
```

**Importante:** el paso **2 no modifica Excel**; solo deja PDF/XML en la carpeta. Los cambios de recepción/XML se ven tras los pasos **3** y **4** (o en **Avance Excel**).

---

## Solicitud.xlsx (columnas clave)

Esquema canónico (validación opt-in): `lib/schema_validator.py`.

### Hojas

| Hoja | Uso |
|------|-----|
| `Solicitud` | Filas de docentes / boletas del mes |
| `Resumen Boletas` | Informe / tipos de pago (paso 6) |
| `Pagos` | Destinatarios y flags de correo de pago (paso 7) |

### Columnas de progreso (hoja Solicitud)

| Columna | Quién la usa | Significado |
|---------|--------------|-------------|
| `Estado_Recepcion` | Paso 3 | `""`, `RECIBIDO`, `RECIBIDO CON ERROR`, `NO RECIBIDO` |
| `Correo Enviado` | Pasos 1, 5 | Estado del mail (enviado / error / omitido idempotencia) |
| `Recordatorios Enviados` | Paso 1 | Contador de recordatorios |
| `Observaciones`, `Observacion_Descartes`, `archivo_xml` | Paso 3 | Validación recepción |
| `*_XML`, `Observaciones_XML` | Paso 4 | Datos extraídos del XML |
| Identidad / montos | Paso 0+ | `EMPLID`, `NAME`, `Email_Docente`, `SEDE`, `CUS_TOT_HON`, `GLOSA`, … |

La pestaña **Avance Excel** agrega recepción, correos, XML y (si existe) hoja Pagos **leyendo el archivo en disco** (si Excel lo tiene abierto, intenta copia temporal).

---

## Frontend (pantallas)

App: `frontend/` (React + Vite + TanStack Query). Dev: **http://127.0.0.1:5173**.

| Ruta | Pantalla | Datos |
|------|----------|--------|
| `/` | Dashboard | Resumen / insights DB |
| `/periodo` | Vista de período | Métricas e insights del mes |
| `/boletas` | Listado de boletas | Filtro por estado, búsqueda |
| `/docentes` | Docentes | Perfil, boletas, métricas, emails |
| `/operacion` | **Sala de control** | Overview Excel + pipeline + sesiones |
| `/runs` | Runs de pipeline | Historial DB |
| `/settings` | Configuración | URL API + `x-api-key` (localStorage) |

### Operación — pestañas

| Tab | Contenido |
|-----|-----------|
| **Ejecutar** | Paso activo: CTA (ej. «Bajar boletas del mes»), prompts, cancelar/retomar sesión |
| **Avance Excel** | Barras + tabla docente (recepción, correo, XML, Pagos) sin abrir el xlsx |
| **Resultados** | Jobs del período, artefactos, bitácora, historial |
| **Más** | Outbox, cierre de período, opciones avanzadas |

El mes por defecto en Operación es el **más reciente abierto** (no un mes hardcodeado).

Tras terminar una sesión/job, la UI invalida overview, avance Excel, jobs y KPIs (sin depender de F5).

---

## API (endpoints)

Base: `http://127.0.0.1:8000`  
Auth: header `x-api-key` (y `x-request-id` recomendado).  
Contrato ampliado: [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md).

### Lectura / analítica

| Método | Ruta | Uso |
|--------|------|-----|
| GET | `/health` | Salud |
| GET | `/periods` | Lista de períodos |
| GET | `/period/{year}/{month}` | Resumen + métricas |
| GET | `/period/{year}/{month}/insights` | Montos, sedes, top docentes |
| GET | `/period/{year}/{month}/boletas` | Listado paginado |
| GET | `/period/{year}/{month}/search/boletas` | Búsqueda |
| GET | `/period/{year}/{month}/boletas/{id}` | Detalle |
| GET | `/period/{year}/{month}/boletas/{id}/files/{type}` | Archivo |
| GET | `/period/{year}/{month}/emails` | Emails del período |
| GET | `/period/{year}/{month}/xml` | XML del período |
| GET | `/runs`, `/runs/{id}/stages` | Runs |
| GET | `/stats/year/{year}` | Stats anuales |
| GET | `/docentes`, `/docentes/{id}`, `…/boletas`, `…/metrics`, `…/emails` | Docentes |

### Operación (Excel / jobs / outbox)

| Método | Ruta | Uso |
|--------|------|-----|
| GET | `/operations/stages` | Catálogo de pasos |
| GET | `/operations/period/overview` | KPIs Excel + estados UI + recomendación |
| GET | `/operations/period/excel-avance` | Avance detallado + filas de `Solicitud.xlsx` |
| GET | `/operations/stages/{n}/options` | Opciones / prerequisitos / schema params |
| POST | `/operations/stages/{n}/start` | Job subprocess (modo avanzado) |
| GET | `/operations/jobs`, `/jobs/{id}`, `…/logs`, `…/artifacts` | Seguimiento de jobs |
| GET | `/operations/history`, `…/logs` | Historial filesystem |
| GET/POST | `/operations/outbox/*` | Stats, filas, `dispatch-com`, `reopen-failed` |

### Sesiones interactivas (WebSocket)

Prefijo: `/operations/interactive`

| Método | Ruta | Uso |
|--------|------|-----|
| POST | `/stages/{n}/sessions` | Crear sesión (params JSON; `streamlined`, etc.) |
| GET | `/sessions/{id}` | Meta de sesión |
| POST | `/sessions/{id}/cancel` | Cancelar |
| WS | `/sessions/{id}/stream?api_key=…` | Eventos (`log`, `prompt.request`, `session.*`) y respuestas |

---

## Requisitos e instalación

- **Windows** (Outlook COM para pasos de correo / extracción).
- **Python 3.10+**
- **PostgreSQL** (local o remoto)
- **Node.js 18+** (solo frontend)
- Outlook de escritorio instalado (no basta la web de Outlook para COM)

```bash
# Backend
python -m pip install -r requirements.txt

# Frontend (una vez)
cd frontend
npm install
```

Checklist rápido de entorno:

```bash
python herramientas/bh_doctor.py --year 2026 --month Julio
```

Migraciones DB (cuando aplique):

```bash
alembic upgrade head
```

---

## Configuración (`.env`)

1. Copiar `.env.example` → `.env` en la raíz.
2. **No** subir `.env` al repositorio.

### Variables de negocio

| Variable | Rol |
|----------|-----|
| `BH_RAIZ` | Raíz de carpetas `{año}/{Mes}/` |
| `BH_ULT_FECHA_RECEPCION` / `BH_HORARIO_RECEPCION` | Textos en correos de solicitud |
| `BH_ULT_FECHA_RECORDATORIO` / `BH_HORARIO_RECORDATORIO` | Recordatorios |
| `BH_EMAIL_CONTABILIDAD`, `BH_EMAIL_XML_1`, `BH_EMAIL_XML_2` | Destinatarios / CC según plantillas |
| `BH_PREFIJO` | Prefijo de archivos (`bhe_` por defecto) |

### Base de datos

Preferir prefijo `BH_DB_*` (evita conflictos con variables globales `DB_*`):

- `BH_DB_HOST`, `BH_DB_PORT`, `BH_DB_NAME`, `BH_DB_USER`, `BH_DB_PASSWORD`

### Seguridad API

| Variable | Rol |
|----------|-----|
| `BH_API_KEY` | Clave principal (`x-api-key`) |
| `BH_API_KEY_PREVIOUS` / `BH_API_KEYS` | Rotación / múltiples keys |
| `BH_API_CORS_ORIGINS` | Orígenes permitidos (ej. Vite `:5173`) |
| `BH_API_RATE_LIMIT_*` | Rate limit in-memory |
| `BH_API_ACCESS_LOG_PATH` | Log JSONL de accesos (opcional) |

Tras cambiar `.env`, **reiniciar uvicorn**.

---

## Ejecución

### Arranque rápido (web) — recomendado en Windows

**Doble clic** en la raíz del proyecto:

| Archivo | Acción |
|---------|--------|
| [`start-web.bat`](start-web.bat) | Abre API `:8000` + Vite `:5173` y el navegador |
| [`stop-web.bat`](stop-web.bat) | Libera esos puertos |

Desde PowerShell:

```powershell
.\start-web.ps1
.\stop-web.ps1
```

En **Cursor / VS Code**: `Terminal` → `Run Task…` → **BH: Start Web (API + Frontend)**.

Primera vez en el navegador: **Ajustes** → pegar `BH_API_KEY` de tu `.env` (se guarda en el navegador).

### 1) Pipeline por consola (sin web)

```bash
python main.py --year 2026 --month Julio
python main.py --year 2026 --month Julio --start-from 2 --end-at 4
```

### 2) API (manual)

```bash
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Smoke test:

```bash
curl -X GET "http://127.0.0.1:8000/periods" \
  -H "x-api-key: <tu_api_key>" \
  -H "x-request-id: smoke-001"
```

Avance Excel (ejemplo):

```bash
curl -s "http://127.0.0.1:8000/operations/period/excel-avance?year=2026&month=Julio" \
  -H "x-api-key: <tu_api_key>"
```

### 3) Frontend (manual)

1. API en `:8000` con la misma key que pondrás en Configuración.
2. CORS en `.env`:

   ```env
   BH_API_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
   ```

3. Dev server:

   ```bash
   cd frontend
   npm run dev -- --host 127.0.0.1 --port 5173
   ```

4. Abrir **http://127.0.0.1:5173** → Configuración (URL + API key) → **Operación**.

Build / preview:

```bash
cd frontend
npm run build
npm run preview   # http://localhost:4173 — sigue necesitando la API
```

### Flujo típico de oficina (web)

1. Elegir mes abierto en Operación.
2. Paso 0: generar Solicitud (si aún no existe).
3. Paso 1: vista previa o envío de solicitudes (Outlook abierto o auto-lanzado).
4. Paso 2: bajar boletas (PDF/XML).
5. Mirar **Avance Excel** (aún sin recepción hasta el 3).
6. Paso 3: marcar recibidos → Excel se guarda (streamlined).
7. Paso 4: completar datos XML → Excel.
8. Continuar 5–10 según el mes (consola o web según política de envío).

---

## Herramientas auxiliares

En `herramientas/`:

| Script | Uso |
|--------|-----|
| `bh_doctor.py` | Checklist de entorno (RAIZ, outbox, adjuntos…) |
| `outbox_worker.py` | Worker / mantenimiento de outbox |
| `runs_report.py` | Reporte de runs |
| `cerrar_periodo.py` | Cierre de período |
| `copiar_plantilla_pagos.py` | Plantilla hoja Pagos |
| `generar_map_ip_cft.py` | Mapa IP/CFT |
| `diagnosticar_correo_docente.py` | Diagnóstico de correo de un docente |

Ejemplo:

```bash
python herramientas/bh_doctor.py --year 2026 --month Julio
```

---

## Estado local (`.state/`)

Carpeta bajo `BH_RAIZ` (no es código; suele estar en `.gitignore` parcial según política del repo):

| Recurso | Rol |
|---------|-----|
| `email_outbox.sqlite3` | Cola de correos pending / sent / failed |
| `interactive-sessions/` | Meta de sesiones WebSocket |
| Idempotencia / ops-jobs | Evitar reenvíos y seguir jobs API |

Si un paso queda “colgado”, en Operación se puede **Cancelar** o **Retomar** la sesión activa; Cancelar libera la UI aunque el WebSocket se haya caído.

---

## Calidad y tests

La CI (y la batería local recomendada) evita Outlook real y envío de correos:

```bash
export PYTHONPATH="$(pwd):$(pwd)/lib"

python -m pytest -q \
  tests/api/test_api_endpoints.py \
  tests/test_cli_entrypoints.py \
  tests/test_bridged_stages.py \
  tests/test_interaction_adapter.py \
  tests/test_stage_commands.py \
  tests/test_stage5_stage7_service.py \
  tests/test_interactive_validation.py \
  tests/test_stage10_progress.py \
  tests/test_session_bus_json_safe.py \
  tests/test_streamlined_flow.py \
  tests/test_outlook_utils_launch.py \
  tests/test_excel_avance.py
```

Solo API:

```bash
python -m pytest -q tests/api/test_api_endpoints.py
```

Checks de consistencia DB:

```bash
python db/check_domain.py
python db/check_period.py
python db/check_runs.py
```

---

## Documentación relacionada

| Documento | Contenido |
|-----------|-----------|
| [`docs/README.md`](docs/README.md) | Índice de documentación |
| [`docs/CLI_FIRST.md`](docs/CLI_FIRST.md) | Reglas: la web no puede romper la consola |
| [`docs/PLAN_OPERACION_WEB.md`](docs/PLAN_OPERACION_WEB.md) | UX Operación, CTAs, streamlined |
| [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) | Contratos de lectura API |
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | Setup, validaciones, troubleshooting, criterios de salida |
| [`docs/qa/`](docs/qa/) | Checklists QA modernización 2026 |
| `lib/pipeline_stages.py` | Catálogo numérico de etapas |
| `lib/schema_validator.py` | Columnas/hojas canónicas de Solicitud |

---

## Estructura del repositorio

```text
.
├── main.py                 # Orquestador CLI
├── lib/                    # Núcleo de negocio (stages, mail, locks, sync…)
├── etapas/                 # Entrypoints CLI oficiales 0–10
├── herramientas/           # Doctor, outbox, reportes, cierre período
├── api/                    # FastAPI (lectura + Operación)
├── db/                     # Modelos, repos, imports, checks
├── alembic/                # Migraciones PostgreSQL
├── frontend/               # React (src/); node_modules/ no va al repo
├── tests/
├── docs/                   # Toda la documentación del proyecto
│   ├── README.md
│   ├── CLI_FIRST.md
│   ├── RUNBOOK.md
│   ├── API_CONTRACT.md
│   ├── PLAN_OPERACION_WEB.md
│   └── qa/                 # Checklists por épica
├── BD-DOCENTES.xlsx        # Maestro operativo (raíz)
├── PROVISIONADOS ACUMULADOS.xlsx
├── EjemploEnvioBoleta.pdf  # Adjunto de ejemplo (config)
├── requirements.txt
└── .env.example
```

**No versionar:** carpetas `2024/`…`2026/` (meses), `.state/`, `.env`, `node_modules/`, backups `*_backup_*.zip`, logs.

---

## Principios de evolución (CLI-first)

1. Cada etapa conserva `etapas/N.-*.py` ejecutable con `--help`.
2. Los scripts **no** importan FastAPI ni React.
3. La lógica compartida vive en `lib/`; la API reutiliza servicios, no al revés.
4. Flags CLI no se rompen sin alias/deprecación.
5. Modo interactivo de consola por defecto; la web usa flags/adaptadores explícitos.
6. `pytest tests/test_cli_entrypoints.py` debe seguir en verde.

Detalle y checklist de PR: [`docs/CLI_FIRST.md`](docs/CLI_FIRST.md).

---

## Licencia

Proyecto interno.
