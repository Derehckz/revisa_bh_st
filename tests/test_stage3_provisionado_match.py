"""Regresión: fila PROVISIONADO no acepta boleta sin esa glosa; deja descarte claro."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd  # noqa: E402
from interaction.auto_adapter import AutoAdapter  # noqa: E402
from stages.stage3.revision_core import procesar_filas  # noqa: E402


def _minimal_xml(path: Path, *, rut: str, dv: str, receptor: str, total: int, glosa: str, folio: int) -> None:
    path.write_text(
        f"""<?xml version="1.0" encoding="ISO-8859-1"?>
<Documento>
  <rutEmisor>{rut}</rutEmisor>
  <dvEmisor>{dv}</dvEmisor>
  <rutReceptor>{receptor}</rutReceptor>
  <dvReceptor>6</dvReceptor>
  <totalHonorarios>{total}</totalHonorarios>
  <liquidoHonorarios>{total}</liquidoHonorarios>
  <impuestoHonorarios>0</impuestoHonorarios>
  <numeroBoleta>{folio}</numeroBoleta>
  <Descripcion>
    <numeroLinea>1</numeroLinea>
    <descripcionLinea>{glosa}</descripcionLinea>
  </Descripcion>
</Documento>
""",
        encoding="latin-1",
    )


class TestProvisionadoMatch(unittest.TestCase):
    def test_excel_provisionado_rechaza_xml_sin_provisionado(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _minimal_xml(
                root / "bhe_14635781-264.xml",
                rut="14635781",
                dv="4",
                receptor="65175242",
                total=30000,
                glosa="CFTST Convenio los Lagos JULIO",
                folio=264,
            )
            (root / "bhe_14635781-264.pdf").write_bytes(b"%PDF-1.4")

            df = pd.DataFrame(
                [
                    {
                        "EMPLID": "14635781-4",
                        "RUT_SIN_DV": "14635781",
                        "RUT RAZON": "65175242-6",
                        "GLOSA": "CFTST Convenio - PROVISIONADO",
                        "CUS_TOT_HON": 30000,
                        "NAME": "Test",
                    }
                ]
            )
            out, _ = procesar_filas(df, str(root), AutoAdapter())
            self.assertEqual(out.iloc[0]["Estado_Recepcion"], "NO RECIBIDO")
            obs = str(out.iloc[0]["Observaciones"])
            self.assertIn("PROVISIONADO", obs.upper())
            self.assertNotIn("XML", obs.upper())
            self.assertNotIn("LÍNEA", obs.upper())
            descartes = str(out.iloc[0]["Observacion_Descartes"])
            self.assertIn("PROVISIONADO", descartes.upper())
            self.assertIn("264", descartes)


if __name__ == "__main__":
    unittest.main()
