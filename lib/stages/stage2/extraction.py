"""Lógica de extracción de adjuntos Outlook (etapa 2)."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import config as cfg
from db import file_repository
from interaction.exceptions import SessionCancelled
from interaction.port import InteractionPort, PromptRequest
from interaction.types import InteractionKind
import utils

CARPETA_BASE = cfg.CARPETA_BASE
ZONA_HORARIA = cfg.ZONA_HORARIA
FORMATO_FECHA_INPUT = "%d/%m/%Y"
MESES_ES = cfg.MESES_ES


def parse_fecha_cl(value: str) -> datetime:
    return datetime.strptime(value.strip(), FORMATO_FECHA_INPUT).replace(tzinfo=ZONA_HORARIA)


def configurar_logging(fecha_referencia: datetime) -> str:
    anio = str(fecha_referencia.year)
    mes_nombre = MESES_ES[fecha_referencia.month - 1]
    carpeta_mes = os.path.join(CARPETA_BASE, anio, mes_nombre)
    os.makedirs(carpeta_mes, exist_ok=True)
    carpeta_logs = os.path.join(carpeta_mes, "logs_extraccion")
    os.makedirs(carpeta_logs, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(carpeta_logs, f"log_{timestamp}.txt")
    utils.configurar_logging(log_file)
    logging.info("=== INICIO EXTRACCIÓN ADJUNTOS OUTLOOK ===")
    logging.info(f"Log: {log_file}")
    return log_file


def decidir_politica_duplicados(
    ui: InteractionPort,
    archivos_repetidos: list[str],
    *,
    preset: str | None = None,
) -> str | None:
    if not archivos_repetidos:
        return None

    if preset and preset.upper() in ("S", "A", "I"):
        politica = preset.upper()
        ui.log(f"Política duplicados (indicada): {politica}", level="info")
        return politica

    import utils as u

    if u.is_non_interactive():
        import os

        politica = os.environ.get("BH_DUPLICADOS", "S").strip().upper()
        if politica not in ("S", "A", "I"):
            politica = "S"
        ui.log(f"Modo no interactivo: duplicados → {politica}", level="info")
        return politica

    ui.log(f"Se detectaron {len(archivos_repetidos)} archivos duplicados.", level="warning")
    ui.emit(
        "duplicates.detected",
        {"count": len(archivos_repetidos), "sample": archivos_repetidos[:20]},
    )

    opciones = ["S", "A", "I"]
    while True:
        resp = ui.ask(
            PromptRequest(
                kind=InteractionKind.CHOICE,
                title="Archivos duplicados",
                message=(
                    "S=Sobrescribir | A=Sufijo (_1…) | I=Ignorar. "
                    f"({len(archivos_repetidos)} duplicados)"
                ),
                payload={
                    "purpose": "duplicate_policy",
                    "options": opciones,
                },
            )
        )
        if resp.action == "cancel":
            raise SessionCancelled()
        val = resp.value
        if isinstance(val, int) and 0 <= val < len(opciones):
            return opciones[val]
        politica = str(val or "S").strip().upper()[:1]
        if politica in opciones:
            return politica
        ui.log("Opción inválida. Use S, A o I.", level="error")


def escanear_adjuntos(mensajes) -> tuple[list[tuple], list[str], int]:
    """Retorna (rutas_a_guardar, duplicados, correos_con_par)."""
    rutas_a_guardar: list[tuple] = []
    archivos_repetidos: list[str] = []
    contador_emails = 0

    for msg in mensajes:
        try:
            adjuntos = [att for att in msg.Attachments if "bhe_" in att.FileName.lower()]
            if not adjuntos:
                continue
            tiene_pdf = any(att.FileName.lower().endswith(".pdf") for att in adjuntos)
            tiene_xml = any(att.FileName.lower().endswith(".xml") for att in adjuntos)
            if not (tiene_pdf and tiene_xml):
                continue

            fecha_msg = msg.ReceivedTime
            try:
                fecha_msg = fecha_msg.replace(tzinfo=ZONA_HORARIA)
            except (TypeError, AttributeError):
                pass

            contador_emails += 1
            anio = str(fecha_msg.year)
            mes_nombre = MESES_ES[fecha_msg.month - 1]
            carpeta_mes = os.path.join(CARPETA_BASE, anio, mes_nombre)

            for att in adjuntos:
                ruta_final = os.path.join(carpeta_mes, att.FileName)
                rutas_a_guardar.append((att, ruta_final, msg))
                if os.path.exists(ruta_final):
                    archivos_repetidos.append(ruta_final)
        except Exception as e:
            logging.error(f"Error en correo: {e}")

    return rutas_a_guardar, archivos_repetidos, contador_emails


def verificar_pares_en_disco(mensajes) -> list[str]:
    """Tras guardar: lista rutas bhe_ PDF/XML del rango que aún no existen en disco.

    Detecta fallos silenciosos (Ignore, COM, ruta incorrecta) que antes hacían
    parecer que el paso 2 «corrió bien» sin dejar archivos.
    """
    faltantes: list[str] = []
    vistos: set[str] = set()
    for msg in mensajes:
        try:
            adjuntos = [att for att in msg.Attachments if "bhe_" in att.FileName.lower()]
            if not adjuntos:
                continue
            tiene_pdf = any(att.FileName.lower().endswith(".pdf") for att in adjuntos)
            tiene_xml = any(att.FileName.lower().endswith(".xml") for att in adjuntos)
            if not (tiene_pdf and tiene_xml):
                continue
            fecha_msg = msg.ReceivedTime
            try:
                fecha_msg = fecha_msg.replace(tzinfo=ZONA_HORARIA)
            except (TypeError, AttributeError):
                pass
            anio = str(fecha_msg.year)
            mes_nombre = MESES_ES[fecha_msg.month - 1]
            carpeta_mes = os.path.join(CARPETA_BASE, anio, mes_nombre)
            for att in adjuntos:
                name = str(att.FileName)
                low = name.lower()
                if not (low.endswith(".pdf") or low.endswith(".xml")):
                    continue
                ruta = os.path.join(carpeta_mes, name)
                key = os.path.normcase(os.path.abspath(ruta))
                if key in vistos:
                    continue
                vistos.add(key)
                if not os.path.isfile(ruta):
                    faltantes.append(ruta)
        except Exception as e:
            logging.error("Error verificando adjuntos en disco: %s", e)
    return faltantes


def guardar_adjuntos(
    ui: InteractionPort,
    rutas_a_guardar: list[tuple],
    *,
    politica_duplicados: str | None,
    dry_run: bool = False,
) -> dict[str, Any]:
    contador_guardados = 0
    contador_pdf = 0
    contador_xml = 0
    total = len(rutas_a_guardar)

    for pos, (att, ruta_final, msg) in enumerate(rutas_a_guardar, start=1):
        ui.progress(pos, total, label="Guardando adjuntos")
        try:
            fecha_msg = msg.ReceivedTime
            try:
                fecha_msg = fecha_msg.replace(tzinfo=ZONA_HORARIA)
            except Exception:
                pass
            anio = str(fecha_msg.year)
            mes_nombre = MESES_ES[fecha_msg.month - 1]
            carpeta_mes = os.path.join(CARPETA_BASE, anio, mes_nombre)
            os.makedirs(carpeta_mes, exist_ok=True)

            ruta_decidida = utils.resolver_conflicto(ruta_final, politica=politica_duplicados)
            if ruta_decidida is None:
                logging.info(f"Ignorado: {att.FileName}")
                continue

            if dry_run:
                logging.info(f"[DRY-RUN] {ruta_decidida}")
                ui.emit("file.saved", {"path": ruta_decidida, "dry_run": True})
            else:
                att.SaveAsFile(ruta_decidida)
                logging.info(f"Guardado: {ruta_decidida}")
                ui.emit("file.saved", {"path": ruta_decidida, "name": att.FileName})
                contador_guardados += 1
                ext = os.path.splitext(ruta_decidida)[1].lower()
                if ext == ".xml":
                    contador_xml += 1
                elif ext == ".pdf":
                    contador_pdf += 1
                periodo_id = file_repository.get_or_create_periodo(
                    anio=int(anio),
                    mes_num=int(fecha_msg.month),
                    mes_nombre=mes_nombre,
                )
                file_repository.save_archivo_event(
                    periodo_id=periodo_id,
                    tipo_archivo=ext.replace(".", "").upper() if ext else "OTRO",
                    nombre_original=att.FileName,
                    ruta_relativa=ruta_decidida,
                    tamano_bytes=None,
                    fecha_origen=fecha_msg if isinstance(fecha_msg, datetime) else None,
                )
        except OSError as e:
            logging.error(f"Error guardando {att.FileName}: {e}")
            ui.log(f"Error guardando {att.FileName}: {e}", level="error")

    return {
        "guardados": contador_guardados,
        "pdf": contador_pdf,
        "xml": contador_xml,
    }
