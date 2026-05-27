"""Progreso etapa 10 — progress_hook sin ejecutar OCR ni disco real."""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
_ETAPAS = os.path.join(_REPO, "etapas")
for _p in (_LIB, _REPO, _ETAPAS):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load_stage10():
    path = os.path.join(_ETAPAS, "10.-revisa_carpetas_ip_cft.py")
    spec = importlib.util.spec_from_file_location("stage10_test", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_ejecutar_trabajos_calls_progress_hook():
    mod = _load_stage10()
    opts = argparse.Namespace(force=True, dry_run=True, ocr=False, mark=False)
    trabajos = [
        ("IP", "/mes", "docente_a", opts),
        ("IP", "/mes", "docente_b", opts),
        ("CFT", "/mes", "docente_c", opts),
    ]
    calls: list[tuple[int, int]] = []

    def fake_worker(_args_tuple):
        return {"Institucion": "IP", "RUT": "1-9"}

    def hook(current, total, _res):
        calls.append((current, total))

    orig = mod._worker_tuple
    mod._worker_tuple = fake_worker
    try:
        out = mod.ejecutar_trabajos(trabajos, 2, progress_hook=hook)
    finally:
        mod._worker_tuple = orig

    assert len(out) == 3
    assert calls == [(1, 3), (2, 3), (3, 3)]
