"""Compara estado canónico DB vs Solicitud.xlsx para rollout en sombra."""
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

import pandas as pd
from sqlalchemy import select

import config
import utils
from db.models import Boleta, BoletaXmlData, Periodo
from db.session import SessionLocal
from db.state_projection import classify_recepcion_status


def _digits(value) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _folio(value) -> str:
    try:
        return str(int(float(str(value or "").strip())))
    except Exception:
        return _digits(value)


def _folio_from_boleta_key(boleta_key: str | None) -> str:
    s = str(boleta_key or "")
    m = re.search(r"\|NB\|(\d+)", s)
    if m:
        return m.group(1)
    return ""


def compare_period(*, year: int, month: str, sheet: str | None = None) -> dict[str, float | int]:
    ruta = os.path.join(config.RAIZ, str(year), month, "Solicitud.xlsx")
    if not os.path.isfile(ruta):
        raise FileNotFoundError(f"No existe: {ruta}")

    with pd.ExcelFile(ruta, engine="openpyxl") as xls:
        use_sheet = sheet or xls.sheet_names[0]
    df = pd.read_excel(ruta, sheet_name=use_sheet, engine="openpyxl")

    with SessionLocal() as session:
        periodo = session.execute(
            select(Periodo).where(Periodo.anio == year, Periodo.mes_nombre == month)
        ).scalar_one_or_none()
        if periodo is None:
            raise ValueError("Período no existe en DB.")
        db_rows = session.execute(
            select(Boleta, BoletaXmlData)
            .outerjoin(BoletaXmlData, BoletaXmlData.boleta_id == Boleta.id)
            .where(Boleta.periodo_id == periodo.id)
        ).all()

    db_map: dict[tuple[str, str], str] = {}
    for b, x in db_rows:
        folio = _folio(x.numero_boleta if x else "") or _folio_from_boleta_key(getattr(b, "boleta_key", ""))
        key = (_digits(b.emplid), folio)
        db_map[key] = str(b.recepcion_status or "")

    total = 0
    diffs = 0
    for _, r in df.iterrows():
        key = (_digits(r.get("EMPLID", "")), _folio(r.get("numeroBoleta_XML", "")))
        if not key[0] or not key[1]:
            continue
        total += 1
        excel_state, _rs, _m = classify_recepcion_status(r.to_dict())
        db_state = db_map.get(key, "")
        if excel_state != db_state:
            diffs += 1
    alignment = (100.0 * (total - diffs) / total) if total else 0.0
    return {"rows_compared": total, "differences": diffs, "alignment_pct": alignment}


def main() -> int:
    utils.asegurar_utf8_salida()
    parser = argparse.ArgumentParser(description="Comparar Excel vs DB por período")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=str, required=True)
    parser.add_argument("--sheet", type=str, default=None)
    args = parser.parse_args()

    try:
        stats = compare_period(year=args.year, month=args.month, sheet=args.sheet)
    except (FileNotFoundError, ValueError) as exc:
        utils.print_error(str(exc))
        return 1
    utils.print_table(
        "Comparación Excel vs DB",
        [
            ("Filas comparadas", str(stats["rows_compared"])),
            ("Diferencias", str(stats["differences"])),
            ("Alineación", f"{stats['alignment_pct']:.2f}%"),
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
