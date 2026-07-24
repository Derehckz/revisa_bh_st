"""Validación de sesiones interactivas (web supervisada)."""
from __future__ import annotations

import os
import sys

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import stage_commands


def test_interactive_stage8_requires_map_csv():
    with pytest.raises(ValueError, match="map_csv"):
        stage_commands.validate_interactive_params(
            8, {"year": 2026, "month": "Mayo"}
        )


def test_interactive_stage8_ok_with_map():
    stage_commands.validate_interactive_params(
        8,
        {"year": 2026, "month": "Mayo", "map_csv": "herramientas/map.csv"},
    )


def test_interactive_stage1_allows_send_in_web():
    stage_commands.validate_interactive_params(
        1, {"year": 2026, "month": "Mayo", "send": True}
    )


def test_interactive_stage5_allows_send_in_web():
    stage_commands.validate_interactive_params(
        5, {"year": 2026, "month": "Mayo", "send": True}
    )


def test_interactive_stage7_allows_send_in_web():
    stage_commands.validate_interactive_params(
        7,
        {
            "year": 2026,
            "month": "Mayo",
            "send": True,
            "fecha_pago": "01/05/2026",
        },
    )


def test_interactive_stage7_requires_fecha_pago_when_send():
    with pytest.raises(ValueError, match="fecha_pago"):
        stage_commands.validate_interactive_params(
            7, {"year": 2026, "month": "Mayo", "send": True}
        )


def test_interactive_stage7_preview_without_send():
    stage_commands.validate_interactive_params(
        7,
        {"year": 2026, "month": "Mayo", "fecha_pago": "01/05/2026", "send": False},
    )
