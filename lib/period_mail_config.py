"""Plazos de correo (etapa 1) persistidos por período.

La UI y el `.env` no deben “resetear” a un mes anterior: se guarda la última
configuración usada para `{año}/{mes}` y, si no hay, se sugiere una fecha
acorde al mes actual (mismo día del mes que indique el .env, si se puede).
"""
from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from typing import Any

import config

_DEADLINE_KEYS = (
    "fecha_limite_recepcion",
    "horario_recepcion",
    "fecha_limite_recordatorio",
    "horario_recordatorio",
)


def _state_path() -> str:
    root = getattr(config, "RAIZ", None) or os.getcwd()
    return os.path.join(str(root), ".state", "period_mail_deadlines.json")


def _period_key(year: int | str, month: str) -> str:
    return f"{int(year)}|{str(month).strip()}"


def _load_store() -> dict[str, Any]:
    path = _state_path()
    if not os.path.isfile(path):
        return {"periods": {}, "last_used_key": None}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"periods": {}, "last_used_key": None}
        data.setdefault("periods", {})
        data.setdefault("last_used_key", None)
        return data
    except (OSError, json.JSONDecodeError):
        return {"periods": {}, "last_used_key": None}


def _save_store(data: dict[str, Any]) -> None:
    path = _state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _day_from_env_fecha(value: str, default: int = 25) -> int:
    m = re.match(r"^\s*(\d{1,2})\b", str(value or ""))
    if not m:
        return default
    day = int(m.group(1))
    return day if 1 <= day <= 31 else default


def suggested_deadlines(year: int | str, month: str) -> dict[str, str]:
    """Fechas alineadas al mes/año del período (no al texto viejo del .env)."""
    day_rec = _day_from_env_fecha(getattr(config, "ULT_FECHA_RECEPCION", "25"), 25)
    day_rem = _day_from_env_fecha(getattr(config, "ULT_FECHA_RECORDATORIO", str(day_rec)), day_rec)
    mes = str(month).strip()
    anio = str(int(year))
    return {
        "fecha_limite_recepcion": f"{day_rec} {mes} {anio}",
        "horario_recepcion": str(getattr(config, "HORARIO_RECEPCION", "19:00") or "19:00"),
        "fecha_limite_recordatorio": f"{day_rem} {mes} {anio}",
        "horario_recordatorio": str(getattr(config, "HORARIO_RECORDATORIO", "19:00") or "19:00"),
    }


def get_deadlines(year: int | str, month: str) -> dict[str, str]:
    """
    Defaults para el período, en orden:
    1) guardado de ese mes
    2) sugerencia del mes actual (día/horario del .env, mes/año del período)
    """
    store = _load_store()
    key = _period_key(year, month)
    periods = store.get("periods") or {}
    saved = periods.get(key) if isinstance(periods, dict) else None
    base = suggested_deadlines(year, month)
    if isinstance(saved, dict):
        out = dict(base)
        for k in _DEADLINE_KEYS:
            val = saved.get(k)
            if val is not None and str(val).strip():
                out[k] = str(val).strip()
        out["source"] = "period"
        return out
    base["source"] = "suggested"
    return base


def save_deadlines(year: int | str, month: str, values: dict[str, Any]) -> dict[str, str]:
    """Persiste plazos del período (solo keys no vacías)."""
    cleaned: dict[str, str] = {}
    for k in _DEADLINE_KEYS:
        raw = values.get(k)
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            cleaned[k] = text
    if not cleaned:
        return get_deadlines(year, month)

    store = _load_store()
    key = _period_key(year, month)
    periods = store.setdefault("periods", {})
    prev = periods.get(key) if isinstance(periods.get(key), dict) else {}
    merged = {**prev, **cleaned}
    merged["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    periods[key] = merged
    store["last_used_key"] = key
    store["last_used_at"] = merged["updated_at"]
    _save_store(store)
    out = get_deadlines(year, month)
    out["source"] = "period"
    return out
