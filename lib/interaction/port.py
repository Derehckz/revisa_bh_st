"""Puerto de interacción para lógica de etapas."""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from interaction.types import InteractionKind


@dataclass(frozen=True)
class PromptRequest:
    kind: InteractionKind
    title: str
    message: str
    payload: dict[str, Any] = field(default_factory=dict)
    prompt_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    default: Any = None
    allow_cancel: bool = True


@dataclass(frozen=True)
class PromptResponse:
    prompt_id: str
    action: Literal["accept", "reject", "skip", "cancel", "choice"]
    value: Any = None


class InteractionPort(ABC):
    """Abstracción de I/O: logs, progreso y preguntas bloqueantes."""

    @abstractmethod
    def log(self, message: str, *, level: str = "info") -> None: ...

    @abstractmethod
    def progress(self, current: int, total: int, *, label: str = "") -> None: ...

    @abstractmethod
    def table(self, title: str, rows: list[tuple[str, str]]) -> None: ...

    @abstractmethod
    def emit(self, event_type: str, payload: dict[str, Any]) -> None: ...

    @abstractmethod
    def ask(self, request: PromptRequest) -> PromptResponse: ...

    def header(self, title: str, subtitle: str | None = None) -> None:
        self.emit("header", {"title": title, "subtitle": subtitle or ""})

    def confirm_yes_no(
        self,
        title: str,
        message: str,
        *,
        default: bool = False,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        req = PromptRequest(
            kind=InteractionKind.CONFIRM,
            title=title,
            message=message,
            payload=payload or {},
            default="accept" if default else "reject",
        )
        resp = self.ask(req)
        if resp.action == "cancel":
            from interaction.exceptions import SessionCancelled

            raise SessionCancelled()
        return resp.action == "accept"

    def prompt_text(self, label: str, message: str = "", *, default: str = "") -> str:
        req = PromptRequest(
            kind=InteractionKind.TEXT,
            title=label,
            message=message or label,
            default=default,
        )
        resp = self.ask(req)
        if resp.action == "cancel":
            from interaction.exceptions import SessionCancelled

            raise SessionCancelled()
        return str(resp.value or default or "").strip()

    def choose_option(
        self,
        title: str,
        message: str,
        options: list[Any],
        *,
        icon: str = "",
    ) -> Any:
        if len(options) == 1:
            return options[0]
        labels = [str(o) for o in options]
        req = PromptRequest(
            kind=InteractionKind.CHOICE,
            title=title,
            message=message,
            payload={"options": labels, "icon": icon},
        )
        resp = self.ask(req)
        if resp.action == "cancel":
            from interaction.exceptions import SessionCancelled

            raise SessionCancelled()
        if resp.action == "choice" and resp.value is not None:
            idx = int(resp.value)
            return options[idx]
        return options[0]
