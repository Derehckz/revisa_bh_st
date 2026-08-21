"""Validación del Excel maestro (paso 0) antes de generar Solicitud."""
from __future__ import annotations

import os
from typing import Any

import pandas as pd

import schema_validator

MAESTRO_REQUIRED_COLUMNS = [
    "EMPLID",
    "NAME",
    "LOCATION",
    "EMPL_RCD",
    "HR_STATUS",
    "DESCR",
    "MONTH",
    "YEAR",
    "CUS_INCIDENCIA",
    "CUS_MTO_CTA",
    "CUS_MTO_BONO",
    "CUS_MTO_DAPTO",
    "CUS_TOT_HON",
]


def validate_maestro_path(path: str) -> dict[str, Any]:
    if not path or not os.path.isfile(path):
        return {
            "ok": False,
            "path": path,
            "errors": ["Archivo maestro no encontrado."],
            "warnings": [],
            "row_count": 0,
            "missing_columns": list(MAESTRO_REQUIRED_COLUMNS),
        }

    try:
        df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    except Exception as exc:
        return {
            "ok": False,
            "path": path,
            "errors": [f"No se pudo leer el Excel: {exc}"],
            "warnings": [],
            "row_count": 0,
            "missing_columns": [],
        }

    cols = {str(c).strip() for c in df.columns}
    missing = [c for c in MAESTRO_REQUIRED_COLUMNS if c not in cols]
    errors: list[str] = []
    warnings: list[str] = []
    if missing:
        errors.append(f"Faltan columnas: {', '.join(missing)}")

    empty_emplid = 0
    zero_monto = 0
    if "EMPLID" in df.columns:
        empty_emplid = int(df["EMPLID"].isna().sum() + (df["EMPLID"].astype(str).str.strip() == "").sum())
    if "CUS_TOT_HON" in df.columns:
        try:
            montos = pd.to_numeric(df["CUS_TOT_HON"], errors="coerce").fillna(0)
            zero_monto = int((montos <= 0).sum())
        except Exception:
            zero_monto = 0
    if empty_emplid:
        warnings.append(f"{empty_emplid} fila(s) sin EMPLID.")
    if zero_monto:
        warnings.append(f"{zero_monto} fila(s) con monto 0 o vacío.")
    if len(df) == 0:
        errors.append("El maestro no tiene filas de datos.")

    # schema_validator opt-in contract
    schema_errors, schema_warnings = schema_validator.validate_for_stage(df, "stage0_maestro")
    errors.extend(schema_errors)
    warnings.extend(schema_warnings)

    return {
        "ok": len(errors) == 0,
        "path": os.path.abspath(path),
        "filename": os.path.basename(path),
        "row_count": int(len(df)),
        "missing_columns": missing,
        "errors": errors,
        "warnings": warnings,
        "empty_emplid": empty_emplid,
        "zero_monto": zero_monto,
    }
