"""Cruzado informe final vs Pagos Contabilidad."""
from __future__ import annotations

import os
import sys
import unittest

import pandas as pd

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for p in (_REPO, _LIB):
    if p not in sys.path:
        sys.path.insert(0, p)

import pagos_informe_cruzado as cruzado  # noqa: E402


def _resumen_row(**kwargs):
    base = {
        "RUT": "6717063-6",
        "Nombre Docente": "Ana",
        "Reg empleo": 0,
        "LOCATION": 114,
        "INS": "CFT",
        "Nombre Sede": "Matriz LL",
        "N° Boleta": 132,
        "Tipo Doc": "15.25",
        "Tipo de Pago": "OK",
        "Fecha emisión": "01/07/2026",
        "Monto Bruto": 108000,
    }
    base.update(kwargs)
    return base


def _pagos_row(**kwargs):
    base = {
        "ID": "6717063-6",
        "Nombre": "Ana",
        "Ubicación": 114,
        "SEDE": "Online",
        "Número Boleta": 132,
        "Tipo Documento": "BER",
        "Bruto $": 108.0,
        "RETENCIÓN": 16.47,
        "LÍQUIDO": 91.53,
        "Liquido Final": 91.53,
    }
    base.update(kwargs)
    return base


def _xml_index_ok():
    return {
        "by_boleta": {
            "6717063-6|132": {
                "bruto": 108000,
                "retencion": 16470,
                "liquido": 91530,
                "pct": 15.25,
                "sede": "TALCA",
                "location": "114",
                "nombre": "Ana",
                "re": "0",
            }
        },
        "by_re_loc": {},
    }


class TestPagosInformeCruzado(unittest.TestCase):
    def test_perfect_match_miles_to_pesos(self):
        resumen = pd.DataFrame([_resumen_row()])
        pagos = pd.DataFrame([_pagos_row()])
        result = cruzado.compare_informe_vs_pagos(
            resumen=resumen, pagos=pagos, xml_index=_xml_index_ok()
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["errors_count"], 0)
        self.assertEqual(result["totals"]["informe_bruto"], 108000)
        self.assertEqual(result["totals"]["pagos_bruto"], 108000)

    def test_only_in_informe(self):
        resumen = pd.DataFrame([_resumen_row(), _resumen_row(RUT="14359985-K", **{"N° Boleta": 99})])
        pagos = pd.DataFrame([_pagos_row()])
        result = cruzado.compare_informe_vs_pagos(
            resumen=resumen, pagos=pagos, xml_index=_xml_index_ok()
        )
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["only_in_informe"]), 1)
        self.assertEqual(result["only_in_informe"][0]["rut"], "14359985-K")

    def test_only_in_pagos(self):
        resumen = pd.DataFrame([_resumen_row()])
        pagos = pd.DataFrame(
            [
                _pagos_row(),
                _pagos_row(ID="14359985-K", **{"Número Boleta": 50, "Nombre": "Extra"}),
            ]
        )
        result = cruzado.compare_informe_vs_pagos(
            resumen=resumen, pagos=pagos, xml_index=_xml_index_ok()
        )
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["only_in_pagos"]), 1)
        self.assertEqual(result["only_in_pagos"][0]["rut"], "14359985-K")

    def test_bruto_mismatch(self):
        resumen = pd.DataFrame([_resumen_row()])
        pagos = pd.DataFrame([_pagos_row(**{"Bruto $": 90.0, "RETENCIÓN": 13.725, "LÍQUIDO": 76.275})])
        xml = _xml_index_ok()
        result = cruzado.compare_informe_vs_pagos(resumen=resumen, pagos=pagos, xml_index=xml)
        self.assertFalse(result["ok"])
        fields = {m["field"] for m in result["amount_mismatches"]}
        self.assertIn("bruto", fields)

    def test_retencion_mismatch(self):
        resumen = pd.DataFrame([_resumen_row()])
        pagos = pd.DataFrame([_pagos_row(**{"RETENCIÓN": 20.0, "LÍQUIDO": 88.0})])
        result = cruzado.compare_informe_vs_pagos(
            resumen=resumen, pagos=pagos, xml_index=_xml_index_ok()
        )
        self.assertFalse(result["ok"])
        fields = {m["field"] for m in result["amount_mismatches"]}
        self.assertIn("retencion", fields)

    def test_pct_mismatch_from_amounts(self):
        resumen = pd.DataFrame([_resumen_row()])
        # Bruto and liquido match-ish but retención implies ~10%
        pagos = pd.DataFrame(
            [_pagos_row(**{"Bruto $": 108.0, "RETENCIÓN": 10.8, "LÍQUIDO": 97.2, "Liquido Final": 97.2})]
        )
        result = cruzado.compare_informe_vs_pagos(
            resumen=resumen, pagos=pagos, xml_index=_xml_index_ok()
        )
        self.assertFalse(result["ok"])
        self.assertTrue(result["pct_mismatches"] or result["amount_mismatches"])

    def test_amount_tolerance_one_peso(self):
        resumen = pd.DataFrame([_resumen_row(**{"Monto Bruto": 108000})])
        # 108.001 miles → rounds near 108001; use exact match via normalizer
        pagos = pd.DataFrame([_pagos_row()])
        xml = _xml_index_ok()
        # tweak xml bruto off by 1
        xml["by_boleta"]["6717063-6|132"]["bruto"] = 108001
        xml["by_boleta"]["6717063-6|132"]["retencion"] = 16470
        xml["by_boleta"]["6717063-6|132"]["liquido"] = 91530
        result = cruzado.compare_informe_vs_pagos(resumen=resumen, pagos=pagos, xml_index=xml)
        # |108000-108001| = 1 → within tolerance for bruto comparison uses xml bruto vs pagos
        # pagos bruto 108000 vs xml 108001 → diff 1 → OK
        bruto_m = [m for m in result["amount_mismatches"] if m["field"] == "bruto"]
        self.assertEqual(bruto_m, [])

    def test_pct_tipo_documento_ber_accepts_15_25(self):
        resumen = pd.DataFrame([_resumen_row()])
        # Sin montos de retención útiles → cae a Tipo Documento BER
        pagos = pd.DataFrame(
            [_pagos_row(**{"Bruto $": "", "RETENCIÓN": "", "LÍQUIDO": 91.53, "Tipo Documento": "BER"})]
        )
        xml = {
            "by_boleta": {
                "6717063-6|132": {
                    "bruto": None,
                    "retencion": None,
                    "liquido": 91530,
                    "pct": 15.25,
                    "sede": "",
                    "location": "114",
                    "nombre": "Ana",
                    "re": "0",
                }
            },
            "by_re_loc": {},
        }
        result = cruzado.compare_informe_vs_pagos(resumen=resumen, pagos=pagos, xml_index=xml)
        self.assertEqual(result["pct_mismatches"], [])


if __name__ == "__main__":
    unittest.main()
