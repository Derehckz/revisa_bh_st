"""Tests de recomendación de siguiente paso."""
from __future__ import annotations

import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import stage_operations  # noqa: E402


def _stage(num: int, ui_status: str, *, enabled: bool = True, email: bool = False) -> dict:
    return {
        "stage_num": num,
        "description": f"Paso {num}",
        "enabled_for_api": enabled,
        "ui_status": ui_status,
        "is_email_stage": email,
        "prerequisites": {"ok": ui_status != "BLOCKED", "message": ""},
        "checklist": [],
    }


class TestRecommendNextAction(unittest.TestCase):
    def test_wait_when_running(self):
        rec = stage_operations.recommend_next_action(
            [_stage(2, "RUNNING")],
            kpis={"solicitud_exists": True},
            running_job={"id": "abc", "stage_num": 2},
        )
        self.assertEqual(rec["kind"], "wait")
        self.assertEqual(rec["stage_num"], 2)

    def test_run_step0_when_no_solicitud(self):
        stages = [_stage(0, "BLOCKED")]
        stages[0]["prerequisites"] = {"ok": False, "message": "Falta maestro"}
        rec = stage_operations.recommend_next_action(
            stages,
            kpis={"solicitud_exists": False},
        )
        self.assertEqual(rec["kind"], "run")
        self.assertEqual(rec["stage_num"], 0)

    def test_fix_blocked_after_solicitud(self):
        stages = [_stage(0, "OK"), _stage(2, "BLOCKED")]
        stages[1]["prerequisites"] = {"ok": False, "message": "Falta carpeta"}
        rec = stage_operations.recommend_next_action(
            stages,
            kpis={"solicitud_exists": True},
        )
        self.assertEqual(rec["kind"], "fix")
        self.assertEqual(rec["stage_num"], 2)

    def test_run_first_ready(self):
        stages = [
            _stage(0, "OK"),
            _stage(1, "OK"),
            _stage(2, "READY"),
            _stage(3, "READY"),
        ]
        rec = stage_operations.recommend_next_action(
            stages,
            kpis={"solicitud_exists": True, "recibidos": 10, "xml_files_in_month": 5},
        )
        self.assertEqual(rec["kind"], "run")
        self.assertEqual(rec["stage_num"], 2)

    def test_retry_on_error(self):
        stages = [_stage(4, "ERROR")]
        rec = stage_operations.recommend_next_action(
            stages,
            kpis={"solicitud_exists": True},
        )
        self.assertEqual(rec["kind"], "run")
        self.assertEqual(rec["stage_num"], 4)


if __name__ == "__main__":
    unittest.main()
