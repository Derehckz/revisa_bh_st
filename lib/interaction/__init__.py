"""Capa de interacción desacoplada (CLI, web, batch)."""
from interaction.exceptions import SessionCancelled
from interaction.port import InteractionPort, PromptRequest, PromptResponse
from interaction.types import InteractionKind, SupervisionMode

__all__ = [
    "InteractionPort",
    "InteractionKind",
    "PromptRequest",
    "PromptResponse",
    "SessionCancelled",
    "SupervisionMode",
]
