"""Clave de idempotencia etapa 1: IP/CFT y filas provisionadas distintas."""
from __future__ import annotations

import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for p in (_LIB, _REPO):
    if p not in sys.path:
        sys.path.insert(0, p)

from stages.stage1.mail import build_mail_item_key, es_glosa_provisionado
from outbox_com_dispatch import _parse_script1_parts, _script1_find_idx
import pandas as pd


def test_item_key_differs_by_rut_razon_same_email():
    k_ip = build_mail_item_key(2026, "Julio", "19389494-1", "76.123.456-7", "docente@example.com")
    k_cft = build_mail_item_key(2026, "Julio", "19389494-1", "77.987.654-3", "docente@example.com")
    assert k_ip != k_cft


def test_item_key_same_for_identical_boleta():
    args = (2026, "Julio", "19389494-1", "76.123.456-7", "docente@example.com")
    assert build_mail_item_key(*args) == build_mail_item_key(*args)


def test_item_key_provisionado_differs_from_normal():
    common = dict(
        año=2026,
        mes="Julio",
        rut_docente="19389494-1",
        rut_razon="76.123.456-7",
        email="docente@example.com",
    )
    k_normal = build_mail_item_key(**common, glosa="Honorarios julio")
    k_prov = build_mail_item_key(**common, glosa="Honorarios julio PROVISIONADO")
    assert k_normal != k_prov
    assert k_prov.endswith("|prov")
    assert "|prov" not in k_normal


def test_item_key_provisionado_recordatorio_suffix():
    k = build_mail_item_key(
        2026,
        "Julio",
        "19389494-1",
        "76.123.456-7",
        "a@b.cl",
        glosa="PROVISIONADO",
        recordatorio_num=2,
    )
    assert k.endswith("|prov|r2")


def test_es_glosa_provisionado():
    assert es_glosa_provisionado("Servicios PROVISIONADO mayo")
    assert es_glosa_provisionado("provisonado")
    assert not es_glosa_provisionado("Honorarios julio")


def test_parse_script1_parts_with_prov_and_razon():
    año, mes, rut, email, rr, prov = _parse_script1_parts(
        "2026|julio|19389494-1|761234567|docente@example.com|prov"
    )
    assert (año, mes, rut, email) == ("2026", "julio", "19389494-1", "docente@example.com")
    assert rr is not None
    assert prov is True


def test_script1_find_idx_prefers_matching_provisionado_flag():
    df = pd.DataFrame(
        [
            {
                "YEAR": 2026,
                "MONTH": "JULIO",
                "EMPLID": "111-1",
                "Email_Docente": "a@b.cl",
                "RUT RAZON": "76.111.111-1",
                "GLOSA": "Honorarios",
            },
            {
                "YEAR": 2026,
                "MONTH": "JULIO",
                "EMPLID": "111-1",
                "Email_Docente": "a@b.cl",
                "RUT RAZON": "76.111.111-1",
                "GLOSA": "Honorarios PROVISIONADO",
            },
        ]
    )
    idx_n = _script1_find_idx(
        df, "2026", "Julio", "111-1", "a@b.cl", rut_razon="76.111.111-1", provisionado=False
    )
    idx_p = _script1_find_idx(
        df, "2026", "Julio", "111-1", "a@b.cl", rut_razon="76.111.111-1", provisionado=True
    )
    assert idx_n == 0
    assert idx_p == 1
