"""Bus de eventos y respuestas para sesiones web (thread-safe)."""
from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from interaction.exceptions import SessionCancelled
from interaction.port import PromptRequest, PromptResponse


EventCallback = Callable[[dict[str, Any]], None]


def json_safe(obj: Any) -> Any:
    """Convierte payloads (numpy/pandas/etc.) a tipos JSON-serializables."""
    if obj is None or isinstance(obj, (str, bool, int, float)):
        return obj
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [json_safe(v) for v in obj]
    item = getattr(obj, "item", None)
    if callable(item):
        try:
            return json_safe(item())
        except Exception:
            pass
    isoformat = getattr(obj, "isoformat", None)
    if callable(isoformat):
        try:
            return isoformat()
        except Exception:
            pass
    return str(obj)


class SessionBus:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._lock = threading.Lock()
        self._seq = 0
        self._events: list[dict[str, Any]] = []
        self._callbacks: list[EventCallback] = []
        self._waiters: dict[str, threading.Event] = {}
        self._responses: dict[str, PromptResponse] = {}
        self._cancel = threading.Event()
        self._state = "created"

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def cancel(self) -> None:
        self._cancel.set()
        with self._lock:
            for ev in self._waiters.values():
                ev.set()

    def set_state(self, state: str) -> None:
        with self._lock:
            self._state = state
        self.publish("session.state", {"state": state})

    def get_state(self) -> str:
        with self._lock:
            return self._state

    def subscribe(self, callback: EventCallback) -> None:
        with self._lock:
            self._callbacks.append(callback)
            snapshot = list(self._events)

        for ev in snapshot:
            callback(ev)

    def unsubscribe(self, callback: EventCallback) -> None:
        with self._lock:
            self._callbacks = [c for c in self._callbacks if c is not callback]

    def publish(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._cancel.is_set() and event_type not in ("session.cancelled", "session.failed"):
            raise SessionCancelled()

        with self._lock:
            self._seq += 1
            event = {
                "v": 1,
                "session_id": self.session_id,
                "seq": self._seq,
                "ts": datetime.now(UTC).isoformat(),
                "type": event_type,
                "payload": json_safe(payload if isinstance(payload, dict) else {"value": payload}),
            }
            self._events.append(event)
            callbacks = list(self._callbacks)

        for cb in callbacks:
            try:
                cb(event)
            except Exception:
                pass
        return event

    def events_since(self, seq: int) -> list[dict[str, Any]]:
        with self._lock:
            return [e for e in self._events if e["seq"] > seq]

    def deliver_response(self, prompt_id: str, action: str, value: Any = None) -> None:
        if action == "cancel":
            self.cancel()
        resp = PromptResponse(prompt_id=prompt_id, action=action, value=value)
        with self._lock:
            self._responses[prompt_id] = resp
            waiter = self._waiters.pop(prompt_id, None)
        if waiter:
            waiter.set()

    def wait_for_response(self, request: PromptRequest, timeout_s: float | None = 3600) -> PromptResponse:
        if self._cancel.is_set():
            raise SessionCancelled()

        waiter = threading.Event()
        with self._lock:
            self._waiters[request.prompt_id] = waiter

        self.publish(
            "prompt.request",
            {
                "prompt_id": request.prompt_id,
                "kind": request.kind.value,
                "title": request.title,
                "message": request.message,
                "payload": request.payload,
                "default": request.default,
                "allow_cancel": request.allow_cancel,
            },
        )
        self.set_state("waiting_input")

        ok = waiter.wait(timeout=timeout_s)
        if self._cancel.is_set():
            raise SessionCancelled()
        if not ok:
            raise TimeoutError(f"Sin respuesta para prompt {request.prompt_id}")

        with self._lock:
            resp = self._responses.pop(request.prompt_id, None)
        self.set_state("running")
        if resp is None:
            raise RuntimeError("Respuesta perdida")
        return resp
