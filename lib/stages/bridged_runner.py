"""Ejecuta etapas 0,5-10 con utils_bridge."""
from __future__ import annotations

import sys
import traceback

from interaction.utils_bridge import utils_bridge
from stages.bridged_args import BridgedContext, build_argv, build_namespace, uses_namespace
from stages.bridged_loader import load_stage_main, load_stage_module


def _result_ok(result) -> bool:
    if result is None:
        return True
    if result is False or result == 1:
        return False
    if isinstance(result, int) and result != 0:
        return False
    return True


def run_bridged_stage(ctx: BridgedContext, ui) -> dict:
    argv = build_argv(ctx)
    old_argv = sys.argv
    sys.argv = argv
    restore_patch: tuple[object, object] | None = None
    try:
        with utils_bridge(ui, ctx):
            if ctx.stage_num == 10:
                mod = load_stage_module(10)
                orig_ejecutar = mod.ejecutar_trabajos

                def _ejecutar_con_progreso(trabajos, procesos, progress_hook=None):
                    total = len(trabajos)

                    def _hook(current, _total, _res):
                        ui.progress(current, total, label="Revisando carpetas")
                        ui.emit(
                            "folder.progress",
                            {"current": current, "total": total},
                        )

                    return orig_ejecutar(trabajos, procesos, progress_hook=_hook)

                mod.ejecutar_trabajos = _ejecutar_con_progreso
                restore_patch = (mod, orig_ejecutar)
                result = mod.main()
            else:
                main_fn = load_stage_main(ctx.stage_num)
                if uses_namespace(ctx.stage_num):
                    result = main_fn(build_namespace(ctx))
                else:
                    result = main_fn()
        ok = _result_ok(result)
        ui.emit("session.summary", {"ok": ok, "stage_num": ctx.stage_num})
        return {"ok": ok, "stage_num": ctx.stage_num}
    except Exception as exc:
        ui.log(f"Error: {exc}", level="error")
        ui.emit("session.failed", {"error": str(exc), "trace": traceback.format_exc()})
        return {"ok": False, "error": str(exc)}
    finally:
        if restore_patch is not None:
            mod, orig_ejecutar = restore_patch
            mod.ejecutar_trabajos = orig_ejecutar
        sys.argv = old_argv
