"""Adaptador batch (--yes, API legacy): defaults seguros."""
from __future__ import annotations

from typing import Any

from interaction.port import InteractionPort, PromptRequest, PromptResponse
from interaction.types import InteractionKind


class AutoAdapter(InteractionPort):
    def __init__(
        self,
        *,
        allow_send: bool = False,
        auto_accept_confirm: bool = False,
        auto_accept_mail: bool = False,
    ) -> None:
        self.allow_send = allow_send
        self.auto_accept_confirm = auto_accept_confirm
        self.auto_accept_mail = auto_accept_mail

    @classmethod
    def from_args(cls, args: Any) -> "AutoAdapter":
        send = bool(getattr(args, "send", False))
        yes = bool(getattr(args, "yes", False))
        return cls(
            allow_send=send,
            auto_accept_confirm=send,
            auto_accept_mail=send and yes,
        )

    def log(self, message: str, *, level: str = "info") -> None:
        import terminal_ui

        fn = {
            "info": terminal_ui.print_info,
            "success": terminal_ui.print_success,
            "warning": terminal_ui.print_warning,
            "error": terminal_ui.print_error,
        }.get(level, terminal_ui.print_info)
        fn(message)

    def progress(self, current: int, total: int, *, label: str = "") -> None:
        pass

    def table(self, title: str, rows: list[tuple[str, str]]) -> None:
        import terminal_ui

        terminal_ui.print_table(title, rows)

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if event_type == "header":
            import terminal_ui

            terminal_ui.print_header(payload.get("title", ""), payload.get("subtitle") or None)

    def ask(self, request: PromptRequest) -> PromptResponse:
        return self._response_for_request(
            request,
            auto_accept_confirm=self.auto_accept_confirm,
            auto_accept_mail=self.auto_accept_mail,
        )

    @staticmethod
    def _response_for_request(
        request: PromptRequest,
        *,
        auto_accept_confirm: bool = False,
        auto_accept_mail: bool = False,
    ) -> PromptResponse:
        if request.kind == InteractionKind.MAIL_REVIEW:
            if auto_accept_mail:
                return PromptResponse(prompt_id=request.prompt_id, action="accept")
            return PromptResponse(prompt_id=request.prompt_id, action="skip")

        if request.kind == InteractionKind.CONFIRM:
            if auto_accept_confirm:
                return PromptResponse(prompt_id=request.prompt_id, action="accept")
            default = request.default == "accept"
            return PromptResponse(
                prompt_id=request.prompt_id,
                action="accept" if default else "reject",
            )

        if request.kind == InteractionKind.CHOICE:
            purpose = (request.payload or {}).get("purpose")
            if purpose == "duplicate_policy":
                import os

                politica = os.environ.get("BH_DUPLICADOS", "S").strip().upper()
                if politica not in ("S", "A", "I"):
                    politica = "S"
                opts = request.payload.get("options") or ["S", "A", "I"]
                try:
                    idx = opts.index(politica)
                except ValueError:
                    idx = 0
                return PromptResponse(
                    prompt_id=request.prompt_id,
                    action="choice",
                    value=opts[idx] if isinstance(opts[idx], str) else politica,
                )
            return PromptResponse(prompt_id=request.prompt_id, action="choice", value=0)

        if request.kind == InteractionKind.TEXT:
            return PromptResponse(
                prompt_id=request.prompt_id,
                action="accept",
                value=str(request.default or ""),
            )

        return PromptResponse(prompt_id=request.prompt_id, action="reject")
