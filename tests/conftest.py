import os
import sys

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (os.path.join(_root, "lib"), _root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest


@pytest.fixture()
def bh_raiz_tmp(monkeypatch, tmp_path):
    """Raíz de proyecto aislada para SQLite bajo .state/."""
    raiz = str(tmp_path / "bh_root")
    os.makedirs(raiz, exist_ok=True)
    monkeypatch.setattr("config.RAIZ", raiz, raising=False)
    yield raiz
