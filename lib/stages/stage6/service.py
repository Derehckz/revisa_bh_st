"""Etapa 6 — Informe final de boletas (envoltorio delgado sobre el script legacy).

Ver ``stages.stage0.service`` para el patrón: la lógica sigue en
``etapas/6.-Informe_final_boletas.py`` y se ejecuta vía
:func:`stages.bridged_runner.run_bridged_stage`.
"""
from __future__ import annotations

from interaction.port import InteractionPort
from stages.bridged_runner import run_bridged_stage
from stages.context import Stage6Context


class Stage6Service:
    def run(self, ctx: Stage6Context, ui: InteractionPort) -> dict:
        return run_bridged_stage(ctx, ui)
