# QA — Épica E10 — Servicio etapa 10 (Revisa carpetas IP/CFT)

## Alcance del cambio
- `lib/stages/stage10/service.py` (`Stage10Service.run(ctx, ui)`)
- `Stage10Context` en `lib/stages/context.py` (subclase de `BridgedContext`, `stage_num=10` fijo)
- `api/interactive/runner.py`: etapa 10 ya no pasa por `_BRIDGED_STAGES`; usa
  `Stage10Context.from_api_params` + `Stage10Service().run(...)`
- Lógica de negocio y el parche de `progress_hook` sobre `ejecutar_trabajos`
  siguen intactos dentro de `stages.bridged_runner.run_bridged_stage`
  (caso especial ya existente para `stage_num == 10`)

## CLI
- [ ] `python "etapas/10.-revisa_carpetas_ip_cft.py" --help` sigue OK
- [ ] Ejecución real (`--dry-run`) revisa carpetas sin cambios de comportamiento

## API
- [ ] `POST /interactive/sessions` con `stage_num=10` inicia sesión y emite eventos igual que antes
- [ ] Eventos `folder.progress` siguen llegando con `current`/`total` correctos
- [ ] `GET /operations/stages/10/options` sin cambios

## Frontend
- [ ] Paso 10 inicia, muestra la barra de progreso ("Revisando carpetas") y termina igual que antes

## Excel
- [ ] N/A (etapa no toca Excel directamente)

## Regresión
- [ ] `pytest tests/test_stage_services_bridged.py -q`
- [ ] `pytest tests/test_stage10_progress.py -q`
- [ ] `pytest tests/test_bridged_stages.py -q`

## Casos borde
- [ ] `--force` reprocesa carpetas ya marcadas, igual que antes
- [ ] `--ocr` sigue deshabilitado/activado según flag, sin cambios

## Automatizado
- [ ] `pytest tests/test_stage_services_bridged.py tests/test_stage10_progress.py -q`

## Veredicto
PASS — implementar tras tests verdes
