"""Envío de correos etapa 1 (lógica de negocio sin Rich)."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import config
import email_outbox
import email_templates as templates
import mail_ledger
import idempotency_store  # compat
import reminder_policy
import utils
from db import email_repository
from interaction.exceptions import SessionCancelled
from interaction.port import InteractionPort, PromptRequest
from interaction.types import InteractionKind, SupervisionMode
from outlook_utils import conectar_outlook_app
import bh_outlook_mail

_parse_recordatorio_count = reminder_policy.parse_recordatorio_count


def es_glosa_provisionado(glosa: object) -> bool:
    """True si la GLOSA marca fila de arrastre/provisión (debe tener correo propio)."""
    text = str(glosa or "").lower()
    return any(p in text for p in ("provisionado", "provisonado", "provs"))


def filas_sin_correo_valido(df, indices) -> list[dict[str, Any]]:
    """Filas del lote cuyo Email_Docente no se puede usar para enviar."""
    out: list[dict[str, Any]] = []
    if df is None or indices is None:
        return out
    has_email = "Email_Docente" in df.columns
    has_name = "NAME" in df.columns
    has_emplid = "EMPLID" in df.columns
    for idx in indices:
        raw = df.at[idx, "Email_Docente"] if has_email else ""
        email = utils.email_from_cell(raw)
        if utils.validar_email(email):
            continue
        out.append(
            {
                "index": int(idx),
                "fila": int(idx) + 1,
                "name": str(df.at[idx, "NAME"]) if has_name else "",
                "emplid": str(df.at[idx, "EMPLID"]) if has_emplid else "",
                "email": email or "(vacío)",
            }
        )
    return out


def announce_invalid_emails(ui: InteractionPort, df, indices) -> list[dict[str, Any]]:
    """Avisa en UI las filas sin correo válido. No bloquea; el envío las omite."""
    invalidos = filas_sin_correo_valido(df, indices)
    if not invalidos:
        return []
    ui.log(
        f"{len(invalidos)} fila(s) sin correo válido: no se enviarán. "
        "Completa Correo_Personal en BD-DOCENTES y regenera Solicitud (paso 0).",
        level="warning",
    )
    ui.table(
        "Sin correo válido (no se envían)",
        [(f"{it['name']} ({it['emplid']})", it["email"]) for it in invalidos],
    )
    return invalidos


def build_mail_item_key(
    año: int,
    mes: str,
    rut_docente,
    rut_razon,
    email: str,
    *,
    recordatorio_num: int | None = None,
    provisionado: bool = False,
    glosa: object | None = None,
) -> str:
    """
    Clave de idempotencia del correo de solicitud.

    Incluye `|prov` cuando la fila es provisionada, para no colisionar con la
    boleta normal del mismo docente/mes/RUT razón (arrastre crea fila aparte).
    """
    rr = utils.normalizar_rut_con_dv(rut_razon)
    base = f"{año}|{mes}|{rut_docente}|{rr}|{email}".lower()
    is_prov = bool(provisionado) or (glosa is not None and es_glosa_provisionado(glosa))
    if is_prov:
        base = f"{base}|prov"
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
    fecha_limite_recepcion: str | None = None,
    horario_recepcion: str | None = None,
    fecha_limite_recordatorio: str | None = None,
    horario_recordatorio: str | None = None,
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
            email = utils.email_from_cell(row["Email_Docente"])
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
                fecha_limite_recepcion=fecha_limite_recepcion,
                horario_recepcion=horario_recepcion,
                fecha_limite_recordatorio=fecha_limite_recordatorio,
                horario_recordatorio=horario_recordatorio,
            )

            cc_list = [config.EMAIL_XML_2] if config.EMAIL_XML_2 else []
            if isinstance(email_dp, str) and utils.validar_email(email_dp):
                cc_list.append(email_dp)
            cc_combined = "; ".join(cc_list)

            if not utils.validar_email(email):
                df.at[idx, columna_envio] = f"❌ Correo inválido ({tipo})"
                nombre = str(nombre_completo or "").strip() or "(sin nombre)"
                rut = str(rut_docente or "").strip()
                ui.log(
                    f"Correo inválido ({tipo}) fila {idx + 1}: {nombre} ({rut}) — "
                    f"{email or '(vacío)'}",
                    level="warning",
                )
                stats["failed"] += 1
                continue

            if tipo == "recordatorio":
                recordatorio_num = _parse_recordatorio_count(df.at[idx, "Recordatorios Enviados"]) + 1
                item_key = build_mail_item_key(
                    año,
                    mes,
                    rut_docente,
                    rut_razon,
                    email,
                    recordatorio_num=recordatorio_num,
                    glosa=glosa,
                )
            else:
                item_key = build_mail_item_key(
                    año, mes, rut_docente, rut_razon, email, glosa=glosa
                )

            already_sent = not force_resend and mail_ledger.was_sent(stage_id, item_key)
            if already_sent:
                label = "provisionado" if es_glosa_provisionado(glosa) else tipo
                df.at[idx, columna_envio] = f"⏭ Omitido por idempotencia ({label})"
                ui.log(
                    f"Omitido (idempotencia): {email} RUT razón {rut_razon}"
                    + (" [provisionado]" if es_glosa_provisionado(glosa) else ""),
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

            if mail_ledger.report_attempt("script1.mail_attempt", item_key):
                logging.warning(f"Reintento detectado (solo reporte): {item_key}")

            if outbox_ids_by_index is not None and idx in outbox_ids_by_index:
                ob_id = outbox_ids_by_index[idx]
            else:
                ob_id = mail_ledger.record_pending(
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
                mail_ledger.mark_outbox_sent(ob_id)
                if tipo == "original":
                    df.at[idx, columna_envio] = "✅ Enviado (original)"
                else:
                    prev_count = _parse_recordatorio_count(df.at[idx, "Recordatorios Enviados"])
                    new_count = prev_count + 1
                    df.at[idx, "Recordatorios Enviados"] = new_count
                    df.at[idx, columna_envio] = f"✅ Enviado (recordatorio #{new_count})"
                mail_ledger.mark_sent(stage_id, item_key, details=f"asunto={asunto}")
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
                mail_ledger.mark_outbox_failed(ob_id, "No se pudo enviar después de 3 intentos")
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
