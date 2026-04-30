"""Carga de configuracion externa con fallback seguro a defaults.

Prioridad de resolucion:
1) Variables de entorno del sistema
2) Archivo .env local (si existe)
3) Valor por defecto pasado al getter
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Dict


def _parse_env_line(line: str) -> tuple[str, str] | None:
    raw = line.strip()
    if not raw or raw.startswith("#") or "=" not in raw:
        return None

    key, value = raw.split("=", 1)
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    if not key:
        return None
    return key, value


@lru_cache(maxsize=1)
def _load_dotenv_file() -> Dict[str, str]:
    values: Dict[str, str] = {}
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.isfile(env_path):
        return values

    try:
        with open(env_path, "r", encoding="utf-8") as fh:
            for line in fh:
                parsed = _parse_env_line(line)
                if parsed is None:
                    continue
                k, v = parsed
                values[k] = v
    except OSError:
        # Modo tolerante: si .env falla, no bloquea la ejecucion.
        return {}

    return values


def get_setting(key: str, default: str = "") -> str:
    env_val = os.getenv(key)
    if env_val not in (None, ""):
        return env_val

    file_values = _load_dotenv_file()
    return file_values.get(key, default)


def get_bool_setting(key: str, default: bool = False) -> bool:
    val = get_setting(key, "")
    if not val:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "si", "s"}
