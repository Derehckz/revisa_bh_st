"""Adaptador web vía SessionBus."""
from __future__ import annotations

from typing import Any

from interaction.exceptions import SessionCancelled
from interaction.port import InteractionPort, PromptRequest, PromptResponse
from interaction.session_bus import SessionBus


class WebAdapter(InteractionPort):
    def __init__(self, bus: SessionBus) -> None:
        self._bus = bus

    def log(self, message: str, *, level: str = "info") -> None:
        self._bus.publish("log", {"level": level, "message": message})

    def progress(self, current: int, total: int, *, label: str = "") -> None:
        self._bus.publish("progress", {"current": current, "total": total, "label": label})

    def table(self, title: str, rows: list[tuple[str, str]]) -> None:
        self._bus.publish("table", {"title": title, "rows": [[a, b] for a, b in rows]})

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        self._bus.publish(event_type, payload)

    def ask(self, request: PromptRequest) -> PromptResponse:
        return self._bus.wait_for_response(request)

    def header(self, title: str, subtitle: str | None = None) -> None:
        self.emit("header", {"title": title, "subtitle": subtitle or ""})
