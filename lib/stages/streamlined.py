"""Helpers de flujo web simplificado (streamlined)."""
from __future__ import annotations

from typing import Any

from interaction.port import InteractionPort


def param_streamlined(params: dict[str, Any], default: bool = True) -> bool:
    """Web: por defecto True. CLI/legacy puede forzar False."""
    if "streamlined" not in params:
        return default
    return bool(params.get("streamlined"))


def confirm_unless_streamlined(
    ui: InteractionPort,
    streamlined: bool,
    title: str,
    message: str,
    *,
    default: bool = True,
) -> bool:
    """Si streamlined, acepta sin preguntar; si no, confirma con el usuario."""
    if streamlined:
        ui.log(f"{title}: automático (flujo simplificado).", level="info")
        return True
    return ui.confirm_yes_no(title, message, default=default)
