from __future__ import annotations

import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import app_capabilities  # noqa: E402


def test_capabilities_version_positive():
    assert app_capabilities.CAPABILITIES_VERSION >= 1
    assert app_capabilities.CAPABILITIES.get("glosa_estricta") is True
    assert app_capabilities.CAPABILITIES.get("period_verify_web") is True
    assert app_capabilities.CAPABILITIES.get("db_migrate_web") is True
