"""Etapa 2 — extracción XML/PDF desde Outlook."""
from __future__ import annotations

import os

import utils
from interaction.exceptions import SessionCancelled
from interaction.port import InteractionPort
from outlook_utils import conectar_outlook_ns, filtrar_correos_por_fecha
from stages.context import Stage2Context
from stages.stage2 import extraction as ext
from stages.streamlined import confirm_unless_streamlined

MESES_ES = ext.MESES_ES
FORMATO_FECHA_INPUT = ext.FORMATO_FECHA_INPUT


class Stage2Service:
    def run(self, ctx: Stage2Context, ui: InteractionPort) -> dict:
        ui.header("Extracción de adjuntos Outlook", "Boletas PDF/XML (prefijo bhe_)")

        fecha_inicio, fecha_fin = self._resolve_dates(ctx, ui)
        if fecha_inicio > fecha_fin:
            ui.log("La fecha de inicio no puede ser posterior a la fecha fin.", level="error")
            return {"ok": False}

        if fecha_inicio.day != 1:
            ui.log(
                f"Nota: el rango empieza el {fecha_inicio.strftime('%d/%m/%Y')} "
                "(no el día 1). Solo se bajarán correos desde esa fecha.",
                level="info",
            )

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
                ("Simulación (sin guardar archivos)", "Sí" if ctx.dry_run else "No"),
            ],
        )
        if not confirm_unless_streamlined(
            ui,
            ctx.streamlined,
            "Continuar",
            "¿Extraer adjuntos del buzón en ese rango de fechas?",
            default=False,
        ):
            ui.log("Cancelado por el usuario.", level="warning")
            return {"ok": False, "cancelled": True}

        log_file = ext.configurar_logging(fecha_inicio)
        ui.log("Conectando a Outlook… Si está cerrado, se abrirá solo.", level="info")

        try:
            bus = getattr(ui, "_bus", None)
            if bus is None:
                inner = getattr(ui, "_inner", None)
                bus = getattr(inner, "_bus", None)

            def cancel_check() -> bool:
                return bool(getattr(bus, "cancelled", False)) if bus is not None else False

            outlook_ns = conectar_outlook_ns(
                ensure_running=True,
                wait_s=60,
                cancel_check=cancel_check if bus is not None else None,
                progress_log=lambda m: ui.log(m, level="info"),
            )
            bandeja = outlook_ns.GetDefaultFolder(6)
            mensajes = filtrar_correos_por_fecha(bandeja, fecha_inicio, fecha_fin)
        except SessionCancelled:
            ui.log("Cancelado mientras se abría Outlook.", level="warning")
            return {"ok": False, "cancelled": True}
        except Exception as e:
            ui.log(
                f"Error Outlook: {e}. Ábrelo manualmente si no arrancó solo y reintenta.",
                level="error",
            )
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

        if not confirm_unless_streamlined(
            ui,
            ctx.streamlined,
            "Guardar archivos",
            f"¿Proceder a guardar {len(rutas)} adjunto(s)?",
            default=True,
        ):
            ui.log("Guardado cancelado.", level="warning")
            return {"ok": False, "cancelled": True}

        try:
            politica = ext.decidir_politica_duplicados(
                ui,
                duplicados,
                # Re-ejecutar debe poder refrescar archivos; «I» dejaba boletas
                # nuevas sin bajar si el usuario creía que «ya corrió» el paso 2.
                preset=ctx.duplicate_policy or ("S" if ctx.streamlined else None),
            )
        except SessionCancelled:
            ui.log("Cancelado.", level="warning")
            return {"ok": False, "cancelled": True}

        stats = ext.guardar_adjuntos(
            ui, rutas, politica_duplicados=politica, dry_run=ctx.dry_run
        )

        faltantes = [] if ctx.dry_run else ext.verificar_pares_en_disco(mensajes)
        if faltantes:
            ui.log(
                f"CRÍTICO: {len(faltantes)} adjunto(s) bhe_ del rango siguen sin archivo "
                "en disco tras guardar. Revisa Outlook/permisos y vuelve a ejecutar "
                "con política Sobrescribir (S).",
                level="error",
            )
            for sample in faltantes[:15]:
                ui.log(f"  Falta: {sample}", level="error")
            ui.emit("save.missing", {"count": len(faltantes), "sample": faltantes[:20]})

        ui.table(
            "Resumen final",
            [
                ("Correos procesados", str(emails_ok)),
                ("Adjuntos guardados", str(stats["guardados"])),
                ("PDF", str(stats["pdf"])),
                ("XML", str(stats["xml"])),
                ("Aún faltantes en disco", str(len(faltantes))),
                ("Política duplicados", politica or "—"),
                ("Log", log_file),
            ],
        )

        if ctx.dry_run:
            ui.log("Simulación: no se escribieron archivos.", level="warning")
        else:
            ui.log("Proceso finalizado.", level="success")

        result = {
            "ok": True,
            "emails": emails_ok,
            "log_file": log_file,
            "duplicate_policy": politica,
            "missing_on_disk": len(faltantes),
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
