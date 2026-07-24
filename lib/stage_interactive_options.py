"""Opciones interactivas para la UI (archivos, hojas, carpetas)."""
from __future__ import annotations

import os
from typing import Any

import config
import schema_validator
import stage_commands


def _month_dir(year: int | str, month: str) -> str:
    return os.path.join(config.RAIZ, str(year), month)


def _list_month_csv(year: int | str, month: str, month_path: str) -> list[dict[str, str]]:
    if not os.path.isdir(month_path):
        return []
    prefix = f"{year}/{month}"
    out: list[dict[str, str]] = []
    for name in sorted(os.listdir(month_path)):
        if name.lower().endswith(".csv") and os.path.isfile(os.path.join(month_path, name)):
            out.append({"value": f"{prefix}/{name}", "label": name})
    return out


def _solicitud_sheets(path: str) -> list[str]:
    if not os.path.isfile(path):
        return []
    try:
        import pandas as pd

        # En Windows hay que cerrar el ExcelFile; si no, uvicorn deja Solicitud.xlsx bloqueado.
        with pd.ExcelFile(path, engine="openpyxl") as xls:
            return list(xls.sheet_names)
    except Exception:
        return []


def build_interactive_choices(stage_num: int, year: int, month: str) -> dict[str, Any]:
    month_path = _month_dir(year, month)
    solicitud = os.path.join(month_path, "Solicitud.xlsx")
    sheets = _solicitud_sheets(solicitud)
    sheet_auto = "Solicitud" if "Solicitud" in sheets else (sheets[0] if sheets else "")

    xlsx_in_month: list[str] = []
    if os.path.isdir(month_path):
        xlsx_in_month = sorted(
            f
            for f in os.listdir(month_path)
            if f.lower().endswith(".xlsx") and os.path.isfile(os.path.join(month_path, f))
        )

    choices: dict[str, Any] = {
        "month_dir": month_path,
        "month_dir_label": f"{month} {year}",
        "solicitud_file": solicitud if os.path.isfile(solicitud) else None,
        "solicitud_sheets": sheets,
        "solicitud_sheet_auto": sheet_auto,
        "excel_files_in_month": xlsx_in_month,
        "map_csv_files": _list_month_csv(year, month, month_path),
    }

    if stage_num == 0:
        maestros = xlsx_in_month
        root_xlsx = sorted(
            f
            for f in os.listdir(config.RAIZ)
            if f.lower().endswith(".xlsx") and os.path.isfile(os.path.join(config.RAIZ, f))
        )
        choices["maestro_files"] = maestros
        choices["bd_candidates"] = [
            f for f in root_xlsx if "bd" in f.lower() or "docentes" in f.lower()
        ]

    if stage_num == 10:
        choices["institucion_options"] = [
            {"value": "", "label": "Todas (IP y CFT)"},
            {"value": "IP", "label": "Solo IP"},
            {"value": "CFT", "label": "Solo CFT"},
        ]

    return choices


def enrich_params_schema(
    stage_num: int,
    year: int,
    month: str,
    schema: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    month_path = _month_dir(year, month)
    choices = build_interactive_choices(stage_num, year, month)
    enriched: list[dict[str, Any]] = []

    for field in schema:
        f = dict(field)
        name = f.get("name", "")

        if name == "sheet":
            f["type"] = "select_sheet"
            sheets = list(choices.get("solicitud_sheets") or [])
            auto = str(choices.get("solicitud_sheet_auto") or "")
            opts: list[dict[str, str]] = []
            for s in sheets:
                label = f"{s} (recomendada)" if s == auto else s
                opts.append({"value": s, "label": label})
            if not opts and auto:
                opts = [{"value": auto, "label": auto}]
            f["options"] = opts
            if auto:
                f["default"] = auto
            if stage_num == 9:
                f["label"] = "Hoja del Excel (origen para agrupar)"
                rb = schema_validator.find_sheet(sheets, "Resumen Boletas")
                if rb:
                    f["default"] = rb

        if name == "map_csv":
            f["type"] = "select_path"
            opts = list(choices.get("map_csv_files") or [])
            default_rel = f"{year}/{month}/map_ip_cft.csv"
            if not any(o["value"] == default_rel for o in opts):
                opts.insert(0, {"value": default_rel, "label": "map_ip_cft.csv (recomendado)"})
            f["options"] = opts
            f["label"] = "Archivo de clasificación IP/CFT (CSV)"

        if name == "institucion":
            f["type"] = "select"
            f["options"] = choices.get("institucion_options") or []

        if stage_num == 1:
            deadlines = None
            try:
                import period_mail_config

                deadlines = period_mail_config.get_deadlines(year, month)
            except Exception:
                deadlines = None
            if name == "fecha_limite_recepcion":
                f["default"] = (deadlines or {}).get("fecha_limite_recepcion") or config.ULT_FECHA_RECEPCION
            elif name == "horario_recepcion":
                f["default"] = (deadlines or {}).get("horario_recepcion") or config.HORARIO_RECEPCION
            elif name == "fecha_limite_recordatorio":
                f["default"] = (deadlines or {}).get("fecha_limite_recordatorio") or config.ULT_FECHA_RECORDATORIO
            elif name == "horario_recordatorio":
                f["default"] = (deadlines or {}).get("horario_recordatorio") or config.HORARIO_RECORDATORIO

        if f.get("type") == "boolean":
            f["label"] = _friendly_boolean_label(name, f.get("label", name))

        enriched.append(f)

    return enriched


def _friendly_boolean_label(name: str, default: str) -> str:
    labels = {
        "send": "Enviar correos reales (si no, solo revisa sin mandar)",
        "force_resend": "Forzar reenvío (ignorar si ya se envió antes)",
        "strict": "Validación estricta del Excel",
        "dry_run": "Solo simular (no mover ni borrar archivos)",
        "mover": "Mover archivos en lugar de copiar (paso 8)",
        "no_interactive": "Ejecutar sin preguntas en consola (recomendado desde la web)",
        "agrupar_archivos": "Copiar PDF/XML a la carpeta de cada docente",
        "force": "Volver a revisar aunque ya exista marca de revisado",
    }
    return labels.get(name, default)
