"""Política de períodos cerrados para API."""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import period_policy  # noqa: E402
import stage_commands  # noqa: E402
import stage_operations  # noqa: E402


def test_is_closed_status():
    assert period_policy.is_closed_status("cerrado")
    assert period_policy.is_closed_status("Cerrado")
    assert not period_policy.is_closed_status("abierto")
    assert not period_policy.is_closed_status(None)


@patch("period_policy.SessionLocal")
def test_assert_period_open_raises_when_closed(mock_session_local):
    session = MagicMock()
    mock_session_local.return_value.__enter__.return_value = session
    session.execute.return_value.scalar_one_or_none.return_value = "cerrado"

    with pytest.raises(ValueError, match="cerrado"):
        period_policy.assert_period_open_for_api(2026, "Abril")


@patch("period_policy.SessionLocal")
def test_validate_stage_params_blocks_closed_period(mock_session_local):
    session = MagicMock()
    mock_session_local.return_value.__enter__.return_value = session
    session.execute.return_value.scalar_one_or_none.return_value = "cerrado"

    with pytest.raises(ValueError, match="cerrado"):
        stage_commands.validate_stage_params(2, {"year": 2026, "month": "Abril", "fecha_inicio": "01/04/2026", "fecha_fin": "30/04/2026"})


def test_interactive_stage1_allows_send_in_web():
    stage_commands.validate_interactive_params(
        1, {"year": 2026, "month": "Mayo", "send": True}
    )


def test_recommend_closed_period():
    stages = [
        {
            "stage_num": 2,
            "ui_status": "READY",
            "enabled_for_api": True,
            "description": "Paso 2",
        }
    ]
    rec = stage_operations.recommend_next_action(
        stages,
        kpis={"solicitud_exists": True},
        period_status="cerrado",
    )
    assert rec["kind"] == "review"
    assert rec["stage_num"] is None
