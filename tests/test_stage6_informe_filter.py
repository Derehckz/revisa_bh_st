"""Paso 6: el informe final no debe incluir errores ni no recibidos."""
from __future__ import annotations

import os
import sys
import unittest

import pandas as pd

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
_ETAPAS = os.path.join(_REPO, "etapas")
for _p in (_LIB, _ETAPAS, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import importlib.util

_SPEC = importlib.util.spec_from_file_location(
    "informe_final_boletas",
    os.path.join(_ETAPAS, "6.-Informe_final_boletas.py"),
)
informe = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(informe)


def _fila(**kwargs):
    base = {
        "Estado_Recepcion": "RECIBIDO",
        "Observaciones_XML": "Datos extraídos OK",
        "GLOSA": "IPST Convenio los lagos Código FDI IST2588-JULIO",
        "descripcionLinea_XML": "IPST CONVENIO LOS LAGOS CODIGO FDI IST2588-JULIO",
        "Observaciones": "OK",
        "numeroBoleta_XML": 100,
        "NAME": "Test",
    }
    base.update(kwargs)
    return base


class TestStage6InformeFilter(unittest.TestCase):
    def test_incluye_recibido_ok(self):
        ok, reason = informe.fila_incluible_en_informe_final(_fila())
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_incluye_glosa_con_prefijo_omitido(self):
        ok, reason = informe.fila_incluible_en_informe_final(
            _fila(descripcionLinea_XML="CONVENIO LOS LAGOS CODIGO FDI IST2588-JULIO")
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_excluye_glosa_mes_distinto(self):
        ok, reason = informe.fila_incluible_en_informe_final(
            _fila(descripcionLinea_XML="IPST CONVENIO LOS LAGOS CODIGO FDI IST2588-JUNIO")
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "glosa_incorrecta")

    def test_excluye_recibido_con_error(self):
        ok, reason = informe.fila_incluible_en_informe_final(
            _fila(Estado_Recepcion="RECIBIDO CON ERROR")
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "recibido_con_error")

    def test_excluye_no_recibido(self):
        ok, reason = informe.fila_incluible_en_informe_final(
            _fila(Estado_Recepcion="NO RECIBIDO")
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "no_recibido")

    def test_excluye_extraccion_fallida(self):
        ok, reason = informe.fila_incluible_en_informe_final(
            _fila(Observaciones_XML="Monto distinto")
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "extraccion_xml")

    def test_filtrar_dataframe(self):
        df = pd.DataFrame(
            [
                _fila(NAME="OK", numeroBoleta_XML=1),
                _fila(
                    NAME="Glosa JUNIO",
                    numeroBoleta_XML=433,
                    descripcionLinea_XML="IPST CONVENIO LOS LAGOS CODIGO FDI IST2588-JUNIO",
                ),
                _fila(NAME="Error", numeroBoleta_XML=2, Estado_Recepcion="RECIBIDO CON ERROR"),
                _fila(NAME="Pendiente", numeroBoleta_XML=3, Estado_Recepcion="NO RECIBIDO"),
            ]
        )
        incluido, exclusiones = informe.filtrar_filas_informe_final(df)
        self.assertEqual(len(incluido), 1)
        self.assertEqual(incluido.iloc[0]["NAME"], "OK")
        self.assertEqual(exclusiones.get("glosa_incorrecta"), 1)
        self.assertEqual(exclusiones.get("recibido_con_error"), 1)
        self.assertEqual(exclusiones.get("no_recibido"), 1)


if __name__ == "__main__":
    unittest.main()
