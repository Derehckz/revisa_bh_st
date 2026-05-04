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

Instalación:

```bash
python -m pip install -r requirements.txt
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

```bash
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Smoke test:

```bash
curl -X GET "http://127.0.0.1:8000/periods" \
  -H "x-api-key: <tu_api_key>" \
  -H "x-request-id: smoke-001"
```

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

Contrato detallado: `API_CONTRACT.md`

---

## Calidad y validación

Tests base API:

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
├── alembic/
├── API_CONTRACT.md
├── RUNBOOK.md
├── requirements.txt
└── .env.example
```

---

## Licencia

Proyecto interno.
