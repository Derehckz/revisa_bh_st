"""Ejecuta scripts legacy en etapas/ dentro de utils_bridge."""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from typing import Any, Callable

from interaction.utils_bridge import utils_bridge

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_LIB = os.path.join(_REPO, "lib")
_ETAPAS = os.path.join(_REPO, "etapas")

for _p in (_LIB, _REPO, _ETAPAS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_SCRIPT_BY_STAGE: dict[int, str] = {
    0: "0.-generar_solicitud.py",
    6: "6.-Informe_final_boletas.py",
    8: "8.-separa_bh_ip_cft.py",
    9: "9.-agrupa_por_docente.py",
    10: "10.-revisa_carpetas_ip_cft.py",
}


def load_stage_module(stage_num: int):
    rel = _SCRIPT_BY_STAGE.get(stage_num)
    if not rel:
        raise ValueError(f"Etapa {stage_num} sin script bridged")
    path = os.path.join(_ETAPAS, rel)
    name = f"stage{stage_num}_bridged_mod"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_stage_main(stage_num: int) -> Callable[..., Any]:
    return load_stage_module(stage_num).main


def run_bridged(stage_num: int, ui: Any, ctx: Any, args: argparse.Namespace) -> dict:
    main_fn = load_stage_main(stage_num)
    with utils_bridge(ui, ctx):
        result = main_fn(args)
    if result == 1:
        return {"ok": False}
    if result is None:
        return {"ok": True}
    return {"ok": bool(result) if isinstance(result, bool) else True}
