"""Tests de historial de ejecuciones (logs en disco + jobs API)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for p in (_REPO, _LIB):
    if p not in sys.path:
        sys.path.insert(0, p)

import ops_execution_history  # noqa: E402


class TestOpsExecutionHistory(unittest.TestCase):
    def test_months_in_range(self):
        months = ops_execution_history._months_in_range(2026, "Enero", "Mayo")
        self.assertEqual(months, ["Enero", "Febrero", "Marzo", "Abril", "Mayo"])

    def test_parse_ts_from_name(self):
        ts = ops_execution_history._parse_ts_from_name("log_20260526_115506.txt")
        self.assertIsNotNone(ts)
        self.assertIn("2026-05-26", ts)

    def test_stage_from_cierre_filename(self):
        stages = ops_execution_history._stage_from_cierre_filename("cierre_5-7_20260526_120000.log")
        self.assertEqual(stages, [5, 6, 7])

    def test_stable_id_deterministic(self):
        a = ops_execution_history._stable_id("2026", "Mayo", "4", "/tmp/x.log")
        b = ops_execution_history._stable_id("2026", "Mayo", "4", "/tmp/x.log")
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("hist_"))

    def test_scan_month_logs_finds_timestamped_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            month_dir = os.path.join(tmp, "2026", "Mayo", "logs_extraccion")
            os.makedirs(month_dir)
            log_path = os.path.join(month_dir, "log_20260526_115506.txt")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("Proceso completado return_code=0\n")

            with mock.patch.object(
                ops_execution_history.config, "RAIZ", tmp
            ):
                entries = ops_execution_history.scan_month_logs(2026, "Mayo")

            self.assertTrue(any(e["stage_num"] == 2 for e in entries))
            self.assertTrue(any(e["log_path"] == log_path for e in entries))

    def test_api_request_log_is_not_a_stage_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = os.path.join(tmp, "2026", "Agosto", "logs_envios")
            os.makedirs(log_dir)
            log_path = os.path.join(log_dir, "envio_boletas.log")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("2026-08-21 12:15:23,740 [INFO] api.request\n" * 20)

            with mock.patch.object(ops_execution_history.config, "RAIZ", tmp):
                entries = ops_execution_history.scan_month_logs(2026, "Agosto")

            self.assertEqual(entries, [])
            self.assertIsNone(ops_execution_history._infer_status_from_log(log_path))

    def test_outlook_send_log_counts_as_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = os.path.join(tmp, "2026", "Julio", "logs_envios")
            os.makedirs(log_dir)
            log_path = os.path.join(log_dir, "envio_boletas.log")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(
                    "2026-07-23 14:09:15 [INFO] [bh-outlook] metric=outcome_send "
                    "outcome=ok attempts=1/3\n"
                    "2026-07-23 14:09:20 [INFO] api.request\n"
                )

            with mock.patch.object(ops_execution_history.config, "RAIZ", tmp):
                entries = ops_execution_history.scan_month_logs(2026, "Julio")

            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["stage_num"], 1)
            self.assertEqual(entries[0]["status"], "success")

    def test_merge_dedupes_api_log_path(self):
        path = "/tmp/shared.log"
        api = [
            {
                "id": "job1",
                "stage_num": 4,
                "status": "success",
                "year": 2026,
                "month": "Mayo",
                "type": "stage",
                "created_at": "t",
                "finished_at": "t",
                "log_path": path,
                "pid": 1,
                "return_code": 0,
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            month_dir = os.path.join(tmp, "2026", "Mayo", "logs_extraccion_xml_excel")
            os.makedirs(month_dir)
            log_path = os.path.join(month_dir, "log_20260526_120000.txt")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("ok return_code=0\n")

            with mock.patch.object(ops_execution_history.config, "RAIZ", tmp):
                merged = ops_execution_history.list_execution_history(
                    year=2026,
                    from_month="Mayo",
                    to_month="Mayo",
                    api_jobs=[{**api[0], "log_path": log_path}],
                    limit=50,
                )
        paths = [e.get("log_path") for e in merged["data"] if e.get("log_path") == log_path]
        self.assertEqual(len(paths), 1)
        self.assertEqual(merged["data"][0]["source"], "api")


if __name__ == "__main__":
    unittest.main()
