"""Consola Rich no debe tumbar etapas bajo stdout inválido (uvicorn/Windows)."""
from __future__ import annotations

import sys

import terminal_ui


def test_print_success_survives_bad_stdout(monkeypatch):
    class BadStdout:
        def write(self, _s):
            raise OSError(22, "Invalid argument")

        def flush(self):
            pass

        def isatty(self):
            return False

        @property
        def encoding(self):
            return "utf-8"

        def fileno(self):
            raise OSError(22, "Invalid argument")

    monkeypatch.setattr(sys, "stdout", BadStdout())
    monkeypatch.setattr(sys, "stderr", BadStdout())
    # Rebind console file to bad stdout (Rich holds reference at import)
    monkeypatch.setattr(terminal_ui.console, "file", BadStdout())
    terminal_ui.print_success("Correos encontrados en rango: 134")
