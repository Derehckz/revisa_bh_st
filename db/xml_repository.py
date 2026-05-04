"""Persistencia de datos XML de boletas."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from db.models import Boleta, BoletaXmlData
from db.session import SessionLocal


def _to_decimal(value) -> Optional[Decimal]:
    if value is None or str(value).strip() == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _find_boleta(session, periodo_id: Optional[int], emplid: Optional[str], rut_sin_dv: Optional[str]) -> Optional[Boleta]:
    if periodo_id is None:
        return None
    if emplid:
        row = session.execute(
            select(Boleta).where(Boleta.periodo_id == periodo_id, Boleta.emplid == emplid)
        ).scalar_one_or_none()
        if row is not None:
            return row
    if rut_sin_dv:
        return session.execute(
            select(Boleta).where(Boleta.periodo_id == periodo_id, Boleta.emplid == rut_sin_dv)
        ).scalar_one_or_none()
    return None


def upsert_boleta_xml_data(
    *,
    periodo_id: Optional[int],
    boleta_key: Optional[str],
    emplid: Optional[str],
    rut_sin_dv: Optional[str],
    datos: dict,
    observaciones_xml: Optional[str],
) -> bool:
    try:
        with SessionLocal() as session:
            boleta = None
            if periodo_id is not None and boleta_key:
                boleta = session.execute(
                    select(Boleta).where(Boleta.periodo_id == periodo_id, Boleta.boleta_key == boleta_key)
                ).scalar_one_or_none()
            if boleta is None:
                boleta = _find_boleta(session, periodo_id, emplid, rut_sin_dv)
            if boleta is None:
                return False

            row = session.execute(
                select(BoletaXmlData).where(BoletaXmlData.boleta_id == boleta.id)
            ).scalar_one_or_none()
            if row is None:
                row = BoletaXmlData(boleta_id=boleta.id)
                session.add(row)

            row.rut_emisor = f"{datos.get('rutEmisor', '')}{datos.get('dvEmisor', '')}".strip() or None
            row.rut_receptor = f"{datos.get('rutReceptor', '')}{datos.get('dvReceptor', '')}".strip() or None
            row.numero_boleta = str(datos.get("numeroBoleta", "")).strip() or None
            row.fecha_boleta = str(datos.get("fechaBoleta", "")).strip() or None
            row.total_honorarios = _to_decimal(datos.get("totalHonorarios"))
            row.liquido_honorarios = _to_decimal(datos.get("liquidoHonorarios"))
            row.impuesto_honorarios = _to_decimal(datos.get("impuestoHonorarios"))
            row.porcentaje_impuesto = _to_decimal(datos.get("porcentajeImpuesto"))
            row.descripcion_linea = str(datos.get("descripcionLinea", "")).strip() or None
            row.observaciones_xml = observaciones_xml
            row.updated_at = datetime.utcnow()

            session.commit()
            return True
    except SQLAlchemyError:
        return False
