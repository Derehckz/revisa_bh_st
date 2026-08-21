"""Tests de db/db_maintenance.py."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from db import db_maintenance


def test_run_alembic_upgrade_calls_command():
    with (
        patch("alembic.config.Config") as mock_cfg_cls,
        patch("alembic.command.upgrade") as mock_upgrade,
        patch("os.path.isfile", return_value=True),
    ):
        mock_cfg = MagicMock()
        mock_cfg_cls.return_value = mock_cfg
        out = db_maintenance.run_alembic_upgrade()
        mock_upgrade.assert_called_once()
        assert out["ok"] is True


def test_consistency_check_structure():
    with patch("db.db_maintenance.SessionLocal") as mock_session_local:
        session = MagicMock()
        mock_session_local.return_value.__enter__.return_value = session
        session.execute.return_value.scalar_one.return_value = 0
        out = db_maintenance.consistency_check(limit=5)
        assert "findings" in out
        assert out["ok"] is True
        assert isinstance(out["findings"], list)


def test_period_check_missing_period():
    with patch("db.db_maintenance.SessionLocal") as mock_session_local:
        session = MagicMock()
        mock_session_local.return_value.__enter__.return_value = session
        session.execute.return_value.scalar_one_or_none.return_value = None
        out = db_maintenance.period_check(2026, "Julio")
        assert out["ok"] is False
