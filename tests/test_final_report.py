"""Tests de lib/final_report.period_final_report."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import final_report as fr


@pytest.fixture
def month_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(fr.config, "RAIZ", str(tmp_path))
    base = tmp_path / "2026" / "Julio"
    base.mkdir(parents=True)
    return base


def test_period_final_report_missing(month_dir, monkeypatch):
    monkeypatch.setattr(
        "period_snapshots.load_informe_snapshot", lambda *a, **k: None, raising=False
    )
    out = fr.period_final_report(2026, "Julio")
    assert out["exists"] is False
    assert out["read_error"]


def test_period_final_report_reads_resumen(month_dir, monkeypatch):
    monkeypatch.setattr(
        "period_snapshots.load_informe_snapshot", lambda *a, **k: None, raising=False
    )
    path = month_dir / "Solicitud.xlsx"
    df = pd.DataFrame(
        [
            {
                "RUT": "15651725-9",
                "Nombre Docente": "Quintana Valdebenito Richard Mauricio",
                "Reg empleo": 1,
                "LOCATION": 114,
                "INS": "CFT",
                "Nombre Sede": "Matriz LL",
                "N° Boleta": 434,
                "Tipo Doc": "15.25",
                "Tipo de Pago": "Boleta Pago Normal",
                "Fecha emisión": "28/07/2026",
                "Monto Bruto": 212320,
            }
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame({"x": [1]}).to_excel(writer, sheet_name="Sheet1", index=False)
        df.to_excel(writer, sheet_name="Resumen Boletas", index=False)

    log_dir = month_dir / "logs_informe"
    log_dir.mkdir()
    log_path = log_dir / "informe_20260728_120000.jsonl"
    log_path.write_text(
        json.dumps({"ts": "2026-07-28T16:00:00+00:00", "status": "success"}) + "\n",
        encoding="utf-8",
    )
    # mtime del xlsx más antigua que el log, para que gane generated_at del jsonl
    import os
    import time

    old = time.mktime((2026, 7, 27, 12, 0, 0, 0, 0, -1))
    os.utime(path, (old, old))

    out = fr.period_final_report(2026, "Julio")
    assert out["exists"] is True
    assert out["total_rows"] == 1
    assert out["rows"][0]["numero_boleta"] == "434"
    assert out["generated_at"] == "2026-07-28T16:00:00+00:00"
    assert out["generated_at_source"] == "logs_informe"
