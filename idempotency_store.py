"""Store simple de idempotencia (modo reporte) con SQLite."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime

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
    return conn


def report_duplicate(stage: str, item_key: str) -> bool:
    """Registra ocurrencia. Devuelve True si ya existia (duplicado)."""
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
