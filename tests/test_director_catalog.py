"""Catálogo DP por sede: overlay de Email_DP y normalización."""
from __future__ import annotations

import os
import sys

import pandas as pd

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for p in (_LIB, _REPO):
    if p not in sys.path:
        sys.path.insert(0, p)

import director_catalog as cat


def test_canonical_sede_uppercases_valdivia():
    assert cat.canonical_sede("Valdivia") == "VALDIVIA"
    assert cat.canonical_sede("  los   angeles ") == "LOS ANGELES"


def test_mapping_majority_vote():
    mapping = cat.mapping_from_pairs(
        [
            ("Valdivia", "saleuy@santotomas.cl"),
            ("VALDIVIA", "saleuy@santotomas.cl"),
            ("Temuco", "lescalante@santotomas.cl"),
            ("Valdivia", "otro@x.cl"),
        ]
    )
    assert mapping["VALDIVIA"] == "saleuy@santotomas.cl"
    assert mapping["TEMUCO"] == "lescalante@santotomas.cl"


def test_apply_email_dp_fills_empty_from_sede():
    df = pd.DataFrame(
        [
            {"NAME": "Argandoña", "SEDE": "Valdivia", "Email_DP": ""},
            {"NAME": "Arcos", "SEDE": "VALDIVIA", "Email_DP": "saleuy@santotomas.cl"},
        ]
    )
    mapping = {"VALDIVIA": "saleuy@santotomas.cl"}
    out, n = cat.apply_email_dp_from_sede(df, mapping=mapping)
    assert n == 1
    assert out.iloc[0]["Email_DP"] == "saleuy@santotomas.cl"
    assert out.iloc[1]["Email_DP"] == "saleuy@santotomas.cl"
