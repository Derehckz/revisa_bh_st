"""Etapa 8 — separa BH IP/CFT (envoltorio delgado sobre el script legacy).

Ver ``stages.stage0.service`` para el patrón: la lógica sigue en
``etapas/8.-separa_bh_ip_cft.py`` y se ejecuta vía
:func:`stages.bridged_runner.run_bridged_stage`.
"""
from __future__ import annotations

from interaction.port import InteractionPort
from stages.bridged_runner import run_bridged_stage
from stages.context import Stage8Context


class Stage8Service:
    def run(self, ctx: Stage8Context, ui: InteractionPort) -> dict:
        return run_bridged_stage(ctx, ui)
