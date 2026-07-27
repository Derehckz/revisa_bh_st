"""Tests unitarios del detector de huecos (sin Outlook)."""
from __future__ import annotations

import inbox_gaps as ig


def test_rut_cuerpo_con_dv():
    assert ig._rut_cuerpo("7819594-0") == "7819594"
    assert ig._rut_cuerpo(7819594) == "7819594"
    assert ig._rut_cuerpo("14.635.781-K") == "14635781"


def test_bhe_name_re():
    m = ig._BHE_NAME_RE.match("bhe_7819594-511.pdf")
    assert m is not None
    assert m.group("rut") == "7819594"
    assert m.group("folio") == "511"
    assert m.group("ext") == "pdf"
