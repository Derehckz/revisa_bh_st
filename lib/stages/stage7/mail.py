"""Envío / previsualización correos de pago (etapa 7)."""
from __future__ import annotations

import logging
import re
import time
from typing import Any

import pandas as pd

import email_outbox
import email_templates as templates
import mail_ledger
import idempotency_store
import utils
from interaction.exceptions import SessionCancelled
from interaction.port import InteractionPort, PromptRequest
from interaction.types import InteractionKind, SupervisionMode
import bh_outlook_mail

STAGE_ID = "script7.pago_send"
EMAIL_COPIA = ""


def normalizar_monto_liquido(valor):
    """Convierte montos de hoja Pagos (escala Contabilidad) a pesos enteros para el correo.

    Contabilidad envía en el mail/CSV valores como 108.000, 91.530, 542.4 o 339
    (miles de pesos). En la hoja Pagos quedan como 108.0 / 91.53 / 542.4 / 339.
    Regla: si |valor| < 1000 → ×1000; si ya es pesos (>=1000) se deja.
    """
    if pd.isna(valor):
        return 0
    if isinstance(valor, bool):
        return int(valor)
    if isinstance(valor, int):
        if abs(valor) < 1000:
            return int(valor * 1000)
        return valor
    if isinstance(valor, float):
        if abs(valor) < 1000:
            return int(round(valor * 1000))
        return int(round(valor))

    texto = str(valor).strip()
    if not texto:
        return 0
    texto = texto.replace("$", "").replace(" ", "").replace("\u00a0", "")
    texto = re.sub(r"[^\d,.\-]", "", texto)
    if not texto or texto in {".", ",", "-", "-.", ".-"}:
        return 0

    # 1.234.567 o 108.000 (miles CL con puntos)
    if "." in texto and "," not in texto:
        partes = texto.split(".")
        if len(partes) > 1 and all(p.isdigit() or (i == 0 and p.lstrip("-").isdigit()) for i, p in enumerate(partes)):
            cuerpo0 = partes[0].lstrip("-")
            if partes[0].startswith("-"):
                sign = -1
            else:
                sign = 1
            if all(len(p) == 3 for p in partes[1:]) and cuerpo0.isdigit():
                try:
                    return sign * int(cuerpo0 + "".join(partes[1:]))
                except ValueError:
                    pass
    # 1.234,56 → CL
    if "." in texto and "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        partes = texto.split(",")
        if len(partes) > 1 and all(p.isdigit() for p in partes) and all(len(p) == 3 for p in partes[1:]):
            texto = "".join(partes)
        else:
            texto = texto.replace(",", ".")

    try:
        num = float(texto)
    except (TypeError, ValueError):
        return 0
    if abs(num) < 1000:
        return int(round(num * 1000))
    return int(round(num))


def normalizar_nro_cuenta(valor):
    if pd.isna(valor):
        return ""
    texto = str(valor).strip()
    if not texto:
        return ""
    if texto.isdigit():
        return texto
    texto_sin_espacios = texto.replace(" ", "")
    try:
        numero = float(texto_sin_espacios.replace(",", "."))
        if numero.is_integer():
            return str(int(numero))
    except (TypeError, ValueError):
        pass
    return texto


def build_item_key(
    mes_año_pago: str,
    rut,
    correo: str,
    codigo_origen: str,
    n_boleta,
    tipo_cuenta,
    nro_cuenta: str,
    monto: int,
) -> str:
    return (
        f"{mes_año_pago}|{rut}|{correo}|{codigo_origen}|{n_boleta}|{tipo_cuenta}|{nro_cuenta}|{monto}"
    ).lower()


def _preview_payload(
    *,
    idx: int,
    nombre,
    correo: str,
    monto_correo: str,
    asunto: str,
    cuerpo_html: str,
    item_key: str,
) -> dict[str, Any]:
    return {
        "index": idx,
        "tipo": "pago",
        "docente": {"name": str(nombre), "email": correo, "monto": monto_correo},
        "mail": {
            "to": correo,
            "cc": EMAIL_COPIA or "",
            "subject": asunto,
            "html_body": cuerpo_html,
        },
        "idempotency_key": item_key,
        "cli_summary": f"{nombre} <{correo}> — {monto_correo}",
    }


def procesar_correos(
    ui: InteractionPort,
    df,
    *,
    mes_año_pago: str,
    fecha_pago: str,
    allow_send: bool,
    force_resend: bool,
    supervision_mode: SupervisionMode,
    outlook,
    ruta_excel: str,
    dispatch_outbox: dict[int, int] | None = None,
    dispatch_only_indices: set[int] | None = None,
) -> dict[str, int]:
    stats = {"sent": 0, "failed": 0, "skipped": 0, "previewed": 0}
    pending = [
        idx
        for idx, fila in df.iterrows()
        if utils.validar_email(str(fila.get("MAIL", "")).strip())
        and "enviado" not in str(fila.get("Correo Enviado", "")).strip().lower()
    ]
    total = len(pending)

    for pos, idx in enumerate(pending, start=1):
        ui.progress(pos, total, label="Pagos")
        fila = df.loc[idx]
        try:
            ix = int(idx)
        except (TypeError, ValueError):
            ix = idx
        if dispatch_only_indices is not None and ix not in dispatch_only_indices:
            continue

        correo = str(fila.get("MAIL", "")).strip()
        nombre = fila.get("Nombre", "")
        rut = fila.get("ID", "")
        banco = fila.get("BANCO", "")
        tipo_cuenta = fila.get("FORMA PAGO", "")
        nro_cuenta = normalizar_nro_cuenta(fila.get("NªCUENTA", ""))
        n_boleta = fila.get("Boleta", fila.get("Número Boleta", ""))
        codigo_origen = str(
            fila.get(
                "LOCATION",
                fila.get("CODIGO", fila.get("INS", fila.get("Ubicación", ""))),
            )
        ).strip()
        monto = normalizar_monto_liquido(fila.get("LÍQUIDO", 0))
        monto_correo = f"${monto:,.0f}".replace(",", ".")

        item_key = build_item_key(
            mes_año_pago, rut, correo, codigo_origen, n_boleta, tipo_cuenta, nro_cuenta, monto
        )
        if not force_resend and mail_ledger.was_sent(STAGE_ID, item_key):
            df.at[idx, "Correo Enviado"] = "⏭ Omitido por idempotencia"
            stats["skipped"] += 1
            continue

        asunto = templates.generar_asunto_pago(nombre, mes_año_pago)
        cuerpo_html = templates.generar_cuerpo_pago(
            nombre=nombre,
            mes_año_pago=mes_año_pago,
            fecha_pago=fecha_pago,
            banco=banco,
            tipo_cuenta=tipo_cuenta,
            nro_cuenta=nro_cuenta,
            monto=monto,
        )
        preview = _preview_payload(
            idx=ix,
            nombre=nombre,
            correo=correo,
            monto_correo=monto_correo,
            asunto=asunto,
            cuerpo_html=cuerpo_html,
            item_key=item_key,
        )

        if not allow_send:
            ui.emit("mail.preview", preview)
            if supervision_mode == SupervisionMode.PER_MAIL:
                resp = ui.ask(
                    PromptRequest(
                        kind=InteractionKind.MAIL_REVIEW,
                        title="Vista previa pago",
                        message=f"{nombre} — {monto_correo} (sin envío)",
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
            resp = ui.ask(
                PromptRequest(
                    kind=InteractionKind.MAIL_REVIEW,
                    title="Confirmar pago",
                    message=f"¿Enviar correo de pago a {nombre}?",
                    payload=preview,
                )
            )
            if resp.action == "cancel":
                raise SessionCancelled()
            if resp.action == "skip":
                stats["skipped"] += 1
                continue

        if dispatch_outbox is not None and ix in dispatch_outbox:
            ob_id = dispatch_outbox[ix]
        else:
            ob_id = mail_ledger.record_pending(
                STAGE_ID,
                item_key,
                {"to": correo, "boleta": str(n_boleta), "monto": monto},
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
                log_context=f"script7 fila={ix + 1}",
            ):
                raise RuntimeError("No se pudo enviar tras reintentos COM")
            mail_ledger.mark_outbox_sent(ob_id)
            df.at[idx, "Correo Enviado"] = "✅ Enviado"
            mail_ledger.mark_sent(STAGE_ID, item_key, details=f"boleta={n_boleta}")
            stats["sent"] += 1
            time.sleep(1)
        except Exception as e:
            mail_ledger.mark_outbox_failed(ob_id, str(e))
            df.at[idx, "Correo Enviado"] = f"❌ Error: {e}"
            stats["failed"] += 1

    return stats
