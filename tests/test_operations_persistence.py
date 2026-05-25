import json
import os
import sys
import tempfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (os.path.join(_REPO, "lib"), os.path.join(_REPO, "api"), _REPO):
    if p not in sys.path:
        sys.path.insert(0, p)

import operations as ops


def test_persist_and_reload_job(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        jobs_dir = os.path.join(td, "ops-jobs")
        os.makedirs(jobs_dir)

        def fake_jobs_dir():
            return jobs_dir

        def fake_state_root():
            return td

        monkeypatch.setattr(ops, "_jobs_dir", fake_jobs_dir)
        monkeypatch.setattr(ops, "_state_root", fake_state_root)
        ops._JOBS.clear()
        ops._LOADED = False

        job = {
            "id": "abc123test01",
            "stage_num": 0,
            "type": "stage0_test",
            "status": "success",
            "year": 2026,
            "month": "Mayo",
            "created_at": "2026-05-25T12:00:00+00:00",
            "log_path": os.path.join(jobs_dir, "abc123test01.log"),
            "pid": None,
            "return_code": 0,
            "finished_at": "2026-05-25T12:01:00+00:00",
        }
        ops._persist_job(job)

        ops._JOBS.clear()
        ops._LOADED = False
        loaded = ops.get_job("abc123test01")
        assert loaded is not None
        assert loaded["status"] == "success"
        assert loaded["stage_num"] == 0

        listed = ops.list_jobs(limit=5)
        assert any(j["id"] == "abc123test01" for j in listed)
