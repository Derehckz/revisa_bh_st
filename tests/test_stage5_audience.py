"""Paso 5: audiencia confirmación / error / reenvío."""
from __future__ import annotations

import os
import sys
import unittest

import pandas as pd

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from stages.stage5 import mail as mail_ops  # noqa: E402


class TestStage5Audience(unittest.TestCase):
    def test_clasificar_audiencia(self):
        self.assertEqual(
            mail_ops.clasificar_audiencia_recepcion({"Estado_Recepcion": "RECIBIDO"}),
            "ok",
        )
        self.assertEqual(
            mail_ops.clasificar_audiencia_recepcion(
                {"Estado_Recepcion": "RECIBIDO CON ERROR"}
            ),
            "error",
        )
        self.assertEqual(
            mail_ops.clasificar_audiencia_recepcion(
                {
                    "Estado_Recepcion": "NO RECIBIDO",
                    "Observacion_Descartes": "bhe_x.xml: glosa",
                }
            ),
            "reenvio",
        )
        self.assertEqual(
            mail_ops.clasificar_audiencia_recepcion(
                {"Estado_Recepcion": "NO RECIBIDO", "Observacion_Descartes": ""}
            ),
            "reenvio",
        )

    def test_clasificar_reenvio_tipo(self):
        self.assertEqual(
            mail_ops.clasificar_reenvio_tipo(
                {
                    "Estado_Recepcion": "NO RECIBIDO",
                    "Observacion_Descartes": "",
                }
            ),
            "recordatorio",
        )
        self.assertEqual(
            mail_ops.clasificar_reenvio_tipo(
                {
                    "Estado_Recepcion": "NO RECIBIDO",
                    "Observacion_Descartes": "bhe_x.xml: glosa",
                }
            ),
            "boleta_incorrecta",
        )

    def test_fila_recepcion_permitida_por_subtipo(self):
        fila_recordatorio = {
            "Estado_Recepcion": "NO RECIBIDO",
            "Observacion_Descartes": "",
        }
        fila_boleta = {
            "Estado_Recepcion": "NO RECIBIDO",
            "Observacion_Descartes": "bhe_x.xml: glosa",
        }
        self.assertTrue(
            mail_ops.fila_recepcion_permitida(
                fila_recordatorio,
                include_ok=False,
                include_error=False,
                include_recordatorio=True,
                include_boleta_incorrecta=False,
            )
        )
        self.assertFalse(
            mail_ops.fila_recepcion_permitida(
                fila_boleta,
                include_ok=False,
                include_error=False,
                include_recordatorio=True,
                include_boleta_incorrecta=False,
            )
        )

    def test_recibido_con_glosa_distinta_es_error(self):
        self.assertEqual(
            mail_ops.clasificar_audiencia_recepcion(
                {
                    "Estado_Recepcion": "RECIBIDO",
                    "GLOSA": "IPST Convenio JULIO",
                    "descripcionLinea_XML": "IPST CONVENIO JUNIO",
                }
            ),
            "error",
        )

        df = pd.DataFrame(
            [
                {
                    "NAME": "A",
                    "Email_Docente": "a@t.com",
                    "EMPLID": "1",
                    "Estado_Recepcion": "RECIBIDO",
                    "Correo_Recepcion_Enviado": "",
                    "Observaciones": "OK",
                    "Observacion_Descartes": "",
                    "CUS_TOT_HON": 1000,
                    "numeroBoleta_XML": 1,
                },
                {
                    "NAME": "B",
                    "Email_Docente": "b@t.com",
                    "EMPLID": "2",
                    "Estado_Recepcion": "NO RECIBIDO",
                    "Correo_Recepcion_Enviado": "Sí",
                    "Observaciones": "glosa",
                    "Observacion_Descartes": "file: glosa",
                    "CUS_TOT_HON": 2000,
                    "numeroBoleta_XML": "",
                },
            ]
        )
        preview = mail_ops.build_recepcion_preview(df)
        self.assertEqual(preview["counts"]["ok"], 1)
        self.assertEqual(preview["counts"]["reenvio"], 1)
        self.assertEqual(preview["counts"]["boleta_incorrecta"], 1)
        self.assertEqual(preview["counts"]["ok_pending"], 1)
        self.assertEqual(preview["counts"]["already_sent"], 1)
        self.assertEqual(len(preview["candidates"]), 2)
        self.assertEqual(preview["candidates"][1]["reenvio_tipo"], "boleta_incorrecta")

    def test_problema_desde_fila_recordatorio_si_no_recibido_sin_boleta(self):
        problema, detalle = mail_ops.problema_desde_fila(
            {
                "Estado_Recepcion": "NO RECIBIDO",
                "Observaciones": "",
                "Observacion_Descartes": "",
                "numeroBoleta_XML": "",
            }
        )
        self.assertIn("recordatorio", problema.lower())
        self.assertEqual(detalle, "")

    def test_problema_desde_fila_incluye_boleta_y_accion(self):
        problema, _detalle = mail_ops.problema_desde_fila(
            {
                "Estado_Recepcion": "RECIBIDO CON ERROR",
                "Observaciones": "totalHonorarios XML (100) distinto a CUS_TOT_HON Excel (200)",
                "Observacion_Descartes": "",
                "numeroBoleta_XML": 433,
            }
        )
        self.assertIn("boleta n° 433", problema.lower())
        self.assertIn("debe anular", problema.lower())


if __name__ == "__main__":
    unittest.main()
