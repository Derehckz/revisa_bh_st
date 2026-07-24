# QA — Épica E7 — Servicio etapa 0 (Generar Solicitud)

## Alcance del cambio
- `lib/stages/stage0/service.py` (`Stage0Service.run(ctx, ui)`)
- `Stage0Context` en `lib/stages/context.py` (subclase de `BridgedContext`, `stage_num=0` fijo)
- `api/interactive/runner.py`: etapa 0 ya no pasa por `_BRIDGED_STAGES`; usa
  `Stage0Context.from_api_params` + `Stage0Service().run(...)`
- Flag `BH_STAGE0_SERVICE` (default `True`): si se pone en `False`, la etapa 0
  vuelve a ejecutarse con `BridgedContext` + `run_bridged_stage` directo (rollback)
- Lógica de negocio intacta en `etapas/0.-generar_solicitud.py` (se sigue
  cargando vía `importlib` desde `stages/bridged_loader.py` + `utils_bridge`)

## CLI
- [ ] `python etapas/0.-generar_solicitud.py --help` sigue OK
- [ ] `python etapas/0.-generar_solicitud.py --mes Julio --año 2026` genera `Solicitud.xlsx` igual que antes

## API
- [ ] `POST /interactive/sessions` con `stage_num=0` inicia sesión y emite eventos igual que antes
- [ ] Con `BH_STAGE0_SERVICE=false` en `.env`, la misma sesión sigue funcionando (ruta de rollback)
- [ ] `GET /operations/stages/0/options?year=2026&month=Julio` sin cambios

## Frontend
- [ ] Paso 0 (Generar Solicitud) inicia, muestra progreso y termina igual que antes de la migración

## Excel
- [ ] `Solicitud.xlsx` y `BD-DOCENTES.xlsx` se generan/actualizan igual que antes

## Regresión
- [ ] `pytest tests/test_stage_services_bridged.py -q`
- [ ] `pytest tests/test_bridged_stages.py -q`
- [ ] `pytest tests/test_cli_entrypoints.py -q` (si existe cobertura de etapa 0)

## Casos borde
- [ ] Docentes no encontrados en BD sin `--csv-nuevos-docentes` en modo no interactivo → error claro (sin cambio)
- [ ] Fallback `BH_STAGE0_SERVICE=false` produce el mismo resultado que el servicio

## Automatizado
- [ ] `pytest tests/test_stage_services_bridged.py -q`

## Veredicto
PASS — implementar tras tests verdes
