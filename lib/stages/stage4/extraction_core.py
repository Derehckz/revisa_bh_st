"""Núcleo etapa 4 — extracción datos XML → columnas en Excel."""
from __future__ import annotations

import logging
import os

import pandas as pd
import xml.etree.ElementTree as ET

import config
import utils
from db import xml_repository
from db.key_builder import build_boleta_key
from interaction.port import InteractionPort

RAIZ = config.RAIZ

EXTRAER_CAMPOS = [
    "rutEmisor",
    "dvEmisor",
    "rutReceptor",
    "dvReceptor",
    "nombreReceptor",
    "totalHonorarios",
    "liquidoHonorarios",
    "impuestoHonorarios",
    "descripcionLinea",
    "fechaBoleta",
    "numeroBoleta",
    "porcentajeImpuesto",
]

COLUMNAS_OBJETIVO = [
    "rutEmisorCompleto_XML",
    "rutReceptorCompleto_XML",
    "nombreReceptor_XML",
    "porcentajeImpuesto_XML",
    "totalHonorarios_XML",
    "liquidoHonorarios_XML",
    "impuestoHonorarios_XML",
    "descripcionLinea_XML",
    "fechaBoleta_XML",
    "numeroBoleta_XML",
    "Archivo_XML_Usado",
    "Observaciones_XML",
]


def crear_columnas_si_no_existen(df: pd.DataFrame) -> None:
    for col in COLUMNAS_OBJETIVO:
        if col not in df.columns:
            df[col] = ""


def limpiar_columnas_objetivo(df: pd.DataFrame) -> None:
    for col in COLUMNAS_OBJETIVO:
        if col in df.columns:
            df.drop(columns=[col], inplace=True)


def extraer_datos_completos_xml(ruta_xml: str) -> dict:
    try:
        tree = ET.parse(ruta_xml)
        root = tree.getroot()
        datos: dict = {}
        for campo in EXTRAER_CAMPOS:
            elem = utils.find_element_ignore_ns(root, campo)
            datos[campo] = elem.text.strip() if elem is not None and elem.text else ""
        return datos
    except (ET.ParseError, OSError, ValueError, TypeError) as e:
        return {"error": f"Error al leer XML: {e}"}


def procesar_filas(
    df: pd.DataFrame,
    ruta_mes: str,
    *,
    periodo_id: int | None,
    sobrescribir_ok: bool,
    ui: InteractionPort,
) -> tuple[pd.DataFrame, dict]:
    crear_columnas_si_no_existen(df)
    for col in COLUMNAS_OBJETIVO:
        df[col] = df[col].astype(str)

    if sobrescribir_ok:
        limpiar_columnas_objetivo(df)
        crear_columnas_si_no_existen(df)
        for col in COLUMNAS_OBJETIVO:
            df[col] = df[col].astype(str)

    total = len(df)
    exitos = 0
    errores = 0
    omitidos = 0
    pos = 0

    ui.log(f"Iniciando extracción XML para {total} filas…", level="info")

    for idx, fila in df.iterrows():
        pos += 1
        ui.progress(pos, total, label="Extrayendo XML")
        archivo_xml = str(fila.get("archivo_xml", "")).strip()
        observacion_actual = str(fila.get("Observaciones_XML", "")).strip()

        if observacion_actual.lower() == "datos extraídos ok" and not sobrescribir_ok:
            omitidos += 1
            continue

        if not archivo_xml:
            if observacion_actual != "Sin archivo XML relacionado":
                df.at[idx, "Observaciones_XML"] = "Sin archivo XML relacionado"
            continue

        ruta_archivo_xml = os.path.join(ruta_mes, archivo_xml)
        if not os.path.isfile(ruta_archivo_xml):
            df.at[idx, "Observaciones_XML"] = "Archivo XML no encontrado"
            errores += 1
            ui.emit(
                "row.error",
                {"index": int(idx), "archivo": archivo_xml, "reason": "no encontrado"},
            )
            continue

        datos = extraer_datos_completos_xml(ruta_archivo_xml)
        if "error" in datos:
            df.at[idx, "Observaciones_XML"] = datos["error"]
            errores += 1
            continue

        df.at[idx, "rutEmisorCompleto_XML"] = datos.get("rutEmisor", "") + datos.get("dvEmisor", "")
        rut_receptor_xml = datos.get("rutReceptor", "") + datos.get("dvReceptor", "")
        df.at[idx, "rutReceptorCompleto_XML"] = rut_receptor_xml
        df.at[idx, "nombreReceptor_XML"] = datos.get("nombreReceptor", "")
        df.at[idx, "porcentajeImpuesto_XML"] = datos.get("porcentajeImpuesto", "")
        df.at[idx, "totalHonorarios_XML"] = datos.get("totalHonorarios", "")
        df.at[idx, "liquidoHonorarios_XML"] = datos.get("liquidoHonorarios", "")
        df.at[idx, "impuestoHonorarios_XML"] = datos.get("impuestoHonorarios", "")
        df.at[idx, "descripcionLinea_XML"] = datos.get("descripcionLinea", "")
        df.at[idx, "fechaBoleta_XML"] = datos.get("fechaBoleta", "")
        df.at[idx, "numeroBoleta_XML"] = datos.get("numeroBoleta", "")
        df.at[idx, "Archivo_XML_Usado"] = archivo_xml

        observaciones: list[str] = []
        try:
            monto_excel = float(fila.get("CUS_TOT_HON", 0))
            monto_xml = float(datos.get("totalHonorarios", 0))
            if abs(monto_excel - monto_xml) > 0.01:
                observaciones.append(
                    f"Monto Excel ({monto_excel}) distinto a XML ({monto_xml})"
                )
        except (TypeError, ValueError):
            observaciones.append("Error conversión monto")

        rut_receptor_xml_con_guion = f"{datos.get('rutReceptor', '')}-{datos.get('dvReceptor', '')}"
        rut_receptor_excel = str(fila.get("RUT RAZON", "")).strip()
        if rut_receptor_xml_con_guion != rut_receptor_excel:
            observaciones.append(
                f"RUT receptor Excel ({rut_receptor_excel}) distinto a XML ({rut_receptor_xml_con_guion})"
            )

        if observaciones:
            df.at[idx, "Observaciones_XML"] = "; ".join(observaciones)
            errores += 1
        else:
            df.at[idx, "Observaciones_XML"] = "Datos extraídos OK"
            exitos += 1
            ui.emit(
                "row.ok",
                {"index": int(idx), "archivo": archivo_xml, "monto": datos.get("totalHonorarios", "")},
            )

        estado_rx = str(fila.get("Estado_Recepcion", "")).strip().upper()
        if estado_rx in {"RECIBIDO", "RECIBIDO CON ERROR"} and archivo_xml:
            xml_repository.upsert_boleta_xml_data(
                periodo_id=periodo_id,
                boleta_key=build_boleta_key(fila.to_dict(), row_index=idx),
                emplid=str(fila.get("EMPLID", "")).strip() if "EMPLID" in df.columns else None,
                rut_sin_dv=str(fila.get("RUT_SIN_DV", "")).strip()
                if "RUT_SIN_DV" in df.columns
                else None,
                datos=datos,
                observaciones_xml=str(df.at[idx, "Observaciones_XML"]).strip() or None,
            )

    stats = {
        "total": total,
        "exitos": exitos,
        "errores": errores,
        "omitidos": omitidos,
        "sobrescribir_ok": sobrescribir_ok,
    }
    ui.table(
        "Resumen extracción",
        [
            ("Filas", str(total)),
            ("Exitosas", str(exitos)),
            ("Errores / advertencias", str(errores)),
            ("Omitidas (ya OK)", str(omitidos)),
            ("Sobrescribir previos", "Sí" if sobrescribir_ok else "No"),
        ],
    )
    ui.emit("analysis.complete", stats)
    return df, stats


def guardar_excel(df: pd.DataFrame, ruta_excel: str, hoja: str, ui: InteractionPort) -> bool:
    try:
        hojas = pd.read_excel(ruta_excel, sheet_name=None, engine="openpyxl")
        hojas[hoja] = df

        def _writer(tmp_path: str) -> None:
            with pd.ExcelWriter(tmp_path, engine="openpyxl", mode="w") as writer:
                for nombre_hoja, df_hoja in hojas.items():
                    df_hoja.to_excel(writer, index=False, sheet_name=nombre_hoja)

        utils.atomic_excel_write(ruta_excel, _writer)
        ui.log(f"Excel guardado: {ruta_excel}", level="success")
        return True
    except PermissionError as e:
        ui.log(f"Excel bloqueado (ciérrelo en Excel): {e}", level="error")
        return False
    except (OSError, IOError, ValueError, KeyError) as e:
        ui.log(f"Error guardando Excel: {e}", level="error")
        logging.exception("Fallo al escribir Excel")
        return False
