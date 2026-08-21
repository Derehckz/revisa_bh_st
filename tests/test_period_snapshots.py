"""Tests de snapshots informe/pagos en PostgreSQL (con mocks de SessionLocal)."""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import period_snapshots
import pagos_report
import final_report as fr


def test_pagos_rows_from_dataframe():
    import pandas as pd

    df = pd.DataFrame([{"ID": "1-9", "LÍQUIDO": 1000, "Correo Enviado": "Enviado"}])
    rows = period_snapshots.pagos_rows_from_dataframe(df)
    assert len(rows) == 1
    assert rows[0]["ID"] == "1-9"
    assert rows[0]["LÍQUIDO"] == 1000


def test_period_pagos_report_from_db_snapshot():
    snap = {
        "exists": True,
        "frozen": False,
        "generated_at": "2026-07-30T12:00:00+00:00",
        "source": "postgresql",
        "source_kind": "postgresql",
        "total_rows": 2,
        "rows": [
            {
                "ID": "1-9",
                "Nombre": "A",
                "Bruto $": 108,
                "RETENCIÓN": 16.47,
                "LÍQUIDO": 91.53,
                "Correo Enviado": "Enviado",
            },
            {"ID": "2-7", "Nombre": "B", "LÍQUIDO": 50, "Correo Enviado": ""},
        ],
        "read_error": None,
        "year": 2026,
        "month": "Julio",
    }
    with patch.object(period_snapshots, "load_pagos_snapshot", return_value=snap):
        with patch.object(pagos_report, "_docente_index", return_value={}):
            out = pagos_report.period_pagos_report(2026, "Julio")
    assert out["exists"] is True
    assert out["counts"]["enviado"] == 1
    assert out["counts"]["pendiente"] == 1
    items = out["items"]
    assert items[0]["liquido"] == 91530
    assert items[0]["bruto"] == 108000
    assert items[0]["retencion"] == 16470
    assert out["totals"]["liquido"] == 91530 + 50000


def test_final_report_prefers_db_snapshot(monkeypatch):
    snap = {
        "exists": True,
        "frozen": True,
        "generated_at": "2026-07-01T00:00:00+00:00",
        "generated_at_source": "db_snapshot",
        "sheet_name": "Resumen Boletas",
        "source": "postgresql",
        "total_rows": 1,
        "total_monto": 500,
        "rows": [{"rut": "1-9", "monto_bruto": 500, "numero_boleta": "1"}],
        "read_error": None,
        "year": 2026,
        "month": "Julio",
    }
    monkeypatch.setattr(period_snapshots, "load_informe_snapshot", lambda *a, **k: snap)
    out = fr.period_final_report(2026, "Julio")
    assert out["source"] == "postgresql"
    assert out["total_rows"] == 1
    assert out["frozen"] is True


def test_build_pagos_payload_from_df():
    import pandas as pd

    df = pd.DataFrame([{"MAIL": "a@b.c", "LÍQUIDO": 2000}])
    payload = period_snapshots.build_pagos_payload_from_df(2026, "julio", df, source="test")
    assert payload["month"] == "Julio"
    assert payload["total_rows"] == 1
    assert payload["source"] == "test"
