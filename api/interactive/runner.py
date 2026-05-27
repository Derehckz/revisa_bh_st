"""Ejecuta etapas en hilo de fondo con adaptador web."""
from __future__ import annotations

import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_LIB = os.path.join(_REPO, "lib")
for p in (_LIB, _REPO):
    if p not in sys.path:
        sys.path.insert(0, p)

from interaction.exceptions import SessionCancelled
from interaction.recording_adapter import RecordingAdapter
from interaction.web_adapter import WebAdapter
from api.interactive import sessions

_BRIDGED_STAGES = {0, 6, 8, 9, 10}


def _run_session(session_id: str, stage_num: int) -> None:
    try:
        session = sessions.get_live_session(session_id)
    except KeyError:
        return

    bus = session["bus"]
    events_path = sessions._events_path(session_id)
    ui = RecordingAdapter(WebAdapter(bus), events_path)
    params = session.get("params") or {}

    bus.publish("session.started", {"stage_num": stage_num, "params": params})
    sessions.update_session_status(session_id, "running")

    try:
        if stage_num == 1:
            from stages.context import Stage1Context
            from stages.stage1.service import Stage1Service

            ctx = Stage1Context.from_api_params(params)
            result = Stage1Service().run(ctx, ui)
        elif stage_num == 2:
            from stages.context import Stage2Context
            from stages.stage2.service import Stage2Service

            ctx = Stage2Context.from_api_params(params)
            if not ctx.fecha_inicio or not ctx.fecha_fin:
                raise ValueError("fecha_inicio y fecha_fin son obligatorias (dd/mm/yyyy)")
            result = Stage2Service().run(ctx, ui)
        elif stage_num == 3:
            from stages.context import Stage3Context
            from stages.stage3.service import Stage3Service

            ctx = Stage3Context.from_api_params(params)
            result = Stage3Service().run(ctx, ui)
        elif stage_num == 4:
            from stages.context import Stage4Context
            from stages.stage4.service import Stage4Service

            ctx = Stage4Context.from_api_params(params)
            result = Stage4Service().run(ctx, ui)
        elif stage_num == 5:
            from stages.context import Stage5Context
            from stages.stage5.service import Stage5Service

            ctx = Stage5Context.from_api_params(params)
            result = Stage5Service().run(ctx, ui)
        elif stage_num == 7:
            from stages.context import Stage7Context
            from stages.stage7.service import Stage7Service

            ctx = Stage7Context.from_api_params(params)
            result = Stage7Service().run(ctx, ui)
        elif stage_num in _BRIDGED_STAGES:
            from stages.bridged_args import BridgedContext
            from stages.bridged_runner import run_bridged_stage

            ctx = BridgedContext.from_api_params(stage_num, params)
            result = run_bridged_stage(ctx, ui)
        else:
            raise ValueError(f"Etapa {stage_num} sin runner interactivo")

        if result.get("cancelled"):
            bus.publish("session.cancelled", result)
            sessions.update_session_status(session_id, "cancelled", result=result)
        elif result.get("ok"):
            bus.publish("session.completed", result)
            sessions.update_session_status(session_id, "completed", result=result)
        else:
            bus.publish("session.failed", result)
            sessions.update_session_status(session_id, "failed", result=result)
    except SessionCancelled:
        bus.publish("session.cancelled", {})
        sessions.update_session_status(session_id, "cancelled")
    except Exception as exc:
        bus.publish("session.failed", {"error": str(exc)})
        sessions.update_session_status(session_id, "failed", result={"error": str(exc)})
        ui.log(f"Error fatal: {exc}", level="error")


def run_stage0_session(session_id: str) -> None:
    _run_session(session_id, 0)


def run_stage1_session(session_id: str) -> None:
    _run_session(session_id, 1)


def run_stage2_session(session_id: str) -> None:
    _run_session(session_id, 2)


def run_stage3_session(session_id: str) -> None:
    _run_session(session_id, 3)


def run_stage4_session(session_id: str) -> None:
    _run_session(session_id, 4)


def run_stage5_session(session_id: str) -> None:
    _run_session(session_id, 5)


def run_stage6_session(session_id: str) -> None:
    _run_session(session_id, 6)


def run_stage7_session(session_id: str) -> None:
    _run_session(session_id, 7)


def run_stage8_session(session_id: str) -> None:
    _run_session(session_id, 8)


def run_stage9_session(session_id: str) -> None:
    _run_session(session_id, 9)


def run_stage10_session(session_id: str) -> None:
    _run_session(session_id, 10)
