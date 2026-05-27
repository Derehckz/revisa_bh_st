"""Envío / previsualización correos recepción (etapa 5)."""
from __future__ import annotations

import logging
import time
from typing import Any

import email_outbox
import email_templates as templates
import idempotency_store
import utils
from interaction.exceptions import SessionCancelled
from interaction.port import InteractionPort, PromptRequest
from interaction.types import InteractionKind, SupervisionMode
import bh_outlook_mail

STAGE_ID = "script5.recepcion_send"
EMAIL_COPIA = ""


def format_entero(valor) -> str:
    import pandas as pd

    if pd.isna(valor):
        return "N/A"
    try:
        return str(int(float(valor)))
    except (TypeError, ValueError):
        return str(valor)


def build_item_key(año: str, mes: str, numero_boleta: str, correo: str) -> str:
    return f"{año}|{mes}|{numero_boleta}|{correo}".lower()


def _preview_payload(
    *,
    idx: int,
    nombre,
    correo: str,
    numero_boleta: str,
    rut: str,
    rut_emisor: str,
    monto,
    asunto: str,
    cuerpo_html: str,
    item_key: str,
    already_sent: bool,
) -> dict[str, Any]:
    return {
        "index": int(idx),
        "tipo": "recepcion",
        "docente": {"name": str(nombre), "email": correo, "numero_boleta": numero_boleta},
        "mail": {
            "to": correo,
            "cc": EMAIL_COPIA or "",
            "subject": asunto,
            "html_body": cuerpo_html,
        },
        "idempotency_key": item_key,
        "already_sent": already_sent,
        "cli_summary": f"{nombre} <{correo}> — boleta {numero_boleta}",
    }


def procesar_correos(
    ui: InteractionPort,
    df,
    df_filtrado,
    *,
    año: str,
    mes: str,
    modo_prueba: bool,
    allow_send: bool,
    force_resend: bool,
    supervision_mode: SupervisionMode,
    outlook,
    dispatch_outbox: dict[int, int] | None = None,
    dispatch_only_indices: set[int] | None = None,
) -> dict[str, int]:
    stats = {"sent": 0, "failed": 0, "omitted": 0, "skipped": 0, "previewed": 0}
    total = len(df_filtrado)

    for pos, (idx, fila) in enumerate(df_filtrado.iterrows(), start=1):
        ui.progress(pos, total, label="Recepción")
        try:
            ix = int(idx)
        except (TypeError, ValueError):
            ix = idx
        if dispatch_only_indices is not None and ix not in dispatch_only_indices:
            continue

        if str(fila.get("Correo_Recepcion_Enviado", "")).strip() == "Sí":
            stats["omitted"] += 1
            continue

        correo = str(fila.get("Email_Docente", "")).strip()
        nombre = fila.get("NAME", "Estimado")
        numero_boleta = format_entero(fila.get("numeroBoleta_XML", "N/A"))
        rut = format_entero(fila.get("rutReceptorCompleto_XML", "N/A"))
        rut_emisor = format_entero(fila.get("rutEmisorCompleto_XML", "N/A"))
        monto = fila.get("totalHonorarios_XML", "N/A")

        if not utils.validar_email(correo):
            df.at[idx, "Correo_Recepcion_Enviado"] = "❌ Correo inválido"
            stats["failed"] += 1
            continue

        item_key = build_item_key(año, mes, numero_boleta, correo)
        if not modo_prueba and not force_resend and idempotency_store.was_success(STAGE_ID, item_key):
            df.at[idx, "Correo_Recepcion_Enviado"] = "⏭ Omitido por idempotencia"
            stats["omitted"] += 1
            continue

        asunto = templates.generar_asunto_recepcion(numero_boleta)
        cuerpo_html = templates.generar_cuerpo_recepcion(
            nombre=nombre,
            numero_boleta=numero_boleta,
            rut=rut,
            rut_emisor=rut_emisor,
            monto=monto,
        )
        preview = _preview_payload(
            idx=ix,
            nombre=nombre,
            correo=correo,
            numero_boleta=numero_boleta,
            rut=rut,
            rut_emisor=rut_emisor,
            monto=monto,
            asunto=asunto,
            cuerpo_html=cuerpo_html,
            item_key=item_key,
            already_sent=False,
        )

        if modo_prueba or not allow_send:
            ui.emit("mail.preview", preview)
            if supervision_mode == SupervisionMode.PER_MAIL:
                resp = ui.ask(
                    PromptRequest(
                        kind=InteractionKind.MAIL_REVIEW,
                        title="Vista previa recepción",
                        message=f"¿Continuar con siguiente? (sin envío — modo prueba)",
                        payload=preview,
                    )
                )
                if resp.action == "cancel":
                    raise SessionCancelled()
                if resp.action == "skip":
                    stats["skipped"] += 1
                    continue
            stats["previewed"] += 1
            if modo_prueba:
                break
            continue

        if supervision_mode == SupervisionMode.PER_MAIL:
            ui.emit("mail.preview", preview)
            resp = ui.ask(
                PromptRequest(
                    kind=InteractionKind.MAIL_REVIEW,
                    title="Confirmar recepción",
                    message=f"¿Enviar correo de recepción a {nombre}?",
                    payload=preview,
                )
            )
            if resp.action == "cancel":
                raise SessionCancelled()
            if resp.action == "skip":
                stats["skipped"] += 1
                ui.emit("mail.skipped", {"index": ix, "email": correo})
                continue

        if dispatch_outbox is not None and ix in dispatch_outbox:
            ob_id = dispatch_outbox[ix]
        else:
            ob_id = email_outbox.record_pending(
                STAGE_ID, item_key, {"boleta": numero_boleta, "to": correo}
            )
        try:
            if not bh_outlook_mail.send_html_mail_with_backoff(
                outlook,
                to=correo,
                cc=EMAIL_COPIA,
                subject=asunto,
                html_body=cuerpo_html,
                max_attempts=3,
                base_delay_s=1.5,
                backoff_factor=1.5,
                log_context=f"script5 boleta={numero_boleta}",
            ):
                raise RuntimeError("No se pudo enviar tras reintentos COM")
            email_outbox.mark_sent(ob_id)
            df.at[idx, "Correo_Recepcion_Enviado"] = "Sí"
            idempotency_store.mark_success(STAGE_ID, item_key, details=f"boleta={numero_boleta}")
            ui.log(f"Correo enviado a {correo} (boleta {numero_boleta})", level="success")
            stats["sent"] += 1
            time.sleep(1)
        except Exception as e:
            email_outbox.mark_failed(ob_id, str(e))
            df.at[idx, "Correo_Recepcion_Enviado"] = f"❌ Error: {e}"
            ui.log(f"Error enviando a {correo}: {e}", level="error")
            stats["failed"] += 1

    return stats
