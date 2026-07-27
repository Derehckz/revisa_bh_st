"""Etapa 1 — envío correo solicitud BH (núcleo compartido CLI + web)."""
from __future__ import annotations

import logging
import os

import pandas as pd

import bh_excel_workbook
import config
import reminder_policy
import schema_validator
import utils
from interaction.exceptions import SessionCancelled
from interaction.port import InteractionPort
from interaction.types import SupervisionMode
from stages.context import Stage1Context
from stages.stage1 import mail as mail_ops
from stages.streamlined import confirm_unless_streamlined

_parse_recordatorio_count = reminder_policy.parse_recordatorio_count


def _batch_preview_table(
    ui: InteractionPort,
    tipo_envio: str,
    cantidad: int,
    mes: str,
    ano: str,
    df,
    indices,
    *,
    fecha_limite: str | None = None,
    horario_limite: str | None = None,
) -> None:
    if tipo_envio == "recordatorio":
        fecha_mostrar = fecha_limite or config.ULT_FECHA_RECORDATORIO
        horario_mostrar = horario_limite or config.HORARIO_RECORDATORIO
        fecha_label = "Fecha límite recordatorio"
        hora_label = "Horario límite recordatorio"
    else:
        fecha_mostrar = fecha_limite or config.ULT_FECHA_RECEPCION
        horario_mostrar = horario_limite or config.HORARIO_RECEPCION
        fecha_label = "Fecha límite recepción"
        hora_label = "Horario límite recepción"
    rows = [
        (fecha_label, str(fecha_mostrar)),
        (hora_label, str(horario_mostrar)),
        ("Correos a enviar", str(cantidad)),
        ("Tipo", tipo_envio),
        ("Período", f"{mes} {ano}"),
        ("Email contabilidad", str(config.EMAIL_CONTABILIDAD)),
        ("Email XML principal", str(config.EMAIL_XML_1)),
    ]
    if config.EMAIL_XML_2:
        rows.append(("Email XML secundario", str(config.EMAIL_XML_2)))
    ui.table(f"Previsualización — {tipo_envio}", rows)

    if df is not None and indices is not None and len(indices) > 0:
        sample_rows: list[tuple[str, str]] = []
        for idx in list(indices)[:5]:
            monto_raw = df.at[idx, "CUS_TOT_HON"] if "CUS_TOT_HON" in df.columns else None
            import email_templates as templates

            sample_rows.append(
                (
                    str(df.at[idx, "NAME"]),
                    f"{df.at[idx, 'Email_Docente']} | {templates._format_monto(monto_raw)}",
                )
            )
        ui.table(
            f"Muestra destinatarios ({min(5, len(indices))}/{len(indices)})",
            sample_rows,
        )
        if len(indices) > 5:
            ui.log(f"... y {len(indices) - 5} destinatarios más", level="info")


class Stage1Service:
    def run(self, ctx: Stage1Context, ui: InteractionPort) -> dict:
        ui.header("Inicio — envío de correos solicitud BH", "Boletas de Honorarios")

        if not os.path.isfile(config.ARCHIVO_ADJUNTO):
            ui.log(f"Archivo adjunto no encontrado: {config.ARCHIVO_ADJUNTO}", level="error")
            return {"ok": False}

        try:
            ano_seleccionado, mes_seleccionado = utils.resolve_año_mes(
                config.RAIZ, ctx.year, ctx.month
            )
        except ValueError as e:
            ui.log(str(e), level="error")
            return {"ok": False}

        ruta_mes = os.path.join(config.RAIZ, ano_seleccionado, mes_seleccionado)
        if ctx.month_dir:
            candidate = ctx.month_dir
            if not os.path.isabs(candidate):
                candidate = os.path.join(config.RAIZ, candidate)
            ruta_mes = os.path.abspath(candidate)
            if not os.path.isdir(ruta_mes):
                ui.log(f"Carpeta no existe: {ruta_mes}", level="error")
                return {"ok": False}

        if ctx.excel_file:
            excel_name = ctx.excel_file
            ruta_archivo_excel = (
                excel_name if os.path.isabs(excel_name) else os.path.join(ruta_mes, excel_name)
            )
            if not os.path.isfile(ruta_archivo_excel):
                ui.log(f"No se encontró Excel: {ruta_archivo_excel}", level="error")
                return {"ok": False}
            archivo_excel = os.path.basename(ruta_archivo_excel)
        else:
            archivos = [f for f in os.listdir(ruta_mes) if f.lower().endswith(".xlsx")]
            if not archivos:
                ui.log(f"No se encontró Excel en {ruta_mes}", level="error")
                return {"ok": False}

            if len(archivos) == 1:
                archivo_excel = archivos[0]
            elif utils.is_non_interactive():
                archivo_excel = archivos[0]
            else:
                archivo_excel = ui.choose_option(
                    "Archivo Excel",
                    "Seleccione el archivo Excel del mes",
                    archivos,
                    icon="📄",
                )
                archivo_excel = str(archivo_excel)

            ruta_archivo_excel = os.path.join(ruta_mes, archivo_excel)
        ruta_logs = os.path.join(ruta_mes, "logs_envios")
        os.makedirs(ruta_logs, exist_ok=True)
        ruta_log_file = os.path.join(ruta_logs, "envio_boletas.log")
        utils.configurar_logging(ruta_log_file)

        ui.table(
            "Contexto de ejecución",
            [
                ("Raíz", config.RAIZ),
                ("Período", f"{mes_seleccionado} {ano_seleccionado}"),
                ("Carpeta mes", ruta_mes),
                ("Excel", ruta_archivo_excel),
                ("Adjunto", config.ARCHIVO_ADJUNTO),
                ("Logs", ruta_log_file),
            ],
        )
        if not confirm_unless_streamlined(
            ui,
            ctx.streamlined,
            "Continuar",
            "¿Continuar con análisis y previsualización?",
            default=False,
        ):
            ui.log("Proceso cancelado por el usuario.", level="warning")
            return {"ok": False, "cancelled": True}

        try:
            with pd.ExcelFile(ruta_archivo_excel, engine="openpyxl") as xls:
                hojas = list(xls.sheet_names)
        except (OSError, ValueError, KeyError) as e:
            ui.log(f"Error al leer Excel: {e}", level="error")
            return {"ok": False}

        if ctx.sheet and ctx.sheet in hojas:
            hoja_seleccionada = ctx.sheet
        elif len(hojas) == 1:
            hoja_seleccionada = hojas[0]
        elif utils.is_non_interactive():
            hoja_seleccionada = utils.pick_excel_sheet(hojas)
        else:
            hoja_seleccionada = str(
                ui.choose_option(
                    "Hoja Excel",
                    "Seleccione la hoja del Excel",
                    hojas,
                    icon="📄",
                )
            )

        df = pd.read_excel(ruta_archivo_excel, sheet_name=hoja_seleccionada, engine="openpyxl")

        canonical_errors, canonical_warnings = schema_validator.validate_for_stage(
            df, "stage1_envio_inicial"
        )
        for w in canonical_warnings:
            logging.warning(f"[stage1] WARN {w}")
            ui.log(f"[schema] {w}", level="warning")
        for e in canonical_errors:
            logging.error(f"[stage1] ERROR {e}")
            ui.log(f"[schema] {e}", level="error")
        if canonical_errors and ctx.strict:
            ui.log("Validación estricta: abortando.", level="error")
            return {"ok": False}

        columna_envio = "Correo Enviado"
        columna_estado = "Estado_Recepcion"
        columna_recordatorios = "Recordatorios Enviados"

        if columna_envio not in df.columns:
            df[columna_envio] = ""
        df[columna_envio] = df[columna_envio].astype(object)
        if columna_recordatorios not in df.columns:
            df[columna_recordatorios] = 0
        df[columna_recordatorios] = df[columna_recordatorios].apply(_parse_recordatorio_count)

        if columna_estado not in df.columns:
            ui.log(f"Falta columna '{columna_estado}'", level="error")
            return {"ok": False}

        ui.log(f"Análisis de {len(df)} filas…", level="info")
        envio_col = df[columna_envio].astype(str).str.lower().str.strip()
        estado_col = df[columna_estado].astype(str).str.lower().str.strip()

        indices_sin_envio = df[
            ~envio_col.str.contains(r"enviado \(original\)", na=False)
            & ~envio_col.str.contains(r"enviado \(recordatorio\)", na=False)
            & ~estado_col.str.contains(r"\brecibido\b", na=False)
        ].index

        indices_recordatorio = reminder_policy.indices_recordatorio(
            df,
            columna_estado,
            columna_recordatorios,
            force_resend=ctx.force_resend,
        )

        if ctx.reminders_only:
            indices_sin_envio = df.iloc[0:0].index
            ui.log(
                "Modo solo recordatorios: no se envían solicitudes originales.",
                level="info",
            )

        ui.log(f"Pendientes envío original: {len(indices_sin_envio)}", level="info")
        ui.log(f"Pendientes recordatorio: {len(indices_recordatorio)}", level="info")

        resumen_rec = reminder_policy.resumen_recordatorios(df, columna_estado, columna_recordatorios)
        ui.table(
            "Resumen recordatorios",
            [
                ("Primera vez (sin recordatorios previos)", str(resumen_rec["cand_1"])),
                ("Reiterados (1 o más recordatorios previos)", str(resumen_rec["cand_reiterados"])),
                ("Total elegibles NO RECIBIDO", str(resumen_rec["total_elegibles"])),
                ("Force-resend", "Sí" if ctx.force_resend else "No"),
            ],
        )

        ui.emit(
            "analysis.ready",
            {
                "original_count": len(indices_sin_envio),
                "reminder_count": len(indices_recordatorio),
                "allow_send": ctx.allow_send,
            },
        )

        from settings import get_bool_setting

        use_ctx_deadlines = get_bool_setting("BH_DEADLINES_VIA_CONTEXT", True)
        deadline_kwargs = {
            "fecha_limite_recepcion": ctx.fecha_limite_recepcion or config.ULT_FECHA_RECEPCION,
            "horario_recepcion": ctx.horario_recepcion or config.HORARIO_RECEPCION,
            "fecha_limite_recordatorio": ctx.fecha_limite_recordatorio or config.ULT_FECHA_RECORDATORIO,
            "horario_recordatorio": ctx.horario_recordatorio or config.HORARIO_RECORDATORIO,
        }

        prev_fecha = config.ULT_FECHA_RECEPCION
        prev_hora = config.HORARIO_RECEPCION
        prev_fecha_rec = config.ULT_FECHA_RECORDATORIO
        prev_hora_rec = config.HORARIO_RECORDATORIO
        if not use_ctx_deadlines:
            if ctx.fecha_limite_recepcion:
                config.ULT_FECHA_RECEPCION = ctx.fecha_limite_recepcion
            if ctx.horario_recepcion:
                config.HORARIO_RECEPCION = ctx.horario_recepcion
            if ctx.fecha_limite_recordatorio:
                config.ULT_FECHA_RECORDATORIO = ctx.fecha_limite_recordatorio
            if ctx.horario_recordatorio:
                config.HORARIO_RECORDATORIO = ctx.horario_recordatorio

        try:
            import period_mail_config

            period_mail_config.save_deadlines(
                ano_seleccionado,
                mes_seleccionado,
                deadline_kwargs,
            )
            ui.log(
                "Plazos de este envío: "
                f"recepción {deadline_kwargs['fecha_limite_recepcion']} "
                f"{deadline_kwargs['horario_recepcion']} | "
                f"recordatorio {deadline_kwargs['fecha_limite_recordatorio']} "
                f"{deadline_kwargs['horario_recordatorio']}",
                level="info",
            )
        except Exception as exc:
            ui.log(f"No se pudieron guardar plazos del período: {exc}", level="warning")

        stats_total: dict[str, int] = {}

        def _send_mail(indices, tipo: str):
            return mail_ops.enviar_correos(
                ui,
                df,
                indices,
                tipo=tipo,
                force_resend=ctx.force_resend,
                allow_send=True,
                supervision_mode=ctx.supervision_mode,
                **deadline_kwargs,
            )

        try:
            if len(indices_sin_envio) > 0:
                if not ctx.allow_send:
                    ui.log(
                        "Sin permiso de envío: no se envían correos originales.",
                        level="warning",
                    )
                else:
                    _batch_preview_table(
                        ui,
                        "correo original",
                        len(indices_sin_envio),
                        mes_seleccionado,
                        ano_seleccionado,
                        df,
                        indices_sin_envio,
                        fecha_limite=deadline_kwargs["fecha_limite_recepcion"],
                        horario_limite=deadline_kwargs["horario_recepcion"],
                    )
                    if ctx.supervision_mode == SupervisionMode.BATCH:
                        if ui.confirm_yes_no(
                            "Envío original",
                            f"¿Confirmar envío de {len(indices_sin_envio)} correos originales?",
                            default=False,
                        ):
                            stats_total.update(_send_mail(indices_sin_envio, "original"))
                        else:
                            ui.log("Envío original cancelado.", level="warning")
                    else:
                        stats_total.update(_send_mail(indices_sin_envio, "original"))
            else:
                ui.log("No hay pendientes de envío original.", level="warning")

            if len(indices_recordatorio) > 0:
                if not ctx.allow_send:
                    ui.log("Sin permiso de envío: no se envían recordatorios.", level="warning")
                else:
                    _batch_preview_table(
                        ui,
                        "recordatorio",
                        len(indices_recordatorio),
                        mes_seleccionado,
                        ano_seleccionado,
                        df,
                        indices_recordatorio,
                        fecha_limite=deadline_kwargs["fecha_limite_recordatorio"],
                        horario_limite=deadline_kwargs["horario_recordatorio"],
                    )
                    if ctx.supervision_mode == SupervisionMode.BATCH:
                        if ui.confirm_yes_no(
                            "Recordatorios",
                            f"¿Confirmar {len(indices_recordatorio)} recordatorios?",
                            default=False,
                        ):
                            r = _send_mail(indices_recordatorio, "recordatorio")
                            for k, v in r.items():
                                stats_total[k] = stats_total.get(k, 0) + v
                        else:
                            ui.log("Recordatorios cancelados.", level="warning")
                    else:
                        r = _send_mail(indices_recordatorio, "recordatorio")
                        for k, v in r.items():
                            stats_total[k] = stats_total.get(k, 0) + v
            else:
                ui.log("No hay destinatarios para recordatorio.", level="warning")

        except SessionCancelled:
            ui.log("Sesión cancelada por el operador.", level="warning")
            if not use_ctx_deadlines:
                config.ULT_FECHA_RECEPCION = prev_fecha
                config.HORARIO_RECEPCION = prev_hora
                config.ULT_FECHA_RECORDATORIO = prev_fecha_rec
                config.HORARIO_RECORDATORIO = prev_hora_rec
            guardado_ok = bh_excel_workbook.replace_sheet_atomically(
                ruta_archivo_excel, hoja_seleccionada, df
            )
            return {
                "ok": False,
                "cancelled": True,
                "excel_saved": guardado_ok,
                "stats": stats_total,
            }

        guardado_ok = bh_excel_workbook.replace_sheet_atomically(
            ruta_archivo_excel, hoja_seleccionada, df
        )
        if guardado_ok:
            ui.log(f"Excel guardado: {ruta_archivo_excel}", level="success")
        else:
            ui.log("Envíos OK pero Excel no guardado (revisar bloqueos/backup).", level="error")
        if not use_ctx_deadlines:
            config.ULT_FECHA_RECEPCION = prev_fecha
            config.HORARIO_RECEPCION = prev_hora
            config.ULT_FECHA_RECORDATORIO = prev_fecha_rec
            config.HORARIO_RECORDATORIO = prev_hora_rec

        ui.emit(
            "session.summary",
            {
                "excel_saved": guardado_ok,
                "excel_path": ruta_archivo_excel,
                "stats": stats_total,
            },
        )
        if guardado_ok:
            ui.header("Proceso finalizado", "Correos procesados")
        return {"ok": guardado_ok, "stats": stats_total, "excel_path": ruta_archivo_excel}
