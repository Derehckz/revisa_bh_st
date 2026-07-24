# QA — Épica E1 — Health gate Outlook

## Alcance del cambio
- `check_outlook_health` en `lib/outlook_utils.py`
- `outlook_health` en options API (etapas 1/2/5/7)
- Banner UI + bloqueo CTA con override
- Check en `bh_doctor.py`

## CLI
- [ ] `python herramientas/bh_doctor.py` muestra ok/warn de Outlook
- [ ] `python etapas/1.-envia_correo_mensual_bh.py --help` sigue OK
- [ ] `python etapas/2.-extrae_xml_correo.py --help` sigue OK

## API
- [ ] `GET /health` 200
- [ ] `GET /operations/stages/1/options?year=2026&month=Julio` incluye `outlook_health`
- [ ] `GET /operations/stages/2/options?...` incluye `outlook_health`
- [ ] `GET /operations/stages/3/options?...` NO requiere outlook_health (N/A etapa sin mail)

## Frontend
- [ ] Operación paso 1 muestra banner Outlook
- [ ] Sin Outlook listo y sin override: CTA deshabilitado
- [ ] Con override: se puede iniciar

## Excel
- [ ] Avance Excel / Solicitud del mes sigue legible (sin cambio)

## Outlook
- [ ] Cerrado: mensaje claro + can_auto_launch si hay exe
- [ ] Abierto: ready true (o com_ok false con mensaje)

## PostgreSQL
- [ ] `GET /period/2026/Julio` 200 (sin cambio)

## Regresión
- [ ] Paso 3/4 siguen iniciables
- [ ] `pytest tests/test_outlook_health.py tests/test_cli_entrypoints.py -q`

## Casos borde
- [ ] API key inválida → 401
- [ ] Cancelar sesión sigue funcionando

## Automatizado
- [ ] `pytest tests/test_outlook_health.py -q`
- [ ] `pytest tests/test_cli_entrypoints.py -q`

## Veredicto
PASS — implementar tras tests verdes
