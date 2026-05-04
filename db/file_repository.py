"""Persistencia mínima para periodos y archivos extraídos."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from db.models import Archivo, Periodo
from db.session import SessionLocal


def get_or_create_periodo(anio: int, mes_num: int, mes_nombre: str) -> Optional[int]:
    try:
        with SessionLocal() as session:
            existing = session.execute(
                select(Periodo).where(Periodo.anio == anio, Periodo.mes_num == mes_num)
            ).scalar_one_or_none()
            if existing is not None:
                return existing.id

            row = Periodo(
                anio=anio,
                mes_num=mes_num,
                mes_nombre=mes_nombre,
                estado="abierto",
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.id
    except SQLAlchemyError:
        return None


def save_archivo_event(
    *,
    periodo_id: Optional[int],
    tipo_archivo: str,
    nombre_original: str,
    ruta_relativa: str,
    tamano_bytes: Optional[int] = None,
    fecha_origen: Optional[datetime] = None,
) -> bool:
    try:
        with SessionLocal() as session:
            row = Archivo(
                periodo_id=periodo_id,
                tipo_archivo=tipo_archivo,
                nombre_original=nombre_original,
                ruta_relativa=ruta_relativa,
                tamano_bytes=tamano_bytes,
                fecha_origen=fecha_origen,
            )
            session.add(row)
            session.commit()
            return True
    except SQLAlchemyError:
        return False
