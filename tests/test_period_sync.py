"""Sync de períodos desde carpetas BH_RAIZ/{año}/{Mes}."""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from db.period_sync import discover_period_folders, ensure_periods_from_disk  # noqa: E402


def test_discover_period_folders_finds_valid_months(tmp_path):
    (tmp_path / "2026" / "Julio").mkdir(parents=True)
    (tmp_path / "2026" / "junio").mkdir(parents=True)  # case-insensitive
    (tmp_path / "2026" / "not-a-month").mkdir()
    (tmp_path / "2026" / "readme.txt").write_text("x", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "1999" / "Enero").mkdir(parents=True)  # año fuera de 20xx

    found = discover_period_folders(str(tmp_path))
    assert found == [
        (2026, 7, "Julio"),
        (2026, 6, "Junio"),
    ]


def test_discover_period_folders_missing_raiz(tmp_path):
    assert discover_period_folders(str(tmp_path / "nope")) == []
    assert discover_period_folders("") == []


def test_ensure_periods_from_disk_creates_only_missing(tmp_path):
    (tmp_path / "2026" / "Julio").mkdir(parents=True)
    (tmp_path / "2026" / "Junio").mkdir(parents=True)

    with (
        patch("db.period_sync._existing_period_keys", return_value={(2026, 6)}),
        patch("db.period_sync.get_or_create_periodo") as mock_create,
    ):
        mock_create.side_effect = lambda anio, mes_num, mes_nombre: 99
        created = ensure_periods_from_disk(str(tmp_path))

    assert created == 1
    mock_create.assert_called_once_with(2026, 7, "Julio")


def test_ensure_periods_from_disk_idempotent_when_all_exist(tmp_path):
    (tmp_path / "2026" / "Julio").mkdir(parents=True)

    with (
        patch("db.period_sync._existing_period_keys", return_value={(2026, 7)}),
        patch("db.period_sync.get_or_create_periodo") as mock_create,
    ):
        created = ensure_periods_from_disk(str(tmp_path))

    assert created == 0
    mock_create.assert_not_called()


def test_list_periods_triggers_disk_sync():
    from api import services

    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = []

    with (
        patch("api.services.get_setting", return_value=str(_REPO)),
        patch("api.services.ensure_periods_from_disk") as mock_ensure,
    ):
        result = services.list_periods(session)

    mock_ensure.assert_called_once()
    assert result == []
