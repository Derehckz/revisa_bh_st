"""E5: pruebas de lib/sync_status.period_sync_status (sin BD real)."""
from __future__ import annotations

from unittest.mock import patch

import sync_status


def _excel_summary(total_rows: int, solicitud_exists: bool = True) -> dict:
    return {
        "year": 2026,
        "month": "Julio",
        "solicitud_exists": solicitud_exists,
        "total_rows": total_rows,
        "recibidos": 0,
        "no_recibidos": 0,
    }


def test_status_ok_when_counts_match():
    with (
        patch("stage_operations.period_summary", return_value=_excel_summary(20)),
        patch("sync_status._db_boleta_count", return_value=20),
    ):
        out = sync_status.period_sync_status(2026, "Julio")
    assert out["status"] == "ok"
    assert out["details"]["excel_total_rows"] == 20
    assert out["details"]["db_total_boletas"] == 20


def test_status_degraded_when_counts_differ_significantly():
    with (
        patch("stage_operations.period_summary", return_value=_excel_summary(20)),
        patch("sync_status._db_boleta_count", return_value=5),
    ):
        out = sync_status.period_sync_status(2026, "Julio")
    assert out["status"] == "degraded"


def test_status_ok_with_small_rounding_difference():
    with (
        patch("stage_operations.period_summary", return_value=_excel_summary(100)),
        patch("sync_status._db_boleta_count", return_value=98),
    ):
        out = sync_status.period_sync_status(2026, "Julio")
    assert out["status"] == "ok"


def test_status_unknown_when_periodo_missing_in_db():
    with (
        patch("stage_operations.period_summary", return_value=_excel_summary(20)),
        patch("sync_status._db_boleta_count", return_value=None),
    ):
        out = sync_status.period_sync_status(2026, "Julio")
    assert out["status"] == "unknown"


def test_status_unknown_when_db_query_raises():
    with (
        patch("stage_operations.period_summary", return_value=_excel_summary(20)),
        patch("sync_status._db_boleta_count", side_effect=RuntimeError("no db")),
    ):
        out = sync_status.period_sync_status(2026, "Julio")
    assert out["status"] == "unknown"
    assert "no db" in out["message"]


def test_status_unknown_when_excel_read_raises():
    with patch("stage_operations.period_summary", side_effect=RuntimeError("locked file")):
        out = sync_status.period_sync_status(2026, "Julio")
    assert out["status"] == "unknown"


def test_status_unknown_when_no_data_at_all():
    with (
        patch("stage_operations.period_summary", return_value=_excel_summary(0, solicitud_exists=False)),
        patch("sync_status._db_boleta_count", return_value=0),
    ):
        out = sync_status.period_sync_status(2026, "Julio")
    assert out["status"] == "unknown"
