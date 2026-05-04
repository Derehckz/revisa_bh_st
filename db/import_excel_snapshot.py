"""Importa snapshot histórico desde Solicitud.xlsx hacia PostgreSQL (dual-write bootstrap)."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

if __package__ is None or __package__ == "":
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    _lib = os.path.join(_root, "lib")
    for _p in (_lib, _root):
        if _p not in sys.path:
            sys.path.insert(0, _p)

import pandas as pd
from sqlalchemy import select

from db.models import Boleta, BoletaXmlData
from db.session import SessionLocal
from db.file_repository import get_or_create_periodo
from db.key_builder import build_boleta_key
import utils

BASE_REQUIRED_SOLICITUD_COLUMNS = {
    "EMPLID", "RUT_SIN_DV", "NAME", "EMPL_RCD", "HR_STATUS", "LOCATION", "RUT RAZON", "NOMBRE RAZON",
    "DireccionRazon", "LOCATION.1", "GLOSA", "DESCR", "MONTH", "YEAR", "CUS_INCIDENCIA", "CUS_MTO_CTA",
    "CUS_MTO_BONO", "CUS_MTO_DAPTO", "CUS_TOT_HON", "Email_Docente", "SEDE", "Email_DP",
    "Estado_Recepcion", "Correo Enviado",
}

OPTIONAL_XML_COLUMNS = {
    "Observaciones", "archivo_xml", "rutEmisorCompleto_XML",
    "rutReceptorCompleto_XML", "nombreReceptor_XML", "porcentajeImpuesto_XML", "totalHonorarios_XML",
    "liquidoHonorarios_XML", "impuestoHonorarios_XML", "descripcionLinea_XML", "fechaBoleta_XML",
    "numeroBoleta_XML", "Archivo_XML_Usado", "Observaciones_XML",
}


def detect_solicitud_sheet(path: str) -> str:
    xls = pd.ExcelFile(path, engine="openpyxl")
    for sheet in xls.sheet_names:
        df0 = pd.read_excel(path, sheet_name=sheet, engine="openpyxl", nrows=0)
        cols = set(map(str, df0.columns))
        if BASE_REQUIRED_SOLICITUD_COLUMNS.issubset(cols):
            return sheet
    raise ValueError("No se encontró hoja con columnas mínimas operativas de Solicitud.")


def _to_decimal(value):
    if value is None:
        return None
    try:
        s = str(value).strip()
        if not s or s.lower() == "nan":
            return None
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _clean(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s.lower() == "nan" else s


def _has_valid_xml_payload(row: dict) -> bool:
    archivo_xml = _clean(row.get("archivo_xml")) or _clean(row.get("Archivo_XML_Usado"))
    numero = _clean(row.get("numeroBoleta_XML"))
    total = _clean(row.get("totalHonorarios_XML"))
    estado_rx = _clean(row.get("Estado_Recepcion")).upper()
    if estado_rx not in {"RECIBIDO", "RECIBIDO CON ERROR"}:
        return False
    if not archivo_xml:
        return False
    return bool(numero or total)


def run_import(path: str, sheet_solicitud: str, sheet_resumen: str, anio: int, mes_nombre: str) -> dict:
    meses = [m.lower() for m in ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]]
    mes_num = meses.index(mes_nombre.lower()) + 1
    periodo_id = get_or_create_periodo(anio=anio, mes_num=mes_num, mes_nombre=mes_nombre)
    if periodo_id is None:
        raise RuntimeError("No fue posible crear/obtener periodo en DB.")

    df = pd.read_excel(path, sheet_name=sheet_solicitud, engine="openpyxl")
    try:
        df_resumen = pd.read_excel(path, sheet_name=sheet_resumen, engine="openpyxl")
    except ValueError:
        df_resumen = df

    stats = {
        "solicitud_rows": len(df),
        "resumen_rows": len(df_resumen),
        "boletas_insertadas": 0,
        "boletas_actualizadas": 0,
        "xml_insertados": 0,
        "xml_actualizados": 0,
        "errores": 0,
        "errores_detalle": [],
    }

    with SessionLocal() as session:
        for idx, row in df.iterrows():
            try:
                emplid = _clean(row.get("EMPLID"))
                rut_sin_dv = _clean(row.get("RUT_SIN_DV"))
                boleta_key = build_boleta_key(row.to_dict())
                boleta = None

                if boleta_key:
                    boleta = session.execute(
                        select(Boleta).where(Boleta.periodo_id == periodo_id, Boleta.boleta_key == boleta_key)
                    ).scalar_one_or_none()
                else:
                    if boleta is None and emplid:
                        boleta = session.execute(
                            select(Boleta).where(Boleta.periodo_id == periodo_id, Boleta.emplid == emplid)
                        ).scalar_one_or_none()
                    if boleta is None and rut_sin_dv:
                        boleta = session.execute(
                            select(Boleta).where(Boleta.periodo_id == periodo_id, Boleta.emplid == rut_sin_dv)
                        ).scalar_one_or_none()

                created = False
                if boleta is None:
                    boleta = Boleta(periodo_id=periodo_id, boleta_key=boleta_key, emplid=emplid or rut_sin_dv or None)
                    session.add(boleta)
                    created = True
                elif boleta_key and not boleta.boleta_key:
                    boleta.boleta_key = boleta_key

                boleta.estado_recepcion = _clean(row.get("Estado_Recepcion")) or None
                boleta.observaciones_recepcion = _clean(row.get("Observaciones")) or None
                boleta.glosa = _clean(row.get("GLOSA")) or None
                boleta.rut_razon = _clean(row.get("RUT RAZON")) or None
                boleta.monto_bruto = _to_decimal(row.get("CUS_TOT_HON"))
                boleta.descripcion = _clean(row.get("archivo_xml")) or None
                boleta.updated_at = datetime.now(UTC)

                session.flush()
                if created:
                    stats["boletas_insertadas"] += 1
                else:
                    stats["boletas_actualizadas"] += 1

                has_xml = _has_valid_xml_payload(row.to_dict())
                if not has_xml:
                    continue

                xml_row = session.execute(
                    select(BoletaXmlData).where(BoletaXmlData.boleta_id == boleta.id)
                ).scalar_one_or_none()
                xml_created = False
                if xml_row is None:
                    xml_row = BoletaXmlData(boleta_id=boleta.id)
                    session.add(xml_row)
                    xml_created = True

                xml_row.rut_emisor = _clean(row.get("rutEmisorCompleto_XML")) or None
                xml_row.rut_receptor = _clean(row.get("rutReceptorCompleto_XML")) or None
                xml_row.numero_boleta = _clean(row.get("numeroBoleta_XML")) or None
                xml_row.fecha_boleta = _clean(row.get("fechaBoleta_XML")) or None
                xml_row.total_honorarios = _to_decimal(row.get("totalHonorarios_XML"))
                xml_row.liquido_honorarios = _to_decimal(row.get("liquidoHonorarios_XML"))
                xml_row.impuesto_honorarios = _to_decimal(row.get("impuestoHonorarios_XML"))
                xml_row.porcentaje_impuesto = _to_decimal(row.get("porcentajeImpuesto_XML"))
                xml_row.descripcion_linea = _clean(row.get("descripcionLinea_XML")) or None
                xml_row.observaciones_xml = _clean(row.get("Observaciones_XML")) or None
                xml_row.updated_at = datetime.now(UTC)

                if xml_created:
                    stats["xml_insertados"] += 1
                else:
                    stats["xml_actualizados"] += 1

            except Exception as exc:
                stats["errores"] += 1
                if len(stats["errores_detalle"]) < 20:
                    stats["errores_detalle"].append(
                        {
                            "row_index": idx,
                            "emplid": _clean(row.get("EMPLID")),
                            "boleta_key": build_boleta_key(row.to_dict()),
                            "error": str(exc),
                        }
                    )

        session.commit()

    return stats


def main() -> int:
    utils.asegurar_utf8_salida()
    parser = argparse.ArgumentParser(description="Importar snapshot mensual desde Solicitud.xlsx")
    parser.add_argument("--file", required=True, help="Ruta al Solicitud.xlsx")
    parser.add_argument("--sheet-solicitud", default="AUTO", help="Hoja principal (AUTO detecta por esquema)")
    parser.add_argument("--sheet-resumen", default="Resumen Boletas", help="Hoja resumen (solo informativa)")
    parser.add_argument("--year", type=int, required=True, help="Año del período")
    parser.add_argument("--month-name", required=True, help="Nombre del mes (ej: Abril)")
    args = parser.parse_args()

    utils.print_header("IMPORT HISTORICO A DB", "Solicitud.xlsx -> PostgreSQL")
    sheet_solicitud = args.sheet_solicitud
    if sheet_solicitud.upper() == "AUTO":
        sheet_solicitud = detect_solicitud_sheet(args.file)
        utils.print_info(f"Hoja detectada automáticamente: {sheet_solicitud}")

    stats = run_import(
        path=args.file,
        sheet_solicitud=sheet_solicitud,
        sheet_resumen=args.sheet_resumen,
        anio=args.year,
        mes_nombre=args.month_name,
    )
    utils.print_table(
        "Resultado importación",
        [
            ("Filas Solicitud", stats["solicitud_rows"]),
            ("Filas Resumen", stats["resumen_rows"]),
            ("Boletas insertadas", stats["boletas_insertadas"]),
            ("Boletas actualizadas", stats["boletas_actualizadas"]),
            ("XML insertados", stats["xml_insertados"]),
            ("XML actualizados", stats["xml_actualizados"]),
            ("Errores", stats["errores"]),
        ],
    )
    if stats["errores_detalle"]:
        utils.print_warning("Se registraron errores por fila (mostrando primeros 20):")
        for item in stats["errores_detalle"]:
            utils.print_warning(
                f"fila={item['row_index']} emplid={item['emplid']} key={item['boleta_key']} error={item['error']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
