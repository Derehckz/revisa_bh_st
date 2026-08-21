"""Filas sin correo válido se detectan antes del envío (paso 1)."""
from __future__ import annotations

import os
import sys

import pandas as pd

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for p in (_LIB, _REPO):
    if p not in sys.path:
        sys.path.insert(0, p)

import utils
from stages.stage1.mail import filas_sin_correo_valido
from stages.stage1.service import _confirm_envio_message


def test_email_from_cell_normalizes_nan():
    assert utils.email_from_cell(float("nan")) == ""
    assert utils.email_from_cell("nan") == ""
    assert utils.email_from_cell(None) == ""
    assert utils.email_from_cell("  arcos12alvear@gmail.com ") == "arcos12alvear@gmail.com"


def test_validar_email_rejects_nan():
    assert utils.validar_email(float("nan")) is False
    assert utils.validar_email("nan") is False
    assert utils.validar_email("arcos12alvear@gmail.com") is True


def test_filas_sin_correo_valido_lists_name_and_rut():
    df = pd.DataFrame(
        [
            {
                "EMPLID": "17967595-1",
                "NAME": "Arcos Alvear,Francisco Ruben",
                "Email_Docente": "arcos12alvear@gmail.com",
            },
            {
                "EMPLID": "18157697-9",
                "NAME": "Argandoña Zumaran,Leonardo Alberto",
                "Email_Docente": float("nan"),
            },
        ]
    )
    invalidos = filas_sin_correo_valido(df, df.index)
    assert len(invalidos) == 1
    assert invalidos[0]["emplid"] == "18157697-9"
    assert "Argandoña" in invalidos[0]["name"]
    assert invalidos[0]["email"] == "(vacío)"
    assert invalidos[0]["fila"] == 2


def test_confirm_message_includes_invalid_names():
    msg = _confirm_envio_message(
        52,
        [
            {
                "name": "Argandoña Zumaran,Leonardo Alberto",
                "emplid": "18157697-9",
            }
        ],
        "original",
    )
    assert "52 correos originales" in msg
    assert "Argandoña Zumaran,Leonardo Alberto" in msg
    assert "18157697-9" in msg
    assert "no se enviarán" in msg
