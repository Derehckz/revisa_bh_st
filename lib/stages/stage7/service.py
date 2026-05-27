"""Etapa 7 — correos de pago (CLI + web)."""
from __future__ import annotations

import logging
import os

import pandas as pd

import config
import schema_validator
import utils
from interaction.exceptions import SessionCancelled
from interaction.port import InteractionPort
from outlook_utils import conectar_outlook_app
import bh_excel_workbook
from stages.context import Stage7Context
from stages.stage7 import mail as mail_ops

RAIZ = config.RAIZ
LOG_FOLDER_NAME = "logs_envios_pagos"


def _guardar_pagos(ruta_excel: str, df) -> bool:
    return bh_excel_workbook.replace_sheet_atomically(ruta_excel, "Pagos", df)


class Stage7Service:
    def run(
        self,
        ctx: Stage7Context,
        ui: InteractionPort,
        *,
        dispatch_outbox: dict[int, int] | None = None,
        dispatch_only_indices: set[int] | None = None,
    ) -> dict:
        ui.header("Envío de correos de pago", "Boletas de Honorarios")

        try:
            año, mes = utils.resolve_año_mes(RAIZ, ctx.year, ctx.month)
        except ValueError as e:
            ui.log(str(e), level="error")
            return {"ok": False}

        ruta_mes = os.path.join(RAIZ, año, mes)
        mes_año_pago = f"{mes} {año}"
        ruta_excel = os.path.join(ruta_mes, "Solicitud.xlsx")
        if not os.path.isfile(ruta_excel):
            ui.log(f"No se encontró Solicitud.xlsx en {ruta_mes}", level="error")
            return {"ok": False}

        ruta_logs = os.path.join(ruta_mes, LOG_FOLDER_NAME)
        os.makedirs(ruta_logs, exist_ok=True)
        utils.configurar_logging(os.path.join(ruta_logs, "envio_pagos.log"))

        if not ui.confirm_yes_no("Continuar", "¿Continuar con la hoja Pagos?", default=False):
            return {"ok": False, "cancelled": True}

        fecha_pago = (ctx.fecha_pago or "").strip()
        if not fecha_pago:
            if utils.is_non_interactive():
                ui.log("Modo no interactivo: use --fecha-pago.", level="error")
                return {"ok": False}
            fecha_pago = ui.prompt_text("Fecha de pago", "Fecha de pago (dd/mm/aaaa)", default="")

        try:
            df = pd.read_excel(ruta_excel, sheet_name="Pagos", engine="openpyxl")
        except Exception as e:
            ui.log(f"Error leyendo hoja Pagos: {e}", level="error")
            return {"ok": False}

        if "MAIL" not in df.columns:
            ui.log("Falta columna MAIL en Pagos.", level="error")
            return {"ok": False}

        if "Correo Enviado" not in df.columns:
            df["Correo Enviado"] = ""

        ui.emit(
            "analysis.ready",
            {"rows": len(df), "allow_send": ctx.allow_send, "fecha_pago": fecha_pago},
        )

        if not ctx.allow_send:
            ui.log("Sin permiso de envío: solo vista previa.", level="warning")
            outlook = None
        else:
            if not ui.confirm_yes_no(
                "Enviar",
                "¿Enviar correos de pago con los montos normalizados?",
                default=False,
            ):
                return {"ok": False, "cancelled": True}
            outlook = conectar_outlook_app()

        try:
            stats = mail_ops.procesar_correos(
                ui,
                df,
                mes_año_pago=mes_año_pago,
                fecha_pago=fecha_pago,
                allow_send=ctx.allow_send,
                force_resend=ctx.force_resend,
                supervision_mode=ctx.supervision_mode,
                outlook=outlook,
                ruta_excel=ruta_excel,
                dispatch_outbox=dispatch_outbox,
                dispatch_only_indices=dispatch_only_indices,
            )
        except SessionCancelled:
            return {"ok": False, "cancelled": True}

        if ctx.allow_send and _guardar_pagos(ruta_excel, df):
            ui.log("Hoja Pagos actualizada.", level="success")

        ui.emit("session.summary", {"ok": True, "stats": stats})
        return {"ok": True, "stats": stats}
