"""Smoke tests — servicios delgados de etapas 0, 6, 8, 9, 10 (E7-E10).

Estas etapas conservan su lógica en ``etapas/<n>.-*.py`` (ejecutada vía
``utils_bridge``/``run_bridged_stage``), pero ahora exponen ``StageNService``
+ ``StageNContext`` igual que las etapas ya migradas al patrón de servicio,
para que ``api/interactive/runner.py`` no dependa de la lista legacy
``_BRIDGED_STAGES``.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
_ETAPAS = os.path.join(_REPO, "etapas")
for _p in (_LIB, _REPO, _ETAPAS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from stages.context import (  # noqa: E402
    Stage0Context,
    Stage6Context,
    Stage8Context,
    Stage9Context,
    Stage10Context,
)
from stages.stage0.service import Stage0Service  # noqa: E402
from stages.stage6.service import Stage6Service  # noqa: E402
from stages.stage8.service import Stage8Service  # noqa: E402
from stages.stage9.service import Stage9Service  # noqa: E402
from stages.stage10.service import Stage10Service  # noqa: E402


_SERVICES = (
    (0, Stage0Context, Stage0Service),
    (6, Stage6Context, Stage6Service),
    (8, Stage8Context, Stage8Service),
    (9, Stage9Context, Stage9Service),
    (10, Stage10Context, Stage10Service),
)


class TestStageServicesShape(unittest.TestCase):
    def test_services_import_and_have_run_method(self):
        for _stage_num, _ctx_cls, service_cls in _SERVICES:
            svc = service_cls()
            self.assertTrue(callable(getattr(svc, "run", None)))

    def test_contexts_from_api_params_sets_stage_num(self):
        for stage_num, ctx_cls, _service_cls in _SERVICES:
            ctx = ctx_cls.from_api_params({"year": 2026, "month": "Julio"})
            self.assertEqual(ctx.stage_num, stage_num)
            self.assertIsInstance(ctx, ctx_cls)

    def test_run_delegates_to_run_bridged_stage(self):
        ui = object()
        for stage_num, ctx_cls, service_cls in _SERVICES:
            ctx = ctx_cls.from_api_params({"year": 2026, "month": "Julio"})
            with patch(
                f"stages.stage{stage_num}.service.run_bridged_stage",
                return_value={"ok": True, "stage_num": stage_num},
            ) as mocked:
                result = service_cls().run(ctx, ui)
            mocked.assert_called_once_with(ctx, ui)
            self.assertEqual(result, {"ok": True, "stage_num": stage_num})


class TestRunnerStageDispatch(unittest.TestCase):
    """El runner interactivo ya no debe depender de _BRIDGED_STAGES (vacío)."""

    def test_bridged_stages_set_is_empty(self):
        from api.interactive import runner

        self.assertEqual(runner._BRIDGED_STAGES, set())

    def test_stage0_service_flag_default_true(self):
        import settings

        self.assertTrue(settings.get_bool_setting("BH_STAGE0_SERVICE", True))


if __name__ == "__main__":
    unittest.main()
