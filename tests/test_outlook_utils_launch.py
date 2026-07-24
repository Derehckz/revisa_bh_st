"""Unit tests for Outlook auto-launch helpers (no real COM)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from outlook_utils import asegurar_outlook_abierto, conectar_outlook_app


def test_asegurar_outlook_noop_si_ya_corre():
    with patch("outlook_utils._outlook_process_running", return_value=True):
        with patch("outlook_utils.subprocess.Popen") as popen:
            asegurar_outlook_abierto()
            popen.assert_not_called()


def test_asegurar_outlook_lanza_exe():
    logs: list[str] = []
    fake_exe = r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE"
    with (
        patch("outlook_utils._outlook_process_running", return_value=False),
        patch("outlook_utils._outlook_exe_candidates", return_value=[fake_exe]),
        patch("outlook_utils.os.path.isfile", return_value=True),
        patch("outlook_utils.subprocess.Popen") as popen,
    ):
        asegurar_outlook_abierto(log=logs.append)
        popen.assert_called_once_with([fake_exe], close_fds=True)
    assert any("abriéndolo" in m.lower() for m in logs)


def test_conectar_respeta_cancel_check():
    with (
        patch("outlook_utils.asegurar_outlook_abierto"),
        patch("outlook_utils._outlook_process_running", return_value=True),
        patch("win32com.client.Dispatch", side_effect=RuntimeError("busy")),
    ):
        from interaction.exceptions import SessionCancelled

        with pytest.raises(SessionCancelled):
            conectar_outlook_app(
                ensure_running=True,
                wait_s=5,
                cancel_check=lambda: True,
            )
