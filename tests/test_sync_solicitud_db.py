"""Sync Solicitud.xlsx → PostgreSQL al generar paso 0."""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
_ETAPAS = os.path.join(_REPO, "etapas")
for _p in (_ETAPAS, _LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "generar_solicitud",
    os.path.join(_ETAPAS, "0.-generar_solicitud.py"),
)
assert _spec and _spec.loader
generar_solicitud = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generar_solicitud)


def test_sync_solicitud_a_db_ok():
    with (
        patch("db.import_excel_snapshot.detect_solicitud_sheet", return_value="Sheet1"),
        patch(
            "db.import_excel_snapshot.run_import",
            return_value={
                "boletas_insertadas": 10,
                "boletas_actualizadas": 2,
                "errores": 0,
            },
        ),
    ):
        out = generar_solicitud.sync_solicitud_a_db("x.xlsx", mes="Julio", año=2026)
    assert out["ok"] is True
    assert out["boletas_insertadas"] == 10
    assert out["boletas_actualizadas"] == 2


def test_sync_solicitud_a_db_soft_fail():
    with patch(
        "db.import_excel_snapshot.detect_solicitud_sheet",
        side_effect=RuntimeError("db down"),
    ):
        out = generar_solicitud.sync_solicitud_a_db("x.xlsx", mes="Julio", año=2026)
    assert out["ok"] is False
    assert "db down" in (out["error"] or "")
