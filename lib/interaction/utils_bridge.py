"""Redirige utils/terminal_ui hacia InteractionPort (etapas aún no refactorizadas)."""
from __future__ import annotations

import contextlib
from collections.abc import Generator
from typing import Any

import terminal_ui
import utils
from interaction.port import InteractionPort


class _BridgeState:
    def __init__(self, ui: InteractionPort, ctx: Any) -> None:
        self.ui = ui
        self.ctx = ctx
        self._orig: dict[str, Any] = {}


@contextlib.contextmanager
def utils_bridge(ui: InteractionPort, ctx: Any) -> Generator[None, None, None]:
    """Parchea I/O de utils para ejecutar scripts legacy con el mismo adaptador."""
    state = _BridgeState(ui, ctx)
    keys = [
        "print_header",
        "print_info",
        "print_success",
        "print_warning",
        "print_error",
        "print_step",
        "print_section",
        "print_table",
        "print_list",
        "print_progress_status",
        "print_separator",
        "print_blank",
        "mostrar_contexto_ejecucion",
        "prompt_yes_no_s",
        "prompt_required",
        "prompt_optional",
        "print_confirm",
        "choose_excel_sheet",
        "seleccionar_opcion",
        "is_non_interactive",
        "apply_non_interactive_from_args",
    ]
    for key in keys:
        if hasattr(utils, key):
            state._orig[key] = getattr(utils, key)

    def _log(msg: str, level: str = "info") -> None:
        ui.log(msg, level=level)

    utils.print_header = lambda t, s=None: ui.header(t, s or "")
    utils.print_info = lambda m: _log(m, "info")
    utils.print_success = lambda m: _log(m, "success")
    utils.print_warning = lambda m: _log(m, "warning")
    utils.print_error = lambda m: _log(m, "error")
    utils.print_step = lambda step, total, msg: _log(f"[{step}/{total}] {msg}", "info")
    utils.print_section = lambda t: _log(t, "info")
    utils.print_progress_status = lambda m: _log(m, "info")
    utils.print_separator = lambda *a, **k: None
    utils.print_blank = lambda: None

    def _print_table(title: str, rows: list[tuple[str, str]]) -> None:
        ui.table(title, rows)

    utils.print_table = _print_table

    def _print_list(title: str, items: list[str]) -> None:
        for item in items:
            _log(f"{title}: {item}", "info")

    utils.print_list = _print_list

    def _mostrar_contexto(
        titulo: str,
        rutas: list[tuple[str, str]],
        preview_items: list[str] | None = None,
        confirm_message: str = "¿Continuar?",
        confirmar: bool = True,
    ) -> bool:
        ui.table(titulo, [(str(k), str(v)) for k, v in rutas])
        if preview_items:
            for p in preview_items:
                _log(p, "info")
        if not confirmar:
            return True
        return ui.confirm_yes_no("Continuar", confirm_message, default=False)

    utils.mostrar_contexto_ejecucion = _mostrar_contexto

    def _prompt_yn(message: str, default: str = "n") -> bool:
        return ui.confirm_yes_no("Confirmar", message, default=(default.lower() == "s"))

    utils.prompt_yes_no_s = _prompt_yn
    utils.print_confirm = lambda m, default=False: ui.confirm_yes_no("Confirmar", m, default=default)

    def _prompt_required(prompt_text: str, default: str = "") -> str:
        return ui.prompt_text(prompt_text, prompt_text, default=default)

    utils.prompt_required = _prompt_required
    utils.prompt_optional = lambda prompt_text, default="": ui.prompt_text(
        prompt_text, prompt_text, default=default
    )

    def _choose_sheet(
        hojas: list[str],
        *,
        sheet: str | None = None,
        canonical: str = "Solicitud",
        prompt_message: str = "Seleccione hoja:",
        icon: str = "📄",
    ) -> str:
        wanted = (sheet or getattr(ctx, "sheet", None) or "").strip()
        if wanted and wanted in hojas:
            return wanted
        if len(hojas) == 1:
            return hojas[0]
        import schema_validator

        found = schema_validator.find_sheet(hojas, canonical)
        if found:
            return found
        picked = ui.choose_option("Hoja Excel", prompt_message, hojas, icon=icon)
        return str(picked)

    utils.choose_excel_sheet = _choose_sheet

    def _seleccionar(lista: list[Any], mensaje: str, icono: str = "") -> Any:
        if len(lista) == 1:
            return lista[0]
        return ui.choose_option("Selección", mensaje, lista, icon=icono)

    utils.seleccionar_opcion = _seleccionar

    utils.is_non_interactive = lambda: False
    utils.apply_non_interactive_from_args = lambda args: None

    terminal_ui.set_non_interactive(False)

    try:
        yield
    finally:
        for key, fn in state._orig.items():
            setattr(utils, key, fn)
        terminal_ui.set_non_interactive(
            bool(getattr(ctx, "yes", False) or getattr(ctx, "non_interactive", False))
        )
