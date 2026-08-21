"""Mensajes de observación en lenguaje del docente."""
from __future__ import annotations

import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from stages.docente_mensajes import (  # noqa: E402
    detalle_descartes_docente,
    explicar_descarte_docente,
    observacion_principal_docente,
)


class TestDocenteMensajes(unittest.TestCase):
    def test_glosa_provisionado(self):
        msg = explicar_descarte_docente(
            "bhe_14635781-264.xml",
            "glosa/provisión inconsistente entre solicitud y XML",
            monto_solicitado=30000,
            glosa_solicitada="CFTST Convenio - PROVISIONADO",
            monto_boleta=30000,
        )
        self.assertIn("PROVISIONADO", msg)
        self.assertIn("264", msg)
        self.assertNotIn("XML", msg)
        self.assertNotIn("línea", msg.lower())

    def test_monto_distinto(self):
        msg = explicar_descarte_docente(
            "bhe_14635781-263.xml",
            "monto XML (270000.0) distinto al monto de esta línea (30000.0)",
            monto_solicitado=30000,
            glosa_solicitada="IPST Convenio JULIO",
        )
        self.assertIn("$270.000", msg)
        self.assertIn("$30.000", msg)
        self.assertIn("solicitud", msg.lower())

    def test_observacion_y_detalle(self):
        fila = {
            "GLOSA": "CFTST Convenio los Lagos - PROVISIONADO",
            "CUS_TOT_HON": 30000,
        }
        descartes = [
            "bhe_14635781-264.xml: glosa/provisión inconsistente entre solicitud y XML",
            "bhe_14635781-263.xml: monto XML (270000.0) distinto al monto de esta línea (30000.0)",
        ]
        obs = observacion_principal_docente(descartes, fila)
        self.assertIn("PROVISIONADO", obs)
        self.assertIn("$30.000", obs)
        det = detalle_descartes_docente(descartes, fila)
        self.assertIn("•", det)
        self.assertNotIn("monto XML", det.lower())


if __name__ == "__main__":
    unittest.main()
