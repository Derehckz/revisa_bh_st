"""Etapa 0 — generar Solicitud.xlsx (envoltorio delgado sobre el script legacy).

El núcleo de negocio sigue viviendo en ``etapas/0.-generar_solicitud.py``.
``Stage0Service`` solo arma el ``sys.argv``/contexto esperado por ese script
y lo ejecuta dentro de ``utils_bridge`` vía
:func:`stages.bridged_runner.run_bridged_stage`, igual que hacía
``api/interactive/runner.py`` antes de migrar esta etapa al patrón de
servicio (``StageNContext.from_api_params`` + ``StageNService().run``).
"""
from __future__ import annotations

from interaction.port import InteractionPort
from stages.bridged_runner import run_bridged_stage
from stages.context import Stage0Context


class Stage0Service:
    def run(self, ctx: Stage0Context, ui: InteractionPort) -> dict:
        return run_bridged_stage(ctx, ui)
