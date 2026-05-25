import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for p in (_LIB, _REPO):
    if p not in sys.path:
        sys.path.insert(0, p)

import stage_commands


def test_list_stages_metadata_has_eleven_steps():
    stages = stage_commands.list_stages_metadata()
    nums = {s["stage_num"] for s in stages}
    assert nums == set(range(0, 11))
    assert stages[0]["enabled_for_api"] is True
    assert stages[1]["enabled_for_api"] is True
    assert stages[1]["is_email_stage"] is True


def test_build_stage_command_step0_includes_yes_and_maestro(tmp_path, monkeypatch):
    import config

    raiz = tmp_path / "data"
    mes = raiz / "2026" / "Mayo"
    mes.mkdir(parents=True)
    (mes / "MAESTRO.xlsx").write_bytes(b"x")
    (raiz / "BD-DOCENTES.xlsx").write_bytes(b"x")
    monkeypatch.setattr(config, "RAIZ", str(raiz))

    cmd = stage_commands.build_stage_command(
        str(_REPO),
        0,
        year=2026,
        month="Mayo",
        params={
            "year": 2026,
            "month": "Mayo",
            "maestro_file": "MAESTRO.xlsx",
            "bd_file": "BD-DOCENTES.xlsx",
        },
        api_mode=True,
    )
    assert cmd[-1] == "--yes"
    assert "--archivo-maestro" in cmd
    assert "--mes" in cmd and "Mayo" in cmd


def test_build_stage_command_step1_year_month_only():
    cmd = stage_commands.build_stage_command(
        _REPO,
        1,
        year=2026,
        month="Mayo",
        api_mode=True,
    )
    joined = " ".join(cmd)
    assert "1.-envia_correo_mensual_bh.py" in joined
    assert "--year" in cmd and "2026" in cmd
    assert "--month" in cmd and "Mayo" in cmd
    assert cmd[-1] == "--yes"


def test_validate_stage2_requires_dates():
    try:
        stage_commands.validate_stage_params(2, {"year": 2026, "month": "Mayo"})
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "fecha" in str(e).lower()


def test_build_stage_command_step7_send_and_fecha():
    cmd = stage_commands.build_stage_command(
        _REPO,
        7,
        year=2026,
        month="Mayo",
        params={
            "year": 2026,
            "month": "Mayo",
            "send": True,
            "fecha_pago": "01/05/2026",
        },
        api_mode=True,
    )
    assert "--send" in cmd
    assert "--fecha-pago" in cmd
    assert "01/05/2026" in cmd
