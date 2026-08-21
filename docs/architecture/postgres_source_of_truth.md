# PostgreSQL Source Of Truth

## Objetivo
Usar PostgreSQL como fuente de verdad para **consulta histórica** (Avance, Informe final, Informe de pagos) y dejar `Solicitud.xlsx` como artefacto de interoperabilidad / export / entrada de etapas.

## Lectura UI
- `BH_READ_FROM_DB=1` (default en `.env.example`): Avance lee boletas canónicas desde DB.
- Informe final: `periodos.informe_snapshot` (luego freeze en disco, luego Excel).
- Informe de pagos: `periodos.pagos_snapshot`.
- Meses cerrados conservan snapshots inmutables al cerrar (`informe_frozen_at`, `pagos_frozen_at`).

## Variables
- `BH_READ_FROM_DB=0|1`: cuando está en `1`, `excel_avance` y pantallas de informe priorizan DB.

## Migración de esquema
**Desde la interfaz (recomendado):**
- **Operación** → panel «Base de datos (PostgreSQL)» → **Migrar esquema** o **Verificar período** / **Sincronizar mes a BD**.
- **Ajustes** → **Base de datos** → **Actualizar esquema DB**.

Equivalente por consola:
- `alembic upgrade head`

Columnas canónicas en `boletas`:
- `recepcion_status`, `xml_status`, `mail_recepcion_status`, `glosa_match_mode`, `effective_status_reason`
- `estado_pago`, `solicitud_row` (JSONB)

Snapshots en `periodos`:
- `informe_snapshot` / `informe_sha256` / `informe_frozen_at`
- `pagos_snapshot` / `pagos_frozen_at`

## Doble escritura por etapas
Las etapas 3–6 proyectan estado canónico a DB (`db/period_projector.py`).
Paso 6 refresca `informe_snapshot`. Paso 7 / import de pagos refrescan `pagos_snapshot` y `estado_pago`.
El cierre de período congela ambos snapshots (y mantiene copia en `informe_congelado/` como backup).

## Backfill histórico
```bash
python herramientas/backfill_period_db.py --year 2026
python herramientas/backfill_period_db.py --year 2026 --month Julio
```

Desde la UI: **Operación** → **Sincronizar mes a BD** / **Backfill año**.

## Comparación en sombra Excel vs DB
**Operación** → **Verificar período** (o `python db/compare_excel_db.py --year 2026 --month Julio`).

## Estado actual
1. Lectura Avance/Informes desde DB cuando hay datos proyectados.
2. Excel sigue siendo input/output de etapas operativas.
3. Disco `informe_congelado/` = backup; la UI no lo necesita si el snapshot está en DB.
