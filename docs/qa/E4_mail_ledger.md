# QA — Épica E4 — MailLedger

## Alcance
- `lib/mail_ledger.py` fachada
- Stages 1/5/7 usan `was_sent` / `mark_sent` / outbox vía ledger
- Claves `|prov` intactas

## CLI / API / Frontend
- [ ] `--help` etapas 1,5,7
- [ ] Outbox API stats siguen respondiendo
- [ ] Envío web: omitidos idempotencia + provisionados distintos

## Excel
- [ ] Columna Correo Enviado se actualiza igual

## Outlook
- [ ] Envío real marca sent en ledger + outbox

## PostgreSQL
- [ ] `save_email_event` sigue tras envío OK

## Regresión / Borde
- [ ] force-resend ignora was_sent
- [ ] item_key normal ≠ `|prov`

## Automatizado
- [ ] `pytest tests/test_mail_ledger.py tests/test_script1_mail_item_key.py -q`

## Veredicto
PASS si checklist OK
