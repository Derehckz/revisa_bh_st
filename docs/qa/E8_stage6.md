# QA — Épica E8 — Servicio etapa 6 (Informe final de boletas)

## Alcance del cambio
- `lib/stages/stage6/service.py` (`Stage6Service.run(ctx, ui)`)
- `Stage6Context` en `lib/stages/context.py` (subclase de `BridgedContext`, `stage_num=6` fijo)
- `api/interactive/runner.py`: etapa 6 ya no pasa por `_BRIDGED_STAGES`; usa
  `Stage6Context.from_api_params` + `Stage6Service().run(...)`
- Lógica de negocio intacta en `etapas/6.-Informe_final_boletas.py` (importlib +
  `Namespace` vía `build_namespace`, ya que la etapa 6 está en
  `_STAGES_WITH_NAMESPACE`)

## CLI
- [ ] `python "etapas/6.-Informe_final_boletas.py" --help` sigue OK
- [ ] `python "etapas/6.-Informe_final_boletas.py" --year 2026 --month Julio` genera el informe igual que antes

## API
- [ ] `POST /interactive/sessions` con `stage_num=6` inicia sesión y emite eventos igual que antes
- [ ] `GET /operations/stages/6/options?year=2026&month=Julio` sin cambios

## Frontend
- [ ] Paso 6 (Informe final) inicia, muestra progreso y termina igual que antes de la migración

## Excel
- [ ] Informe/planilla resultante sin cambios respecto a la ejecución previa a la migración

## Regresión
- [ ] `pytest tests/test_stage_services_bridged.py -q`
- [ ] `pytest tests/test_bridged_stages.py -q` (incluye `test_namespace_stages` para etapa 6)

## Casos borde
- [ ] Ejecutar sin período resuelto (año/mes) → mismo comportamiento de selección interactiva/errores que antes

## Automatizado
- [ ] `pytest tests/test_stage_services_bridged.py -q`

## Veredicto
PASS — implementar tras tests verdes
