#!/usr/bin/env python3
"""Entrypoint CLI etapa 7 — delega en stages.stage7 (misma lógica que web)."""
import _sys_path  # noqa: E402
import argparse

import utils
from interaction.auto_adapter import AutoAdapter
from interaction.cli_adapter import CLIAdapter
from stages.context import Stage7Context
from stages.stage7.service import Stage7Service


def main(args=None):
    if args is None:
        args = argparse.Namespace(
            force_resend=False,
            yes=False,
            send=False,
            fecha_pago=None,
            year=None,
            month=None,
        )
    utils.apply_non_interactive_from_args(args)
    ctx = Stage7Context.from_args(args)
    ui = AutoAdapter.from_args(args) if utils.is_non_interactive() else CLIAdapter()
    return Stage7Service().run(ctx, ui)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Envío de correos de pago de boletas de honorarios")
    parser.add_argument(
        "--force-resend",
        action="store_true",
        help="Ignora idempotencia y reenvía aunque el correo ya esté marcado como exitoso.",
    )
    parser.add_argument(
        "--fecha-pago",
        dest="fecha_pago",
        type=str,
        default=None,
        help="Fecha de pago mostrada en el correo (ej: 05/09/2025). Obligatoria con --yes.",
    )
    parser.add_argument(
        "--supervision-mode",
        choices=["batch", "per_mail"],
        default="batch",
        help="batch: confirmación por lote. per_mail: confirmar cada correo.",
    )
    utils.register_non_interactive_cli(parser, with_send=True)
    utils.register_period_args(parser)
    main(parser.parse_args())
