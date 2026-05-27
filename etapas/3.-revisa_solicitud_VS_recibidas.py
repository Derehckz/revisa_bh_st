#!/usr/bin/env python3
"""Entrypoint CLI etapa 3 — delega en stages.stage3."""
import _sys_path  # noqa: E402
import argparse

import utils
from interaction.auto_adapter import AutoAdapter
from interaction.cli_adapter import CLIAdapter
from stages.context import Stage3Context
from stages.stage3.service import Stage3Service


def main(args=None) -> None:
    if args is None:
        args = argparse.Namespace(strict=False, yes=False, year=None, month=None, sheet=None)
    utils.apply_non_interactive_from_args(args)
    ctx = Stage3Context.from_args(args)
    ui = AutoAdapter(auto_accept_confirm=True) if utils.is_non_interactive() else CLIAdapter()
    Stage3Service().run(ctx, ui)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validación de recepción PDF/XML")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Aborta si la Solicitud.xlsx no cumple el esquema canónico.",
    )
    parser.add_argument(
        "--sheet",
        type=str,
        default=None,
        help="Nombre de la hoja del Excel (ej. Solicitud).",
    )
    utils.register_non_interactive_cli(parser)
    utils.register_period_args(parser)
    main(parser.parse_args())
