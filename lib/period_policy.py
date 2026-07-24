"""Política de períodos (abierto/cerrado) para API y validaciones."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from db.models import Periodo
from db.session import SessionLocal


def is_closed_status(estado: str | None) -> bool:
    return "cerrad" in (estado or "").strip().lower()


def get_period_status(year: int | str, month: str) -> Optional[str]:
    """Devuelve estado del período en BD o None si no existe."""
    try:
        y = int(year)
    except (TypeError, ValueError):
        y = year
    month_s = str(month or "").strip()
    if not month_s:
        return None
    with SessionLocal() as session:
        row = session.execute(
            select(Periodo.estado).where(Periodo.anio == y, Periodo.mes_nombre == month_s)
        ).scalar_one_or_none()
    return str(row) if row is not None else None


def assert_period_open_for_api(year: int | str, month: str) -> None:
    """Bloquea operaciones API sobre períodos cerrados en BD."""
    estado = get_period_status(year, month)
    if estado is None:
        return
    if is_closed_status(estado):
        raise ValueError(
            f"El período {month} {year} está cerrado. "
            "No se pueden lanzar jobs ni sesiones interactivas desde la API. "
            "Use la consola con supervisión manual si debe reabrir el mes."
        )
