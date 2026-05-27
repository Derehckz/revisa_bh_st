# -*- coding: utf-8 -*-
"""Capa visual centralizada para terminal (Rich)."""
from __future__ import annotations

import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table


def _ensure_utf8_stdio() -> None:
    """Asegura UTF-8 en stdout/stderr para evitar fallos con emojis en Windows."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        # Modo tolerante: si no se puede reconfigurar, seguimos con defaults.
        pass


_ensure_utf8_stdio()
console = Console()

_NON_INTERACTIVE = False


def set_non_interactive(flag: bool) -> None:
    """Activa modo sin prompts (confirmaciones usan defaults seguros)."""
    global _NON_INTERACTIVE
    _NON_INTERACTIVE = bool(flag)


def is_non_interactive() -> bool:
    return _NON_INTERACTIVE


def print_header(title: str, subtitle: str | None = None) -> None:
    contenido = f"[bold white]{title}[/bold white]"
    if subtitle:
        contenido += f"\n[dim]{subtitle}[/dim]"
    console.print(Panel.fit(contenido, border_style="cyan", padding=(1, 2)))


def print_step(step: int, total: int, message: str) -> None:
    console.print(f"\n[bold yellow][{step}/{total}] {message}[/bold yellow]")


def print_info(message: str) -> None:
    console.print(f"[cyan]ℹ️ {message}[/cyan]")


def print_success(message: str) -> None:
    console.print(f"[green]✅ {message}[/green]")


def print_warning(message: str) -> None:
    console.print(f"[yellow]⚠️ {message}[/yellow]")


def print_error(message: str) -> None:
    console.print(f"[red]❌ {message}[/red]")


def print_section(title: str) -> None:
    console.print(Panel.fit(f"[bold cyan]{title}[/bold cyan]", border_style="blue"))


def prompt_required(prompt_text: str, default: str = "") -> str:
    if is_non_interactive():
        valor = (default or "").strip()
        if valor:
            return valor
        raise RuntimeError(
            f"Modo no interactivo: falta valor para '{prompt_text}'. "
            "Pase el flag CLI correspondiente o defina BH_NON_INTERACTIVE solo con datos completos."
        )
    while True:
        valor = Prompt.ask(f"[cyan]{prompt_text}[/cyan]", default=default).strip()
        if valor:
            return valor
        print_warning("Este campo es obligatorio. Ingrese un valor válido.")


def print_confirm(message: str, default: bool = False) -> bool:
    if is_non_interactive():
        return default
    return Confirm.ask(f"[cyan]{message}[/cyan]", default=default)


def prompt_yes_no_s(message: str, default: str = "n") -> bool:
    if is_non_interactive():
        return default.strip().lower() == "s"
    respuesta = Prompt.ask(f"[cyan]{message}[/cyan]", default=default).strip().lower()
    return respuesta == "s"


def prompt_optional(prompt_text: str, default: str = "") -> str:
    if is_non_interactive():
        return default.strip()
    return Prompt.ask(f"[cyan]{prompt_text}[/cyan]", default=default).strip()


def print_progress_status(message: str) -> None:
    console.print(f"[bold blue]⏳ {message}[/bold blue]")


def print_separator(char: str = "─", width: int = 80) -> None:
    console.print(char * width)


def print_blank() -> None:
    console.print()


def print_table(title: str, rows: list[tuple[str, str]]) -> None:
    tabla = Table(title=title, title_style="bold cyan", show_lines=False, expand=False)
    tabla.add_column("Campo", style="bold white", no_wrap=True)
    tabla.add_column("Valor", style="white")
    for clave, valor in rows:
        tabla.add_row(clave, str(valor))
    console.print(tabla)


def print_list(title: str, items: list[str]) -> None:
    if not items:
        return
    console.print(f"[bold cyan]{title}[/bold cyan]")
    for item in items:
        console.print(f"   • {item}")


def seleccionar_opcion(lista: list[Any], mensaje: str, icono: str = "") -> Any:
    if not lista:
        raise ValueError("Lista vacía en seleccionar_opcion")
    if is_non_interactive():
        # Primera opción en el orden listado (no orden alfabético) para flujos batch predecibles.
        return lista[0]
    lista_ordenada = sorted(lista)
    console.print(Panel.fit(f"{icono} {mensaje}", style="cyan bold"))
    for i, opt in enumerate(lista_ordenada, 1):
        console.print(f"[yellow]{i}.[/] {opt}")
    while True:
        try:
            sel = int(console.input("[green]👉 Seleccione número:[/] ").strip())
            if 1 <= sel <= len(lista_ordenada):
                return lista_ordenada[sel - 1]
        except (ValueError, TypeError):
            pass
        print_error("Opción inválida, intente de nuevo.")
