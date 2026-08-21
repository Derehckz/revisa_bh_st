"""Arrastre de provisionados: filas aparte, maestro intacto."""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pandas as pd

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
_ETAPAS = os.path.join(_REPO, "etapas")
for _p in (_ETAPAS, _LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "generar_solicitud",
    os.path.join(_ETAPAS, "0.-generar_solicitud.py"),
)
assert _spec and _spec.loader
generar_solicitud = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generar_solicitud)


def _write_solicitud(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cols = [
        "EMPLID",
        "NAME",
        "LOCATION",
        "RUT RAZON",
        "GLOSA",
        "MONTH",
        "YEAR",
        "CUS_TOT_HON",
        "Estado_Recepcion",
        "Email_Docente",
        "Correo Enviado",
    ]
    pd.DataFrame(rows).reindex(columns=cols).to_excel(path, index=False, engine="openpyxl")


def test_arrastre_deja_maestro_intacto_y_crea_fila_provisionado(tmp_path, monkeypatch):
    monkeypatch.setattr(generar_solicitud.config, "RAIZ", str(tmp_path))

    _write_solicitud(
        tmp_path / "2026" / "Mayo" / "Solicitud.xlsx",
        [
            {
                "EMPLID": "17255004-5",
                "NAME": "Bustos",
                "LOCATION": 508,
                "RUT RAZON": "65175239-6",
                "GLOSA": "IP-MAYO",
                "MONTH": "MAYO",
                "YEAR": 2026,
                "CUS_TOT_HON": 30000,
                "Estado_Recepcion": "NO RECIBIDO",
                "Correo Enviado": "",
            }
        ],
    )
    _write_solicitud(
        tmp_path / "2026" / "Junio" / "Solicitud.xlsx",
        [
            {
                "EMPLID": "17255004-5",
                "NAME": "Bustos",
                "LOCATION": 508,
                "RUT RAZON": "65175239-6",
                "GLOSA": "IP-JUNIO",
                "MONTH": "JUNIO",
                "YEAR": 2026,
                "CUS_TOT_HON": 30000,
                "Estado_Recepcion": "NO RECIBIDO",
                "Correo Enviado": "",
            }
        ],
    )

    df_julio = pd.DataFrame(
        [
            {
                "EMPLID": "17255004-5",
                "NAME": "Bustos",
                "LOCATION": 508,
                "RUT RAZON": "65175239-6",
                "GLOSA": "IP-JULIO",
                "MONTH": "JULIO",
                "YEAR": 2026,
                "CUS_TOT_HON": 30000,
                "Estado_Recepcion": "",
                "Correo Enviado": "",
            }
        ]
    )

    def fake_closed(year, month):
        return (str(year), str(month)) == ("2026", "Abril")

    with patch.object(generar_solicitud, "_period_is_closed", side_effect=fake_closed):
        out, n = generar_solicitud.aplicar_arrastre_provisionados(df_julio, "Julio", 2026)

    assert n == 1
    assert len(out) == 2

    maestro = out.iloc[0]
    assert float(maestro["CUS_TOT_HON"]) == 30000.0
    assert str(maestro["GLOSA"]) == "IP-JULIO"

    prov = out.iloc[1]
    assert float(prov["CUS_TOT_HON"]) == 60000.0  # mayo+junio aún NO RECIBIDO
    assert "provisionado" in str(prov["GLOSA"]).lower()


def test_arrastre_no_trae_provision_ya_recibida_en_mes_posterior(tmp_path, monkeypatch):
    """Caso Cornejo: Mayo NO RECIBIDO pagado en Junio como PROVISIONADO RECIBIDO."""
    monkeypatch.setattr(generar_solicitud.config, "RAIZ", str(tmp_path))
    _write_solicitud(
        tmp_path / "2026" / "Mayo" / "Solicitud.xlsx",
        [
            {
                "EMPLID": "11554091-2",
                "NAME": "Cornejo",
                "LOCATION": 508,
                "RUT RAZON": "65175239-6",
                "GLOSA": "IP-MAYO",
                "MONTH": "MAYO",
                "YEAR": 2026,
                "CUS_TOT_HON": 324000,
                "Estado_Recepcion": "NO RECIBIDO",
                "Correo Enviado": "",
            }
        ],
    )
    _write_solicitud(
        tmp_path / "2026" / "Junio" / "Solicitud.xlsx",
        [
            {
                "EMPLID": "11554091-2",
                "NAME": "Cornejo",
                "LOCATION": 508,
                "RUT RAZON": "65175239-6",
                "GLOSA": "IP-JUNIO PROVISIONADO",
                "MONTH": "JUNIO",
                "YEAR": 2026,
                "CUS_TOT_HON": 324000,
                "Estado_Recepcion": "RECIBIDO",
                "Correo Enviado": "",
            }
        ],
    )
    df_julio = pd.DataFrame(
        [
            {
                "EMPLID": "11554091-2",
                "NAME": "Cornejo",
                "LOCATION": 508,
                "RUT RAZON": "65175239-6",
                "GLOSA": "IP-JULIO",
                "MONTH": "JULIO",
                "YEAR": 2026,
                "CUS_TOT_HON": 324000,
                "Estado_Recepcion": "",
                "Correo Enviado": "",
            }
        ]
    )

    def fake_closed(year, month):
        return str(month) == "Abril"

    with patch.object(generar_solicitud, "_period_is_closed", side_effect=fake_closed):
        out, n = generar_solicitud.aplicar_arrastre_provisionados(df_julio, "Julio", 2026)

    assert n == 0
    assert len(out) == 1
    assert float(out.iloc[0]["CUS_TOT_HON"]) == 324000.0
    assert "provisionado" not in str(out.iloc[0]["GLOSA"]).lower()


def test_arrastre_crea_fila_si_no_esta_en_mes_actual(tmp_path, monkeypatch):
    monkeypatch.setattr(generar_solicitud.config, "RAIZ", str(tmp_path))
    _write_solicitud(
        tmp_path / "2026" / "Junio" / "Solicitud.xlsx",
        [
            {
                "EMPLID": "14359985-K",
                "NAME": "Estroz",
                "LOCATION": 508,
                "RUT RAZON": "65175239-6",
                "GLOSA": "IP-JUNIO",
                "MONTH": "JUNIO",
                "YEAR": 2026,
                "CUS_TOT_HON": 30000,
                "Estado_Recepcion": "NO RECIBIDO",
                "Correo Enviado": "x",
            }
        ],
    )
    df_julio = pd.DataFrame(
        [
            {
                "EMPLID": "999",
                "NAME": "Otro",
                "LOCATION": 508,
                "RUT RAZON": "65175239-6",
                "GLOSA": "IP-JULIO",
                "MONTH": "JULIO",
                "YEAR": 2026,
                "CUS_TOT_HON": 1000,
                "Estado_Recepcion": "",
                "Correo Enviado": "",
            }
        ]
    )

    def fake_closed(year, month):
        return str(month) == "Mayo"

    with patch.object(generar_solicitud, "_period_is_closed", side_effect=fake_closed):
        out, n = generar_solicitud.aplicar_arrastre_provisionados(df_julio.copy(), "Julio", 2026)

    assert n == 1
    assert len(out) == 2
    assert float(out.iloc[0]["CUS_TOT_HON"]) == 1000.0
    assert "provisionado" not in str(out.iloc[0]["GLOSA"]).lower()

    added = out[out["EMPLID"].astype(str) == "14359985-K"].iloc[0]
    assert float(added["CUS_TOT_HON"]) == 30000.0
    assert "provisionado" in str(added["GLOSA"]).lower()


def test_arrastre_no_duplica_provisionado_pendiente(tmp_path, monkeypatch):
    """Regresión Contabilidad: PROVISIONADO NO RECIBIDO no se suma otra vez.

    Estroz: Mayo/Junio solo tienen la misma deuda 30k ya marcada PROVISIONADO.
    Julio debe arrastrar 30k, no 60k.
    """
    monkeypatch.setattr(generar_solicitud.config, "RAIZ", str(tmp_path))
    for mes, glosa in (
        ("Mayo", "IP-MAYO PROVISIONADO"),
        ("Junio", "IP-JUNIO PROVISIONADO"),
    ):
        _write_solicitud(
            tmp_path / "2026" / mes / "Solicitud.xlsx",
            [
                {
                    "EMPLID": "14359985-K",
                    "NAME": "Estroz",
                    "LOCATION": 508,
                    "RUT RAZON": "65175239-6",
                    "GLOSA": glosa,
                    "MONTH": mes.upper(),
                    "YEAR": 2026,
                    "CUS_TOT_HON": 30000,
                    "Estado_Recepcion": "NO RECIBIDO",
                    "Correo Enviado": "",
                }
            ],
        )

    df_julio = pd.DataFrame(
        [
            {
                "EMPLID": "999",
                "NAME": "Otro",
                "LOCATION": 508,
                "RUT RAZON": "65175239-6",
                "GLOSA": "IP-JULIO",
                "MONTH": "JULIO",
                "YEAR": 2026,
                "CUS_TOT_HON": 1000,
                "Estado_Recepcion": "",
                "Correo Enviado": "",
            }
        ]
    )

    def fake_closed(year, month):
        return str(month) == "Abril"

    with patch.object(generar_solicitud, "_period_is_closed", side_effect=fake_closed):
        out, n = generar_solicitud.aplicar_arrastre_provisionados(df_julio, "Julio", 2026)

    assert n == 1
    prov = out[out["EMPLID"].astype(str) == "14359985-K"].iloc[0]
    assert float(prov["CUS_TOT_HON"]) == 30000.0
    assert "provisionado" in str(prov["GLOSA"]).lower()


def test_arrastre_suma_mes_nuevo_sin_duplicar_provision_previa(tmp_path, monkeypatch):
    """Bustos CFT: Mayo 60 NR + Junio 30 NR + Junio 60 PROVISIONADO NR → arrastre 90, no 150."""
    monkeypatch.setattr(generar_solicitud.config, "RAIZ", str(tmp_path))
    _write_solicitud(
        tmp_path / "2026" / "Mayo" / "Solicitud.xlsx",
        [
            {
                "EMPLID": "17255004-5",
                "NAME": "Bustos",
                "LOCATION": 114,
                "RUT RAZON": "65175242-6",
                "GLOSA": "CFT-MAYO",
                "MONTH": "MAYO",
                "YEAR": 2026,
                "CUS_TOT_HON": 60000,
                "Estado_Recepcion": "NO RECIBIDO",
                "Correo Enviado": "",
            }
        ],
    )
    _write_solicitud(
        tmp_path / "2026" / "Junio" / "Solicitud.xlsx",
        [
            {
                "EMPLID": "17255004-5",
                "NAME": "Bustos",
                "LOCATION": 114,
                "RUT RAZON": "65175242-6",
                "GLOSA": "CFT-JUNIO",
                "MONTH": "JUNIO",
                "YEAR": 2026,
                "CUS_TOT_HON": 30000,
                "Estado_Recepcion": "NO RECIBIDO",
                "Correo Enviado": "",
            },
            {
                "EMPLID": "17255004-5",
                "NAME": "Bustos",
                "LOCATION": 114,
                "RUT RAZON": "65175242-6",
                "GLOSA": "CFT-JUNIO PROVISIONADO",
                "MONTH": "JUNIO",
                "YEAR": 2026,
                "CUS_TOT_HON": 60000,
                "Estado_Recepcion": "NO RECIBIDO",
                "Correo Enviado": "",
            },
        ],
    )
    df_julio = pd.DataFrame(
        [
            {
                "EMPLID": "17255004-5",
                "NAME": "Bustos",
                "LOCATION": 114,
                "RUT RAZON": "65175242-6",
                "GLOSA": "CFT-JULIO",
                "MONTH": "JULIO",
                "YEAR": 2026,
                "CUS_TOT_HON": 90000,
                "Estado_Recepcion": "",
                "Correo Enviado": "",
            }
        ]
    )

    def fake_closed(year, month):
        return str(month) == "Abril"

    with patch.object(generar_solicitud, "_period_is_closed", side_effect=fake_closed):
        out, n = generar_solicitud.aplicar_arrastre_provisionados(df_julio, "Julio", 2026)

    assert n == 1
    assert len(out) == 2
    assert float(out.iloc[0]["CUS_TOT_HON"]) == 90000.0
    assert "provisionado" not in str(out.iloc[0]["GLOSA"]).lower()
    assert float(out.iloc[1]["CUS_TOT_HON"]) == 90000.0
    assert "provisionado" in str(out.iloc[1]["GLOSA"]).lower()


def test_arrastre_no_cruza_periodo_cerrado(tmp_path, monkeypatch):
    monkeypatch.setattr(generar_solicitud.config, "RAIZ", str(tmp_path))
    _write_solicitud(
        tmp_path / "2026" / "Abril" / "Solicitud.xlsx",
        [
            {
                "EMPLID": "1-9",
                "NAME": "Viejo",
                "LOCATION": 508,
                "RUT RAZON": "65175239-6",
                "GLOSA": "IP-ABRIL",
                "MONTH": "ABRIL",
                "YEAR": 2026,
                "CUS_TOT_HON": 999999,
                "Estado_Recepcion": "NO RECIBIDO",
                "Correo Enviado": "",
            }
        ],
    )
    df_julio = pd.DataFrame(
        [
            {
                "EMPLID": "1-9",
                "NAME": "Viejo",
                "LOCATION": 508,
                "RUT RAZON": "65175239-6",
                "GLOSA": "IP-JULIO",
                "MONTH": "JULIO",
                "YEAR": 2026,
                "CUS_TOT_HON": 100,
                "Estado_Recepcion": "",
                "Correo Enviado": "",
            }
        ]
    )

    def fake_closed(year, month):
        return str(month) == "Abril"

    with patch.object(generar_solicitud, "_period_is_closed", side_effect=fake_closed):
        out, n = generar_solicitud.aplicar_arrastre_provisionados(df_julio, "Julio", 2026)

    assert n == 0
    assert len(out) == 1
    assert float(out.iloc[0]["CUS_TOT_HON"]) == 100.0
    assert str(out.iloc[0]["GLOSA"]) == "IP-JULIO"


def test_arrastre_incluye_mes_anterior_aunque_este_cerrado(tmp_path, monkeypatch):
    """Cerrar julio no puede varar el NO RECIBIDO: agosto debe arrastrarlo."""
    monkeypatch.setattr(generar_solicitud.config, "RAIZ", str(tmp_path))
    _write_solicitud(
        tmp_path / "2026" / "Julio" / "Solicitud.xlsx",
        [
            {
                "EMPLID": "17255004-5",
                "NAME": "Bustos",
                "LOCATION": 508,
                "RUT RAZON": "65175239-6",
                "GLOSA": "IP-JULIO - PROVISIONADO",
                "MONTH": "JULIO",
                "YEAR": 2026,
                "CUS_TOT_HON": 30000,
                "Estado_Recepcion": "NO RECIBIDO",
                "Correo Enviado": "",
            }
        ],
    )
    df_agosto = pd.DataFrame(
        [
            {
                "EMPLID": "17255004-5",
                "NAME": "Bustos",
                "LOCATION": 508,
                "RUT RAZON": "65175239-6",
                "GLOSA": "IP-AGOSTO",
                "MONTH": "AGOSTO",
                "YEAR": 2026,
                "CUS_TOT_HON": 30000,
                "Estado_Recepcion": "",
                "Correo Enviado": "",
            }
        ]
    )

    def fake_closed(year, month):
        return str(month) == "Julio"

    with patch.object(generar_solicitud, "_period_is_closed", side_effect=fake_closed):
        out, n = generar_solicitud.aplicar_arrastre_provisionados(df_agosto, "Agosto", 2026)

    assert n == 1
    assert len(out) == 2
    maestro = out.iloc[0]
    assert str(maestro["GLOSA"]) == "IP-AGOSTO"
    assert float(maestro["CUS_TOT_HON"]) == 30000.0
    prov = out.iloc[1]
    assert "provisionado" in str(prov["GLOSA"]).lower()
    assert float(prov["CUS_TOT_HON"]) == 30000.0


def test_preview_arrastre_lista_filas_sin_escribir(tmp_path, monkeypatch):
    import arrastre_provisionados as arrastre

    monkeypatch.setattr(arrastre.config, "RAIZ", str(tmp_path))
    _write_solicitud(
        tmp_path / "2026" / "Julio" / "Solicitud.xlsx",
        [
            {
                "EMPLID": "17255004-5",
                "NAME": "Bustos",
                "LOCATION": 114,
                "RUT RAZON": "65175242-6",
                "GLOSA": "CFT-JULIO - PROVISIONADO",
                "MONTH": "JULIO",
                "YEAR": 2026,
                "CUS_TOT_HON": 90000,
                "Estado_Recepcion": "NO RECIBIDO",
                "Email_Docente": "cbustos27@santotomas.cl",
                "Correo Enviado": "",
            }
        ],
    )

    def fake_closed(year, month):
        return str(month) == "Julio"

    preview = arrastre.preview_arrastre_provisionados(
        "Agosto", 2026, period_is_closed=fake_closed
    )
    assert preview["count"] == 1
    assert preview["total_monto"] == 90000.0
    assert preview["previous_closed"] is True
    assert preview["rows"][0]["emplid"] == "17255004-5"
    assert preview["rows"][0]["institucion"] == "CFT"
    assert preview["rows"][0]["email"] == "cbustos27@santotomas.cl"
    assert "provisionado" in preview["rows"][0]["glosa"].lower()
    assert not (tmp_path / "2026" / "Agosto" / "Solicitud.xlsx").exists()
