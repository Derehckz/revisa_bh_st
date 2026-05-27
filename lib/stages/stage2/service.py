"""Etapa 2 — extracción XML/PDF desde Outlook."""
from __future__ import annotations

import os

import utils
from interaction.exceptions import SessionCancelled
from interaction.port import InteractionPort
from outlook_utils import conectar_outlook_ns, filtrar_correos_por_fecha
from stages.context import Stage2Context
from stages.stage2 import extraction as ext

MESES_ES = ext.MESES_ES
FORMATO_FECHA_INPUT = ext.FORMATO_FECHA_INPUT


class Stage2Service:
    def run(self, ctx: Stage2Context, ui: InteractionPort) -> dict:
        ui.header("Extracción de adjuntos Outlook", "Boletas PDF/XML (prefijo bhe_)")

        fecha_inicio, fecha_fin = self._resolve_dates(ctx, ui)
        if fecha_inicio > fecha_fin:
            ui.log("La fecha de inicio no puede ser posterior a la fecha fin.", level="error")
            return {"ok": False}

        anio = str(fecha_inicio.year)
        mes_nombre = MESES_ES[fecha_inicio.month - 1]
        carpeta_mes = os.path.join(ext.CARPETA_BASE, anio, mes_nombre)

        ui.table(
            "Contexto",
            [
                ("Carpeta base", ext.CARPETA_BASE),
                ("Período", f"{mes_nombre} {anio}"),
                ("Carpeta mes", carpeta_mes),
                ("Desde", fecha_inicio.strftime("%d/%m/%Y %H:%M")),
                ("Hasta", fecha_fin.strftime("%d/%m/%Y %H:%M")),
                ("Simulación (dry-run)", "Sí" if ctx.dry_run else "No"),
            ],
        )
        if not ui.confirm_yes_no(
            "Continuar",
            "¿Extraer adjuntos del buzón en ese rango de fechas?",
            default=False,
        ):
            ui.log("Cancelado por el usuario.", level="warning")
            return {"ok": False, "cancelled": True}

        log_file = ext.configurar_logging(fecha_inicio)
        ui.log("Conectando a Outlook…", level="info")

        try:
            outlook_ns = conectar_outlook_ns()
            bandeja = outlook_ns.GetDefaultFolder(6)
            mensajes = filtrar_correos_por_fecha(bandeja, fecha_inicio, fecha_fin)
        except Exception as e:
            ui.log(f"Error Outlook: {e}", level="error")
            return {"ok": False, "error": str(e)}

        if not mensajes:
            ui.log("No se encontraron correos en el rango.", level="warning")
            return {"ok": True, "emails": 0, "guardados": 0}

        ui.log(f"Correos en rango: {len(mensajes)}. Escaneando adjuntos…", level="info")
        rutas, duplicados, emails_ok = ext.escanear_adjuntos(mensajes)

        ui.emit(
            "scan.ready",
            {
                "emails_with_bhe": emails_ok,
                "attachments_planned": len(rutas),
                "duplicates": len(duplicados),
            },
        )
        ui.table(
            "Resumen del escaneo",
            [
                ("Correos con PDF+XML bhe_", str(emails_ok)),
                ("Adjuntos a procesar", str(len(rutas))),
                ("Rutas ya existentes", str(len(duplicados))),
            ],
        )

        if len(rutas) == 0:
            ui.log("No hay adjuntos bhe_ con PDF y XML para guardar.", level="warning")
            return {"ok": True, "emails": emails_ok, "guardados": 0}

        if not ui.confirm_yes_no(
            "Guardar archivos",
            f"¿Proceder a guardar {len(rutas)} adjunto(s)?",
            default=False,
        ):
            ui.log("Guardado cancelado.", level="warning")
            return {"ok": False, "cancelled": True}

        try:
            politica = ext.decidir_politica_duplicados(
                ui, duplicados, preset=ctx.duplicate_policy
            )
        except SessionCancelled:
            ui.log("Cancelado.", level="warning")
            return {"ok": False, "cancelled": True}

        stats = ext.guardar_adjuntos(
            ui, rutas, politica_duplicados=politica, dry_run=ctx.dry_run
        )

        ui.table(
            "Resumen final",
            [
                ("Correos procesados", str(emails_ok)),
                ("Adjuntos guardados", str(stats["guardados"])),
                ("PDF", str(stats["pdf"])),
                ("XML", str(stats["xml"])),
                ("Política duplicados", politica or "—"),
                ("Log", log_file),
            ],
        )

        if ctx.dry_run:
            ui.log("[DRY-RUN] No se escribieron archivos.", level="warning")
        else:
            ui.log("Proceso finalizado.", level="success")

        result = {
            "ok": True,
            "emails": emails_ok,
            "log_file": log_file,
            "duplicate_policy": politica,
            **stats,
        }
        ui.emit("session.summary", result)
        return result

    def _resolve_dates(self, ctx: Stage2Context, ui: InteractionPort):
        if ctx.fecha_inicio and ctx.fecha_fin:
            inicio = ext.parse_fecha_cl(ctx.fecha_inicio)
            fin = ext.parse_fecha_cl(ctx.fecha_fin).replace(hour=23, minute=59, second=59)
            return inicio, fin

        if ctx.fecha_inicio or ctx.fecha_fin:
            raise ValueError("Indique ambas fechas (inicio y fin).")

        if utils.is_non_interactive():
            raise ValueError(
                "Modo no interactivo: use --fecha-inicio y --fecha-fin (dd/mm/yyyy)."
            )

        ui.log("Ingrese el rango de fechas del buzón:", level="info")
        inicio_s = ui.prompt_text(
            "Fecha inicio",
            "Fecha inicio (dd/mm/yyyy):",
        )
        fin_s = ui.prompt_text(
            "Fecha fin",
            "Fecha fin (dd/mm/yyyy):",
        )
        inicio = ext.parse_fecha_cl(inicio_s)
        fin = ext.parse_fecha_cl(fin_s).replace(hour=23, minute=59, second=59)
        return inicio, fin
