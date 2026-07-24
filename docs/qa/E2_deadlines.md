# QA — Épica E2 — Plazos sin mutar config

## Alcance
- `email_templates.plazo_por_tipo` / `generar_cuerpo_solicitud` aceptan plazos explícitos
- Stage1 pasa `deadline_kwargs`; con `BH_DEADLINES_VIA_CONTEXT=1` (default) no muta `config.*`
- Persistencia vía `period_mail_config`

## CLI
- [ ] `python etapas/1.-envia_correo_mensual_bh.py --help`
- [ ] Envío con `--fecha-limite-recepcion "30 Julio 2026"` refleja en preview/cuerpo

## API
- [ ] Options stage1 defaults = Julio (o guardados del mes)
- [ ] Tras sesión, `period_mail_deadlines.json` actualizado

## Frontend
- [ ] F5 en Operación paso 1: plazos del mes actual, no mes anterior

## Excel / Outlook / PG
- [ ] N/A Excel estructura
- [ ] Outlook: envío usa plazos del contexto
- [ ] PG: sin cambio

## Regresión / Borde
- [ ] `BH_DEADLINES_VIA_CONTEXT=0` restaura mutación legacy
- [ ] Dos sesiones no se pisan plazos (con flag on)

## Automatizado
- [ ] `pytest tests/test_period_mail_config.py tests/test_email_templates.py -q`

## Veredicto
PASS si checklist OK
