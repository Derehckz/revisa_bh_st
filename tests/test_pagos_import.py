"""Import de pagos Contabilidad → hoja Pagos."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

import pandas as pd

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for p in (_REPO, _LIB):
    if p not in sys.path:
        sys.path.insert(0, p)

import pagos_import  # noqa: E402


class TestPagosImport(unittest.TestCase):
    def test_parse_amount_preserves_miles_format(self):
        self.assertEqual(pagos_import._parse_amount_miles("91.53"), 91.53)
        self.assertEqual(pagos_import._parse_amount_miles("91,53"), 91.53)
        self.assertEqual(pagos_import._parse_amount_miles(108), 108.0)

    def test_parse_cuenta_avoids_scientific(self):
        self.assertEqual(pagos_import._parse_cuenta(5.51e10), "55100000000")
        self.assertEqual(pagos_import._parse_cuenta("272012101"), "272012101")

    def test_build_pagos_maps_columns_and_mail_sede(self):
        src = pd.DataFrame(
            [
                {
                    "Descripción": "Boleta Pago CFT",
                    "RUT": "67.170.63-6",
                    "RE": 0,
                    "Nombre": "Test",
                    "Ubicación": 114,
                    "Número Boleta": 10,
                    "Bruto $": 108,
                    "RETENCIÓN": 16.47,
                    "LÍQUIDO": 91.53,
                    "FORMA PAGO": "Cuenta Corriente",
                    "BANCO": "BCI",
                    "NºCUENTA": "272012101",
                }
            ]
        )
        mapped = pagos_import._map_columns(src)
        out = pagos_import.build_pagos_dataframe(
            mapped,
            mail_by_rut={"6717063-6": "a@test.cl"},
            sede_by_rut={"6717063-6": "Online"},
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out.iloc[0]["ID"], "6717063-6")
        self.assertEqual(out.iloc[0]["MAIL"], "a@test.cl")
        self.assertEqual(out.iloc[0]["SEDE"], "Online")
        self.assertEqual(float(out.iloc[0]["LÍQUIDO"]), 91.53)

    def test_dataframe_from_html_paste(self):
        html = """
        <table>
          <tr><th>ID</th><th>Nombre</th><th>LÍQUIDO</th><th>NªCUENTA</th></tr>
          <tr><td>6717063-6</td><td>Ana</td><td>91.53</td><td>272012101</td></tr>
        </table>
        """
        df = pagos_import.dataframe_from_paste(html)
        self.assertIn("ID", df.columns)
        self.assertEqual(str(df.iloc[0]["ID"]), "6717063-6")
        out = pagos_import.build_pagos_dataframe(
            df, mail_by_rut={"6717063-6": "a@test.cl"}, sede_by_rut={"6717063-6": "TALCA"}
        )
        self.assertEqual(out.iloc[0]["MAIL"], "a@test.cl")
        self.assertEqual(out.iloc[0]["SEDE"], "TALCA")
        self.assertEqual(float(out.iloc[0]["LÍQUIDO"]), 91.53)

    def test_dataframe_from_tsv_paste(self):
        tsv = "ID\tNombre\tLÍQUIDO\tNªCUENTA\n14359985-K\tEstroz\t50.85\t12345678\n"
        df = pagos_import.dataframe_from_paste(tsv)
        out = pagos_import.build_pagos_dataframe(df, mail_by_rut={"14359985-K": "x@y.cl"})
        self.assertEqual(out.iloc[0]["MAIL"], "x@y.cl")
        self.assertEqual(float(out.iloc[0]["LÍQUIDO"]), 50.85)

    def test_roundtrip_xlsx(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "contab.xlsx")
            pd.DataFrame(
                [
                    {
                        "Descripción": "Boleta Pago IPS",
                        "ID": "14359985-K",
                        "RE": 0,
                        "Nombre": "Estroz",
                        "Bruto $": "60",
                        "RETENCIÓN": "9.15",
                        "LÍQUIDO": "50.85",
                        "NªCUENTA": 12345678,
                    }
                ]
            ).to_excel(src, index=False)
            df = pagos_import.load_contabilidad_dataframe(src)
            out = pagos_import.build_pagos_dataframe(df, mail_by_rut={"14359985-K": "x@y.cl"})
            self.assertEqual(float(out.iloc[0]["Bruto $"]), 60.0)
            self.assertEqual(out.iloc[0]["MAIL"], "x@y.cl")


if __name__ == "__main__":
    unittest.main()
