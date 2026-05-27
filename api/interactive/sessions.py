"""Almacén de sesiones interactivas en memoria + disco."""
from __future__ import annotations

import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from settings import get_setting

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="bh-interactive")
_LOCK = threading.Lock()
_SESSIONS: dict[str, dict[str, Any]] = {}


def _state_root() -> str:
    return os.path.abspath(get_setting("BH_RAIZ", _REPO_ROOT))


def sessions_dir() -> str:
    path = os.path.join(_state_root(), ".state", "interactive-sessions")
    os.makedirs(path, exist_ok=True)
    return path


def _session_dir(session_id: str) -> str:
    path = os.path.join(sessions_dir(), session_id)
    os.makedirs(path, exist_ok=True)
    return path


def _meta_path(session_id: str) -> str:
    return os.path.join(_session_dir(session_id), "meta.json")


def _events_path(session_id: str) -> str:
    return os.path.join(_session_dir(session_id), "events.jsonl")


def _persist_meta(session: dict[str, Any]) -> None:
    with open(_meta_path(session["id"]), "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False, indent=2)


def create_session(stage_num: int, params: dict[str, Any]) -> dict[str, Any]:
    import stage_commands

    stage_commands.validate_interactive_params(stage_num, params)
    year = params.get("year")
    month = params.get("month")
    if year is None or not month:
        raise ValueError("params debe incluir year y month")

    session_id = uuid.uuid4().hex[:12]
    from interaction.session_bus import SessionBus

    bus = SessionBus(session_id)
    session = {
        "id": session_id,
        "stage_num": stage_num,
        "year": year,
        "month": month,
        "params": dict(params),
        "status": "created",
        "created_at": datetime.now(UTC).isoformat(),
        "finished_at": None,
        "result": None,
        "bus": bus,
    }
    with _LOCK:
        for s in _SESSIONS.values():
            if (
                s.get("status") in ("running", "waiting_input", "created")
                and s.get("year") == year
                and s.get("month") == month
                and s.get("stage_num") == stage_num
            ):
                raise ValueError(
                    f"Ya hay sesión activa para paso {stage_num} en {month} {year} "
                    f"(id={s['id']})"
                )
        _SESSIONS[session_id] = session
    _persist_meta(_public_meta(session))
    return _public_meta(session)


def _public_meta(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": session["id"],
        "stage_num": session["stage_num"],
        "year": session["year"],
        "month": session["month"],
        "params": session.get("params") or {},
        "status": session.get("status", "created"),
        "created_at": session.get("created_at"),
        "finished_at": session.get("finished_at"),
        "result": session.get("result"),
    }


def get_session(session_id: str) -> dict[str, Any] | None:
    with _LOCK:
        s = _SESSIONS.get(session_id)
    if s:
        return _public_meta(s)
    meta_path = _meta_path(session_id)
    if not os.path.isfile(meta_path):
        return None
    with open(meta_path, encoding="utf-8") as f:
        return json.load(f)


def get_live_session(session_id: str) -> dict[str, Any]:
    with _LOCK:
        s = _SESSIONS.get(session_id)
    if not s:
        raise KeyError(session_id)
    return s


def get_session_bus(session_id: str) -> Any:
    with _LOCK:
        s = _SESSIONS.get(session_id)
    if not s:
        raise KeyError(session_id)
    return s["bus"]


def update_session_status(session_id: str, status: str, **extra: Any) -> None:
    with _LOCK:
        s = _SESSIONS.get(session_id)
        if not s:
            return
        s["status"] = status
        for k, v in extra.items():
            s[k] = v
        if status in ("completed", "cancelled", "failed"):
            s["finished_at"] = datetime.now(UTC).isoformat()
        _persist_meta(_public_meta(s))


def submit_executor(fn) -> None:
    _EXECUTOR.submit(fn)


def cancel_session(session_id: str) -> dict[str, Any]:
    with _LOCK:
        s = _SESSIONS.get(session_id)
    if not s:
        raise KeyError(session_id)
    bus = s["bus"]
    bus.cancel()
    update_session_status(session_id, "cancelled")
    return _public_meta(s)
