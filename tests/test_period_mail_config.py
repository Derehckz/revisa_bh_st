"""Persistencia de plazos de correo por período."""
from __future__ import annotations

from period_mail_config import get_deadlines, save_deadlines, suggested_deadlines


def test_suggested_deadlines_use_period_month(monkeypatch):
    import config

    monkeypatch.setattr(config, "ULT_FECHA_RECEPCION", "25 Junio 2026")
    monkeypatch.setattr(config, "HORARIO_RECEPCION", "9:00")
    monkeypatch.setattr(config, "ULT_FECHA_RECORDATORIO", "28 Junio 2026")
    monkeypatch.setattr(config, "HORARIO_RECORDATORIO", "10:00")

    out = suggested_deadlines(2026, "Julio")
    assert out["fecha_limite_recepcion"] == "25 Julio 2026"
    assert out["fecha_limite_recordatorio"] == "28 Julio 2026"
    assert out["horario_recepcion"] == "9:00"
    assert out["horario_recordatorio"] == "10:00"


def test_save_and_get_period_deadlines(tmp_path, monkeypatch):
    import config
    import period_mail_config as pmc

    monkeypatch.setattr(config, "RAIZ", str(tmp_path))
    monkeypatch.setattr(config, "ULT_FECHA_RECEPCION", "25 Junio 2026")
    monkeypatch.setattr(config, "HORARIO_RECEPCION", "9:00")
    monkeypatch.setattr(config, "ULT_FECHA_RECORDATORIO", "25 Junio 2026")
    monkeypatch.setattr(config, "HORARIO_RECORDATORIO", "9:00")

    before = get_deadlines(2026, "Julio")
    assert before["fecha_limite_recepcion"] == "25 Julio 2026"
    assert before["source"] == "suggested"

    save_deadlines(
        2026,
        "Julio",
        {
            "fecha_limite_recepcion": "30 Julio 2026",
            "horario_recepcion": "18:00",
            "fecha_limite_recordatorio": "31 Julio 2026",
            "horario_recordatorio": "18:30",
        },
    )
    after = get_deadlines(2026, "Julio")
    assert after["fecha_limite_recepcion"] == "30 Julio 2026"
    assert after["horario_recepcion"] == "18:00"
    assert after["source"] == "period"
    assert (tmp_path / ".state" / "period_mail_deadlines.json").is_file()


def test_enrich_schema_uses_saved_deadlines(tmp_path, monkeypatch):
    import config
    import period_mail_config as pmc
    import stage_interactive_options as sio

    monkeypatch.setattr(config, "RAIZ", str(tmp_path))
    monkeypatch.setattr(config, "ULT_FECHA_RECEPCION", "25 Junio 2026")
    monkeypatch.setattr(config, "HORARIO_RECEPCION", "9:00")
    monkeypatch.setattr(config, "ULT_FECHA_RECORDATORIO", "25 Junio 2026")
    monkeypatch.setattr(config, "HORARIO_RECORDATORIO", "9:00")

    pmc.save_deadlines(
        2026,
        "Julio",
        {"fecha_limite_recepcion": "29 Julio 2026", "horario_recepcion": "17:00"},
    )
    schema = [
        {"name": "fecha_limite_recepcion", "type": "string"},
        {"name": "horario_recepcion", "type": "string"},
    ]
    enriched = sio.enrich_params_schema(1, 2026, "Julio", schema)
    by_name = {f["name"]: f for f in enriched}
    assert by_name["fecha_limite_recepcion"]["default"] == "29 Julio 2026"
    assert by_name["horario_recepcion"]["default"] == "17:00"
