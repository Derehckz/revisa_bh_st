"""Tests de contexto operativo (prerequisitos, overview)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
_LIB = os.path.join(_REPO, "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import stage_operations  # noqa: E402


class TestStageOperations(unittest.TestCase):
    def test_prerequisites_summary_blocks_on_failed(self):
        checklist = [
            {"id": "a", "label": "A", "ok": True, "blocking": True},
            {"id": "b", "label": "B", "ok": False, "blocking": True, "message": "falta B"},
        ]
        summary = stage_operations.prerequisites_summary(checklist)
        self.assertFalse(summary["ok"])
        self.assertIn("b", summary["failed_ids"])

    def test_ui_status_blocked_without_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(stage_operations.config, "RAIZ", tmp):
                st = stage_operations.ui_status_for_stage(1, 2026, "Mayo", jobs=[])
        self.assertEqual(st, "BLOCKED")

    def test_ui_status_ok_from_filesystem_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = os.path.join(tmp, "2026", "Mayo", "logs_extraccion")
            os.makedirs(log_dir)
            log_path = os.path.join(log_dir, "log_20260526_115506.txt")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("Proceso completado return_code=0\n")
            with patch.object(stage_operations.config, "RAIZ", tmp):
                with patch("email_outbox.stats_by_status", return_value={}):
                    overview = stage_operations.period_overview(2026, "Mayo", jobs=[])
            stage2 = next(s for s in overview["stages"] if s["stage_num"] == 2)
            self.assertEqual(stage2["ui_status"], "OK")
            self.assertIsNotNone(stage2["last_job"])
            self.assertEqual(stage2["last_job"]["source"], "filesystem")

    def test_period_overview_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "2026", "Mayo"), exist_ok=True)
            with patch.object(stage_operations.config, "RAIZ", tmp):
                with patch(
                    "email_outbox.stats_by_status",
                    return_value={"pending": 1},
                ):
                    overview = stage_operations.period_overview(2026, "Mayo", jobs=[])
        self.assertEqual(overview["period"]["year"], 2026)
        self.assertEqual(overview["period"]["month"], "Mayo")
        self.assertIn("status", overview["period"])
        self.assertIn("stages", overview)
        self.assertGreater(len(overview["stages"]), 0)
        self.assertEqual(overview["outbox_stats"], {"pending": 1})


if __name__ == "__main__":
    unittest.main()
