#!/usr/bin/env python3
"""Entrypoint CLI etapa 2 — delega en stages.stage2."""
import _sys_path  # noqa: E402
import argparse

import utils
from interaction.auto_adapter import AutoAdapter
from interaction.cli_adapter import CLIAdapter
from stages.context import Stage2Context
from stages.stage2.service import Stage2Service


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extraer adjuntos (XML y PDF) de correos de Outlook"
    )
    parser.add_argument("--fecha-inicio", type=str, help="Fecha inicio dd/mm/yyyy")
    parser.add_argument("--fecha-fin", type=str, help="Fecha fin dd/mm/yyyy")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la ejecución sin guardar archivos",
    )
    utils.register_non_interactive_cli(parser)
    args = parser.parse_args()
    utils.apply_non_interactive_from_args(args)

    ctx = Stage2Context.from_args(args)
    ui = AutoAdapter(auto_accept_confirm=True) if utils.is_non_interactive() else CLIAdapter()
    try:
        Stage2Service().run(ctx, ui)
    except ValueError as e:
        utils.print_error(str(e))


if __name__ == "__main__":
    main()
