"""Etapa 10 — revisa carpetas IP/CFT (envoltorio delgado sobre el script legacy).

Ver ``stages.stage0.service`` para el patrón: la lógica (incluido el parche
de ``progress_hook`` sobre ``ejecutar_trabajos``) sigue en
``etapas/10.-revisa_carpetas_ip_cft.py`` y se ejecuta vía
:func:`stages.bridged_runner.run_bridged_stage`, que ya contempla el caso
especial de la etapa 10.
"""
from __future__ import annotations

from interaction.port import InteractionPort
from stages.bridged_runner import run_bridged_stage
from stages.context import Stage10Context


class Stage10Service:
    def run(self, ctx: Stage10Context, ui: InteractionPort) -> dict:
        return run_bridged_stage(ctx, ui)
