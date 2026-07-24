"""Sincroniza filas de periodos desde carpetas BH_RAIZ/{año}/{Mes}."""
from __future__ import annotations

import os
import re
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from db.file_repository import get_or_create_periodo
from db.models import Periodo
from db.session import SessionLocal

# Misma lista canónica que lib/config.MESES_ES (evita importar config y sus .env obligatorios).
MESES_ES: list[str] = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]

_YEAR_RE = re.compile(r"^20\d{2}$")
_MESES_BY_LOWER: dict[str, tuple[int, str]] = {
    name.casefold(): (idx + 1, name) for idx, name in enumerate(MESES_ES)
}


def discover_period_folders(raiz: str) -> list[tuple[int, int, str]]:
    """Devuelve (anio, mes_num, mes_nombre) por cada carpeta año/mes válida bajo raiz."""
    found: list[tuple[int, int, str]] = []
    if not raiz or not os.path.isdir(raiz):
        return found

    try:
        year_entries: Iterable[str] = os.listdir(raiz)
    except OSError:
        return found

    for year_name in year_entries:
        if not _YEAR_RE.match(year_name):
            continue
        year_path = os.path.join(raiz, year_name)
        if not os.path.isdir(year_path):
            continue
        anio = int(year_name)
        try:
            month_entries = os.listdir(year_path)
        except OSError:
            continue
        for month_name in month_entries:
            month_path = os.path.join(year_path, month_name)
            if not os.path.isdir(month_path):
                continue
            hit = _MESES_BY_LOWER.get(month_name.casefold())
            if hit is None:
                continue
            mes_num, mes_nombre = hit
            found.append((anio, mes_num, mes_nombre))

    found.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return found


def _existing_period_keys() -> set[tuple[int, int]]:
    try:
        with SessionLocal() as session:
            rows = session.execute(select(Periodo.anio, Periodo.mes_num)).all()
            return {(int(anio), int(mes_num)) for anio, mes_num in rows}
    except SQLAlchemyError:
        return set()


def ensure_periods_from_disk(raiz: str) -> int:
    """Crea en BD períodos abiertos para carpetas que aún no existen. Devuelve cuántos creó."""
    folders = discover_period_folders(raiz)
    if not folders:
        return 0

    existing = _existing_period_keys()
    created = 0
    for anio, mes_num, mes_nombre in folders:
        if (anio, mes_num) in existing:
            continue
        periodo_id = get_or_create_periodo(anio, mes_num, mes_nombre)
        if periodo_id is None:
            continue
        created += 1
        existing.add((anio, mes_num))
    return created
