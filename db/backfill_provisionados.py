"""Backfill de glosa PROVISIONADO usando arrastre desde mes previo NO RECIBIDO."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
import re

if __package__ is None or __package__ == "":
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    _lib = os.path.join(_root, "lib")
    for _p in (_lib, _root):
        if _p not in sys.path:
            sys.path.insert(0, _p)

from sqlalchemy import select

import config
import utils
from db.models import Boleta, Periodo
from db.session import SessionLocal


def _norm(value: object) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s.lower() == "nan" else s


def _month_name(month_num: int) -> str:
    return config.MESES_ES[month_num - 1]


def _month_sequence(start_month: int, end_month: int) -> list[int]:
    return [m for m in range(start_month, end_month + 1)]


def _strip_provisionado(glosa: object) -> str:
    base = _norm(glosa)
    if not base:
        return ""
    # Quita marcas repetidas de provisionado sin romper la glosa base.
    base = re.sub(r"\s*[-–—]?\s*PROVISIONADO\b", "", base, flags=re.IGNORECASE)
    base = re.sub(r"\s{2,}", " ", base).strip(" -")
    return base.strip()


def _append_provisionado(glosa: object) -> str:
    current = _norm(glosa)
    if "provisionado" in current.lower():
        return current
    if current:
        return f"{current} - PROVISIONADO"
    return "PROVISIONADO"


def _key(emplid: object, rut_razon: object, monto: Decimal | None) -> tuple[str, str, str]:
    return (_norm(emplid), _norm(rut_razon), f"{float(monto or 0):.2f}")


def run(year: int, start_month: int, end_month: int, recompute: bool = False) -> dict:
    if start_month < 1 or end_month > 12 or start_month > end_month:
        raise ValueError("Rango de meses inválido.")

    stats = {"updated": 0, "months": []}
    with SessionLocal() as session:
        for month_num in _month_sequence(start_month, end_month):
            if month_num == 1:
                continue
            prev_name = _month_name(month_num - 1)
            curr_name = _month_name(month_num)
            prev_period = session.execute(
                select(Periodo).where(Periodo.anio == year, Periodo.mes_num == (month_num - 1))
            ).scalar_one_or_none()
            curr_period = session.execute(
                select(Periodo).where(Periodo.anio == year, Periodo.mes_num == month_num)
            ).scalar_one_or_none()
            if not prev_period or not curr_period:
                stats["months"].append((curr_name, 0, "periodo faltante"))
                continue

            prev_pending = session.execute(
                select(Boleta).where(
                    Boleta.periodo_id == prev_period.id,
                    Boleta.estado_recepcion == "NO RECIBIDO",
                )
            ).scalars().all()
            pending_keys = {_key(b.emplid, b.rut_razon, b.monto_bruto) for b in prev_pending if _norm(b.rut_razon)}
            if not pending_keys:
                stats["months"].append((curr_name, 0, "sin pendientes previos"))
                continue

            current_rows = session.execute(
                select(Boleta).where(Boleta.periodo_id == curr_period.id)
            ).scalars().all()
            month_updates = 0
            for row in current_rows:
                row_key = _key(row.emplid, row.rut_razon, row.monto_bruto)
                if row_key[1] and row_key in pending_keys:
                    new_glosa = _append_provisionado(row.glosa)
                    if new_glosa != _norm(row.glosa):
                        row.glosa = new_glosa
                        row.updated_at = datetime.now(UTC)
                        month_updates += 1
                    continue
                if recompute and "provisionado" in _norm(row.glosa).lower():
                    cleaned = _strip_provisionado(row.glosa)
                    if cleaned != _norm(row.glosa):
                        row.glosa = cleaned
                        row.updated_at = datetime.now(UTC)
                        month_updates += 1
            stats["updated"] += month_updates
            stats["months"].append((f"{prev_name}->{curr_name}", month_updates, "ok"))
        session.commit()
    return stats


def main() -> int:
    utils.asegurar_utf8_salida()
    parser = argparse.ArgumentParser(description="Backfill PROVISIONADO por arrastre mensual")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--start-month", type=int, default=1)
    parser.add_argument("--end-month", type=int, default=12)
    parser.add_argument("--recompute", action="store_true", help="Recalcula y limpia provisionados incorrectos en rango")
    args = parser.parse_args()

    result = run(args.year, args.start_month, args.end_month, recompute=args.recompute)
    utils.print_table(
        "Backfill PROVISIONADO",
        [
            ("Año", args.year),
            ("Mes inicio", args.start_month),
            ("Mes fin", args.end_month),
            ("Filas actualizadas", result["updated"]),
        ],
    )
    for month_label, count, note in result["months"]:
        utils.print_info(f"{month_label}: {count} ({note})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

