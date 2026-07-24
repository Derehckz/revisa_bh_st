# RUNBOOK - Boletas Honorarios

## Objetivo

Guía operativa para levantar, validar y diagnosticar el backend actual (pipeline + PostgreSQL + API FastAPI).

## 1) Pre-requisitos

- Windows con Python 3.10+.
- PostgreSQL corriendo localmente.
- Dependencias instaladas:

```bash
python -m pip install -r requirements.txt
```

## 2) Configuración de entorno

Archivo requerido: `.env` en la raíz del proyecto.

Variables mínimas esperadas:

- Base:
  - `BH_RAIZ`
  - `BH_ULT_FECHA_RECEPCION`
  - `BH_HORARIO_RECEPCION`
- DB (usar prefijo `BH_DB_*`):
  - `BH_DB_HOST`
  - `BH_DB_PORT`
  - `BH_DB_NAME`
  - `BH_DB_USER`
  - `BH_DB_PASSWORD`
- Seguridad API:
  - `BH_API_KEY`
  - `BH_API_CORS_ORIGINS`
- Rate limit:
  - `BH_API_RATE_LIMIT_ENABLED`
  - `BH_API_RATE_LIMIT_MAX_REQUESTS`
  - `BH_API_RATE_LIMIT_WINDOW_SECONDS`

Referencia: `/.env.example`.

## 3) Arranque de API

**Rápido (API + frontend):** en la raíz, doble clic en `start-web.bat` (o `.\start-web.ps1`).
Detener: `stop-web.bat`. En Cursor: Run Task → **BH: Start Web (API + Frontend)**.

Solo API:

```bash
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Log de acceso API (JSONL):
- Default: `<BH_RAIZ>/.logs/api_access.jsonl`
- Override: `BH_API_ACCESS_LOG_PATH`

Health check:

```bash
curl -X GET "http://127.0.0.1:8000/health"
```

Prueba autenticada:

```bash
curl -X GET "http://127.0.0.1:8000/periods" \
  -H "x-api-key: <BH_API_KEY>" \
  -H "x-request-id: runbook-smoke-001"
```

## 4) Operación de pipeline

Ejecución completa:

```bash
python main.py
```

Ejecución por tramo de etapas:

```bash
python main.py --year 2026 --month Abril --start-from 1 --end-at 1
```

## 5) Validaciones operativas recomendadas

### API

- `GET /periods` devuelve períodos esperados.
- `GET /period/{year}/{month}` devuelve métricas coherentes.
- `GET /runs` devuelve historial de corridas.

### Data DB

- Verificación dominio:

```bash
python db/check_domain.py
```

- Verificación por período:

```bash
python db/check_period.py
```

- Verificación de runs:

```bash
python db/check_runs.py
```

### Tests

```bash
python -m pytest -q tests/api/test_api_endpoints.py
```

### Frontend MVP (si aplica)

```bash
cd frontend
npm install
npm run dev
```

Abrir `http://127.0.0.1:5173`.

### Pre-release Frontend hardening

```bash
cd frontend
npm run typecheck
npm run build
npm run perf:budget
```

Smoke E2E automatizado:

```bash
cd frontend
npx playwright install chromium
npm run e2e:smoke
```

## 6) Troubleshooting rápido

### Error `curl: (7) Failed to connect`

Causa: API no levantada.

Acción:
- Iniciar `uvicorn` en `127.0.0.1:8000`.
- Confirmar con `GET /health`.

### Error `401 UNAUTHORIZED`

Causa: `x-api-key` faltante/incorrecta.

Acción:
- Revisar `BH_API_KEY` en `.env`.
- Enviar header `x-api-key` en request.

### Error `503 SECURITY_NOT_CONFIGURED`

Causa: faltan `BH_API_KEY`/`BH_API_KEYS`.

Acción:
- Definir `BH_API_KEY` en `.env`.
- Reiniciar API.

### Error `429 RATE_LIMIT_EXCEEDED`

Causa: exceso de requests en ventana configurada.

Acción:
- esperar `retry-after`;
- o ajustar temporalmente:
  - `BH_API_RATE_LIMIT_MAX_REQUESTS`
  - `BH_API_RATE_LIMIT_WINDOW_SECONDS`

### Error autenticación PostgreSQL

Causa común: conflicto entre `DB_*` global y `.env`.

Acción:
- Asegurar uso correcto de `BH_DB_*`.
- Validar usuario/password directos con `psql`.

## 7) Sesiones web supervisadas vs envío real

- La **CI y pytest** no envían correos ni abren Outlook (ver batería en `README.md`).
- En la web, las etapas **5 y 7** rechazan `send=true` en sesión interactiva; solo **vista previa** (`per_mail`).
- El **envío real** de recepción/pagos: consola con supervisión manual, por ejemplo:
  ```bash
  python etapas/5.-Enviar_Correo_Recepcion.py --year 2026 --month Mayo --supervision-mode per_mail --send
  python etapas/7.-Envia_mail_pagos.py --year 2026 --month Mayo --fecha-pago 15/05/2026 --supervision-mode per_mail --send
  ```
- Etapa **8** en web: obligatorio `map_csv` (CSV RUT,IP|CFT). Generar con `python herramientas/generar_map_ip_cft.py` si falta.
- Etapa **10**: la sesión web emite eventos `folder.progress` (N/M carpetas).

## 8) Criterio de salida (release-ready mínimo)

- API responde `200` en `/health` y `/periods` con key.
- Batería pytest de CI en verde (sin envío de correos).
- `check_domain.py` y `check_period.py` sin inconsistencias críticas.
- `.env` completo y validado en ambiente.
- Contrato actualizado en `API_CONTRACT.md`.

### Smoke E2E (API + Frontend)

- API levantada en `127.0.0.1:8000`.
- Frontend levantado en `127.0.0.1:5173`.
- En UI:
  - conectar con API key válida;
  - seleccionar período;
  - visualizar resumen;
  - listar boletas;
  - buscar por `emplid` o `boleta_key`;
  - validar mensaje UX para `401/422/429/503`.
  - validar shortcuts (`Ctrl+B`, `/`, `Esc`).

## 9) Referencias

- Contrato API: `API_CONTRACT.md`
- Variables ejemplo: `.env.example`
- Scripts de validación DB: `db/check_domain.py`, `db/check_period.py`, `db/check_runs.py`
