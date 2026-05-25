"""Construcción de comandos CLI y prerequisitos compartidos (main.py + API)."""
from __future__ import annotations

import os
import sys
from typing import Any

import config
from pipeline_stages import MAX_STEP, MIN_STEP, SCRIPTS

# Fase B: etapas 0–10 habilitadas vía API (correos requieren send=true en params).
API_ENABLED_STAGES: frozenset[int] = frozenset(range(0, MAX_STEP + 1))

EMAIL_STAGES: frozenset[int] = frozenset({1, 5, 7})


def get_stage(stage_num: int) -> dict | None:
    for s in SCRIPTS:
        if s["num"] == stage_num:
            return s
    return None


def build_period_args(stage: dict, year: str | int | None, month: str | None) -> list[str]:
    """Argumentos de período según contrato de la etapa."""
    extra: list[str] = []
    if stage["accepts"] == "year_month":
        if year:
            extra.extend(["--year", str(year)])
        if month:
            extra.extend(["--month", month])
    elif stage["accepts"] == "mes_ano":
        if month:
            extra.extend(["--mes", month])
        if year:
            extra.extend(["--año", str(year)])
    return extra


def check_prerequisites(stage_num: int, year: str | int | None = None, month: str | None = None) -> None:
    """Verifica pre-requisitos; lanza ValueError si no se cumplen."""
    base_path = os.path.join(config.RAIZ, str(year), month) if year and month else None

    if stage_num == 0:
        return

    if stage_num == 1:
        if not os.path.isfile(config.ARCHIVO_ADJUNTO):
            raise ValueError(f"Archivo adjunto no encontrado: {config.ARCHIVO_ADJUNTO}")
        return

    if stage_num == 2:
        return

    if stage_num == 3:
        if base_path and not any(
            f.endswith(".xlsx")
            for f in os.listdir(base_path)
            if os.path.isfile(os.path.join(base_path, f))
        ):
            raise ValueError(f"No se encontró archivo Excel en {base_path}")
        return

    if stage_num in (4, 5, 6, 7, 8, 9, 10):
        if base_path:
            excel_path = os.path.join(base_path, "Solicitud.xlsx")
            if not os.path.isfile(excel_path):
                raise ValueError(f"Archivo Solicitud.xlsx no encontrado en {base_path}")
        return


def describe_prerequisites(stage_num: int, year: str | int | None, month: str | None) -> dict[str, Any]:
    """Estado de prerequisitos para la UI (sin lanzar)."""
    try:
        check_prerequisites(stage_num, year, month)
        return {"ok": True, "message": ""}
    except (ValueError, OSError) as e:
        return {"ok": False, "message": str(e)}


def _param_field(
    name: str,
    *,
    type_: str = "boolean",
    label: str = "",
    cli: str | None = None,
    required: bool = False,
    default: Any = None,
    help_text: str = "",
) -> dict[str, Any]:
    return {
        "name": name,
        "type": type_,
        "label": label or name,
        "cli": cli,
        "required": required,
        "default": default,
        "help": help_text,
    }


def params_schema_for_stage(stage_num: int) -> list[dict[str, Any]]:
    """Esquema de parámetros para formularios de Operación."""
    if stage_num == 0:
        return [
            _param_field("maestro_file", type_="select_maestro", label="Archivo maestro", required=True),
            _param_field("bd_file", type_="select_bd", label="BD docentes", required=True),
            _param_field("output_file", type_="string", label="Nombre salida", default="Solicitud.xlsx"),
        ]
    if stage_num in (3, 4):
        return [
            _param_field("strict", cli="--strict", label="Validación estricta del Excel"),
        ]
    if stage_num == 1:
        return [
            _param_field(
                "send",
                cli="--send",
                label="Enviar correos reales",
                help_text="Sin esto solo se analiza/previsualiza (no despacha).",
            ),
            _param_field("force_resend", cli="--force-resend", label="Forzar reenvío (ignora idempotencia)"),
            _param_field("strict", cli="--strict", label="Validación estricta del Excel"),
        ]
    if stage_num == 5:
        return [
            _param_field("send", cli="--send", label="Enviar correos de recepción"),
            _param_field("force_resend", cli="--force-resend", label="Forzar reenvío"),
        ]
    if stage_num == 7:
        return [
            _param_field("send", cli="--send", label="Enviar correos de pago"),
            _param_field(
                "fecha_pago",
                type_="string",
                cli="--fecha-pago",
                label="Fecha de pago (dd/mm/aaaa)",
                required=False,
                help_text="Obligatoria si envía correos.",
            ),
            _param_field("force_resend", cli="--force-resend", label="Forzar reenvío"),
        ]
    if stage_num == 2:
        return [
            _param_field(
                "fecha_inicio",
                type_="string",
                cli="--fecha-inicio",
                label="Fecha inicio (dd/mm/aaaa)",
                required=True,
            ),
            _param_field(
                "fecha_fin",
                type_="string",
                cli="--fecha-fin",
                label="Fecha fin (dd/mm/aaaa)",
                required=True,
            ),
            _param_field("dry_run", cli="--dry-run", label="Simular (no guardar archivos)"),
        ]
    if stage_num == 8:
        return [
            _param_field("dry_run", cli="--dry-run", label="Simular (no copiar/mover)", default=True),
            _param_field("mover", cli="--mover", label="Mover en lugar de copiar"),
            _param_field(
                "map_csv",
                type_="string",
                cli="--map",
                label="Ruta CSV clasificación (RUT,CFT|IP)",
                help_text="Recomendado en modo API para evitar prompts.",
            ),
            _param_field("no_interactive", cli="--no-interactive", label="Sin prompts (usar con CSV)"),
        ]
    if stage_num == 9:
        return [
            _param_field(
                "agrupar_archivos",
                cli="--agrupar-archivos",
                label="Copiar PDF/XML bhe_* a carpetas docente",
            ),
        ]
    if stage_num == 10:
        return [
            _param_field("dry_run", cli="--dry-run", label="Simular (no escribir marcadores)"),
            _param_field("force", cli="--force", label="Re-evaluar aunque exista .revisado"),
            _param_field(
                "institucion",
                type_="string",
                cli="--institucion",
                label="Filtrar institución (IP o CFT)",
            ),
        ]
    return []


def validate_stage_params(stage_num: int, params: dict[str, Any]) -> None:
    """Valida parámetros del body API antes de armar el comando."""
    schema = {f["name"]: f for f in params_schema_for_stage(stage_num)}
    for name, field in schema.items():
        if field.get("required") and not params.get(name):
            raise ValueError(f"Falta parámetro obligatorio: {name}")

    if stage_num == 7 and params.get("send") and not params.get("fecha_pago"):
        raise ValueError("fecha_pago es obligatoria cuando send=true en el paso 7")

    if stage_num == 2:
        if not params.get("fecha_inicio") or not params.get("fecha_fin"):
            raise ValueError("fecha_inicio y fecha_fin son obligatorias para el paso 2")


def _apply_schema_flags(stage_num: int, params: dict[str, Any], extra: list[str], *, repo_root: str) -> None:
    for field in params_schema_for_stage(stage_num):
        name = field["name"]
        cli = field.get("cli")
        if not cli:
            continue
        type_ = field.get("type", "boolean")
        val = params.get(name)
        if type_ == "boolean":
            if val:
                extra.append(cli)
        elif type_ == "string" and val:
            if name == "map_csv":
                path = str(val)
                if not os.path.isabs(path):
                    path = os.path.join(config.RAIZ, path)
                extra.extend([cli, path])
            else:
                extra.extend([cli, str(val)])


def build_stage_extra_args(stage_num: int, params: dict[str, Any], *, repo_root: str) -> list[str]:
    """Flags adicionales por etapa (parámetros del body API)."""
    validate_stage_params(stage_num, params)
    extra: list[str] = []

    if stage_num == 0:
        maestro_file = params.get("maestro_file")
        bd_file = params.get("bd_file")
        if not maestro_file or not bd_file:
            raise ValueError("maestro_file y bd_file son obligatorios para el paso 0")
        year = params.get("year")
        month = params.get("month")
        if year is None or not month:
            raise ValueError("year y month son obligatorios para el paso 0")
        month_dir = os.path.join(config.RAIZ, str(year), month)
        maestro_path = os.path.join(month_dir, maestro_file)
        bd_path = os.path.join(config.RAIZ, bd_file) if not os.path.isabs(bd_file) else bd_file
        if not os.path.isfile(maestro_path):
            raise FileNotFoundError(f"No existe archivo maestro: {maestro_path}")
        if not os.path.isfile(bd_path):
            raise FileNotFoundError(f"No existe BD docentes: {bd_path}")
        extra.extend(["--archivo-maestro", maestro_file, "--ruta-bd", bd_path])
        output_file = params.get("output_file")
        if output_file:
            extra.extend(["--ruta-salida", os.path.join(month_dir, output_file)])
        csv_nuevos = params.get("csv_nuevos_docentes")
        if csv_nuevos:
            extra.extend(["--csv-nuevos-docentes", str(csv_nuevos)])
        return extra

    _apply_schema_flags(stage_num, params, extra, repo_root=repo_root)

    if stage_num == 8 and params.get("map_csv") and not params.get("no_interactive"):
        extra.append("--no-interactive")

    return extra


def primary_output_for_stage(stage_num: int, year: int | str, month: str, params: dict[str, Any] | None = None) -> str | None:
    """Ruta del artefacto principal tras éxito (para descarga en UI)."""
    month_dir = os.path.join(config.RAIZ, str(year), month)
    params = params or {}
    if stage_num == 0:
        name = params.get("output_file") or "Solicitud.xlsx"
        return os.path.join(month_dir, name)
    if stage_num in (1, 3, 4, 5, 6, 7, 8, 9):
        path = os.path.join(month_dir, "Solicitud.xlsx")
        return path if os.path.isfile(path) else None
    if stage_num == 10:
        path = os.path.join(month_dir, "revision_carpetas.xlsx")
        return path if os.path.isfile(path) else None
    return None


def build_stage_command(
    repo_root: str,
    stage_num: int,
    *,
    year: str | int | None = None,
    month: str | None = None,
    params: dict[str, Any] | None = None,
    api_mode: bool = False,
) -> list[str]:
    """
    Lista argv para ejecutar una etapa.

    En api_mode añade --yes (scripts con register_non_interactive_cli).
    """
    stage = get_stage(stage_num)
    if not stage:
        raise ValueError(f"Etapa inválida: {stage_num} (rango {MIN_STEP}-{MAX_STEP})")

    script_path = stage["file"]
    if not os.path.isabs(script_path):
        script_path = os.path.join(repo_root, script_path)

    cmd = [sys.executable, "-X", "utf8", script_path]
    cmd.extend(build_period_args(stage, year, month))
    if params:
        cmd.extend(build_stage_extra_args(stage_num, params, repo_root=repo_root))
    if api_mode:
        cmd.append("--yes")
    return cmd


def list_stages_metadata() -> list[dict[str, Any]]:
    """Metadatos de etapas para GET /operations/stages."""
    out: list[dict[str, Any]] = []
    for s in SCRIPTS:
        num = s["num"]
        out.append(
            {
                "stage_num": num,
                "file": s["file"],
                "description": s["desc"],
                "accepts": s["accepts"],
                "optional_in_full_run": s.get("optional_in_full_run", False),
                "enabled_for_api": num in API_ENABLED_STAGES,
                "is_email_stage": num in EMAIL_STAGES,
            }
        )
    return out
