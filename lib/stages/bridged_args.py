"""Construcción de sys.argv / Namespace para scripts legacy vía bridge."""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BridgedContext:
    stage_num: int
    year: str | int | None = None
    month: str | None = None
    sheet: str | None = None
    supervised: bool = False
    send: bool = False
    force_resend: bool = False
    strict: bool = False
    dry_run: bool = False
    mover: bool = False
    no_interactive: bool = False
    fecha_inicio: str | None = None
    fecha_fin: str | None = None
    fecha_pago: str | None = None
    maestro_file: str | None = None
    bd_file: str | None = None
    output_file: str | None = None
    map_csv: str | None = None
    institucion: str | None = None
    agrupar_archivos: bool = False
    force: bool = False
    streamlined: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_params(cls, stage_num: int, params: dict[str, Any]) -> "BridgedContext":
        from stages.streamlined import param_streamlined

        def _str(k: str) -> str | None:
            v = params.get(k)
            return str(v).strip() if v not in (None, "") else None

        return cls(
            stage_num=stage_num,
            year=params.get("year"),
            month=_str("month"),
            sheet=_str("sheet"),
            supervised=True,
            send=bool(params.get("send")),
            force_resend=bool(params.get("force_resend")),
            strict=bool(params.get("strict")),
            dry_run=bool(params.get("dry_run")),
            mover=bool(params.get("mover")),
            no_interactive=bool(params.get("no_interactive")),
            fecha_inicio=_str("fecha_inicio"),
            fecha_fin=_str("fecha_fin"),
            fecha_pago=_str("fecha_pago"),
            maestro_file=_str("maestro_file"),
            bd_file=_str("bd_file"),
            output_file=_str("output_file"),
            map_csv=_str("map_csv"),
            institucion=_str("institucion"),
            agrupar_archivos=bool(params.get("agrupar_archivos")),
            force=bool(params.get("force")),
            streamlined=param_streamlined(params),
            extra=dict(params),
        )


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _resolve_map_path(rel: str | None) -> str | None:
    if not rel:
        return None
    rel = rel.replace("/", os.sep)
    if os.path.isabs(rel):
        return rel
    return os.path.join(_repo_root(), rel)


def build_argv(ctx: BridgedContext) -> list[str]:
    argv = ["bridged-stage"]
    y = ctx.year
    m = ctx.month

    if y is not None and m:
        if ctx.stage_num == 0:
            argv.extend(["--mes", str(m), "--año", str(y)])
        else:
            argv.extend(["--year", str(y), "--month", str(m)])

    if ctx.sheet:
        argv.extend(["--sheet", ctx.sheet])

    if ctx.strict:
        argv.append("--strict")

    if ctx.send:
        argv.append("--send")

    if ctx.force_resend:
        argv.append("--force-resend")

    if ctx.dry_run:
        argv.append("--dry-run")

    if ctx.mover:
        argv.append("--mover")

    if ctx.no_interactive:
        argv.append("--no-interactive")

    if ctx.agrupar_archivos:
        argv.append("--agrupar-archivos")

    if ctx.force:
        argv.append("--force")

    if ctx.institucion:
        argv.extend(["--institucion", ctx.institucion])

    if ctx.fecha_inicio:
        argv.extend(["--fecha-inicio", ctx.fecha_inicio])
    if ctx.fecha_fin:
        argv.extend(["--fecha-fin", ctx.fecha_fin])
    if ctx.fecha_pago:
        argv.extend(["--fecha-pago", ctx.fecha_pago])

    map_path = _resolve_map_path(ctx.map_csv)
    if map_path:
        argv.extend(["--map", map_path])

    if ctx.stage_num == 0:
        import config

        if ctx.maestro_file and y and m:
            argv.extend(
                [
                    "--ruta-maestro",
                    os.path.join(config.RAIZ, str(y), str(m), ctx.maestro_file),
                ]
            )
        if ctx.bd_file:
            argv.extend(
                ["--ruta-bd", os.path.join(config.RAIZ, ctx.bd_file)]
            )
        if ctx.output_file and y and m:
            out = ctx.output_file
            if not out.lower().endswith(".xlsx"):
                out = "Solicitud.xlsx"
            argv.extend(
                ["--ruta-salida", os.path.join(config.RAIZ, str(y), str(m), out)]
            )

    if not ctx.supervised or ctx.streamlined:
        argv.append("--yes")

    return argv


_STAGES_WITH_NAMESPACE = frozenset({6, 9})


def build_namespace(ctx: BridgedContext) -> argparse.Namespace:
    """Namespace para scripts que aceptan main(args=...)."""
    return argparse.Namespace(
        year=str(ctx.year) if ctx.year is not None else None,
        month=ctx.month,
        sheet=ctx.sheet,
        send=ctx.send,
        force_resend=ctx.force_resend,
        fecha_pago=ctx.fecha_pago,
        dry_run=ctx.dry_run,
        mover=ctx.mover,
        agrupar_archivos=ctx.agrupar_archivos,
        yes=(not ctx.supervised) or ctx.streamlined,
    )


def uses_namespace(stage_num: int) -> bool:
    return stage_num in _STAGES_WITH_NAMESPACE
