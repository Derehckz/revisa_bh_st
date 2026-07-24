"""Etapa 9 — agrupa por docente (envoltorio delgado sobre el script legacy).

Ver ``stages.stage0.service`` para el patrón: la lógica sigue en
``etapas/9.-agrupa_por_docente.py`` y se ejecuta vía
:func:`stages.bridged_runner.run_bridged_stage`.
"""
from __future__ import annotations

from interaction.port import InteractionPort
from stages.bridged_runner import run_bridged_stage
from stages.context import Stage9Context


class Stage9Service:
    def run(self, ctx: Stage9Context, ui: InteractionPort) -> dict:
        return run_bridged_stage(ctx, ui)
