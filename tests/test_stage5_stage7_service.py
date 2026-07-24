"""Etapa 5/7 — servicios y per_mail sin Outlook ni envío."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_REPO, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)


from interaction.auto_adapter import AutoAdapter
from interaction.types import SupervisionMode
from stages.context import Stage5Context, Stage7Context
from stages.stage5 import mail as mail5
from stages.stage7 import mail as mail7


class TestStage5Mail(unittest.TestCase):
    def test_build_item_key(self):
        k = mail5.build_item_key("2026", "Mayo", "123", "a@b.cl")
        self.assertIn("2026", k)
        self.assertIn("a@b.cl", k)

    def test_preview_only_per_mail_no_outlook(self):
        df = pd.DataFrame(
            [
                {
                    "Estado_Recepcion": "RECIBIDO",
                    "Email_Docente": "docente@ejemplo.cl",
                    "NAME": "Ana",
                    "numeroBoleta_XML": 1,
                    "rutReceptorCompleto_XML": 11111111,
                    "rutEmisorCompleto_XML": 22222222,
                    "totalHonorarios_XML": 1000,
                    "Correo_Recepcion_Enviado": "",
                }
            ]
        )
        ui = AutoAdapter(
            allow_send=False,
            auto_accept_confirm=True,
            auto_accept_mail=True,
        )
        with patch("stages.stage5.mail.idempotency_store.was_success", return_value=False):
            stats = mail5.procesar_correos(
            ui,
            df,
            df[df["Estado_Recepcion"] == "RECIBIDO"],
            año="2026",
            mes="Mayo",
            modo_prueba=True,
            allow_send=False,
            force_resend=False,
            supervision_mode=SupervisionMode.PER_MAIL,
            outlook=None,
            )
        self.assertGreaterEqual(stats["previewed"], 1)

    def test_sent_marker_is_not_resent(self):
        df = pd.DataFrame(
            [
                {
                    "Estado_Recepcion": "RECIBIDO",
                    "Email_Docente": "docente@ejemplo.cl",
                    "NAME": "Ana",
                    "numeroBoleta_XML": 1,
                    "rutReceptorCompleto_XML": 11111111,
                    "rutEmisorCompleto_XML": 22222222,
                    "totalHonorarios_XML": 1000,
                    "Correo_Recepcion_Enviado": "✅ Enviado anteriormente",
                }
            ]
        )
        ui = AutoAdapter(
            allow_send=False,
            auto_accept_confirm=True,
            auto_accept_mail=True,
        )
        stats = mail5.procesar_correos(
            ui,
            df,
            df[df["Estado_Recepcion"] == "RECIBIDO"],
            año="2026",
            mes="Mayo",
            modo_prueba=True,
            allow_send=False,
            force_resend=False,
            supervision_mode=SupervisionMode.PER_MAIL,
            outlook=None,
        )
        self.assertEqual(stats["omitted"], 1)


class TestStage7Mail(unittest.TestCase):
    def test_normalizar_monto_liquido_miles(self):
        self.assertEqual(mail7.normalizar_monto_liquido("159.669"), 159669)

    def test_correo_enviado_column_accepts_text_markers(self):
        df = pd.DataFrame(
            [
                {
                    "MAIL": "docente@ejemplo.cl",
                    "Nombre": "Ana",
                    "ID": "1-9",
                    "BANCO": "X",
                    "FORMA PAGO": "Cta",
                    "NªCUENTA": "123",
                    "Número Boleta": 1,
                    "Ubicación": "508",
                    "LÍQUIDO": "50.000",
                    "Correo Enviado": float("nan"),
                }
            ]
        )
        df["Correo Enviado"] = df["Correo Enviado"].fillna("").astype(object)
        ui = AutoAdapter(
            allow_send=False,
            auto_accept_confirm=True,
            auto_accept_mail=True,
        )
        with (
            patch("stages.stage7.mail.idempotency_store.was_success", return_value=False),
            patch.object(mail7.bh_outlook_mail, "send_html_mail_with_backoff") as send,
        ):
            mail7.procesar_correos(
                ui,
                df,
                mes_año_pago="Mayo 2026",
                fecha_pago="15/05/2026",
                allow_send=True,
                force_resend=False,
                supervision_mode=SupervisionMode.BATCH,
                outlook=MagicMock(),
                ruta_excel="/tmp/x.xlsx",
            )
            send.assert_called_once()
        self.assertEqual(df.iloc[0]["Correo Enviado"], "✅ Enviado")

    def test_preview_without_send(self):
        df = pd.DataFrame(
            [
                {
                    "MAIL": "pago@ejemplo.cl",
                    "Nombre": "Luis",
                    "ID": "1-9",
                    "BANCO": "X",
                    "FORMA PAGO": "Cta",
                    "NªCUENTA": "123",
                    "Boleta": 1,
                    "LÍQUIDO": "50.000",
                    "Correo Enviado": "",
                    "LOCATION": "IP",
                }
            ]
        )
        ui = AutoAdapter(
            allow_send=False,
            auto_accept_confirm=True,
            auto_accept_mail=True,
        )
        with (
            patch("stages.stage7.mail.idempotency_store.was_success", return_value=False),
            patch.object(mail7.bh_outlook_mail, "send_html_mail_with_backoff") as send,
        ):
            stats = mail7.procesar_correos(
                ui,
                df,
                mes_año_pago="Mayo 2026",
                fecha_pago="15/05/2026",
                allow_send=False,
                force_resend=False,
                supervision_mode=SupervisionMode.PER_MAIL,
                outlook=MagicMock(),
                ruta_excel="/tmp/x.xlsx",
            )
            send.assert_not_called()
        self.assertGreaterEqual(stats["previewed"], 1)


class TestStageContexts(unittest.TestCase):
    def test_stage5_api_blocks_send_flag(self):
        ctx = Stage5Context.from_api_params(
            {"year": 2026, "month": "Mayo", "send": False, "supervision_mode": "per_mail"}
        )
        self.assertFalse(ctx.allow_send)
        self.assertEqual(ctx.supervision_mode, SupervisionMode.PER_MAIL)

    def test_stage5_modo_prueba_confirm_not_inverted(self):
        from stages.stage5.service import Stage5Service

        class _UI:
            def __init__(self, modo_prueba_answer: bool):
                self._modo_prueba_answer = modo_prueba_answer
                self._calls = 0

            def header(self, *_a, **_k):
                pass

            def log(self, *_a, **_k):
                pass

            def table(self, *_a, **_k):
                pass

            def emit(self, *_a, **_k):
                pass

            def confirm_yes_no(self, title, *_a, **_k):
                self._calls += 1
                if title == "Modo prueba":
                    return self._modo_prueba_answer
                return True

        df = pd.DataFrame(
            [
                {
                    "Estado_Recepcion": "RECIBIDO",
                    "Email_Docente": "docente@ejemplo.cl",
                    "NAME": "Ana",
                    "numeroBoleta_XML": 1,
                    "Correo_Recepcion_Enviado": "",
                }
            ]
        )
        svc = Stage5Service()
        with (
            patch.object(svc, "_sent_keys_from_logs", return_value=set()),
            patch("stages.stage5.service.utils.resolve_año_mes", return_value=("2026", "Mayo")),
            patch("stages.stage5.service.os.path.isfile", return_value=True),
            patch("stages.stage5.service.pd.ExcelFile") as xls_cls,
            patch("stages.stage5.service.pd.read_excel", return_value=df),
            patch("stages.stage5.service.mail_ops.procesar_correos", return_value={"sent": 0}) as proc,
            patch("stages.stage5.service.utils.is_non_interactive", return_value=False),
            patch("stages.stage5.service.utils.configurar_logging"),
            patch("stages.stage5.service.os.makedirs"),
        ):
            xls_cls.return_value.sheet_names = ["Solicitud"]
            ui_yes = _UI(True)
            svc.run(Stage5Context(year="2026", month="Mayo", allow_send=True, supervised=False), ui_yes)
            self.assertTrue(proc.call_args.kwargs["modo_prueba"])

            ui_no = _UI(False)
            svc.run(Stage5Context(year="2026", month="Mayo", allow_send=True, supervised=False), ui_no)
            self.assertFalse(proc.call_args.kwargs["modo_prueba"])

    def test_stage7_api_fecha_pago(self):
        ctx = Stage7Context.from_api_params(
            {
                "year": 2026,
                "month": "Mayo",
                "fecha_pago": "01/05/2026",
                "send": False,
            }
        )
        self.assertEqual(ctx.fecha_pago, "01/05/2026")


if __name__ == "__main__":
    unittest.main()
