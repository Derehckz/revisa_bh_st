"""Adaptador Rich/consola (experiencia CLI histórica)."""
from __future__ import annotations

from typing import Any

import terminal_ui
from interaction.port import InteractionPort, PromptRequest, PromptResponse
from interaction.types import InteractionKind


class CLIAdapter(InteractionPort):
    def log(self, message: str, *, level: str = "info") -> None:
        fn = {
            "info": terminal_ui.print_info,
            "success": terminal_ui.print_success,
            "warning": terminal_ui.print_warning,
            "error": terminal_ui.print_error,
        }.get(level, terminal_ui.print_info)
        fn(message)

    def progress(self, current: int, total: int, *, label: str = "") -> None:
        if total > 0 and current % max(1, total // 20) == 0:
            terminal_ui.print_progress_status(f"{label} {current}/{total}")

    def table(self, title: str, rows: list[tuple[str, str]]) -> None:
        terminal_ui.print_table(title, rows)

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if event_type == "header":
            terminal_ui.print_header(payload.get("title", ""), payload.get("subtitle") or None)
        elif event_type == "mail.preview" and payload.get("cli_summary"):
            self.log(payload["cli_summary"], level="info")

    def ask(self, request: PromptRequest) -> PromptResponse:
        if terminal_ui.is_non_interactive():
            from interaction.auto_adapter import AutoAdapter

            return AutoAdapter(auto_accept_confirm=True).ask(request)

        if request.kind == InteractionKind.CONFIRM:
            default = request.default == "accept"
            ok = terminal_ui.print_confirm(f"{request.title}: {request.message}", default=default)
            return PromptResponse(
                prompt_id=request.prompt_id,
                action="accept" if ok else "reject",
            )

        if request.kind == InteractionKind.CHOICE:
            opts = request.payload.get("options") or []
            icon = request.payload.get("icon") or ""
            picked = terminal_ui.seleccionar_opcion(opts, request.message, icon)
            try:
                idx = opts.index(str(picked))
            except ValueError:
                idx = 0
            return PromptResponse(
                prompt_id=request.prompt_id,
                action="choice",
                value=idx,
            )

        if request.kind == InteractionKind.TEXT:
            default = str(request.default or "")
            val = terminal_ui.prompt_required(request.message, default=default)
            return PromptResponse(prompt_id=request.prompt_id, action="accept", value=val)

        if request.kind == InteractionKind.MAIL_REVIEW:
            summary = request.payload.get("cli_summary") or request.message
            terminal_ui.print_info(summary)
            ok = terminal_ui.prompt_yes_no_s(
                "¿Enviar este correo? (s=enviar / n=omitir / esc=cancelar lote)",
                default="n",
            )
            if ok:
                return PromptResponse(prompt_id=request.prompt_id, action="accept")
            return PromptResponse(prompt_id=request.prompt_id, action="skip")

        ok = terminal_ui.prompt_yes_no_s(request.message, default="n")
        return PromptResponse(
            prompt_id=request.prompt_id,
            action="accept" if ok else "reject",
        )
