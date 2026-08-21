"""Tests de exportación detallada Solicitud.xlsx desde BD."""
from __future__ import annotations

import io

import pandas as pd
import pytest

import solicitud_export as se
from db.solicitud_row import SOLICITUD_COLUMNS


def test_solicitud_columns_count():
    assert len(SOLICITUD_COLUMNS) == 41


def test_export_julio_has_full_schema():
    try:
        filename, content = se.export_solicitud_excel(2026, "Julio")
    except ValueError:
        pytest.skip("Período Julio 2026 no existe en DB de prueba")

    assert filename == "Solicitud_2026_Julio.xlsx"
    xl = pd.ExcelFile(io.BytesIO(content), engine="openpyxl")
    assert "Solicitud" in xl.sheet_names
    df = pd.read_excel(io.BytesIO(content), sheet_name="Solicitud", engine="openpyxl", nrows=0)
    for col in SOLICITUD_COLUMNS:
        assert col in df.columns
