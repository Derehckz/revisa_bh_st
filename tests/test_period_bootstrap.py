"""Tests de onboarding: crear mes, upload y setup."""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config  # noqa: E402
import period_bootstrap as pb  # noqa: E402
import stage_operations  # noqa: E402


@pytest.fixture()
def raiz(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAIZ", str(tmp_path))
    monkeypatch.setattr(
        config,
        "ARCHIVO_ADJUNTO",
        str(tmp_path / "EjemploEnvioBoleta.pdf"),
    )
    return tmp_path


def test_list_missing_months(raiz):
    (raiz / "2026" / "Julio").mkdir(parents=True)
    out = pb.list_missing_months(2026)
    names = {m["month_name"] for m in out["missing"]}
    assert "Julio" not in names
    assert "Agosto" in names
    assert out["existing_count"] == 1


def test_create_period_and_conflict(raiz):
    with patch("period_bootstrap.get_or_create_periodo", return_value=42):
        res = pb.create_period(2026, "Agosto")
    assert res["ok"] is True
    assert res["period"]["month_name"] == "Agosto"
    assert (raiz / "2026" / "Agosto").is_dir()

    with pytest.raises(pb.PeriodBootstrapError) as exc:
        pb.create_period(2026, "Agosto")
    assert exc.value.status_code == 409


def test_upload_maestro_bd_adjunto_and_setup(raiz):
    import pandas as pd

    (raiz / "2026" / "Agosto").mkdir(parents=True)

    with pytest.raises(pb.PeriodBootstrapError):
        pb.upload_period_file(
            2026,
            "Agosto",
            "maestro",
            filename="Solicitud.xlsx",
            data=b"fake",
        )

    maestro_path = raiz / "2026" / "Agosto" / "_tmp_maestro.xlsx"
    cols = [
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
    pd.DataFrame([{c: (1 if c != "NAME" else "Ana") for c in cols}]).to_excel(
        maestro_path, index=False
    )
    with open(maestro_path, "rb") as f:
        data = f.read()
    up = pb.upload_period_file(
        2026,
        "Agosto",
        "maestro",
        filename="Pagos Agosto.xlsx",
        data=data,
    )
    assert up["ok"]
    assert (raiz / "2026" / "Agosto" / "Pagos Agosto.xlsx").is_file()

    up_bd = pb.upload_period_file(
        2026,
        "Agosto",
        "bd",
        filename="random.xlsx",
        data=b"PK\x03\x04bd",
    )
    assert up_bd["filename"] == "BD-DOCENTES.xlsx"
    assert (raiz / "BD-DOCENTES.xlsx").is_file()

    up_pdf = pb.upload_period_file(
        2026,
        "Agosto",
        "adjunto",
        filename="ejemplo.pdf",
        data=b"%PDF-1.4",
    )
    assert up_pdf["ok"]
    assert (raiz / "EjemploEnvioBoleta.pdf").is_file()

    with pytest.raises(pb.PeriodBootstrapError):
        pb.upload_period_file(
            2026,
            "Agosto",
            "maestro",
            filename="x.txt",
            data=b"nope",
        )

    setup = pb.period_setup(2026, "Agosto")
    assert setup["ready_for_step0"] is True
    assert setup["solicitud_exists"] is False
    assert setup["needs_setup_panel"] is True
    by_id = {i["id"]: i for i in setup["items"]}
    assert by_id["maestro"]["ok"] is True
    assert by_id["bd_docentes"]["ok"] is True
    assert by_id["adjunto_ejemplo"]["ok"] is True


def test_contabilidad_xlsx_not_treated_as_maestro(raiz):
    import pandas as pd

    month = raiz / "2026" / "Julio"
    month.mkdir(parents=True)
    # Artefacto de paso 7 — no es maestro
    pd.DataFrame([{"ID": "1-9", "LÍQUIDO": 91.53}]).to_excel(
        month / "Contabilidad_pagos.xlsx", index=False
    )
    # Solicitud ya generada (cierre)
    pd.DataFrame([{"EMPLID": "1-9"}]).to_excel(month / "Solicitud.xlsx", index=False)
    (raiz / "BD-DOCENTES.xlsx").write_bytes(b"PK\x03\x04bd")
    (raiz / "EjemploEnvioBoleta.pdf").write_bytes(b"%PDF")

    assert pb._maestro_files(str(month)) == []
    setup = pb.period_setup(2026, "Julio")
    by_id = {i["id"]: i for i in setup["items"]}
    assert by_id["maestro"]["ok"] is True
    assert by_id["solicitud"]["ok"] is True
    assert setup["setup_complete"] is True
    assert setup["needs_setup_panel"] is False
    assert by_id["maestro"]["kind"] is None  # no ofrece subir maestro otra vez


def test_solicitud_exists_hides_setup_even_with_bad_extra_xlsx(raiz):
    import pandas as pd

    month = raiz / "2026" / "Julio"
    month.mkdir(parents=True)
    pd.DataFrame([{"foo": 1}]).to_excel(month / "basura.xlsx", index=False)
    pd.DataFrame([{"EMPLID": "1-9"}]).to_excel(month / "Solicitud.xlsx", index=False)
    setup = pb.period_setup(2026, "Julio")
    assert setup["needs_setup_panel"] is False
    assert setup["setup_complete"] is True
    assert {i["id"]: i for i in setup["items"]}["maestro"]["ok"] is True


def test_recommend_wait_for_boletas_after_step1():
    stages = [
        {
            "stage_num": 0,
            "description": "0",
            "enabled_for_api": True,
            "ui_status": "OK",
            "is_email_stage": False,
            "prerequisites": {"ok": True},
            "checklist": [],
        },
        {
            "stage_num": 1,
            "description": "1",
            "enabled_for_api": True,
            "ui_status": "OK",
            "is_email_stage": True,
            "prerequisites": {"ok": True},
            "checklist": [],
        },
        {
            "stage_num": 2,
            "description": "2",
            "enabled_for_api": True,
            "ui_status": "READY",
            "is_email_stage": False,
            "prerequisites": {"ok": True},
            "checklist": [],
        },
    ]
    rec = stage_operations.recommend_next_action(
        stages,
        kpis={"solicitud_exists": True, "xml_files_in_month": 0, "no_recibidos": 0},
    )
    assert rec["kind"] == "run"
    assert rec["stage_num"] == 2
    assert "empiecen a llegar" in rec["message"].lower() or "lleguen" in rec["title"].lower()
