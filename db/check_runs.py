"""Consulta rápida de trazabilidad de runs/etapas desde PostgreSQL."""
from __future__ import annotations

import argparse
import os
import sys

if __package__ is None or __package__ == "":
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    _lib = os.path.join(_root, "lib")
    for _p in (_lib, _root):
        if _p not in sys.path:
            sys.path.insert(0, _p)

from sqlalchemy import select

from db.models import PipelineRun, PipelineStageRun
from db.session import SessionLocal
import utils


def _format_nullable(value) -> str:
    return str(value) if value is not None else "-"


def main() -> int:
    utils.asegurar_utf8_salida()
    parser = argparse.ArgumentParser(description="Mostrar últimas ejecuciones del pipeline")
    parser.add_argument("--limit-runs", type=int, default=5, help="Cantidad de runs a mostrar")
    parser.add_argument(
        "--show-stages",
        action="store_true",
        help="Mostrar también etapas por cada run",
    )
    args = parser.parse_args()

    utils.print_header("CONSULTA DE RUNS PIPELINE", "PostgreSQL")

    with SessionLocal() as session:
        runs = (
            session.execute(
                select(PipelineRun)
                .order_by(PipelineRun.started_at.desc())
                .limit(max(1, args.limit_runs))
            )
            .scalars()
            .all()
        )

        if not runs:
            utils.print_warning("No hay runs registrados todavía.")
            return 0

        utils.print_table(
            "Últimos runs",
            [
                (
                    f"Run #{run.id}",
                    f"run_id={run.run_id} | status={run.status} | period={_format_nullable(run.period_label)} | started={_format_nullable(run.started_at)}",
                )
                for run in runs
            ],
        )

        if not args.show_stages:
            utils.print_info("Tip: usa --show-stages para ver el detalle por etapa.")
            return 0

        for run in runs:
            stages = (
                session.execute(
                    select(PipelineStageRun)
                    .where(PipelineStageRun.pipeline_run_id == run.id)
                    .order_by(PipelineStageRun.stage_num.asc())
                )
                .scalars()
                .all()
            )
            if not stages:
                continue

            utils.print_section(f"Run #{run.id} - Etapas")
            utils.print_table(
                "Detalle de etapas",
                [
                    (
                        f"Etapa {st.stage_num}: {st.stage_name}",
                        f"status={st.status} | correlation={_format_nullable(st.correlation_id)} | msg={_format_nullable(st.message)}",
                    )
                    for st in stages
                ],
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
