"""Rutas REST y WebSocket para sesiones interactivas."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect

from api import security
from api.interactive import runner, sessions

router = APIRouter(prefix="/operations/interactive", tags=["operations-interactive"])

_INTERACTIVE_STAGES = set(range(0, 11))


def _validate_api_key_query(api_key: str | None) -> None:
    keys = security.get_api_keys()
    if not keys:
        raise HTTPException(status_code=503, detail="API key no configurada")
    if not api_key or api_key not in keys:
        raise HTTPException(status_code=401, detail="API key inválida")


_RUNNERS = {
    0: runner.run_stage0_session,
    1: runner.run_stage1_session,
    2: runner.run_stage2_session,
    3: runner.run_stage3_session,
    4: runner.run_stage4_session,
    5: runner.run_stage5_session,
    6: runner.run_stage6_session,
    7: runner.run_stage7_session,
    8: runner.run_stage8_session,
    9: runner.run_stage9_session,
    10: runner.run_stage10_session,
}


@router.post("/stages/{stage_num}/sessions")
def create_interactive_session(
    stage_num: int,
    payload: dict[str, Any],
    _: None = Depends(security.require_api_key),
) -> dict:
    if stage_num not in _INTERACTIVE_STAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Etapa {stage_num} no tiene sesión interactiva.",
        )
    try:
        meta = sessions.create_session(stage_num, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    session_id = meta["id"]
    fn = _RUNNERS.get(stage_num)
    if fn:
        sessions.submit_executor(lambda: fn(session_id))

    return meta


@router.get("/sessions/{session_id}")
def get_interactive_session(
    session_id: str,
    _: None = Depends(security.require_api_key),
) -> dict:
    meta = sessions.get_session(session_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return meta


@router.post("/sessions/{session_id}/cancel")
def cancel_interactive_session(
    session_id: str,
    _: None = Depends(security.require_api_key),
) -> dict:
    try:
        return sessions.cancel_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada") from exc


@router.websocket("/sessions/{session_id}/stream")
async def session_stream(
    websocket: WebSocket,
    session_id: str,
    api_key: str | None = Query(default=None),
    last_seq: int = Query(default=0),
) -> None:
    _validate_api_key_query(api_key)
    try:
        session = sessions.get_live_session(session_id)
    except KeyError:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    bus = session["bus"]
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def on_event(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    bus.subscribe(on_event)
    for ev in bus.events_since(last_seq):
        await websocket.send_json(ev)

    async def pump_out() -> None:
        while True:
            event = await queue.get()
            await websocket.send_json(event)

    pump_task = asyncio.create_task(pump_out())
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "prompt.response":
                payload = msg.get("payload") or msg
                bus.deliver_response(
                    str(payload.get("prompt_id", "")),
                    str(payload.get("action", "reject")),
                    payload.get("value"),
                )
            elif msg.get("type") == "session.cancel":
                bus.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(on_event)
        pump_task.cancel()
