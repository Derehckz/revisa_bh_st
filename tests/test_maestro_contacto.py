"""Ficha mínima y filtro de envío por RUT."""
from __future__ import annotations

import os
import sys

import pandas as pd

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for p in (_LIB, _REPO):
    if p not in sys.path:
        sys.path.insert(0, p)

import maestro_contacto
from stages.stage1.service import _confirm_envio_message


def test_ficha_minima_exige_correo_y_sede():
    assert maestro_contacto.ficha_minima_ok("a@b.cl", "VALDIVIA") is True
    assert maestro_contacto.ficha_minima_ok("", "VALDIVIA") is False
    assert maestro_contacto.ficha_minima_ok("a@b.cl", "") is False
    assert maestro_contacto.ficha_minima_ok(float("nan"), "VALDIVIA") is False
    assert maestro_contacto.ficha_error("", "VALDIVIA")
    assert maestro_contacto.ficha_error("a@b.cl", "")


def test_mask_ficha_incompleta_only_merged_rows():
    df = pd.DataFrame(
        [
            {
                "EMPLID": "1-9",
                "merge_status": "both",
                "Correo_Personal": "ok@x.cl",
                "SEDE": "VALDIVIA",
            },
            {
                "EMPLID": "2-7",
                "merge_status": "both",
                "Correo_Personal": "",
                "SEDE": "VALDIVIA",
            },
            {
                "EMPLID": "3-5",
                "merge_status": "left_only",
                "Correo_Personal": "",
                "SEDE": "",
            },
        ]
    )
    mask = maestro_contacto.mask_ficha_incompleta(df)
    assert int(mask.sum()) == 1
    assert bool(mask.iloc[1]) is True


def test_filter_indices_by_emplid():
    df = pd.DataFrame(
        [
            {"EMPLID": "18157697-9", "NAME": "A"},
            {"EMPLID": "17967595-1", "NAME": "B"},
        ]
    )
    kept = maestro_contacto.filter_indices_by_emplid(df, df.index, ["18157697-9"])
    assert list(kept) == [0]


def test_parse_emplid_list_dedupes():
    assert maestro_contacto.parse_emplid_list("18157697-9, 18157697-9 ; 17967595-1") == [
        "18157697-9",
        "17967595-1",
    ]


def test_recipient_payload_marks_invalid():
    df = pd.DataFrame(
        [
            {"EMPLID": "1-9", "NAME": "Ok", "Email_Docente": "ok@x.cl", "SEDE": "VALDIVIA"},
            {"EMPLID": "2-7", "NAME": "Bad", "Email_Docente": float("nan"), "SEDE": "VALDIVIA"},
        ]
    )
    rows = maestro_contacto.recipient_payload(df, df.index, tipo="original")
    assert rows[0]["valid"] is True
    assert rows[1]["valid"] is False
    assert rows[1]["email"] == "(vacío)"


def test_confirm_message_does_not_ask_to_regenerate_step0():
    msg = _confirm_envio_message(1, [{"name": "X", "emplid": "1-9"}], "original")
    assert "no hace falta regenerar el paso 0" in msg
    assert "regenera el paso 0." not in msg
