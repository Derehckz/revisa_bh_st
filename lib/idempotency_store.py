"""Store de idempotencia con SQLite.

Este módulo tiene dos roles:

1) Reporte de duplicados (modo observabilidad):
   - `report_duplicate(stage, key)` registra ocurrencias y devuelve True
     si ya existía. Útil para detectar reejecuciones sin bloquear.

2) Idempotencia con enforcement (modo seguridad operativa):
   - `mark_success(stage, key)` marca un envío como exitoso.
   - `was_success(stage, key)` indica si un envío ya fue exitoso.
   - Los scripts de envío de correo deben omitir el envío cuando
     `was_success(...)` es True salvo override explícito (--force-resend).
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Optional

import config


def _db_path() -> str:
    state_dir = os.path.join(config.RAIZ, ".state")
    os.makedirs(state_dir, exist_ok=True)
    return os.path.join(state_dir, "idempotency.sqlite3")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS idempotency_events (
            stage TEXT NOT NULL,
            item_key TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            seen_count INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY(stage, item_key)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS idempotency_success (
            stage TEXT NOT NULL,
            item_key TEXT NOT NULL,
            success_at TEXT NOT NULL,
            details TEXT,
            PRIMARY KEY(stage, item_key)
        )
        """
    )
    return conn


def report_duplicate(stage: str, item_key: str) -> bool:
    """Registra ocurrencia. Devuelve True si ya existía (duplicado)."""
    now = datetime.utcnow().isoformat()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT seen_count FROM idempotency_events WHERE stage = ? AND item_key = ?",
            (stage, item_key),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO idempotency_events(stage, item_key, first_seen_at, seen_count) VALUES (?, ?, ?, 1)",
                (stage, item_key, now),
            )
            return False

        seen_count = int(row[0]) + 1
        conn.execute(
            "UPDATE idempotency_events SET seen_count = ? WHERE stage = ? AND item_key = ?",
            (seen_count, stage, item_key),
        )
        return True


def was_success(stage: str, item_key: str) -> bool:
    """Indica si una operación ya fue ejecutada con éxito previamente."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM idempotency_success WHERE stage = ? AND item_key = ? LIMIT 1",
            (stage, item_key),
        ).fetchone()
        return row is not None


def mark_success(stage: str, item_key: str, details: Optional[str] = None) -> None:
    """Marca una operación como exitosa para evitar reejecuciones futuras."""
    now = datetime.utcnow().isoformat()
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO idempotency_success(stage, item_key, success_at, details)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(stage, item_key) DO UPDATE SET
                success_at = excluded.success_at,
                details = excluded.details
            """,
            (stage, item_key, now, details),
        )


def clear_success(stage: str, item_key: str) -> None:
    """Elimina marca de éxito (útil para forzar reenvío manual de un caso puntual)."""
    with _get_conn() as conn:
        conn.execute(
            "DELETE FROM idempotency_success WHERE stage = ? AND item_key = ?",
            (stage, item_key),
        )
