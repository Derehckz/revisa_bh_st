"""Envío de correos etapa 1 (lógica de negocio sin Rich)."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import config
import email_outbox
import email_templates as templates
import idempotency_store
import reminder_policy
import utils
from db import email_repository
from interaction.exceptions import SessionCancelled
from interaction.port import InteractionPort, PromptRequest
from interaction.types import InteractionKind, SupervisionMode
from outlook_utils import conectar_outlook_app
import bh_outlook_mail

_parse_recordatorio_count = reminder_policy.parse_recordatorio_count


def build_mail_item_key(
    año: int,
    mes: str,
    rut_docente,
    rut_razon,
    email: str,
    *,
    recordatorio_num: int | None = None,
) -> str:
    rr = utils.normalizar_rut_con_dv(rut_razon)
    base = f"{año}|{mes}|{rut_docente}|{rr}|{email}".lower()
    if recordatorio_num is not None:
        return f"{base}|r{recordatorio_num}"
    return base


def _mail_preview_payload(
    df,
    idx: int,
    tipo: str,
    *,
    asunto: str,
    cuerpo_html: str,
    email: str,
    cc_combined: str,
    item_key: str,
    already_sent: bool,
) -> dict[str, Any]:
    row = df.loc[idx]
    monto_raw = row["CUS_TOT_HON"] if "CUS_TOT_HON" in df.columns else None
    return {
        "index": int(idx),
        "tipo": tipo,
        "docente": {
            "name": str(row.get("NAME", "")),
            "email": str(email),
            "rut": str(row.get("EMPLID", "")),
            "rut_razon": str(row.get("RUT RAZON", "")),
            "monto": templates._format_monto(monto_raw),
        },
        "mail": {
            "to": email,
            "cc": cc_combined,
            "subject": asunto,
            "html_body": cuerpo_html,
            "attachment": os.path.basename(config.ARCHIVO_ADJUNTO) if tipo == "original" else None,
        },
        "idempotency_key": item_key,
        "already_sent": already_sent,
        "cli_summary": (
            f"{row.get('NAME')} <{email}> — {asunto}"
            + (" [ya enviado]" if already_sent else "")
        ),
    }


def enviar_correos(
    ui: InteractionPort,
    df,
    indices,
    *,
    tipo: str = "original",
    force_resend: bool = False,
    allow_send: bool = True,
    supervision_mode: SupervisionMode = SupervisionMode.BATCH,
    outbox_ids_by_index: dict[int, int] | None = None,
) -> dict[str, int]:
    """Envía correos; devuelve contadores {sent, skipped, failed, omitted}."""
    stats = {"sent": 0, "skipped": 0, "failed": 0, "omitted": 0}
    if not allow_send or len(indices) == 0:
        return stats

    outlook = conectar_outlook_app()
    columna_envio = "Correo Enviado"
    tipo_envio_db = "SOLICITUD" if tipo == "original" else "RECORDATORIO"
    stage_id = f"script1.mail_send.{tipo}"
    total = len(indices)

    for pos, idx in enumerate(indices, start=1):
        ui.progress(pos, total, label=f"Enviando ({tipo})")
        try:
            row = df.loc[idx]
            nombre_completo = row["NAME"]
            rut_docente = row["EMPLID"]
            rut_razon = row["RUT RAZON"]
            razon_social = row["NOMBRE RAZON"]
            direccion_razon = row["DireccionRazon"]
            glosa = row["GLOSA"]
            monto = row["CUS_TOT_HON"]
            email = row["Email_Docente"]
            email_dp = row.get("Email_DP")
            mes = str(row["MONTH"]).upper()
            año = int(row["YEAR"])

            asunto = templates.generar_asunto_solicitud(tipo, mes, año, rut_docente, nombre_completo)
            cuerpo_html = templates.generar_cuerpo_solicitud(
                tipo=tipo,
                nombre_completo=nombre_completo,
                rut_docente=rut_docente,
                rut_razon=rut_razon,
                razon_social=razon_social,
                direccion_razon=direccion_razon,
                glosa=glosa,
                monto=monto,
                email_dp=email_dp,
                mes=mes,
                año=año,
            )

            cc_list = [config.EMAIL_XML_2] if config.EMAIL_XML_2 else []
            if isinstance(email_dp, str) and utils.validar_email(email_dp):
                cc_list.append(email_dp)
            cc_combined = "; ".join(cc_list)

            if not (isinstance(email, str) and utils.validar_email(email)):
                df.at[idx, columna_envio] = f"❌ Correo inválido ({tipo})"
                ui.log(f"Correo inválido ({tipo}) fila {idx + 1}: {email}", level="warning")
                stats["failed"] += 1
                continue

            if tipo == "recordatorio":
                recordatorio_num = _parse_recordatorio_count(df.at[idx, "Recordatorios Enviados"]) + 1
                item_key = build_mail_item_key(
                    año, mes, rut_docente, rut_razon, email, recordatorio_num=recordatorio_num
                )
            else:
                item_key = build_mail_item_key(año, mes, rut_docente, rut_razon, email)

            already_sent = not force_resend and idempotency_store.was_success(stage_id, item_key)
            if already_sent:
                df.at[idx, columna_envio] = f"⏭ Omitido por idempotencia ({tipo})"
                ui.log(
                    f"Omitido (idempotencia): {email} RUT razón {rut_razon}",
                    level="warning",
                )
                stats["omitted"] += 1
                continue

            preview = _mail_preview_payload(
                df,
                idx,
                tipo,
                asunto=asunto,
                cuerpo_html=cuerpo_html,
                email=email,
                cc_combined=cc_combined,
                item_key=item_key,
                already_sent=False,
            )

            if supervision_mode == SupervisionMode.PER_MAIL:
                ui.emit("mail.preview", preview)
                resp = ui.ask(
                    PromptRequest(
                        kind=InteractionKind.MAIL_REVIEW,
                        title="Confirmar envío",
                        message=f"¿Enviar correo a {nombre_completo}?",
                        payload=preview,
                    )
                )
                if resp.action == "cancel":
                    raise SessionCancelled()
                if resp.action == "skip":
                    stats["skipped"] += 1
                    ui.emit("mail.skipped", {"index": int(idx), "email": email})
                    continue

            if idempotency_store.report_duplicate("script1.mail_attempt", item_key):
                logging.warning(f"Reintento detectado (solo reporte): {item_key}")

            if outbox_ids_by_index is not None and idx in outbox_ids_by_index:
                ob_id = outbox_ids_by_index[idx]
            else:
                ob_id = email_outbox.record_pending(
                    stage_id, item_key, {"tipo": tipo, "to": email, "asunto": asunto}
                )

            enviado = bh_outlook_mail.send_html_mail_with_backoff(
                outlook,
                to=email,
                cc=cc_combined,
                subject=asunto,
                html_body=cuerpo_html,
                attachment_path=config.ARCHIVO_ADJUNTO if tipo == "original" else None,
                max_attempts=3,
                base_delay_s=2.0,
                backoff_factor=1.5,
                log_context=f"script1 {tipo} {item_key}",
            )

            if enviado:
                email_outbox.mark_sent(ob_id)
                if tipo == "original":
                    df.at[idx, columna_envio] = "✅ Enviado (original)"
                else:
                    prev_count = _parse_recordatorio_count(df.at[idx, "Recordatorios Enviados"])
                    new_count = prev_count + 1
                    df.at[idx, "Recordatorios Enviados"] = new_count
                    df.at[idx, columna_envio] = f"✅ Enviado (recordatorio #{new_count})"
                idempotency_store.mark_success(stage_id, item_key, details=f"asunto={asunto}")
                ui.log(f"Correo ({tipo}) enviado a {email} (fila {idx + 1})", level="success")
                ui.emit("mail.sent", {"index": int(idx), "email": email, "tipo": tipo})
                email_repository.save_email_event(
                    tipo_envio=tipo_envio_db,
                    to_email=email,
                    cc_email=cc_combined,
                    subject=asunto,
                    estado="ENVIADO",
                    periodo_label=f"{año}-{mes}",
                )
                stats["sent"] += 1
            else:
                email_outbox.mark_failed(ob_id, "No se pudo enviar después de 3 intentos")
                df.at[idx, columna_envio] = f"❌ Error envío ({tipo})"
                ui.log(f"Error envío ({tipo}) a {email} (fila {idx + 1})", level="error")
                ui.emit("mail.failed", {"index": int(idx), "email": email, "tipo": tipo})
                email_repository.save_email_event(
                    tipo_envio=tipo_envio_db,
                    to_email=email,
                    cc_email=cc_combined,
                    subject=asunto,
                    estado="ERROR",
                    error_detalle="No se pudo enviar después de 3 intentos",
                    periodo_label=f"{año}-{mes}",
                )
                stats["failed"] += 1

            time.sleep(1.5)

        except SessionCancelled:
            raise
        except Exception as e:
            df.at[idx, columna_envio] = f"❌ Error: {e} ({tipo})"
            ui.log(f"Fila {idx + 1}: {e} ({tipo})", level="error")
            stats["failed"] += 1

    return stats
