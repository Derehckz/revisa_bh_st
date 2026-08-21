"""Abrir archivos locales del proyecto (misma máquina que la API / Outlook)."""
from __future__ import annotations

import logging
import os
from typing import Any

import config
import stage_commands


def _safe_under_raiz(path: str) -> bool:
    try:
        root = os.path.abspath(config.RAIZ)
        target = os.path.abspath(path)
        return os.path.commonpath([root, target]) == root
    except ValueError:
        return False


def resolve_period_dir(year: int | str, month: str) -> str:
    month_dir = os.path.abspath(os.path.join(config.RAIZ, str(year), str(month).strip()))
    if not _safe_under_raiz(month_dir):
        raise ValueError("Ruta fuera de la carpeta del proyecto.")
    if not os.path.isdir(month_dir):
        raise FileNotFoundError(f"No existe la carpeta: {month_dir}")
    return month_dir


def resolve_period_file(year: int | str, month: str, *, name: str = "Solicitud.xlsx") -> str:
    month_dir = resolve_period_dir(year, month)
    path = os.path.abspath(os.path.join(month_dir, name))
    if not _safe_under_raiz(path):
        raise ValueError("Ruta fuera de la carpeta del proyecto.")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"No existe: {path}")
    return path


def _start_local(path: str) -> None:
    try:
        os.startfile(path)  # type: ignore[attr-defined]
    except AttributeError as e:
        raise RuntimeError(
            "Abrir local solo está disponible en Windows con la API en este equipo."
        ) from e
    except OSError as e:
        logging.warning("os.startfile falló (%s): %s", path, e)
        raise RuntimeError(
            f"No se pudo abrir. Ábrelo manualmente: {path}. Detalle: {e}"
        ) from e


def open_local_file(path: str) -> dict[str, Any]:
    """Abre un archivo con la app asociada (Excel en Windows)."""
    abs_path = os.path.abspath(path)
    if not _safe_under_raiz(abs_path):
        raise ValueError("Ruta fuera de la carpeta del proyecto.")
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"No existe: {abs_path}")

    _start_local(abs_path)
    return {
        "ok": True,
        "path": abs_path,
        "filename": os.path.basename(abs_path),
        "message": f"Abriendo {os.path.basename(abs_path)}…",
    }


def open_local_folder(path: str) -> dict[str, Any]:
    """Abre una carpeta en el Explorador de Windows."""
    abs_path = os.path.abspath(path)
    if not _safe_under_raiz(abs_path):
        raise ValueError("Ruta fuera de la carpeta del proyecto.")
    if not os.path.isdir(abs_path):
        raise FileNotFoundError(f"No existe la carpeta: {abs_path}")

    _start_local(abs_path)
    return {
        "ok": True,
        "path": abs_path,
        "filename": os.path.basename(abs_path),
        "message": f"Abriendo carpeta {os.path.basename(abs_path)}…",
    }


def open_stage_primary(year: int | str, month: str, stage_num: int) -> dict[str, Any]:
    path = stage_commands.primary_output_for_stage(stage_num, year, month)
    if not path:
        raise FileNotFoundError(
            f"No hay artefacto principal del paso {stage_num} en {month} {year}."
        )
    return open_local_file(path)
