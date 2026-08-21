"""Clave de boleta: IP/CFT y PROVISIONADO no deben colapsar."""
from __future__ import annotations

import os
import sys
from decimal import Decimal
from types import SimpleNamespace

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for p in (_REPO, _LIB):
    if p not in sys.path:
        sys.path.insert(0, p)

from db.key_builder import build_boleta_key
from db.import_excel_snapshot import select_compatible_boleta


def test_provisionado_key_differs_from_normal_same_monto():
    base = {
        "EMPLID": "17255004-5",
        "CUS_TOT_HON": 30000,
        "RUT RAZON": "65175239-6",
        "GLOSA": "IPST Convenio los lagos Código FDI IST2588-AGOSTO",
    }
    k_normal = build_boleta_key(base)
    k_prov = build_boleta_key({**base, "GLOSA": base["GLOSA"] + " - PROVISIONADO"})
    assert k_normal != k_prov
    assert "|P|0" in k_normal
    assert "|P|1" in k_prov


def test_ip_cft_keys_differ():
    base = {"EMPLID": "8530103-9", "CUS_TOT_HON": 100, "GLOSA": "x"}
    k_cft = build_boleta_key({**base, "RUT RAZON": "65175242-6"})
    k_ip = build_boleta_key({**base, "RUT RAZON": "65175239-6"})
    assert k_cft != k_ip


def test_select_does_not_reuse_only_row_of_other_institution():
    existing = SimpleNamespace(
        rut_razon="65175239-6",
        glosa="IPST …",
        monto_bruto=Decimal("30000"),
        boleta_key="17255004-5|MTO|30000|RR|65175239-6",
    )
    found = select_compatible_boleta(
        [existing],
        rut_razon="65175242-6",
        monto_decimal=Decimal("90000"),
        incoming_prov=True,
    )
    assert found is None


def test_select_does_not_reuse_normal_row_for_provisionado_same_monto():
    existing = SimpleNamespace(
        rut_razon="65175239-6",
        glosa="IPST Convenio AGOSTO",
        monto_bruto=Decimal("30000"),
        boleta_key="x|P|0",
    )
    found = select_compatible_boleta(
        [existing],
        rut_razon="65175239-6",
        monto_decimal=Decimal("30000"),
        incoming_prov=True,
    )
    assert found is None


def test_select_matches_same_identity():
    existing = SimpleNamespace(
        rut_razon="65175239-6",
        glosa="IPST … - PROVISIONADO",
        monto_bruto=Decimal("30000"),
        boleta_key="x|P|1",
    )
    found = select_compatible_boleta(
        [existing],
        rut_razon="65175239-6",
        monto_decimal=Decimal("30000"),
        incoming_prov=True,
    )
    assert found is existing
