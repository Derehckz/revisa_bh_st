"""Bitácora durable de intentos de envío de correo (outbox / journal).

Complementa `idempotency_store`: aquí queda constancia de pending/sent/failed
por intento, útil para reconciliación si Outlook falla o el proceso se interrumpe.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Optional

import config


def _db_path() -> str:
    state_dir = os.path.join(config.RAIZ, ".state")
    os.makedirs(state_dir, exist_ok=True)
    return os.path.join(state_dir, "email_outbox.sqlite3")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS email_outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stage TEXT NOT NULL,
            item_key TEXT NOT NULL,
            status TEXT NOT NULL,
            payload TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_outbox_stage_key ON email_outbox(stage, item_key)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_outbox_status ON email_outbox(status)"
    )
    return conn


def record_pending(stage: str, item_key: str, payload: Optional[dict[str, Any]] = None) -> int:
    """Inserta fila en estado pending. Devuelve el id de outbox."""
    now = datetime.utcnow().isoformat()
    blob = json.dumps(payload, ensure_ascii=False) if payload is not None else None
    with _get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO email_outbox(stage, item_key, status, payload, created_at, updated_at, attempts)
            VALUES (?, ?, 'pending', ?, ?, ?, 0)
            """,
            (stage, item_key, blob, now, now),
        )
        return int(cur.lastrowid)


def mark_sent(outbox_id: int) -> None:
    now = datetime.utcnow().isoformat()
    with _get_conn() as conn:
        conn.execute(
            """
            UPDATE email_outbox
            SET status = 'sent', updated_at = ?, attempts = attempts + 1, last_error = NULL
            WHERE id = ?
            """,
            (now, outbox_id),
        )


def mark_failed(outbox_id: int, error: str) -> None:
    now = datetime.utcnow().isoformat()
    with _get_conn() as conn:
        conn.execute(
            """
            UPDATE email_outbox
            SET status = 'failed', updated_at = ?, attempts = attempts + 1, last_error = ?
            WHERE id = ?
            """,
            (now, error[:2000], outbox_id),
        )


def stats_by_status() -> dict[str, int]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) FROM email_outbox GROUP BY status"
        ).fetchall()
    return {str(r[0]): int(r[1]) for r in rows}


def list_rows(
    *,
    status: Optional[str] = None,
    stage_prefix: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    q = "SELECT id, stage, item_key, status, created_at, updated_at, attempts, last_error, payload FROM email_outbox WHERE 1=1"
    params: list[Any] = []
    if status:
        q += " AND status = ?"
        params.append(status)
    if stage_prefix:
        q += " AND stage LIKE ?"
        params.append(f"{stage_prefix}%")
    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with _get_conn() as conn:
        cur = conn.execute(q, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_row_status(outbox_id: int) -> Optional[str]:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM email_outbox WHERE id = ?", (outbox_id,)
        ).fetchone()
    return str(row[0]) if row else None


def fetch_pending_rows(*, limit: int = 50) -> list[dict[str, Any]]:
    """Filas `pending` en orden FIFO (reintentos COM sin re-ejecutar el script completo)."""
    q = (
        "SELECT id, stage, item_key, status, created_at, updated_at, attempts, last_error, payload "
        "FROM email_outbox WHERE status = 'pending' ORDER BY id ASC LIMIT ?"
    )
    with _get_conn() as conn:
        cur = conn.execute(q, (limit,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def reopen_failed_as_pending(*, max_attempts: int = 5, limit: int = 200) -> int:
    """Pone filas failed elegibles en pending para un nuevo intento (p. ej. tras corregir Outlook)."""
    now = datetime.utcnow().isoformat()
    with _get_conn() as conn:
        ids = [
            int(r[0])
            for r in conn.execute(
                """
                SELECT id FROM email_outbox
                WHERE status = 'failed' AND attempts < ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (max_attempts, limit),
            ).fetchall()
        ]
        n = 0
        for oid in ids:
            conn.execute(
                """
                UPDATE email_outbox
                SET status = 'pending', updated_at = ?, attempts = 0, last_error = NULL
                WHERE id = ?
                """,
                (now, oid),
            )
            n += 1
        return n
