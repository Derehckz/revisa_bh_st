# Boletas de Honorarios

Sistema para gestionar el flujo mensual de boletas de honorarios, con:

- pipeline operativo en scripts Python (Outlook + Excel),
- persistencia en PostgreSQL (shadow/dual-write),
- API de lectura en FastAPI para interfaz web y monitoreo.

---

## Estado actual del proyecto

- Pipeline productivo por etapas (`main.py` + scripts en `etapas/`).
- Base de datos PostgreSQL integrada con SQLAlchemy + Alembic.
- API read-only con contratos Pydantic.
- Seguridad API activa:
  - `x-api-key`,
  - CORS configurable,
  - `x-request-id`,
  - rate limit básico por IP + key.
- Tests base de API pasando.
- Frontend web (React + Vite) en `frontend/` con vista **Operación** (pipeline 0–10 vía API).

### CLI siempre vigente (independiente de la web)

Los scripts en `etapas/` y `main.py` **no dependen** del frontend ni de uvicorn.
La web es un cliente opcional; la consola sigue siendo la vía oficial para informática.

Reglas y checklist: [`docs/CLI_FIRST.md`](docs/CLI_FIRST.md)  
Tests de regresión: `pytest tests/test_cli_entrypoints.py`

---

## Arquitectura (resumen)

### Capa pipeline (operación)

- Scripts numerados para el proceso mensual.
- Excel sigue siendo fuente operativa del equipo.
- Dual-write hacia DB para trazabilidad y analítica.

### Capa datos (DB)

- PostgreSQL como base principal de evolución.
- Modelos en `db/models.py`.
- Migraciones con Alembic.
- Repositorios en `db/*_repository.py`.

### Capa API (web)

- App FastAPI en `api/app.py`.
- Servicios de lectura en `api/services.py`.
- Contratos en `api/schemas.py`.
- Seguridad en `api/security.py`.

---

## Requisitos

- Windows (Outlook COM para scripts de correo/extracción).
- Python 3.10+.
- PostgreSQL local o remoto.
- **Node.js 18+** (solo para el frontend web).

Instalación backend:

```bash
python -m pip install -r requirements.txt
```

Instalación frontend (una vez):

```bash
cd frontend
npm install
```

---

## Configuración

1. Crear `.env` en raíz (usar `.env.example` como base).
2. Definir al menos:
   - rutas/config de negocio (`BH_RAIZ`, etc.),
   - DB (`BH_DB_HOST`, `BH_DB_NAME`, `BH_DB_USER`, `BH_DB_PASSWORD`, ...),
   - seguridad API (`BH_API_KEY`, `BH_API_CORS_ORIGINS`).

Notas:
- Preferir `BH_DB_*` para evitar conflictos con variables globales del sistema.
- No subir `.env` al repositorio.

---

## Ejecución

### Pipeline completo

```bash
python main.py
```

### Pipeline por tramo

```bash
python main.py --year 2026 --month Abril --start-from 3 --end-at 5
```

### API local

En una terminal, desde la raíz del repo:

```bash
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Smoke test:

```bash
curl -X GET "http://127.0.0.1:8000/periods" \
  -H "x-api-key: <tu_api_key>" \
  -H "x-request-id: smoke-001"
```

### Frontend web (desarrollo)

1. Levanta la API (paso anterior) con la misma `BH_API_KEY` que usarás en el navegador.
2. En `.env` de la raíz, permite CORS del dev server (si no, el navegador bloqueará las peticiones):

   ```env
   BH_API_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
   ```

   Reinicia uvicorn después de cambiar `.env`.

3. En otra terminal:

   ```bash
   cd frontend
   npm run dev
   ```

4. Abre en el navegador: **http://localhost:5173**

   - **Dashboard**, **Período**, **Boletas**, **Docentes**, **Runs**: lectura vía API.
   - **Operación**: ejecutar pasos 0–10 del pipeline. Paso 1: **envío supervisado** (WebSocket, confirmación por correo) o modo rápido (job + log).
   - **Configuración**: URL de la API (por defecto `http://127.0.0.1:8000`) y `x-api-key` (debe coincidir con `BH_API_KEY` del `.env`).

El período por defecto en Operación es **Abril 2026** (mes cerrado de referencia).

Build de producción (opcional):

```bash
cd frontend
npm run build
npm run preview
```

`preview` sirve el build en **http://localhost:4173** (sigue necesitando la API en `:8000`).

---

## Endpoints principales

- `GET /health`
- `GET /periods`
- `GET /period/{year}/{month}`
- `GET /period/{year}/{month}/boletas`
- `GET /period/{year}/{month}/boletas/{boleta_id}`
- `GET /period/{year}/{month}/xml`
- `GET /period/{year}/{month}/emails`
- `GET /runs`
- `GET /runs/{run_id}/stages`
- `GET /stats/year/{year}`
- `POST /operations/interactive/stages/{1|2|3|4}/sessions` — sesiones supervisadas (correos / extracción / revisión / XML→Excel)
- `WS /operations/interactive/sessions/{id}/stream?api_key=…` — eventos y respuestas en vivo

Contrato detallado: `API_CONTRACT.md` · CLI-first: `docs/CLI_FIRST.md`

---

## Calidad y validación

La CI ejecuta compilación, migraciones Alembic y esta batería (sin Outlook ni envío de correos):

```bash
python -m pytest -q \
  tests/api/test_api_endpoints.py \
  tests/test_cli_entrypoints.py \
  tests/test_bridged_stages.py \
  tests/test_interaction_adapter.py \
  tests/test_stage_commands.py \
  tests/test_stage5_stage7_service.py \
  tests/test_interactive_validation.py \
  tests/test_stage10_progress.py
```

Tests base API únicamente:

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

## Operación y soporte

Guía operativa completa (setup, validaciones, troubleshooting, criterios de salida):

- `RUNBOOK.md`

---

## Estructura principal

```text
.
├── main.py                 # orquestador (añade lib/ al sys.path)
├── lib/                    # módulos compartidos: config, utils, outbox, templates, etc.
├── etapas/                 # scripts numerados del pipeline (0–10)
├── herramientas/           # CLIs: outbox_worker, runs_report, bh_doctor
├── api/
│   ├── app.py
│   ├── services.py
│   ├── schemas.py
│   └── security.py
├── db/
│   ├── models.py
│   ├── session.py
│   ├── *_repository.py
│   ├── check_domain.py
│   ├── check_period.py
│   └── check_runs.py
├── frontend/               # UI React (Vite): npm run dev → :5173
│   └── src/features/operacion/  # sala de control pipeline
├── alembic/
├── API_CONTRACT.md
├── RUNBOOK.md
├── requirements.txt
└── .env.example
```

---

## Licencia

Proyecto interno.
