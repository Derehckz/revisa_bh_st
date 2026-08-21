# QA — Épica E13 — Operación mensual empresa

Checklist de humo para cierre real de período, backup, validación de maestro y bitácora.

## 1. Checklist + cierre / reapertura

- [ ] `GET /operations/period/monthly-checklist?year=&month=` muestra ítems ok/warn/block.
- [ ] Con bloqueantes, `POST /operations/period/close` responde 422.
- [ ] Sin bloqueantes (o `force`), close marca `periodos.estado=cerrado`, crea `informe_congelado/` y escribe audit `period.close`.
- [ ] Sección Informe muestra badge “Congelado” y no regenera desde hoja viva.
- [ ] `POST /operations/period/reopen` vuelve a `abierto` y deja audit `period.reopen`.
- [ ] Panel “Ejecutar pendientes (2–10)” **no** cierra el mes.

## 2. Backup PostgreSQL

- [ ] `herramientas/backup_postgres.ps1` genera `.backups/postgres/bh_*.dump`.
- [ ] Ajustes → Crear backup ahora (`POST /operations/db/backup`) lista el dump.
- [ ] Restore documentado en `docs/RUNBOOK.md` (no ejecutar en prod sin confirmación).

## 3. Validación maestro (paso 0)

- [ ] Upload de maestro sin columnas requeridas falla con mensaje claro.
- [ ] `GET /operations/period/validate-maestro` refleja errores/warnings.
- [ ] UI paso 0 bloquea “Generar” si validación falla.
- [ ] `POST /operations/stages/0/start` rechaza maestro inválido.

## 4. Operador + bitácora

- [ ] Ajustes guarda nombre de operador (`bh_operator_name`).
- [ ] Mutaciones envían header `x-operator-name`.
- [ ] `GET /audit/events` lista close/reopen/backup/jobs/docentes.

## 5. Pasos 7–10

- [ ] Tras paso 7 con envío, `boletas.estado_pago` se actualiza cuando hay match.
- [ ] Guías UI 6–10 hablan de período / planilla, no de Excel como fuente de verdad.

## Automatizable (barato)

```bash
python -c "from monthly_checklist import monthly_checklist; print(monthly_checklist(2026,'Julio')['can_close'])"
pytest tests/ -q -k "period or maestro or audit" --maxfail=5
cd frontend && npm run build
```
