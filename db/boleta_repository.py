"""Persistencia mínima para estado de recepción de boletas."""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from db.models import Boleta, Docente
from db.session import SessionLocal


def _normalize_boleta_key(key: Optional[str]) -> str:
    raw = (key or "").strip()
    if not raw:
        return ""
    return re.sub(r"\|IDX\|\d+$", "", raw, flags=re.IGNORECASE)


def _to_decimal(value) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def upsert_boleta_recepcion(
    *,
    periodo_id: Optional[int],
    boleta_key: Optional[str],
    emplid: Optional[str],
    rut_sin_dv: Optional[str],
    rut_razon: Optional[str],
    estado_recepcion: Optional[str],
    observaciones_recepcion: Optional[str],
    glosa: Optional[str],
    monto_bruto,
    archivo_xml: Optional[str],
) -> bool:
    try:
        with SessionLocal() as session:
            row = None
            monto_decimal = _to_decimal(monto_bruto)
            normalized_incoming_key = _normalize_boleta_key(boleta_key)
            if boleta_key and periodo_id is not None:
                row = session.execute(
                    select(Boleta).where(Boleta.periodo_id == periodo_id, Boleta.boleta_key == boleta_key)
                ).scalar_one_or_none()
                if row is None and normalized_incoming_key:
                    # Evita duplicados cuando cambia key IDX -> XML/NB.
                    candidates = session.execute(
                        select(Boleta).where(
                            Boleta.periodo_id == periodo_id,
                            Boleta.emplid == (emplid or rut_sin_dv),
                        )
                    ).scalars().all()
                    for candidate in candidates:
                        if _normalize_boleta_key(candidate.boleta_key) == normalized_incoming_key:
                            row = candidate
                            break
                    if row is None and monto_decimal is not None:
                        for candidate in candidates:
                            if candidate.monto_bruto == monto_decimal and (
                                not rut_razon or not candidate.rut_razon or candidate.rut_razon == rut_razon
                            ):
                                row = candidate
                                break

            if row is None:
                if emplid and periodo_id is not None:
                    rows = session.execute(
                        select(Boleta).where(Boleta.periodo_id == periodo_id, Boleta.emplid == emplid)
                    ).scalars().all()
                    if len(rows) == 1:
                        row = rows[0]
                    elif monto_decimal is not None:
                        for candidate in rows:
                            if candidate.monto_bruto == monto_decimal and (
                                not rut_razon or not candidate.rut_razon or candidate.rut_razon == rut_razon
                            ):
                                row = candidate
                                break

                if row is None and rut_sin_dv and periodo_id is not None:
                    rows = session.execute(
                        select(Boleta).where(Boleta.periodo_id == periodo_id, Boleta.emplid == rut_sin_dv)
                    ).scalars().all()
                    if len(rows) == 1:
                        row = rows[0]
                    elif monto_decimal is not None:
                        for candidate in rows:
                            if candidate.monto_bruto == monto_decimal and (
                                not rut_razon or not candidate.rut_razon or candidate.rut_razon == rut_razon
                            ):
                                row = candidate
                                break

            docente = None
            candidate_rut = (emplid or rut_sin_dv or "").strip()
            if candidate_rut:
                docente = session.execute(select(Docente).where(Docente.rut == candidate_rut)).scalar_one_or_none()

            if row is None:
                row = Boleta(
                    periodo_id=periodo_id,
                    boleta_key=boleta_key,
                    emplid=emplid or rut_sin_dv,
                    docente_id=docente.id if docente else None,
                )
                session.add(row)
            elif boleta_key and not row.boleta_key:
                row.boleta_key = boleta_key
            if row.docente_id is None and docente is not None:
                row.docente_id = docente.id

            row.estado_recepcion = estado_recepcion
            row.observaciones_recepcion = observaciones_recepcion
            row.glosa = glosa
            row.rut_razon = rut_razon
            row.monto_bruto = monto_decimal
            row.descripcion = archivo_xml
            row.updated_at = datetime.utcnow()

            session.commit()
            return True
    except SQLAlchemyError:
        return False
