"""E3: PeriodLock aplicado a jobs (api/operations.py:start_stage_job)."""
from __future__ import annotations

import os
import sys

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (os.path.join(_REPO, "lib"), os.path.join(_REPO, "api"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config  # noqa: E402
import period_lock  # noqa: E402
import operations as ops  # noqa: E402
from period_lock import PeriodLock  # noqa: E402


class _SyncThread:
    """Reemplaza threading.Thread para ejecutar el job de forma síncrona en tests."""

    def __init__(self, target=None, args=(), daemon=None):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAIZ", str(tmp_path), raising=False)
    monkeypatch.setattr(ops, "_state_root", lambda: str(tmp_path))
    monkeypatch.setattr(ops.stage_commands, "check_prerequisites", lambda *a, **k: None)
    monkeypatch.setattr(
        ops.stage_commands,
        "build_stage_command",
        lambda *a, **k: [sys.executable, "-c", "pass"],
    )
    monkeypatch.setattr(ops.stage_commands, "primary_output_for_stage", lambda *a, **k: None)
    ops._JOBS.clear()
    ops._JOB_LOCKS.clear()
    ops._LOADED = True
    period_lock._ACTIVE_LOCKS.clear()
    yield
    ops._JOBS.clear()
    ops._JOB_LOCKS.clear()
    period_lock._ACTIVE_LOCKS.clear()


def test_start_stage_job_blocked_by_existing_period_lock():
    external_lock = PeriodLock(2026, "Julio", script="interactive-1")
    external_lock.acquire()
    try:
        with pytest.raises(ops.PeriodLockError, match="bloqueado"):
            ops.start_stage_job(0, {"year": 2026, "month": "Julio"})
    finally:
        external_lock.release()


def test_start_stage_job_acquires_and_releases_lock_on_completion(monkeypatch):
    monkeypatch.setattr(ops.threading, "Thread", _SyncThread)

    job = ops.start_stage_job(0, {"year": 2026, "month": "Julio"})
    assert job["status"] == "success"
    # El job síncrono ya terminó: el lock debe haberse liberado.
    assert job["id"] not in ops._JOB_LOCKS
    assert period_lock._ACTIVE_LOCKS.get(("2026", "Julio")) is None

    # Ahora un segundo job para el mismo período no debería toparse con lock.
    job2 = ops.start_stage_job(0, {"year": 2026, "month": "Julio"})
    assert job2["id"] != job["id"]
