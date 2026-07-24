"""E11: SyncProjector.apply_hints (sin BD real)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import sync_projector


def test_apply_hints_ok_status():
    with patch(
        "sync_status.period_sync_status",
        return_value={"status": "ok", "message": "alineado", "details": {"excel": 10, "db": 10}},
    ):
        out = sync_projector.apply_hints(2026, "Julio")
    assert out["ok"] is True
    assert out["status"] == "ok"
    assert out["details"]["excel"] == 10


def test_apply_hints_degraded():
    with patch(
        "sync_status.period_sync_status",
        return_value={"status": "degraded", "message": "drift", "details": {}},
    ):
        out = sync_projector.apply_hints(2026, "Julio", {"reason": "manual"})
    assert out["ok"] is False
    assert out["status"] == "degraded"


def test_apply_hints_handles_exception():
    with patch("sync_status.period_sync_status", side_effect=RuntimeError("boom")):
        out = sync_projector.apply_hints(2026, "Julio")
    assert out["ok"] is False
    assert out["status"] == "unknown"
    assert "boom" in out["message"]


def test_apply_hints_ensure_periods_from_disk():
    fake_config = MagicMock()
    fake_config.RAIZ = "/tmp/bh"
    with (
        patch.dict("sys.modules", {"config": fake_config}),
        patch("db.period_sync.ensure_periods_from_disk", return_value=2) as ensure,
        patch(
            "sync_status.period_sync_status",
            return_value={"status": "ok", "message": "alineado"},
        ),
    ):
        out = sync_projector.apply_hints(2026, "Julio", {"ensure_periods_from_disk": True})
    ensure.assert_called_once_with("/tmp/bh")
    assert out["ok"] is True
    assert out.get("periods_created") == 2
