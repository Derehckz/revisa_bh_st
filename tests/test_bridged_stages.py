"""Smoke tests para etapas bridged (0, 5-10)."""
from __future__ import annotations

import sys
import os

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
_ETAPAS = os.path.join(_REPO, "etapas")
for _p in (_LIB, _REPO, _ETAPAS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from stages.bridged_args import BridgedContext, build_argv, build_namespace, uses_namespace
from stages.bridged_loader import _SCRIPT_BY_STAGE, load_stage_main


def test_all_bridged_stages_mapped():
    assert set(_SCRIPT_BY_STAGE) == {0, 6, 8, 9, 10}


def test_build_argv_period_and_flags():
    ctx = BridgedContext(
        stage_num=7,
        year=2026,
        month="Mayo",
        supervised=True,
        send=True,
        fecha_pago="15/05/2026",
    )
    argv = build_argv(ctx)
    assert "--year" in argv and "2026" in argv
    assert "--month" in argv and "Mayo" in argv
    assert "--send" in argv
    assert "--fecha-pago" in argv
    assert "--yes" not in argv


def test_build_argv_stage0_mes_ano():
    ctx = BridgedContext(stage_num=0, year=2026, month="Abril", supervised=True)
    argv = build_argv(ctx)
    assert "--mes" in argv and "Abril" in argv
    assert "--año" in argv


def test_namespace_stages():
    assert uses_namespace(6)
    assert not uses_namespace(8)
    ns = build_namespace(
        BridgedContext(stage_num=6, year=2026, month="Mayo", supervised=True)
    )
    assert ns.year == "2026"


def test_load_main_callable():
    for n in (0, 6, 8, 9, 10):
        fn = load_stage_main(n)
        assert callable(fn)
