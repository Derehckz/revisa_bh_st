from __future__ import annotations

import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (_REPO, os.path.join(_REPO, "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from db.state_projection import (  # noqa: E402
    classify_mail_recepcion_status,
    classify_recepcion_status,
    classify_xml_status,
)


class TestStateProjection(unittest.TestCase):
    def test_recepcion_ok(self):
        status, reason, mode = classify_recepcion_status(
            {
                "Estado_Recepcion": "RECIBIDO",
                "GLOSA": "IPST Convenio ... IST2588-JULIO",
                "descripcionLinea_XML": "IPST CONVENIO ... IST2588-JULIO",
            }
        )
        self.assertEqual(status, "RECIBIDO_OK")
        self.assertIsNone(reason)
        self.assertEqual(mode, "exacta")

    def test_recepcion_error_glosa(self):
        status, reason, mode = classify_recepcion_status(
            {
                "Estado_Recepcion": "RECIBIDO",
                "GLOSA": "IPST Convenio ... IST2588-JULIO",
                "descripcionLinea_XML": "IPST CONVENIO ... IST2588-JUNIO",
            }
        )
        self.assertEqual(status, "RECIBIDO_ERROR")
        self.assertEqual(reason, "glosa_incorrecta")
        self.assertEqual(mode, "distinta")

    def test_xml_status(self):
        self.assertEqual(classify_xml_status({"archivo_xml": "", "Observaciones_XML": ""}), "PENDIENTE")
        self.assertEqual(
            classify_xml_status({"archivo_xml": "a.xml", "Observaciones_XML": "Datos extraídos OK"}),
            "OK",
        )
        self.assertEqual(
            classify_xml_status({"archivo_xml": "a.xml", "Observaciones_XML": "Monto distinto"}),
            "ERROR",
        )

    def test_mail_status(self):
        self.assertEqual(classify_mail_recepcion_status({"Correo_Recepcion_Enviado": ""}), "PENDIENTE")
        self.assertEqual(
            classify_mail_recepcion_status({"Correo_Recepcion_Enviado": "✅ Enviado (confirmación)"}),
            "ENVIADO_OK",
        )
        self.assertEqual(
            classify_mail_recepcion_status({"Correo_Recepcion_Enviado": "✅ Enviado (observación/reenvío)"}),
            "ENVIADO_PROBLEMA",
        )


if __name__ == "__main__":
    unittest.main()
