#!/usr/bin/env python3
"""Genera CSV RUT_SIN_DV,IP|CFT desde Solicitud.xlsx del período."""
from __future__ import annotations

import argparse
import csv
import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config
import pandas as pd


def _cat_from_row(row) -> str | None:
    rut_razon = str(row.get("RUT RAZON", "") or row.get("RUT_RAZON", "")).strip()
    if "65175239" in rut_razon.replace(".", "").replace("-", ""):
        return "IP"
    if "65175242" in rut_razon.replace(".", "").replace("-", ""):
        return "CFT"
    nombre = str(row.get("NOMBRE RAZON", "") or row.get("NOMBRE_RAZON", "")).upper()
    if "INSTITUTO PROFESIONAL" in nombre or " INSTITUTO" in nombre:
        return "IP"
    if ("FORMACI" in nombre and "TÉCNICA" in nombre) or "FORMACION TECNICA" in nombre:
        return "CFT"
    return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--year", required=True)
    p.add_argument("--month", required=True)
    p.add_argument("--output", default=None)
    args = p.parse_args()

    solicitud = os.path.join(config.RAIZ, args.year, args.month, "Solicitud.xlsx")
    if not os.path.isfile(solicitud):
        print(f"No existe {solicitud}", file=sys.stderr)
        return 1

    out = args.output or os.path.join(config.RAIZ, args.year, args.month, "map_ip_cft.csv")
    df = pd.read_excel(solicitud, sheet_name=0, engine="openpyxl")
    col_rut = "RUT_SIN_DV" if "RUT_SIN_DV" in df.columns else "EMPLID"

    mapping: dict[str, str] = {}
    for _, row in df.iterrows():
        rut_raw = str(row.get(col_rut, "")).strip()
        rut = rut_raw.split("-")[0].replace(".", "").strip()
        if not rut or not rut.isdigit():
            continue
        cat = _cat_from_row(row)
        if cat:
            mapping[rut] = cat

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["RUT_SIN_DV", "Categoria"])
        for rut in sorted(mapping):
            w.writerow([rut, mapping[rut]])

    print(f"Mapa escrito: {out} ({len(mapping)} RUTs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
