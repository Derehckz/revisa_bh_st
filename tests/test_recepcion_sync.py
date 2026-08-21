"""Regresión: glosa estricta y sync de marcas de correo recepción."""
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
import mail_ledger  # noqa: E402
from interaction.auto_adapter import AutoAdapter  # noqa: E402
from stages.recepcion_sync import sync_correo_recepcion_after_revision  # noqa: E402
from stages.stage3.revision_core import glosas_coinciden, procesar_filas  # noqa: E402
from stages.stage5 import mail as mail_ops  # noqa: E402


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


class TestGlosaEstricta(unittest.TestCase):
    def test_audita_recibido_con_glosa_distinta(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _minimal_xml(
                root / "bhe_15651725-433.xml",
                rut="15651725",
                dv="9",
                receptor="65175239",
                total=101916,
                glosa="IPST CONVENIO LOS LAGOS CODIGO FDI IST2588-JUNIO",
                folio=433,
            )
            (root / "bhe_15651725-433.pdf").write_bytes(b"%PDF-1.4")
            df = pd.DataFrame(
                [
                    {
                        "EMPLID": "15651725-9",
                        "RUT_SIN_DV": "15651725",
                        "RUT RAZON": "65175239-6",
                        "GLOSA": "IPST Convenio los lagos Código FDI IST2588-JULIO",
                        "CUS_TOT_HON": 101916,
                        "NAME": "Quintana",
                        "Estado_Recepcion": "RECIBIDO",
                        "Observaciones": "OK",
                        "archivo_xml": "bhe_15651725-433.xml",
                        "descripcionLinea_XML": "IPST CONVENIO LOS LAGOS CODIGO FDI IST2588-JUNIO",
                    }
                ]
            )
            from stages.stage3.revision_core import auditar_glosas_recibidas
            from interaction.auto_adapter import AutoAdapter

            n = auditar_glosas_recibidas(df, str(root), AutoAdapter())
            self.assertEqual(n, 1)
            self.assertEqual(df.iloc[0]["Estado_Recepcion"], "RECIBIDO CON ERROR")

    def test_normaliza_tildes_y_mayusculas(self):
        self.assertTrue(
            glosas_coinciden(
                "IPST Convenio los lagos Código FDI IST2588-JULIO",
                "IPST CONVENIO LOS LAGOS CODIGO FDI IST2588-JULIO",
            )
        )

    def test_rechaza_mes_distinto_en_glosa(self):
        self.assertFalse(
            glosas_coinciden(
                "IPST Convenio los lagos Código FDI IST2588-JULIO",
                "IPST CONVENIO LOS LAGOS CODIGO FDI IST2588-JUNIO",
            )
        )

    def test_tolera_espacios_extra_en_codigo(self):
        casos = [
            (
                "CFTST Convenio los Lagos Código FDI CST2588-JULIO",
                "CFTST CONVENIO LOS LAGOS CODIGO FDICST2588-JULIO",
            ),
            (
                "IPST Convenio los lagos Código FDI IST2588-JULIO",
                "IPST CONVENIO LOS LAGOS CODIGO FDI IST 2588 - JULIO",
            ),
            (
                "CFTST Convenio los Lagos Código FDI CST2588-JULIO",
                "CFTST CONVENIO LOS LAGOS CODIGO FDI CST 2588- JULIO",
            ),
        ]
        for excel, xml in casos:
            with self.subTest(excel=excel[:30]):
                self.assertTrue(glosas_coinciden(excel, xml))

    def test_tolera_anio_al_final(self):
        self.assertTrue(
            glosas_coinciden(
                "CFTST Convenio los Lagos Código FDI CST2588-JULIO",
                "CFTST CONVENIO LOS LAGOS CODIGO FDI CST2588-JULIO 2026",
            )
        )

    def test_tolera_prefijo_institucional_faltante(self):
        self.assertTrue(
            glosas_coinciden(
                "IPST Convenio los lagos Código FDI IST2588-JULIO",
                "CONVENIO LOS LAGOS CODIGO FDI IST2588- JULIO",
            )
        )

    def test_rechaza_prefijo_institucional_distinto(self):
        self.assertFalse(
            glosas_coinciden(
                "IPST Convenio los lagos Código FDI IST2588-JULIO",
                "CFTST CONVENIO LOS LAGOS CODIGO FDI IST2588-JULIO",
            )
        )

    def test_xml_mes_distinto_queda_no_recibido(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _minimal_xml(
                root / "bhe_15651725-433.xml",
                rut="15651725",
                dv="9",
                receptor="65175239",
                total=101916,
                glosa="IPST CONVENIO LOS LAGOS CODIGO FDI IST2588-JUNIO",
                folio=433,
            )
            (root / "bhe_15651725-433.pdf").write_bytes(b"%PDF-1.4")

            df = pd.DataFrame(
                [
                    {
                        "EMPLID": "15651725-9",
                        "RUT_SIN_DV": "15651725",
                        "RUT RAZON": "65175239-6",
                        "GLOSA": "IPST Convenio los lagos Código FDI IST2588-JULIO",
                        "CUS_TOT_HON": 101916,
                        "NAME": "Quintana",
                    }
                ]
            )
            out, _ = procesar_filas(df, str(root), AutoAdapter())
            self.assertEqual(out.iloc[0]["Estado_Recepcion"], "NO RECIBIDO")
            self.assertIn("glosa", str(out.iloc[0]["Observacion_Descartes"]).lower())


class TestRecepcionSync(unittest.TestCase):
    def test_limpia_marca_si_pasa_de_reenvio_a_confirmacion(self):
        before = pd.DataFrame(
            [
                {
                    "Estado_Recepcion": "NO RECIBIDO",
                    "Observaciones": "Sin boleta",
                    "Observacion_Descartes": "detalle",
                    "archivo_xml": "",
                    "Correo_Recepcion_Enviado": "✅ Enviado (observación/reenvío)",
                    "Email_Docente": "doc@t.com",
                    "EMPLID": "15651725-9",
                    "RUT RAZON": "65175239-6",
                    "numeroBoleta_XML": "",
                }
            ]
        )
        after = before.copy()
        after.at[0, "Estado_Recepcion"] = "RECIBIDO"
        after.at[0, "Observaciones"] = "OK"
        after.at[0, "Observacion_Descartes"] = ""
        after.at[0, "archivo_xml"] = "bhe_15651725-433.xml"
        after.at[0, "numeroBoleta_XML"] = "433"

        key = mail_ops.build_item_key(
            "2026",
            "Julio",
            "N/A",
            "doc@t.com",
            kind="problema",
            emplid="15651725-9",
            rut_razon="65175239-6",
        )
        mail_ledger.mark_sent(mail_ops.STAGE_ID, key)

        stats = sync_correo_recepcion_after_revision(before, after, año="2026", mes="Julio")
        self.assertEqual(stats["cleared_markers"], 1)
        self.assertEqual(after.iloc[0]["Correo_Recepcion_Enviado"], "")
        self.assertFalse(mail_ledger.was_sent(mail_ops.STAGE_ID, key))

    def test_paso5_detecta_marca_desactualizada(self):
        fila = {
            "Estado_Recepcion": "RECIBIDO",
            "Observaciones": "OK",
            "Observacion_Descartes": "",
            "Correo_Recepcion_Enviado": "✅ Enviado (observación/reenvío)",
        }
        self.assertFalse(mail_ops.correo_recepcion_cubierto(fila))
        preview = mail_ops.build_recepcion_preview(pd.DataFrame([fila]))
        self.assertEqual(preview["counts"]["ok_pending"], 1)
        self.assertEqual(preview["counts"]["already_sent"], 0)


if __name__ == "__main__":
    unittest.main()
