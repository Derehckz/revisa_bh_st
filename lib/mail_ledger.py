"""Fachada única de correo: outbox + idempotencia (MailLedger)."""
from __future__ import annotations

from typing import Any, Optional

import email_outbox
import idempotency_store


def was_sent(stage: str, item_key: str) -> bool:
    return idempotency_store.was_success(stage, item_key)


def mark_sent(stage: str, item_key: str, *, details: Optional[str] = None) -> None:
    idempotency_store.mark_success(stage, item_key, details=details)


def clear_sent(stage: str, item_key: str) -> None:
    idempotency_store.clear_success(stage, item_key)


def record_pending(stage: str, item_key: str, payload: Optional[dict[str, Any]] = None) -> int:
    return email_outbox.record_pending(stage, item_key, payload)


def mark_outbox_sent(outbox_id: int) -> None:
    email_outbox.mark_sent(outbox_id)


def mark_outbox_failed(outbox_id: int, error: str) -> None:
    email_outbox.mark_failed(outbox_id, error)


def report_attempt(stage: str, item_key: str) -> bool:
    return idempotency_store.report_duplicate(stage, item_key)


def list_outbox(*, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    return email_outbox.list_rows(status=status, limit=limit)


def stats_by_status() -> dict[str, int]:
    return email_outbox.stats_by_status()
