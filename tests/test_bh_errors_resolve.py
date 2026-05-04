import os

import bh_errors
import pytest
import utils


def test_format_bh():
    assert "[BH-X]" in bh_errors.format_bh("x", "msg")


def test_resolve_año_mes_explicit(tmp_path):
    raiz = str(tmp_path / "r")
    os.makedirs(os.path.join(raiz, "2026", "Abril"), exist_ok=True)
    y, m = utils.resolve_año_mes(raiz, "2026", "Abril")
    assert y == "2026" and m == "Abril"


def test_resolve_period_incomplete():
    with pytest.raises(ValueError) as ei:
        utils.resolve_año_mes(".", "2026", None)
    assert "PERIOD_INCOMPLETE" in str(ei.value)
