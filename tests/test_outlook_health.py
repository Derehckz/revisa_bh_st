"""Tests health gate Outlook (sin COM real obligatorio)."""
from __future__ import annotations

from unittest.mock import patch

from outlook_utils import check_outlook_health


def test_outlook_health_closed_but_exe_found():
    with (
        patch("outlook_utils._outlook_process_running", return_value=False),
        patch("outlook_utils._outlook_exe_candidates", return_value=[r"C:\Outlook\OUTLOOK.EXE"]),
        patch("outlook_utils.os.path.isfile", return_value=True),
    ):
        h = check_outlook_health(probe_com=False)
    assert h["ready"] is False
    assert h["can_auto_launch"] is True
    assert "cerrado" in h["message"].lower() or "abrir" in h["message"].lower()


def test_outlook_health_running_ready_without_com_probe():
    with patch("outlook_utils._outlook_process_running", return_value=True):
        h = check_outlook_health(probe_com=False)
    assert h["ready"] is True
    assert h["process_running"] is True


def test_outlook_health_no_exe():
    with (
        patch("outlook_utils._outlook_process_running", return_value=False),
        patch("outlook_utils._outlook_exe_candidates", return_value=[]),
    ):
        h = check_outlook_health(probe_com=False)
    assert h["ready"] is False
    assert h["can_auto_launch"] is False
