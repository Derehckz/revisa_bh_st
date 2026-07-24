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


class TestEmailTemplatesPlazo(unittest.TestCase):
    def test_recordatorio_uses_plazo_recordatorio(self):
        import config

        prev_fecha = config.ULT_FECHA_RECEPCION
        prev_hora = config.HORARIO_RECEPCION
        prev_fecha_rec = config.ULT_FECHA_RECORDATORIO
        prev_hora_rec = config.HORARIO_RECORDATORIO
        try:
            config.ULT_FECHA_RECEPCION = "1 Enero 2026"
            config.HORARIO_RECEPCION = "10:00"
            config.ULT_FECHA_RECORDATORIO = "5 Enero 2026"
            config.HORARIO_RECORDATORIO = "18:30"
            html = email_templates.generar_cuerpo_solicitud(
                tipo="recordatorio",
                nombre_completo="Ana",
                rut_docente="1-9",
                rut_razon="2-7",
                razon_social="RS",
                direccion_razon="Dir",
                glosa="G",
                monto=1000,
                email_dp="dp@test.cl",
                mes="mayo",
                año=2026,
            )
            self.assertIn("5 Enero 2026", html)
            self.assertIn("18:30", html)
            self.assertNotIn("1 Enero 2026", html)
        finally:
            config.ULT_FECHA_RECEPCION = prev_fecha
            config.HORARIO_RECEPCION = prev_hora
            config.ULT_FECHA_RECORDATORIO = prev_fecha_rec
            config.HORARIO_RECORDATORIO = prev_hora_rec


class TestEmailTemplatesMonto(unittest.TestCase):
    def test_format_monto_with_thousands_comma(self):
        self.assertEqual(email_templates._format_monto("206,000"), "$206.000")

    def test_format_monto_with_thousands_dot(self):
        self.assertEqual(email_templates._format_monto("206.000"), "$206.000")

    def test_format_monto_with_decimal_comma(self):
        self.assertEqual(email_templates._format_monto("206,5"), "$206")


if __name__ == "__main__":
    unittest.main()

