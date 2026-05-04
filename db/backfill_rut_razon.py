"""Rellena boletas.rut_razon usando boleta_key RR o patrones de glosa."""
from __future__ import annotations

import argparse
import os
import re
import sys

if __package__ is None or __package__ == "":
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    _lib = os.path.join(_root, "lib")
    for _p in (_lib, _root):
        if _p not in sys.path:
            sys.path.insert(0, _p)

from sqlalchemy import select

from db.models import Boleta, Periodo
from db.session import SessionLocal
import utils


def _norm(value: object) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s.lower() == "nan" else s


def _infer(row: Boleta) -> str:
    key = _norm(row.boleta_key)
    if key:
        rr = re.search(r"\|RR\|([^|]+)", key, flags=re.IGNORECASE)
        if rr:
            return _norm(rr.group(1))
    glosa = _norm(row.glosa).upper()
    if "CFTST" in glosa or "CST2588" in glosa:
        return "65175242-6"
    if "IPST" in glosa or "IST2588" in glosa:
        return "65175239-6"
    return ""


def run(year: int | None, month: str | None) -> dict:
    stats = {"updated": 0, "scanned": 0}
    with SessionLocal() as session:
        query = select(Boleta)
        if year is not None and month:
            p = session.execute(
                select(Periodo).where(Periodo.anio == year, Periodo.mes_nombre == month.strip().capitalize())
            ).scalar_one_or_none()
            if p is None:
                raise RuntimeError(f"No existe período {year}-{month}")
            query = query.where(Boleta.periodo_id == p.id)

        for row in session.execute(query).scalars():
            stats["scanned"] += 1
            if _norm(row.rut_razon):
                continue
            inferred = _infer(row)
            if inferred:
                row.rut_razon = inferred
                stats["updated"] += 1
        session.commit()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill de rut_razon en boletas")
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--month", type=str, default=None)
    args = parser.parse_args()
    stats = run(args.year, args.month)
    utils.print_table(
        "Backfill rut_razon",
        [("Scanned", stats["scanned"]), ("Updated", stats["updated"])],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

