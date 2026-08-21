"""Exporta Solicitud.xlsx detallada desde PostgreSQL (fila completa en solicitud_row)."""
from __future__ import annotations

import io
import os
from typing import Any

import config
import pandas as pd
from sqlalchemy import select

from db.models import Boleta, BoletaXmlData, Docente, Institucion, Periodo
from db.session import SessionLocal
from db.solicitud_row import SOLICITUD_COLUMNS, apply_live_overrides, serialize_solicitud_row


def _month_dir(year: int | str, month: str) -> str:
    return os.path.join(config.RAIZ, str(year), str(month).strip())


def _mail_recepcion_label(status: str | None) -> str:
    s = str(status or "").upper()
    if s == "ENVIADO_OK":
        return "Enviado (confirmación)"
    if s == "ENVIADO_PROBLEMA":
        return "Enviado (observación/reenvío)"
    return ""


def _xml_obs(xml_status: str | None, obs: str | None) -> str:
    if obs:
        return str(obs)
    if str(xml_status or "").upper() == "OK":
        return "Datos extraídos OK"
    return ""


def _blank_to_none(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _row_from_boleta(
    boleta: Boleta,
    xml: BoletaXmlData | None,
    docente: Docente | None,
    institucion: Institucion | None,
    periodo: Periodo,
) -> dict[str, Any]:
    base = serialize_solicitud_row(boleta.solicitud_row or {})

    # Completa con relaciones / campos canónicos si el snapshot no los trae.
    fills = {
        "EMPLID": boleta.emplid or (docente.rut if docente else None),
        "RUT_SIN_DV": (docente.rut_sin_dv if docente else None) or base.get("RUT_SIN_DV"),
        "NAME": (docente.nombre_completo if docente else None) or base.get("NAME"),
        "EMPL_RCD": boleta.empl_rcd or base.get("EMPL_RCD"),
        "LOCATION": (institucion.codigo_location if institucion else None) or base.get("LOCATION"),
        "LOCATION.1": (institucion.codigo_location if institucion else None) or base.get("LOCATION.1"),
        "RUT RAZON": boleta.rut_razon or (institucion.rut_razon if institucion else None),
        "NOMBRE RAZON": (institucion.nombre_razon if institucion else None) or base.get("NOMBRE RAZON"),
        "DireccionRazon": (institucion.direccion_razon if institucion else None) or base.get("DireccionRazon"),
        "GLOSA": boleta.glosa,
        "MONTH": periodo.mes_nombre,
        "YEAR": periodo.anio,
        "CUS_TOT_HON": float(boleta.monto_bruto) if boleta.monto_bruto is not None else base.get("CUS_TOT_HON"),
        "Email_Docente": (docente.email_personal if docente else None) or base.get("Email_Docente"),
        "SEDE": (docente.sede if docente else None) or base.get("SEDE"),
        "Email_DP": (docente.email_dp if docente else None) or base.get("Email_DP"),
    }
    for key, value in fills.items():
        if _blank_to_none(base.get(key)) is None and _blank_to_none(value) is not None:
            base[key] = value

    archivo = boleta.descripcion or base.get("archivo_xml") or base.get("Archivo_XML_Usado")
    overrides = {
        "Estado_Recepcion": boleta.estado_recepcion or "",
        "Observaciones": boleta.observaciones_recepcion or "",
        "archivo_xml": archivo or "",
        "Archivo_XML_Usado": archivo or "",
        "Correo_Recepcion_Enviado": _mail_recepcion_label(boleta.mail_recepcion_status)
        or base.get("Correo_Recepcion_Enviado")
        or "",
        "rutEmisorCompleto_XML": (xml.rut_emisor if xml else None) or base.get("rutEmisorCompleto_XML") or "",
        "rutReceptorCompleto_XML": (xml.rut_receptor if xml else None) or base.get("rutReceptorCompleto_XML") or "",
        "nombreReceptor_XML": base.get("nombreReceptor_XML")
        or (institucion.nombre_razon if institucion else None)
        or "",
        "porcentajeImpuesto_XML": (
            float(xml.porcentaje_impuesto) if xml and xml.porcentaje_impuesto is not None else base.get("porcentajeImpuesto_XML")
        ),
        "totalHonorarios_XML": (
            float(xml.total_honorarios) if xml and xml.total_honorarios is not None else base.get("totalHonorarios_XML")
        ),
        "liquidoHonorarios_XML": (
            float(xml.liquido_honorarios) if xml and xml.liquido_honorarios is not None else base.get("liquidoHonorarios_XML")
        ),
        "impuestoHonorarios_XML": (
            float(xml.impuesto_honorarios) if xml and xml.impuesto_honorarios is not None else base.get("impuestoHonorarios_XML")
        ),
        "descripcionLinea_XML": (xml.descripcion_linea if xml else None) or base.get("descripcionLinea_XML") or "",
        "fechaBoleta_XML": (xml.fecha_boleta if xml else None) or base.get("fechaBoleta_XML") or "",
        "numeroBoleta_XML": (xml.numero_boleta if xml else None) or base.get("numeroBoleta_XML") or "",
        "Observaciones_XML": _xml_obs(boleta.xml_status, xml.observaciones_xml if xml else None)
        or base.get("Observaciones_XML")
        or "",
    }
    return apply_live_overrides(base, overrides)


def _ordered_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    for col in SOLICITUD_COLUMNS:
        if col not in df.columns:
            df[col] = None
    extras = [c for c in df.columns if c not in SOLICITUD_COLUMNS]
    df = df[SOLICITUD_COLUMNS + extras]
    # Evita NaN en celdas de texto al abrir en Excel.
    for col in df.columns:
        df[col] = df[col].map(lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else v)
    return df


def _load_resumen_sheet(year: int, month: str) -> pd.DataFrame | None:
    path = os.path.join(_month_dir(year, month), "Solicitud.xlsx")
    if not os.path.isfile(path):
        return None
    try:
        xl = pd.ExcelFile(path, engine="openpyxl")
        sheet = next(
            (s for s in xl.sheet_names if s.strip().lower() in {"resumen boletas", "resumen de boletas", "resumenboletas"}),
            None,
        )
        if not sheet:
            return None
        return pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
    except Exception:
        return None


def export_solicitud_excel(year: int | str, month: str) -> tuple[str, bytes]:
    """
    Exporta Solicitud.xlsx con el esquema completo (41 columnas) desde PostgreSQL.

    Fuente principal: ``boletas.solicitud_row`` (snapshot del maestro/solicitud).
    Los campos operativos (recepción/XML/correo) se sobreescriben con el estado canónico vivo.
    """
    month_norm = str(month).strip().capitalize()
    year_int = int(year)

    with SessionLocal() as session:
        periodo = session.execute(
            select(Periodo).where(Periodo.anio == year_int, Periodo.mes_nombre == month_norm)
        ).scalar_one_or_none()
        if periodo is None:
            raise ValueError(f"Período no existe en DB: {year_int}-{month_norm}")

        rows = session.execute(
            select(Boleta, BoletaXmlData, Docente, Institucion)
            .outerjoin(BoletaXmlData, BoletaXmlData.boleta_id == Boleta.id)
            .outerjoin(Docente, Docente.id == Boleta.docente_id)
            .outerjoin(Institucion, Institucion.id == Boleta.institucion_id)
            .where(Boleta.periodo_id == periodo.id)
            .order_by(Boleta.id.asc())
        ).all()

        records = [
            _row_from_boleta(boleta, xml, docente, institucion, periodo)
            for boleta, xml, docente, institucion in rows
        ]

    df = _ordered_frame(records)
    sheets: dict[str, pd.DataFrame] = {"Solicitud": df}
    resumen = _load_resumen_sheet(year_int, month_norm)
    if resumen is not None and not resumen.empty:
        sheets["Resumen Boletas"] = resumen

    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, index=False, sheet_name=name)
    out.seek(0)
    filename = f"Solicitud_{year_int}_{month_norm}.xlsx"
    return filename, out.getvalue()
