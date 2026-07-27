#!/usr/bin/env python3
"""Entrypoint CLI etapa 1 — delega en stages.stage1 (misma lógica que web)."""
import _sys_path  # noqa: E402
import argparse

import utils
from interaction.auto_adapter import AutoAdapter
from interaction.cli_adapter import CLIAdapter
from stages.context import Stage1Context
from stages.stage1.mail import build_mail_item_key as _build_mail_item_key
from stages.stage1.mail import enviar_correos  # noqa: F401 — usado por outbox_com_dispatch
from stages.stage1.service import Stage1Service


def main(args) -> None:
    utils.apply_non_interactive_from_args(args)
    ctx = Stage1Context.from_args(args)
    if utils.is_non_interactive():
        ui = AutoAdapter.from_args(args)
    else:
        ui = CLIAdapter()
    Stage1Service().run(ctx, ui)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Envío de correos de boletas de honorarios")
    parser.add_argument("--year", type=str, help="Año específico")
    parser.add_argument("--month", type=str, help="Mes específico")
    parser.add_argument(
        "--force-resend",
        action="store_true",
        help="Ignora idempotencia y reenvía aunque el correo ya esté marcado como exitoso.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Aborta si la Solicitud.xlsx no cumple el esquema canónico.",
    )
    parser.add_argument(
        "--month-dir",
        dest="month_dir",
        type=str,
        default=None,
        help="Carpeta del período (ej: 2026/Mayo).",
    )
    parser.add_argument(
        "--excel-file",
        dest="excel_file",
        type=str,
        default=None,
        help="Archivo Excel del mes (ej: Solicitud.xlsx).",
    )
    parser.add_argument(
        "--sheet",
        type=str,
        default=None,
        help="Nombre de la hoja del Excel (ej. Solicitud).",
    )
    parser.add_argument(
        "--fecha-limite-recepcion",
        dest="fecha_limite_recepcion",
        type=str,
        default=None,
        help="Fecha límite en correos originales (ej: 27 Mayo 2026).",
    )
    parser.add_argument(
        "--horario-recepcion",
        dest="horario_recepcion",
        type=str,
        default=None,
        help="Horario límite en correos originales (ej: 19:00).",
    )
    parser.add_argument(
        "--fecha-limite-recordatorio",
        dest="fecha_limite_recordatorio",
        type=str,
        default=None,
        help="Fecha límite en correos de recordatorio (ej: 30 Mayo 2026).",
    )
    parser.add_argument(
        "--horario-recordatorio",
        dest="horario_recordatorio",
        type=str,
        default=None,
        help="Horario límite en correos de recordatorio (ej: 19:00).",
    )
    parser.add_argument(
        "--supervision-mode",
        choices=["batch", "per_mail"],
        default="batch",
        help="batch: confirmación por lote (default CLI). per_mail: confirmar cada correo.",
    )
    parser.add_argument(
        "--reminders-only",
        action="store_true",
        help="Solo envía recordatorios a NO RECIBIDO (no solicitudes originales).",
    )
    utils.register_non_interactive_cli(parser, with_send=True)
    main(parser.parse_args())
