"""Generación y validación del CSV RUT→IP|CFT para el paso 8."""
from __future__ import annotations

import csv
import os
from typing import Any

import config


def _cat_from_row(row: Any) -> str | None:
    rut_razon = str(row.get("RUT RAZON", "") or row.get("RUT_RAZON", "")).strip()
    if "65175239" in rut_razon.replace(".", "").replace("-", ""):
        return "IP"
    if "65175242" in rut_razon.replace(".", "").replace("-", ""):
        return "CFT"
    nombre = str(row.get("NOMBRE RAZON", "") or row.get("NOMBRE_RAZON", "")).upper()
    if "INSTITUTO PROFESIONAL" in nombre or " INSTITUTO" in nombre:
        return "IP"
    if ("FORMACI" in nombre and "TÉCNICA" in nombre) or "FORMACION TECNICA" in nombre:
        return "CFT"
    return None


def default_map_relpath(year: int | str, month: str) -> str:
    return f"{year}/{month}/map_ip_cft.csv"


def default_map_abspath(year: int | str, month: str) -> str:
    return os.path.join(config.RAIZ, str(year), month, "map_ip_cft.csv")


def generate_map_ip_cft(year: int | str, month: str, output: str | None = None) -> tuple[str, int]:
    """Escribe map_ip_cft.csv desde Solicitud.xlsx. Retorna (ruta, n_ruts)."""
    import pandas as pd

    solicitud = os.path.join(config.RAIZ, str(year), month, "Solicitud.xlsx")
    if not os.path.isfile(solicitud):
        raise FileNotFoundError(f"No existe {solicitud}")

    out = output or default_map_abspath(year, month)
    df = pd.read_excel(solicitud, sheet_name=0, engine="openpyxl")
    col_rut = "RUT_SIN_DV" if "RUT_SIN_DV" in df.columns else "EMPLID"

    mapping: dict[str, str] = {}
    for _, row in df.iterrows():
        rut_raw = str(row.get(col_rut, "")).strip()
        rut = rut_raw.split("-")[0].replace(".", "").strip()
        if not rut or not rut.isdigit():
            continue
        cat = _cat_from_row(row)
        if cat:
            mapping[rut] = cat

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["RUT_SIN_DV", "Categoria"])
        for rut in sorted(mapping):
            w.writerow([rut, mapping[rut]])

    return out, len(mapping)


def _read_map_rows(path: str) -> list[list[str]]:
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "mac_roman", "latin-1"):
        try:
            with open(path, newline="", encoding=enc) as fh:
                return list(csv.reader(fh))
        except UnicodeDecodeError as exc:
            last_err = exc
            continue
    raise ValueError(f"No se pudo leer mapping CSV (encoding): {path}. Detalle: {last_err}")


def load_map_ip_cft(path: str) -> dict[str, str]:
    """Carga CSV RUT,Categoria (IP|CFT) con encodings tolerantes."""
    mapping: dict[str, str] = {}
    for row in _read_map_rows(path):
        if not row:
            continue
        rut = str(row[0]).strip()
        cat = str(row[1]).strip().upper() if len(row) > 1 else ""
        if rut.upper() in ("RUT", "RUT_SIN_DV", "EMPLID", "CATEGORIA"):
            continue
        if cat in ("IP", "CFT"):
            rut_n = rut.split("-")[0].replace(".", "").strip()
            if rut_n:
                mapping[rut_n] = cat
    return mapping


def looks_like_map_csv(path: str) -> bool:
    name = os.path.basename(path).lower()
    if "contabilidad" in name or "pagos" in name:
        return False
    if name.startswith("map_ip_cft") or name.startswith("map_"):
        return True
    if not os.path.isfile(path):
        return False
    try:
        return bool(load_map_ip_cft(path))
    except Exception:
        return False


def resolve_map_path(map_csv: str) -> str:
    path = str(map_csv).strip()
    if not path:
        return ""
    if not os.path.isabs(path):
        path = os.path.join(config.RAIZ, path)
    return path


def ensure_map_for_period(year: int | str, month: str, map_csv: str | None = None) -> str:
    """
    Resuelve ruta del mapa; si apunta al default y no existe, lo genera desde Solicitud.
    Valida que el archivo sea un mapa IP/CFT (no Contabilidad_pagos.csv).
    """
    rel_default = default_map_relpath(year, month)
    chosen = (map_csv or "").strip() or rel_default
    path = resolve_map_path(chosen)

    if not os.path.isfile(path) and chosen.replace("\\", "/") == rel_default.replace("\\", "/"):
        generate_map_ip_cft(year, month, output=path)

    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"No existe el CSV de clasificación: {path}. "
            f"Genérelo con: python herramientas/generar_map_ip_cft.py --year {year} --month {month}"
        )

    if not looks_like_map_csv(path):
        raise ValueError(
            f"El archivo no parece un mapa IP/CFT (RUT,Categoria): {os.path.basename(path)}. "
            f"Use map_ip_cft.csv (no Contabilidad_pagos ni otros CSV del mes)."
        )

    mapping = load_map_ip_cft(path)
    if not mapping:
        raise ValueError(
            f"El CSV de clasificación no tiene filas IP/CFT válidas: {os.path.basename(path)}"
        )
    return path
