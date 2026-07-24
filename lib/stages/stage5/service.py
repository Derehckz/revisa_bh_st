"""Etapa 5 — correos de recepción (CLI + web)."""
from __future__ import annotations

import json
import logging
import os
import re

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
_SENT_LOG_RE = re.compile(
    r"Correo enviado a\s+(?P<email>[^\s]+)\s+\(boleta\s+(?P<boleta>[^)]+)\)",
    re.IGNORECASE,
)


def _is_sent_marker(value: object) -> bool:
    s = str(value or "").strip().lower()
    if not s:
        return False
    return (
        s in {"sí", "si"}
        or "enviado" in s
        or "correo enviado" in s
    )


class Stage5Service:
    @staticmethod
    def _sent_keys_from_logs(log_dir: str, año: str, mes: str) -> set[str]:
        keys: set[str] = set()
        if not os.path.isdir(log_dir):
            return keys

        for name in os.listdir(log_dir):
            if not (name.endswith(".jsonl") or name.endswith(".log")):
                continue
            path = os.path.join(log_dir, name)
            if not os.path.isfile(path):
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    for raw in fh:
                        line = raw.strip()
                        if not line:
                            continue
                        msg = line
                        if name.endswith(".jsonl"):
                            try:
                                row = json.loads(line)
                                msg = str(row.get("message") or "")
                            except Exception:
                                msg = line
                        m = _SENT_LOG_RE.search(msg)
                        if not m:
                            continue
                        email = m.group("email").strip()
                        boleta = m.group("boleta").strip()
                        keys.add(mail_ops.build_item_key(año, mes, boleta, email))
            except OSError:
                continue
        return keys

    @staticmethod
    def _apply_log_sent_markers(df: pd.DataFrame, *, año: str, mes: str, sent_keys: set[str]) -> int:
        if not sent_keys:
            return 0
        updated = 0
        for idx, row in df.iterrows():
            correo = str(row.get("Email_Docente", "")).strip()
            boleta = mail_ops.format_entero(row.get("numeroBoleta_XML", "N/A"))
            if not correo or not boleta:
                continue
            item_key = mail_ops.build_item_key(año, mes, boleta, correo)
            if item_key in sent_keys and not _is_sent_marker(row.get("Correo_Recepcion_Enviado", "")):
                df.at[idx, "Correo_Recepcion_Enviado"] = "✅ Enviado (detectado por log)"
                updated += 1
        return updated

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
            modo_prueba = ui.confirm_yes_no(
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
        ruta_excel = os.path.join(ruta_mes, "Solicitud.xlsx")
        if not os.path.isfile(ruta_excel):
            ui.log(f"No se encontró Excel: {ruta_excel}", level="error")
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
            with pd.ExcelFile(ruta_excel, engine="openpyxl") as xls:
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

        sent_from_logs = self._sent_keys_from_logs(ruta_logs, año, mes)
        restored_count = self._apply_log_sent_markers(df, año=año, mes=mes, sent_keys=sent_from_logs)
        if restored_count > 0:
            ui.log(
                f"Histórico: se marcaron {restored_count} fila(s) como enviadas según logs previos.",
                level="info",
            )

        df_filtrado = df[df["Estado_Recepcion"] == "RECIBIDO"]
        if df_filtrado.empty:
            ui.log("No hay filas RECIBIDO para procesar.", level="warning")
            return {"ok": True, "stats": {}}

        df_pendientes = df_filtrado[~df_filtrado["Correo_Recepcion_Enviado"].apply(_is_sent_marker)]
        if df_pendientes.empty:
            ui.log("No hay correos de recepción pendientes; todo ya fue enviado.", level="warning")
            return {"ok": True, "stats": {}}

        ui.emit(
            "analysis.ready",
            {"count": len(df_pendientes), "modo_prueba": modo_prueba, "allow_send": ctx.allow_send},
        )

        outlook = None if modo_prueba else conectar_outlook_app()

        try:
            stats = mail_ops.procesar_correos(
                ui,
                df,
                df_pendientes,
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
        rows = [
            ("Pendientes procesados", str(len(df_pendientes))),
            ("Enviados", str(stats.get("sent", 0))),
            ("Previsualizados", str(stats.get("previewed", 0))),
            ("Omitidos", str(stats.get("omitted", 0))),
            ("Saltados por operador", str(stats.get("skipped", 0))),
            ("Con error", str(stats.get("failed", 0))),
            ("Modo", "Prueba (sin envío real)" if modo_prueba else "Envío real"),
        ]
        ui.table("Resumen etapa 5 — recepción", rows)
        ui.header("Etapa 5 finalizada", "Revisa resumen y estado en Solicitud.xlsx")

        ui.emit("session.summary", {"ok": True, "stats": stats, "modo_prueba": modo_prueba})
        return {"ok": True, "stats": stats}
