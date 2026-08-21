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

from db.models import Boleta, BoletaXmlData, Docente, Institucion
from db.session import SessionLocal
from db.file_repository import get_or_create_periodo
from db.key_builder import build_boleta_key, is_provisionado_glosa
from db.solicitud_row import merge_solicitud_row, serialize_solicitud_row
from db.state_projection import (
    classify_mail_recepcion_status,
    classify_recepcion_status,
    classify_xml_status,
)
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
    with pd.ExcelFile(path, engine="openpyxl") as xls:
        for sheet in xls.sheet_names:
            df0 = pd.read_excel(xls, sheet_name=sheet, nrows=0)
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


def _key_kind(key: str) -> str:
    s = _clean(key)
    if "|NB|" in s:
        return "NB"
    if "|XML|" in s:
        return "XML"
    if "|MTO|" in s:
        return "MTO"
    return ""


def _should_replace_key(old_key: str | None, new_key: str | None) -> bool:
    old_kind = _key_kind(old_key or "")
    new_kind = _key_kind(new_key or "")
    if not _clean(new_key):
        return False
    if not _clean(old_key):
        return True
    # Subir de una clave "débil" (MTO) a una más estable (NB/XML).
    if old_kind == "MTO" and new_kind in {"NB", "XML"}:
        return True
    return False


def _normalize_location_code(value: object) -> str:
    text = _clean(value)
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _link_docente_institucion(
    session,
    boleta: Boleta,
    *,
    emplid: str,
    rut_sin_dv: str,
    rut_razon: str,
    location: str,
    nombre: str = "",
    email: str = "",
    sede: str = "",
    email_dp: str = "",
) -> None:
    docente = None
    if emplid:
        docente = session.execute(select(Docente).where(Docente.rut == emplid)).scalar_one_or_none()
    if docente is None and rut_sin_dv:
        docente = session.execute(
            select(Docente).where(Docente.rut_sin_dv == rut_sin_dv)
        ).scalar_one_or_none()
    if docente is None and emplid and nombre:
        docente = Docente(
            rut=emplid,
            rut_sin_dv=rut_sin_dv or None,
            nombre_completo=nombre,
            activo="true",
        )
        session.add(docente)
        session.flush()
    if docente is not None:
        if nombre and not (docente.nombre_completo or "").strip():
            docente.nombre_completo = nombre
        if email and not (docente.email_personal or "").strip():
            docente.email_personal = email
        elif email:
            docente.email_personal = email
        if sede and not (docente.sede or "").strip():
            docente.sede = sede
        if email_dp and not (docente.email_dp or "").strip():
            docente.email_dp = email_dp
        boleta.docente_id = docente.id
    if boleta.institucion_id is None:
        inst = None
        loc = _normalize_location_code(location)
        if loc:
            inst = session.execute(
                select(Institucion).where(Institucion.codigo_location == loc)
            ).scalar_one_or_none()
        if inst is None and rut_razon:
            inst = session.execute(
                select(Institucion).where(Institucion.rut_razon == rut_razon)
            ).scalar_one_or_none()
        if inst is not None:
            boleta.institucion_id = inst.id


def _legacy_mto_keys(boleta_key: str) -> list[str]:
    """Claves MTO anteriores, sin el discriminador |P|0/1 de provisionado."""
    if "|P|" not in (boleta_key or ""):
        return []
    base, _rest = boleta_key.rsplit("|P|", 1)
    return [base] if base else []


def select_compatible_boleta(
    rows: list,
    *,
    rut_razon: str,
    monto_decimal: Decimal | None,
    incoming_prov: bool,
):
    """Elige la boleta del mismo docente/institución/provisión/monto.

    No reutiliza «la única fila del EMPLID»: eso fusionaba IP+CFT y
    maestro+PROVISIONADO en una sola boleta.
    """
    compatible = []
    for row in rows:
        row_rut = str(getattr(row, "rut_razon", None) or "").strip()
        if rut_razon and row_rut and row_rut != rut_razon:
            continue
        if is_provisionado_glosa(getattr(row, "glosa", None)) != incoming_prov:
            continue
        compatible.append(row)
    if not compatible:
        return None
    if monto_decimal is not None:
        matches = [r for r in compatible if r.monto_bruto == monto_decimal]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            mto = [r for r in matches if _key_kind(r.boleta_key or "") == "MTO"]
            if len(mto) == 1:
                return mto[0]
        return None
    if len(compatible) == 1:
        return compatible[0]
    return None


def _find_existing_boleta(
    *,
    session,
    periodo_id: int,
    boleta_key: str,
    emplid: str,
    rut_sin_dv: str,
    monto_decimal: Decimal | None,
    rut_razon: str,
    glosa: str = "",
) -> Boleta | None:
    incoming_prov = is_provisionado_glosa(glosa)
    keys_to_try = [boleta_key] if boleta_key else []
    keys_to_try.extend(_legacy_mto_keys(boleta_key))
    for key in keys_to_try:
        row = session.execute(
            select(Boleta).where(Boleta.periodo_id == periodo_id, Boleta.boleta_key == key)
        ).scalar_one_or_none()
        if row is None:
            continue
        if key != boleta_key and is_provisionado_glosa(row.glosa) != incoming_prov:
            continue
        return row

    candidate_ids = [c for c in {emplid, rut_sin_dv} if c]
    for candidate_id in candidate_ids:
        rows = session.execute(
            select(Boleta).where(Boleta.periodo_id == periodo_id, Boleta.emplid == candidate_id)
        ).scalars().all()
        if not rows:
            continue
        found = select_compatible_boleta(
            rows,
            rut_razon=rut_razon,
            monto_decimal=monto_decimal,
            incoming_prov=incoming_prov,
        )
        if found is not None:
            return found
    return None


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
                rut_razon = _clean(row.get("RUT RAZON"))
                monto_decimal = _to_decimal(row.get("CUS_TOT_HON"))
                glosa = _clean(row.get("GLOSA"))
                boleta = _find_existing_boleta(
                    session=session,
                    periodo_id=periodo_id,
                    boleta_key=boleta_key,
                    emplid=emplid,
                    rut_sin_dv=rut_sin_dv,
                    monto_decimal=monto_decimal,
                    rut_razon=rut_razon,
                    glosa=glosa,
                )

                created = False
                if boleta is None:
                    boleta = Boleta(periodo_id=periodo_id, boleta_key=boleta_key, emplid=emplid or rut_sin_dv or None)
                    session.add(boleta)
                    created = True
                elif _should_replace_key(boleta.boleta_key, boleta_key):
                    boleta.boleta_key = boleta_key

                boleta.estado_recepcion = _clean(row.get("Estado_Recepcion")) or None
                boleta.observaciones_recepcion = _clean(row.get("Observaciones")) or None
                recepcion_status, reason, glosa_mode = classify_recepcion_status(row.to_dict())
                boleta.recepcion_status = recepcion_status
                boleta.xml_status = classify_xml_status(row.to_dict())
                boleta.mail_recepcion_status = classify_mail_recepcion_status(row.to_dict())
                boleta.glosa_match_mode = glosa_mode
                boleta.effective_status_reason = reason
                boleta.glosa = _clean(row.get("GLOSA")) or None
                boleta.rut_razon = rut_razon or None
                boleta.monto_bruto = monto_decimal
                boleta.descripcion = _clean(row.get("archivo_xml")) or None
                boleta.empl_rcd = _clean(row.get("EMPL_RCD")) or None
                boleta.solicitud_row = merge_solicitud_row(
                    boleta.solicitud_row,
                    serialize_solicitud_row(row.to_dict()),
                )
                _link_docente_institucion(
                    session,
                    boleta,
                    emplid=emplid,
                    rut_sin_dv=rut_sin_dv,
                    rut_razon=rut_razon,
                    location=_clean(row.get("LOCATION")),
                    nombre=_clean(row.get("NAME")),
                    email=_clean(row.get("Email_Docente")),
                    sede=_clean(row.get("SEDE")),
                    email_dp=_clean(row.get("Email_DP")),
                )
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
