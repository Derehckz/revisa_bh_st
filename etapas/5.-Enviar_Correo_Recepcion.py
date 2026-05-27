#!/usr/bin/env python3
"""Entrypoint CLI etapa 5 — delega en stages.stage5 (misma lógica que web)."""
import _sys_path  # noqa: E402
import argparse

import utils
from interaction.auto_adapter import AutoAdapter
from interaction.cli_adapter import CLIAdapter
from stages.context import Stage5Context
from stages.stage5.service import Stage5Service


def main(
    args=None,
    dispatch_outbox: dict[int, int] | None = None,
    dispatch_only_indices: set[int] | None = None,
):
    if args is None:
        args = argparse.Namespace(force_resend=False, yes=False, send=False, year=None, month=None)
    utils.apply_non_interactive_from_args(args)
    ctx = Stage5Context.from_args(args)
    ui = AutoAdapter.from_args(args) if utils.is_non_interactive() else CLIAdapter()
    return Stage5Service().run(
        ctx,
        ui,
        dispatch_outbox=dispatch_outbox,
        dispatch_only_indices=dispatch_only_indices,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Envío de correos de recepción de boletas")
    parser.add_argument(
        "--force-resend",
        action="store_true",
        help="Ignora idempotencia y reenvía aunque el correo ya esté marcado como exitoso.",
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
