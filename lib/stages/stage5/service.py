"""Etapa 5 — correos de recepción (CLI + web)."""
from __future__ import annotations

import logging
import os

import pandas as pd

import config
import utils
from interaction.exceptions import SessionCancelled
from interaction.port import InteractionPort
from interaction.types import SupervisionMode
from outlook_utils import conectar_outlook_app
import bh_excel_workbook
from stages.context import Stage5Context
from stages.stage5 import mail as mail_ops

RAIZ = config.RAIZ
LOG_FOLDER_NAME = "logs_envio_recepcion"


class Stage5Service:
    def run(
        self,
        ctx: Stage5Context,
        ui: InteractionPort,
        *,
        dispatch_outbox: dict[int, int] | None = None,
        dispatch_only_indices: set[int] | None = None,
    ) -> dict:
        ui.header("Envío de correos de recepción", "Boletas de Honorarios")

        modo_prueba = not ctx.allow_send
        if not utils.is_non_interactive() and not ctx.supervised:
            modo_prueba = not ui.confirm_yes_no(
                "Modo prueba",
                "¿Modo de prueba? (no envía correos ni modifica Excel)",
                default=True,
            )

        if modo_prueba:
            ui.log("Modo prueba: no se envían correos ni se modifica Excel.", level="warning")

        try:
            año, mes = utils.resolve_año_mes(RAIZ, ctx.year, ctx.month)
        except ValueError as e:
            ui.log(str(e), level="error")
            return {"ok": False}

        ruta_mes = os.path.join(RAIZ, año, mes)
        excel_filename = "Solicitud_prueba.xlsx" if modo_prueba else "Solicitud.xlsx"
        ruta_excel = os.path.join(ruta_mes, excel_filename)
        if not os.path.isfile(ruta_excel):
            ui.log(f"No se encontró {excel_filename} en {ruta_mes}", level="error")
            return {"ok": False}

        ruta_logs = os.path.join(ruta_mes, LOG_FOLDER_NAME)
        os.makedirs(ruta_logs, exist_ok=True)
        utils.configurar_logging(os.path.join(ruta_logs, "envio_recepcion.log"))

        if not ui.confirm_yes_no(
            "Continuar",
            "¿Continuar con lectura del Excel y procesamiento?",
            default=False,
        ):
            return {"ok": False, "cancelled": True}

        try:
            xls = pd.ExcelFile(ruta_excel, engine="openpyxl")
            sheet_name = xls.sheet_names[0]
            df = pd.read_excel(ruta_excel, sheet_name=sheet_name, engine="openpyxl")
        except Exception as e:
            ui.log(f"Error leyendo Excel: {e}", level="error")
            return {"ok": False}

        required = ["Estado_Recepcion", "Email_Docente", "NAME", "numeroBoleta_XML"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            ui.log(f"Columnas faltantes: {missing}", level="error")
            return {"ok": False}

        if "Correo_Recepcion_Enviado" not in df.columns:
            df["Correo_Recepcion_Enviado"] = ""

        df_filtrado = df[df["Estado_Recepcion"] == "RECIBIDO"]
        if df_filtrado.empty:
            ui.log("No hay filas RECIBIDO para procesar.", level="warning")
            return {"ok": True, "stats": {}}

        ui.emit(
            "analysis.ready",
            {"count": len(df_filtrado), "modo_prueba": modo_prueba, "allow_send": ctx.allow_send},
        )

        outlook = None if modo_prueba else conectar_outlook_app()

        try:
            stats = mail_ops.procesar_correos(
                ui,
                df,
                df_filtrado,
                año=año,
                mes=mes,
                modo_prueba=modo_prueba,
                allow_send=ctx.allow_send,
                force_resend=ctx.force_resend,
                supervision_mode=ctx.supervision_mode,
                outlook=outlook,
                dispatch_outbox=dispatch_outbox,
                dispatch_only_indices=dispatch_only_indices,
            )
        except SessionCancelled:
            return {"ok": False, "cancelled": True}

        if not modo_prueba:
            if bh_excel_workbook.replace_sheet_atomically(ruta_excel, sheet_name, df):
                ui.log("Excel actualizado.", level="success")
            else:
                ui.log("No se pudo guardar Excel.", level="error")
                return {"ok": False}

        ui.emit("session.summary", {"ok": True, "stats": stats, "modo_prueba": modo_prueba})
        return {"ok": True, "stats": stats}
