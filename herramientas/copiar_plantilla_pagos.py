#!/usr/bin/env python3
"""Copia la hoja Pagos desde un período cerrado (ej. Abril) hacia otro mes nuevo.

Origen recomendado: Abril 2026 (ya tiene Pagos completa). No usar como destino un mes
cerrado de referencia; solo meses que aún no tengan hoja Pagos.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config
import pandas as pd
import bh_excel_workbook


def _solicitud_path(year: str | int, month: str) -> str:
    return os.path.join(config.RAIZ, str(year), month, "Solicitud.xlsx")


def _empty_plantilla(df_src: pd.DataFrame) -> pd.DataFrame:
    out = df_src.iloc[0:0].copy()
    if "Correo Enviado" in out.columns:
        out["Correo Enviado"] = out["Correo Enviado"].astype("object")
    return out


def _sembrar_desde_solicitud(plantilla: pd.DataFrame, ruta_destino: str) -> pd.DataFrame:
    """Prellena filas RECIBIDO del destino con columnas compatibles de Pagos."""
    xls = pd.ExcelFile(ruta_destino, engine="openpyxl")
    hoja = None
    for candidata in ("Sheet1", "Solicitud", xls.sheet_names[0]):
        if candidata in xls.sheet_names:
            probe = pd.read_excel(ruta_destino, sheet_name=candidata, engine="openpyxl", nrows=2)
            if "Estado_Recepcion" in probe.columns:
                hoja = candidata
                break
    if not hoja:
        raise ValueError("No se encontró hoja con columna Estado_Recepcion en el destino")
    sol = pd.read_excel(ruta_destino, sheet_name=hoja, engine="openpyxl")
    if "Estado_Recepcion" not in sol.columns:
        raise ValueError(f"No hay Estado_Recepcion en hoja {hoja}")

    estado = sol["Estado_Recepcion"].astype(str).str.strip().str.upper()
    rec = sol[estado.eq("RECIBIDO") | estado.str.startswith("RECIBIDO ")]
    filas: list[dict] = []
    for _, row in rec.iterrows():
        item = {c: "" for c in plantilla.columns}
        mapping = {
            "MAIL": row.get("Email_Docente", ""),
            "Nombre": row.get("NAME", ""),
            "ID": row.get("EMPLID", ""),
            "Número Boleta": row.get("numeroBoleta_XML", row.get("numeroBoleta", "")),
            "Boleta": row.get("numeroBoleta_XML", row.get("numeroBoleta", "")),
            "LÍQUIDO": row.get("liquidoHonorarios_XML", row.get("CUS_TOT_HON", "")),
            "RE": row.get("RUT RAZON", row.get("RUT_RAZON", "")),
            "Ubicación": row.get("LOCATION", row.get("SEDE", "")),
            "SEDE": row.get("SEDE", ""),
            "Mes": row.get("MONTH", ""),
            "Año": row.get("YEAR", ""),
        }
        for col, val in mapping.items():
            if col in item and pd.notna(val):
                item[col] = val
        if "Correo Enviado" in item:
            item["Correo Enviado"] = ""
        filas.append(item)

    if not filas:
        return plantilla
    return pd.DataFrame(filas, columns=plantilla.columns)


def main() -> int:
    p = argparse.ArgumentParser(description="Copia plantilla hoja Pagos entre períodos")
    p.add_argument("--from-year", required=True)
    p.add_argument("--from-month", required=True)
    p.add_argument("--to-year", required=True)
    p.add_argument("--to-month", required=True)
    p.add_argument(
        "--sembrar",
        action="store_true",
        help="Prellena filas desde RECIBIDO del Solicitud destino (MAIL, montos, boleta)",
    )
    p.add_argument("--sin-backup", action="store_true", help="No crear zip de respaldo del destino")
    args = p.parse_args()

    src = _solicitud_path(args.from_year, args.from_month)
    dst = _solicitud_path(args.to_year, args.to_month)
    if not os.path.isfile(src):
        print(f"No existe origen: {src}", file=sys.stderr)
        return 1
    if not os.path.isfile(dst):
        print(f"No existe destino: {dst}", file=sys.stderr)
        return 1

    df_pagos = pd.read_excel(src, sheet_name="Pagos", engine="openpyxl")
    plantilla = _empty_plantilla(df_pagos)
    if args.sembrar:
        plantilla = _sembrar_desde_solicitud(plantilla, dst)

    if not args.sin_backup:
        mes_dir = os.path.dirname(dst)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = os.path.join(mes_dir, f"Solicitud_backup_pagos_{stamp}.zip")
        shutil.make_archive(backup.replace(".zip", ""), "zip", mes_dir, "Solicitud.xlsx")
        print(f"Backup: {backup}")

    ok = bh_excel_workbook.replace_sheet_atomically(dst, "Pagos", plantilla)
    if not ok:
        print("No se pudo escribir hoja Pagos.", file=sys.stderr)
        return 1

    print(
        f"Pagos copiada: {args.from_month} {args.from_year} -> {args.to_month} {args.to_year} "
        f"({len(plantilla)} filas, columnas={len(plantilla.columns)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
