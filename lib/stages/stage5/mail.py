"""Envío / previsualización correos recepción (etapa 5)."""
from __future__ import annotations

import time
from typing import Any, Literal

import email_templates as templates
import mail_ledger
import utils
from db import email_repository
from interaction.exceptions import SessionCancelled
from interaction.port import InteractionPort, PromptRequest
from interaction.types import InteractionKind, SupervisionMode
import bh_outlook_mail

STAGE_ID = "script5.recepcion_send"
EMAIL_COPIA = ""

RecepcionKind = Literal["ok", "problema"]
RecepcionAudience = Literal["ok", "error", "reenvio"]
ReenvioTipo = Literal["recordatorio", "boleta_incorrecta"]


def _is_sent_marker(value: object) -> bool:
    s = str(value or "").strip().lower()
    if not s:
        return False
    return (
        s in {"sí", "si"}
        or "enviado" in s
        or "correo enviado" in s
    )


def _sent_marker_kind(value: object) -> RecepcionKind | Literal["generic"] | None:
    s = str(value or "").strip().lower()
    if not s:
        return None
    if "confirmación" in s or "confirmacion" in s:
        return "ok"
    if "observación" in s or "observacion" in s or "reenvío" in s or "reenvio" in s:
        return "problema"
    if _is_sent_marker(s):
        return "generic"
    return None


def correo_recepcion_cubierto(fila) -> bool:
    """True si ya se envió el tipo de correo que corresponde al estado actual."""
    from stages.stage3.revision_core import glosa_recibida_es_valida

    aud = clasificar_audiencia_recepcion(fila)
    if aud is None:
        return True
    # Excel puede decir RECIBIDO pero la glosa XML no cuadra → debe poder enviarse error.
    if (
        str(fila.get("Estado_Recepcion", "") or "").strip().upper() == "RECIBIDO"
        and not glosa_recibida_es_valida(fila)
    ):
        return False
    needed = audience_to_mail_kind(aud)
    sent = _sent_marker_kind(fila.get("Correo_Recepcion_Enviado", ""))
    if sent is None:
        return False
    if sent == "generic":
        return True
    return sent == needed


def format_entero(valor) -> str:
    import pandas as pd

    if pd.isna(valor):
        return "N/A"
    try:
        return str(int(float(valor)))
    except (TypeError, ValueError):
        return str(valor)


def clasificar_audiencia_recepcion(fila) -> RecepcionAudience | None:
    """
    ok      → RECIBIDO (confirmación)
    error   → RECIBIDO CON ERROR
    reenvio → NO RECIBIDO con descartes (boleta llegó sin match)
    """
    from stages.stage3.revision_core import glosa_recibida_es_valida

    estado = str(fila.get("Estado_Recepcion", "") or "").strip().upper()
    if estado == "RECIBIDO":
        if not glosa_recibida_es_valida(fila):
            return "error"
        return "ok"
    if estado == "RECIBIDO CON ERROR":
        return "error"
    if estado == "NO RECIBIDO":
        # Si no llegó ninguna boleta, etapa 5 opera como recordatorio/reenvío
        # (no como "error" de boleta).
        return "reenvio"
    return None


def clasificar_reenvio_tipo(fila) -> ReenvioTipo | None:
    """Subtipo de audiencia reenvio: sin boleta vs boleta descartada."""
    if clasificar_audiencia_recepcion(fila) != "reenvio":
        return None
    descartes = str(fila.get("Observacion_Descartes", "") or "").strip()
    if descartes:
        return "boleta_incorrecta"
    return "recordatorio"


def fila_recepcion_permitida(
    fila,
    *,
    include_ok: bool,
    include_error: bool,
    include_recordatorio: bool,
    include_boleta_incorrecta: bool,
) -> bool:
    aud = clasificar_audiencia_recepcion(fila)
    if aud == "ok":
        return include_ok
    if aud == "error":
        return include_error
    if aud == "reenvio":
        tipo = clasificar_reenvio_tipo(fila)
        if tipo == "recordatorio":
            return include_recordatorio
        if tipo == "boleta_incorrecta":
            return include_boleta_incorrecta
    return False


def clasificar_fila_recepcion(fila) -> RecepcionKind | None:
    """
    ok       → RECIBIDO (confirmación positiva)
    problema → RECIBIDO CON ERROR, o NO RECIBIDO con descartes (hubo archivos sin match)
    None     → no corresponde correo de recepción (p.ej. NO RECIBIDO sin archivos)
    """
    aud = clasificar_audiencia_recepcion(fila)
    if aud == "ok":
        return "ok"
    if aud in ("error", "reenvio"):
        return "problema"
    return None


def audience_to_mail_kind(audience: RecepcionAudience) -> RecepcionKind:
    return "ok" if audience == "ok" else "problema"


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


def problema_desde_fila(fila) -> tuple[str, str]:
    """(problema principal, detalle) en lenguaje del docente."""
    from stages.docente_mensajes import (
        detalle_descartes_docente,
        observacion_principal_docente,
    )

    obs = str(fila.get("Observaciones", "") or "").strip()
    descartes = str(fila.get("Observacion_Descartes", "") or "").strip()
    estado = str(fila.get("Estado_Recepcion", "") or "").strip().upper()
    numero_boleta = format_entero(fila.get("numeroBoleta_XML", "N/A"))
    boleta_label = f"la boleta n° {numero_boleta}" if numero_boleta not in {"", "N/A"} else "la boleta"

    # Si el detalle aún es técnico (corridas viejas), traducirlo.
    if descartes and (
        "glosa/provisión" in descartes.lower()
        or "monto xml" in descartes.lower()
        or ".xml:" in descartes.lower()
    ):
        detalle = detalle_descartes_docente(descartes, fila)
    else:
        detalle = descartes

    if obs and obs.upper() not in {"OK", "N/A"}:
        # Reescribir obs antiguas demasiado técnicas
        if any(
            t in obs.lower()
            for t in ("línea del excel", "esta línea", "solicitud.xlsx", "xml válido", "monto esperado")
        ):
            obs = observacion_principal_docente(
                [p.strip() for p in descartes.split(";") if p.strip()] or [obs],
                fila,
            )
        return (
            f"Detectamos un problema en {boleta_label}: {obs}. "
            "Debe anularla y reenviar PDF + XML corregidos.",
            detalle,
        )

    if descartes:
        return (
            observacion_principal_docente(
                [p.strip() for p in descartes.split(";") if p.strip()],
                fila,
            ),
            detalle,
        )

    if estado == "NO RECIBIDO":
        return (
            "Aún no recibimos su boleta. Este correo es un recordatorio para enviarla "
            "según la solicitud original.",
            "",
        )
    return (
        f"Detectamos un problema en {boleta_label}. "
        "Revise monto, glosa y razón social; debe anular y reenviar PDF + XML corregidos.",
        "",
    )


def build_recepcion_preview(df) -> dict[str, Any]:
    """Candidatos para la UI (filtros confirmación / error / reenvío)."""
    import pandas as pd

    candidates: list[dict[str, Any]] = []
    counts = {
        "ok": 0,
        "error": 0,
        "reenvio": 0,
        "recordatorio": 0,
        "boleta_incorrecta": 0,
        "ok_pending": 0,
        "error_pending": 0,
        "reenvio_pending": 0,
        "recordatorio_pending": 0,
        "boleta_incorrecta_pending": 0,
        "already_sent": 0,
    }
    for idx, fila in df.iterrows():
        audience = clasificar_audiencia_recepcion(fila)
        if audience is None:
            continue
        already = correo_recepcion_cubierto(fila)
        reenvio_tipo = clasificar_reenvio_tipo(fila) if audience == "reenvio" else None
        counts[audience] += 1
        if reenvio_tipo:
            counts[reenvio_tipo] += 1
        if already:
            counts["already_sent"] += 1
        else:
            counts[f"{audience}_pending"] += 1
            if reenvio_tipo:
                counts[f"{reenvio_tipo}_pending"] += 1

        problema, _detalle = problema_desde_fila(fila) if audience != "ok" else ("", "")
        monto = fila.get("CUS_TOT_HON", fila.get("totalHonorarios_XML", ""))
        import display_format as fmt

        monto_s = fmt.format_monto_cl(monto)

        try:
            row_num = int(idx) + 2  # header + 1-based
        except (TypeError, ValueError):
            row_num = idx

        candidate: dict[str, Any] = {
            "row": row_num,
            "index": idx if isinstance(idx, int) else row_num,
            "audience": audience,
            "kind": audience_to_mail_kind(audience),
            "name": str(fila.get("NAME", "") or "").strip(),
            "email": str(fila.get("Email_Docente", "") or "").strip(),
            "emplid": str(fila.get("EMPLID", "") or "").strip(),
            "estado_recepcion": str(fila.get("Estado_Recepcion", "") or "").strip(),
            "numero_boleta": format_entero(fila.get("numeroBoleta_XML", "N/A")),
            "monto": monto_s,
            "problema": problema[:220] if problema else "",
            "already_sent": already,
            "correo_recepcion": str(fila.get("Correo_Recepcion_Enviado", "") or "").strip(),
        }
        if reenvio_tipo:
            candidate["reenvio_tipo"] = reenvio_tipo
        candidates.append(candidate)

    return {"candidates": candidates, "counts": counts}


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

        if not force_resend and correo_recepcion_cubierto(fila):
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
            from stages.stage1.mail import es_glosa_provisionado

            es_prov = es_glosa_provisionado(fila.get("GLOSA"))
            asunto = templates.generar_asunto_recepcion(numero_boleta, provisionado=es_prov)
            cuerpo_html = templates.generar_cuerpo_recepcion(
                nombre=nombre,
                numero_boleta=numero_boleta,
                rut=rut if rut != "N/A" else (rut_razon or rut),
                rut_emisor=rut_emisor,
                monto=monto_xml if str(monto_xml) not in {"", "N/A", "nan"} else monto_esperado,
                provisionado=es_prov,
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
                glosa=str(fila.get("GLOSA", "") or "").strip(),
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
            email_repository.save_email_event(
                tipo_envio="recepcion_ok" if kind == "ok" else "recepcion_problema",
                to_email=correo,
                cc_email=EMAIL_COPIA or None,
                subject=asunto,
                estado="ENVIADO",
                periodo_label=f"{mes}-{año}",
            )
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
            email_repository.save_email_event(
                tipo_envio="recepcion_ok" if kind == "ok" else "recepcion_problema",
                to_email=correo,
                cc_email=EMAIL_COPIA or None,
                subject=asunto,
                estado="ERROR",
                error_detalle=str(e),
                periodo_label=f"{mes}-{año}",
            )
            ui.log(f"Error enviando a {correo}: {e}", level="error")
            stats["failed"] += 1

    return stats
