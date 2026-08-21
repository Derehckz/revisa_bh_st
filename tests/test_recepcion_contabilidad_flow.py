"""Validación Contabilidad y textos de recepción técnica."""
from __future__ import annotations

import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for p in (_REPO, _LIB):
    if p not in sys.path:
        sys.path.insert(0, p)

import email_templates  # noqa: E402


class TestRecepcionTecnicaCopy(unittest.TestCase):
    def test_confirmacion_no_dice_lista_para_pago(self):
        html = email_templates.generar_cuerpo_recepcion(
            "Ana", "10", "1-9", "2-7", 1000, provisionado=False
        )
        self.assertIn("revisión técnica", html.lower())
        self.assertNotIn("lista para procesamiento de pago", html.lower())

    def test_provisionado_menciona_contabilidad(self):
        html = email_templates.generar_cuerpo_recepcion(
            "Ana", "10", "1-9", "2-7", 1000, provisionado=True
        )
        self.assertIn("contabilidad", html.lower())
        asunto = email_templates.generar_asunto_recepcion("10", provisionado=True)
        self.assertIn("Contabilidad", asunto)


if __name__ == "__main__":
    unittest.main()
