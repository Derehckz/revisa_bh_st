# RUNBOOK - Boletas Honorarios

## Objetivo

Guía operativa para levantar, validar y diagnosticar el backend (pipeline + PostgreSQL + API FastAPI).

## Cubrir el mes (suplente)

1. Arranque: `start-bh.bat` → http://127.0.0.1:8000/ — Outlook abierto en este PC.
2. Docente sin correo o sede: **Docentes** (obligatorio correo + sede; el DP sale de la sede). Al guardar se actualiza la Solicitud del mes abierto; **no regeneres el paso 0**.
3. Envío puntual: paso 1 → Opciones → «Solo estos RUT». Marca «forzar reenvío» solo si ya se había enviado.
4. Avance y Excel deben coincidir persona/monto/estado. Si no, sincroniza (paso 0 ya hecho: import/snapshot) o avisa.
5. Cierre: pasos 6–10, checklist, OK Contabilidad, **Cerrar mes**. Eso no es «Ejecutar pendientes».
6. Backup: Ajustes → Crear backup ahora. Restore: `herramientas/restore_postgres.ps1`.
7. Si cambias código Python: `reiniciar-bh.bat` (raíz). La UI se reconstruye al arrancar si hay cambios en `frontend/src`.

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

## 3) Arranque de API / interfaz

**Oficina (recomendado):** doble clic `start-bh.bat` → **http://127.0.0.1:8000/**  
(UI embebida en la API; construye `frontend/dist` si falta.)

**Desarrollo (hot-reload):** `start-web.bat` (API `:8000` + Vite `:5173`).

Detener: `stop-bh.bat`. En Cursor: Run Task → **BH: Start (embebido :8000)**.

Solo API (sin UI embebida si no hay `dist`):

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

**Desde la interfaz (recomendado):**
- **Operación** → **Verificar período** (import + proyección + comparación + métricas del mes).
- **Ajustes** → **Revisar consistencia global**.

Equivalente por consola (mantenimiento avanzado):

```bash
python db/check_domain.py
python db/check_period.py --year 2026 --month Julio
python db/check_runs.py
```

Endpoints API:
- `POST /operations/period/verify`
- `POST /operations/db/migrate`
- `POST /operations/db/consistency-check`

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
- En la web, las etapas **5 y 7** **sí permiten** `send=true` en sesión interactiva, con confirmación explícita de envío a producción en la UI.
- Sin marcar envío real, la sesión solo previsualiza / analiza (`per_mail` / dry preview).
- Alternativa por consola (supervisión correo a correo):
  ```bash
  python etapas/5.-Enviar_Correo_Recepcion.py --year 2026 --month Mayo --supervision-mode per_mail --send
  python etapas/7.-Envia_mail_pagos.py --year 2026 --month Mayo --fecha-pago 15/05/2026 --supervision-mode per_mail --send
  ```
- Etapa **8** en web: obligatorio `map_csv` (CSV RUT,IP|CFT). Si falta `map_ip_cft.csv`, la API lo genera desde Solicitud al iniciar; o: `python herramientas/generar_map_ip_cft.py --year … --month …`.
- Etapa **10** = **revisión de carpetas IP/CFT** (no cierra el mes). El cierre formal está en Operación → pestaña **Cierre**.
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

## 9) Operación mensual en empresa (dueño del servidor)

### Quién reinicia / mantiene el servidor

- Responsable local: operador que ejecuta `scripts/start-bh.ps1` (o el banner de reinicio en la UI).
- Si la API no responde: reiniciar con `.\reiniciar-bh.bat` desde la raíz del repo; verificar `/health`.

### Backups PostgreSQL

- Carpeta: `.backups/postgres/bh_YYYYMMDD_HHMMSS.dump`
- Manual (PowerShell):
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\herramientas\backup_postgres.ps1
  ```
- Desde la web: **Ajustes → Crear backup ahora** (`POST /operations/db/backup`).
- Restaurar (cuidado: sobrescribe la BD):
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\herramientas\restore_postgres.ps1 -DumpPath .\.backups\postgres\bh_....dump
  ```
- Programar diario: Programador de tareas de Windows → acción = el script `backup_postgres.ps1` (retención ~14 dumps).
- Requiere `pg_dump` / `pg_restore` en PATH y variables `BH_DB_*` en `.env`.

### Dependencias del entorno

- Outlook / Windows COM para envío de correos (pasos 1, 5, 7).
- PostgreSQL local como fuente de verdad del período.
- Nombre del operador en Ajustes (header `x-operator-name`) para la bitácora.

### Checklist antes del cierre mensual

1. Mes creado y maestro validado (paso 0 OK, Solicitud sincronizada en BD).
2. Pasos 1–6 completos; informe visible en **Informe**.
3. Revisar checklist en **Operación** (ítems bloqueantes en verde).
4. Opcional: backup BD antes de cerrar.
5. **Cerrar período** (congela informe + `estado=cerrado`). No confundir con “Ejecutar pendientes (2–10)”.
6. Si hay que corregir: **Reabrir período** (confirmación explícita) → corregir → volver a cerrar.

## 10) Referencias

- Contrato API: `API_CONTRACT.md`
- Variables ejemplo: `.env.example`
- Scripts de validación DB: `db/check_domain.py`, `db/check_period.py`, `db/check_runs.py`
- Backup: `herramientas/backup_postgres.ps1`, `herramientas/restore_postgres.ps1`
