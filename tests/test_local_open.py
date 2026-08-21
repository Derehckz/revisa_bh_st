"""Tests de apertura local segura."""
from __future__ import annotations

import os
from pathlib import Path

import local_open
import pytest


def test_resolve_period_file_rejects_outside_root(tmp_path, monkeypatch):
    monkeypatch.setattr(local_open.config, "RAIZ", str(tmp_path / "raiz"))
    (tmp_path / "raiz").mkdir()
    outside = tmp_path / "afuera.xlsx"
    outside.write_bytes(b"PK")
    with pytest.raises(ValueError):
        local_open.open_local_file(str(outside))


def test_resolve_period_file_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(local_open.config, "RAIZ", str(tmp_path))
    mes = tmp_path / "2026" / "Julio"
    mes.mkdir(parents=True)
    target = mes / "Solicitud.xlsx"
    target.write_bytes(b"PK")
    path = local_open.resolve_period_file(2026, "Julio", name="Solicitud.xlsx")
    assert Path(path) == target.resolve()
