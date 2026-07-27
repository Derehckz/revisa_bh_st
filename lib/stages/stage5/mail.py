"""Envío / previsualización correos recepción (etapa 5)."""
from __future__ import annotations

import time
from typing import Any, Literal

import email_templates as templates
import mail_ledger
import utils
from interaction.exceptions import SessionCancelled
from interaction.port import InteractionPort, PromptRequest
from interaction.types import InteractionKind, SupervisionMode
import bh_outlook_mail

STAGE_ID = "script5.recepcion_send"
EMAIL_COPIA = ""

RecepcionKind = Literal["ok", "problema"]


def _is_sent_marker(value: object) -> bool:
    s = str(value or "").strip().lower()
    if not s:
        return False
    return (
        s in {"sí", "si"}
        or "enviado" in s
        or "correo enviado" in s
    )


def format_entero(valor) -> str:
    import pandas as pd

    if pd.isna(valor):
        return "N/A"
    try:
        return str(int(float(valor)))
    except (TypeError, ValueError):
        return str(valor)


def build_item_key(
    año: str,
    mes: str,
    numero_boleta: str,
    correo: str,
    *,
    kind: RecepcionKind = "ok",
    emplid: str = "",
    rut_razon: str = "",
) -> str:
    """Clave de idempotencia. `problema` y `ok` son independientes."""
    boleta = (numero_boleta or "N/A").strip() or "N/A"
    if boleta.upper() in {"N/A", "NAN", "NONE"} and (emplid or rut_razon):
        boleta = f"row:{emplid}|{rut_razon}"
    return f"{año}|{mes}|{boleta}|{correo}|{kind}".lower()


def clasificar_fila_recepcion(fila) -> RecepcionKind | None:
    """
    ok       → RECIBIDO (confirmación positiva)
    problema → RECIBIDO CON ERROR, o NO RECIBIDO con descartes (hubo archivos sin match)
    None     → no corresponde correo de recepción (p.ej. NO RECIBIDO sin archivos)
    """
    estado = str(fila.get("Estado_Recepcion", "") or "").strip().upper()
    if estado == "RECIBIDO":
        return "ok"
    if estado == "RECIBIDO CON ERROR":
        return "problema"
    if estado == "NO RECIBIDO":
        descartes = str(fila.get("Observacion_Descartes", "") or "").strip()
        if descartes:
            return "problema"
    return None


def problema_desde_fila(fila) -> tuple[str, str]:
    """(problema principal, detalle descartes)."""
    obs = str(fila.get("Observaciones", "") or "").strip()
    descartes = str(fila.get("Observacion_Descartes", "") or "").strip()
    if obs and obs.upper() not in {"OK", "N/A"}:
        return obs, descartes
    if descartes:
        return (
            "Se revisaron archivos enviados, pero ninguno coincidió con esta línea de la solicitud.",
            descartes,
        )
    return (
        "La boleta recibida no pudo validarse contra la solicitud (datos incompletos o inconsistentes).",
        "",
    )


def _preview_payload(
    *,
    idx: int,
    kind: RecepcionKind,
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
    problema: str = "",
) -> dict[str, Any]:
    return {
        "index": int(idx),
        "tipo": "recepcion" if kind == "ok" else "recepcion_problema",
        "kind": kind,
        "docente": {"name": str(nombre), "email": correo, "numero_boleta": numero_boleta},
        "mail": {
            "to": correo,
            "cc": EMAIL_COPIA or "",
            "subject": asunto,
            "html_body": cuerpo_html,
        },
        "problema": problema,
        "idempotency_key": item_key,
        "already_sent": already_sent,
        "cli_summary": (
            f"{nombre} <{correo}> — boleta {numero_boleta}"
            if kind == "ok"
            else f"{nombre} <{correo}> — OBSERVACIÓN / reenvío"
        ),
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
    stats = {
        "sent": 0,
        "sent_ok": 0,
        "sent_problema": 0,
        "failed": 0,
        "omitted": 0,
        "skipped": 0,
        "previewed": 0,
    }
    total = len(df_filtrado)

    for pos, (idx, fila) in enumerate(df_filtrado.iterrows(), start=1):
        ui.progress(pos, total, label="Recepción")
        try:
            ix = int(idx)
        except (TypeError, ValueError):
            ix = idx
        if dispatch_only_indices is not None and ix not in dispatch_only_indices:
            continue

        if _is_sent_marker(fila.get("Correo_Recepcion_Enviado", "")):
            stats["omitted"] += 1
            continue

        kind = clasificar_fila_recepcion(fila)
        if kind is None:
            stats["omitted"] += 1
            continue

        correo = str(fila.get("Email_Docente", "")).strip()
        nombre = fila.get("NAME", "Estimado")
        numero_boleta = format_entero(fila.get("numeroBoleta_XML", "N/A"))
        rut = format_entero(fila.get("rutReceptorCompleto_XML", "N/A"))
        rut_emisor = format_entero(fila.get("rutEmisorCompleto_XML", "N/A"))
        monto_xml = fila.get("totalHonorarios_XML", "N/A")
        monto_esperado = fila.get("CUS_TOT_HON", monto_xml)
        emplid = str(fila.get("EMPLID", "") or "").strip()
        rut_razon = str(fila.get("RUT RAZON", "") or "").strip()

        if not utils.validar_email(correo):
            df.at[idx, "Correo_Recepcion_Enviado"] = "❌ Correo inválido"
            stats["failed"] += 1
            continue

        item_key = build_item_key(
            año,
            mes,
            numero_boleta,
            correo,
            kind=kind,
            emplid=emplid,
            rut_razon=rut_razon,
        )
        if not modo_prueba and not force_resend and mail_ledger.was_sent(STAGE_ID, item_key):
            df.at[idx, "Correo_Recepcion_Enviado"] = "⏭ Omitido por idempotencia"
            stats["omitted"] += 1
            continue

        problema = ""
        detalle_descartes = ""
        if kind == "ok":
            asunto = templates.generar_asunto_recepcion(numero_boleta)
            cuerpo_html = templates.generar_cuerpo_recepcion(
                nombre=nombre,
                numero_boleta=numero_boleta,
                rut=rut if rut != "N/A" else (rut_razon or rut),
                rut_emisor=rut_emisor,
                monto=monto_xml if str(monto_xml) not in {"", "N/A", "nan"} else monto_esperado,
            )
        else:
            problema, detalle_descartes = problema_desde_fila(fila)
            asunto = templates.generar_asunto_recepcion_problema(
                mes=mes,
                año=año,
                numero_boleta=numero_boleta,
            )
            cuerpo_html = templates.generar_cuerpo_recepcion_problema(
                nombre=str(nombre),
                mes=mes,
                año=año,
                problema=problema,
                detalle_descartes=detalle_descartes,
                monto_esperado=monto_esperado,
                rut_razon=rut_razon or rut,
                numero_boleta=numero_boleta,
                emplid=emplid,
            )

        preview = _preview_payload(
            idx=ix,
            kind=kind,
            nombre=nombre,
            correo=correo,
            numero_boleta=numero_boleta,
            rut=rut,
            rut_emisor=rut_emisor,
            monto=monto_esperado,
            asunto=asunto,
            cuerpo_html=cuerpo_html,
            item_key=item_key,
            already_sent=False,
            problema=problema,
        )

        if modo_prueba or not allow_send:
            ui.emit("mail.preview", preview)
            if supervision_mode == SupervisionMode.PER_MAIL:
                resp = ui.ask(
                    PromptRequest(
                        kind=InteractionKind.MAIL_REVIEW,
                        title="Vista previa recepción",
                        message="¿Continuar con siguiente? (sin envío — modo prueba)",
                        payload=preview,
                    )
                )
                if resp.action == "cancel":
                    raise SessionCancelled()
                if resp.action == "skip":
                    stats["skipped"] += 1
                    continue
            stats["previewed"] += 1
            continue

        if supervision_mode == SupervisionMode.PER_MAIL:
            ui.emit("mail.preview", preview)
            label = "confirmación" if kind == "ok" else "observación / reenvío"
            resp = ui.ask(
                PromptRequest(
                    kind=InteractionKind.MAIL_REVIEW,
                    title="Confirmar recepción",
                    message=f"¿Enviar correo de {label} a {nombre}?",
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
            ob_id = mail_ledger.record_pending(
                STAGE_ID,
                item_key,
                {"boleta": numero_boleta, "to": correo, "kind": kind},
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
                log_context=f"script5 kind={kind} boleta={numero_boleta}",
            ):
                raise RuntimeError("No se pudo enviar tras reintentos COM")
            mail_ledger.mark_outbox_sent(ob_id)
            if kind == "ok":
                df.at[idx, "Correo_Recepcion_Enviado"] = "✅ Enviado (confirmación)"
                stats["sent_ok"] += 1
            else:
                df.at[idx, "Correo_Recepcion_Enviado"] = "✅ Enviado (observación/reenvío)"
                stats["sent_problema"] += 1
            mail_ledger.mark_sent(STAGE_ID, item_key, details=f"kind={kind};boleta={numero_boleta}")
            ui.log(
                f"Correo enviado a {correo} (boleta {numero_boleta}) [{kind}]",
                level="success",
            )
            stats["sent"] += 1
            time.sleep(1)
        except Exception as e:
            mail_ledger.mark_outbox_failed(ob_id, str(e))
            df.at[idx, "Correo_Recepcion_Enviado"] = f"❌ Error: {e}"
            ui.log(f"Error enviando a {correo}: {e}", level="error")
            stats["failed"] += 1

    return stats
