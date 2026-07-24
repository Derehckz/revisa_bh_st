# QA — Épica E9 — Servicios etapas 8 y 9 (Separa BH IP/CFT, Agrupa por docente)

## Alcance del cambio
- `lib/stages/stage8/service.py` (`Stage8Service.run(ctx, ui)`)
- `lib/stages/stage9/service.py` (`Stage9Service.run(ctx, ui)`)
- `Stage8Context` / `Stage9Context` en `lib/stages/context.py` (subclases de
  `BridgedContext`, `stage_num` fijo)
- `api/interactive/runner.py`: etapas 8 y 9 ya no pasan por `_BRIDGED_STAGES`;
  usan `StageNContext.from_api_params` + `StageNService().run(...)`
- Lógica de negocio intacta en `etapas/8.-separa_bh_ip_cft.py` y
  `etapas/9.-agrupa_por_docente.py` (etapa 9 usa `Namespace` vía
  `build_namespace`, ya que está en `_STAGES_WITH_NAMESPACE`)

## CLI
- [ ] `python "etapas/8.-separa_bh_ip_cft.py" --help` sigue OK
- [ ] `python "etapas/9.-agrupa_por_docente.py" --help` sigue OK
- [ ] Ejecución real de etapa 8 (separación IP/CFT) sin cambios de comportamiento
- [ ] Ejecución real de etapa 9 (`--agrupar-archivos`) sin cambios de comportamiento

## API
- [ ] `POST /interactive/sessions` con `stage_num=8` inicia sesión y emite eventos igual que antes
- [ ] `POST /interactive/sessions` con `stage_num=9` inicia sesión y emite eventos igual que antes
- [ ] `GET /operations/stages/8/options` y `.../9/options` sin cambios

## Frontend
- [ ] Paso 8 y paso 9 inician, muestran progreso y terminan igual que antes de la migración

## Excel
- [ ] Carpetas/archivos generados por etapa 8/9 sin cambios respecto a la ejecución previa

## Regresión
- [ ] `pytest tests/test_stage_services_bridged.py -q`
- [ ] `pytest tests/test_bridged_stages.py -q`

## Casos borde
- [ ] Etapa 9 sin hoja "Resumen Boletas" → mismo fallback/errores que antes
- [ ] Etapa 8 con institución no mapeada → mismo comportamiento de advertencia/error

## Automatizado
- [ ] `pytest tests/test_stage_services_bridged.py -q`

## Veredicto
PASS — implementar tras tests verdes
