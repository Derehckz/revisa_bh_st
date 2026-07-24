"""E3: PeriodLock aplicado a sesiones interactivas (api/interactive/sessions.py)."""
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
from api.interactive import sessions as sessions_module  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAIZ", str(tmp_path), raising=False)
    monkeypatch.setattr(sessions_module, "_state_root", lambda: str(tmp_path))
    monkeypatch.setattr("stage_commands.validate_interactive_params", lambda *a, **k: None)
    sessions_module._SESSIONS.clear()
    period_lock._ACTIVE_LOCKS.clear()
    yield
    sessions_module._SESSIONS.clear()
    period_lock._ACTIVE_LOCKS.clear()


def test_create_session_acquires_period_lock():
    meta = sessions_module.create_session(1, {"year": 2026, "month": "Julio"})
    live = sessions_module.get_live_session(meta["id"])
    assert live.get("lock") is not None
    assert live["lock"].read() is not None


def test_conflicting_period_lock_raises_clear_error():
    sessions_module.create_session(1, {"year": 2026, "month": "Julio"})

    with pytest.raises(ValueError, match="bloqueado"):
        sessions_module.create_session(2, {"year": 2026, "month": "Julio"})


def test_different_period_does_not_conflict():
    sessions_module.create_session(1, {"year": 2026, "month": "Julio"})
    meta2 = sessions_module.create_session(1, {"year": 2026, "month": "Agosto"})
    assert meta2["month"] == "Agosto"


def test_cancel_session_releases_lock_allowing_new_session():
    meta = sessions_module.create_session(1, {"year": 2026, "month": "Julio"})
    sessions_module.cancel_session(meta["id"])

    meta2 = sessions_module.create_session(2, {"year": 2026, "month": "Julio"})
    assert meta2["id"] != meta["id"]


def test_terminal_status_releases_lock():
    meta = sessions_module.create_session(1, {"year": 2026, "month": "Agosto"})
    sessions_module.update_session_status(meta["id"], "completed", result={"ok": True})

    meta2 = sessions_module.create_session(3, {"year": 2026, "month": "Agosto"})
    assert meta2["id"] != meta["id"]


def test_release_session_lock_if_held_is_safe_after_release():
    meta = sessions_module.create_session(1, {"year": 2026, "month": "Septiembre"})
    sessions_module.update_session_status(meta["id"], "failed", result={"error": "x"})
    # Segunda liberación (p.ej. desde runner.finally) no debe romper nada.
    sessions_module.release_session_lock_if_held(meta["id"])
