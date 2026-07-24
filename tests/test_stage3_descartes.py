"""Tests columna Observacion_Descartes (etapa 3)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "lib"))

from interaction.auto_adapter import AutoAdapter
from stages.stage3 import revision_core as core


class _DummyUI:
    def progress(self, *_args, **_kwargs):
        return None

    def table(self, *_args, **_kwargs):
        return None

    def log(self, *_args, **_kwargs):
        return None

    def emit(self, *_args, **_kwargs):
        return None


def _write_xml(path: Path, *, rut_emisor: str, rut_receptor: str, dv: str, monto: str) -> None:
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<root>
  <rutEmisor>{rut_emisor}</rutEmisor>
  <rutReceptor>{rut_receptor}</rutReceptor>
  <dvReceptor>{dv}</dvReceptor>
  <totalHonorarios>{monto}</totalHonorarios>
  <descripcionLinea>Honorarios</descripcionLinea>
</root>
""",
        encoding="utf-8",
    )


class Stage3DescartesTests(unittest.TestCase):
    def test_registra_boleta_descartada_por_monto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            xml_name = "bhe_123456789_100.xml"
            pdf_name = "bhe_123456789_100.pdf"
            _write_xml(
                carpeta / xml_name,
                rut_emisor="12345678-9",
                rut_receptor="65175242",
                dv="6",
                monto="25000",
            )
            (carpeta / pdf_name).write_bytes(b"%PDF")

            df = pd.DataFrame(
                [
                    {
                        "RUT_SIN_DV": "12345678-9",
                        "RUT RAZON": "65175242-6",
                        "CUS_TOT_HON": 30000,
                        "GLOSA": "Honorarios",
                        "Estado_Recepcion": "",
                        "Observaciones": "",
                    }
                ]
            )

            df_out, _stats = core.procesar_filas(df, str(carpeta), _DummyUI())
            descartes = str(df_out.iloc[0]["Observacion_Descartes"])
            self.assertIn(xml_name, descartes)
            self.assertIn("monto XML", descartes)
            self.assertEqual(df_out.iloc[0]["Estado_Recepcion"], "NO RECIBIDO")

    def test_filas_mismo_docente_no_mezclan_descartes_en_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            xml_ip = "bhe_10279931330_330.xml"
            pdf_ip = "bhe_10279931330_330.pdf"
            _write_xml(
                carpeta / xml_ip,
                rut_emisor="10279931-3",
                rut_receptor="65175242",
                dv="6",
                monto="384000",
            )
            (carpeta / pdf_ip).write_bytes(b"%PDF")

            df = pd.DataFrame(
                [
                    {
                        "RUT_SIN_DV": "10279931-3",
                        "RUT RAZON": "65175220-6",
                        "CUS_TOT_HON": 108000,
                        "GLOSA": "Honorarios IP",
                        "Estado_Recepcion": "",
                        "Observaciones": "",
                    },
                    {
                        "RUT_SIN_DV": "10279931-3",
                        "RUT RAZON": "65175242-6",
                        "CUS_TOT_HON": 384000,
                        "GLOSA": "Honorarios CFT",
                        "Estado_Recepcion": "",
                        "Observaciones": "",
                    },
                ]
            )

            df_out, _stats = core.procesar_filas(df, str(carpeta), _DummyUI())
            fila_ip = df_out.iloc[0]
            fila_cft = df_out.iloc[1]

            self.assertEqual(fila_ip["Estado_Recepcion"], "NO RECIBIDO")
            self.assertIn("monto XML", str(fila_ip["Observacion_Descartes"]))
            self.assertEqual(fila_ip["archivo_xml"], "")

            self.assertEqual(fila_cft["Estado_Recepcion"], "RECIBIDO")
            self.assertEqual(str(fila_cft["Observacion_Descartes"]).strip(), "")
            self.assertEqual(fila_cft["archivo_xml"], xml_ip)


if __name__ == "__main__":
    unittest.main()
