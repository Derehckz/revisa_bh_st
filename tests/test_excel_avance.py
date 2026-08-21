"""Tests for excel_avance progress reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from stage_operations import excel_avance


def test_excel_avance_reads_solicitud(tmp_path: Path, monkeypatch):
    month_dir = tmp_path / "2026" / "Julio"
    month_dir.mkdir(parents=True)
    (month_dir / "a.xml").write_text("<x/>", encoding="utf-8")
    (month_dir / "b.pdf").write_bytes(b"%PDF")

    df = pd.DataFrame(
        [
            {
                "NAME": "Ana",
                "SEDE": "Santiago",
                "Email_Docente": "ana@x.cl",
                "Estado_Recepcion": "RECIBIDO",
                "Correo Enviado": "✅ Enviado (original)",
                "Recordatorios Enviados": "",
                "archivo_xml": "a.xml",
                "Observaciones_XML": "DATOS EXTRAIDOS OK",
                "CUS_TOT_HON": 1000,
            },
            {
                "NAME": "Bob",
                "SEDE": "Valpo",
                "Email_Docente": "bob@x.cl",
                "Estado_Recepcion": "RECIBIDO CON ERROR",
                "Correo Enviado": "❌ Error envío (original)",
                "Recordatorios Enviados": "1",
                "archivo_xml": "",
                "Observaciones_XML": "RUT no coincide",
                "CUS_TOT_HON": 2000,
            },
            {
                "NAME": "Cata",
                "SEDE": "Santiago",
                "Email_Docente": "cata@x.cl",
                "Estado_Recepcion": "",
                "Correo Enviado": "",
                "Recordatorios Enviados": "",
                "archivo_xml": "",
                "Observaciones_XML": "",
                "CUS_TOT_HON": 3000,
            },
        ]
    )
    xlsx = month_dir / "Solicitud.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Solicitud", index=False)

    monkeypatch.setattr("stage_operations.config.RAIZ", str(tmp_path))
    monkeypatch.setattr("stage_operations.get_bool_setting", lambda *a, **k: False)
    out = excel_avance(2026, "Julio")

    assert out["solicitud_exists"] is True
    assert out["total_rows"] == 3
    assert out["recepcion"]["recibido"] == 1
    assert out["recepcion"]["recibido_con_error"] == 1
    assert out["recepcion"]["pendiente"] == 1
    assert out["correo_solicitud"]["enviado"] == 1
    assert out["correo_solicitud"]["error"] == 1
    assert out["correo_solicitud"]["pendiente"] == 1
    assert out["xml_extract"]["ok"] == 1
    assert out["xml_extract"]["observacion"] == 1
    assert out["xml_extract"]["pendiente"] == 1
    assert out["archivos_mes"]["xml"] == 1
    assert out["archivos_mes"]["pdf"] == 1
    assert out["pagos"]["sheet_exists"] is False
    assert len(out["rows"]) == 3
    assert out["rows"][0]["name"] == "Ana"
    assert out["rows"][0]["emplid"] == ""
    assert "observaciones_xml" in out["rows"][1]
    assert out["rows"][1]["estado_recepcion"] == "RECIBIDO CON ERROR"


def test_excel_avance_marks_provisionado(tmp_path: Path, monkeypatch):
    month_dir = tmp_path / "2026" / "Agosto"
    month_dir.mkdir(parents=True)
    df = pd.DataFrame(
        [
            {
                "NAME": "Bustos",
                "GLOSA": "IPST Convenio los lagos Código FDI IST2588-AGOSTO",
                "CUS_TOT_HON": 30000,
                "Estado_Recepcion": "",
            },
            {
                "NAME": "Bustos",
                "GLOSA": "CFTST Convenio los Lagos Código FDI CST2588-AGOSTO - PROVISIONADO",
                "CUS_TOT_HON": 90000,
                "Estado_Recepcion": "",
            },
        ]
    )
    with pd.ExcelWriter(month_dir / "Solicitud.xlsx", engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Solicitud", index=False)

    monkeypatch.setattr("stage_operations.config.RAIZ", str(tmp_path))
    monkeypatch.setattr("stage_operations.get_bool_setting", lambda *a, **k: False)
    out = excel_avance(2026, "Agosto")
    assert out["total_rows"] == 2
    assert out["rows"][0]["provisionado"] is False
    assert out["rows"][1]["provisionado"] is True


def test_solicitud_field_reads_name_from_snapshot():
    from stage_operations import _solicitud_field

    sr = {"NAME": "Maass Olate,Fernando Ricardo", "SEDE": "LOS ANGELES", "Email_Docente": "a@b.cl"}
    assert _solicitud_field(sr, "NAME") == "Maass Olate,Fernando Ricardo"
    assert _solicitud_field(sr, "Email_Docente", "Correo_Personal") == "a@b.cl"
    assert _solicitud_field(None, "NAME") == ""
    assert _solicitud_field({"NAME": ""}, "NAME") == ""


def test_excel_avance_missing_file(tmp_path: Path, monkeypatch):
    (tmp_path / "2026" / "Julio").mkdir(parents=True)
    monkeypatch.setattr("stage_operations.config.RAIZ", str(tmp_path))
    monkeypatch.setattr("stage_operations.get_bool_setting", lambda *a, **k: False)
    out = excel_avance(2026, "Julio")
    assert out["solicitud_exists"] is False
    assert out["total_rows"] == 0
