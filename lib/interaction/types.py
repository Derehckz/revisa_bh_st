"""Tipos compartidos de interacción."""
from __future__ import annotations

from enum import Enum


class InteractionKind(str, Enum):
    CONFIRM = "confirm"
    CHOICE = "choice"
    SELECT = "select"
    TEXT = "text"
    MAIL_REVIEW = "mail_review"


class SupervisionMode(str, Enum):
    """Granularidad de confirmación en envíos (etapa 1)."""

    BATCH = "batch"
    PER_MAIL = "per_mail"
