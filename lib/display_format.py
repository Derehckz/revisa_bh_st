"""Formato de presentación para UI (montos CLP, RUT, folios)."""
from __future__ import annotations

import re
from typing import Any

import utils


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    try:
        import pandas as pd

        if pd.isna(value):
            return True
    except Exception:
        pass
    s = str(value).strip()
    return not s or s.lower() in {"nan", "none", "nat", "n/a"}


def format_folio(value: Any) -> str:
    """Número de boleta / folio sin decimales."""
    if _is_blank(value):
        return ""
    try:
        return str(int(float(str(value).replace(",", "."))))
    except (TypeError, ValueError):
        return str(value).strip()


def format_monto_cl(value: Any, *, suffix: bool = True) -> str:
    """Monto chileno: $101.916.-"""
    if _is_blank(value):
        return ""
    try:
        s = str(value).strip().replace("$", "").replace(" ", "").replace(".-", "")
        if s.endswith(".") and s.count(".") == 1:
            s = s[:-1]
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s:
            parts = s.split(",")
            if (
                len(parts) > 1
                and all(p.isdigit() for p in parts)
                and all(len(p) == 3 for p in parts[1:])
            ):
                s = "".join(parts)
            else:
                s = s.replace(",", ".")
        elif "." in s:
            parts = s.split(".")
            if (
                len(parts) > 1
                and all(p.isdigit() for p in parts)
                and all(len(p) == 3 for p in parts[1:])
            ):
                s = "".join(parts)
        n = int(float(s))
        body = f"{n:,}".replace(",", ".")
        return f"${body}.-" if suffix else f"${body}"
    except (TypeError, ValueError):
        return str(value).strip()


def format_rut_cl(value: Any) -> str:
    """RUT con puntos y guión: 65.175.239-6"""
    if _is_blank(value):
        return ""
    raw = str(value).strip()
    if re.match(r"^[\d\.]+-[\dkK]$", raw) and raw.count(".") >= 1:
        return raw
    # Excel suele entregar RUT+DV como float (651752396.0 → 65175239-6).
    if re.match(r"^\d+\.0+$", raw):
        raw = raw.split(".", 1)[0]
    elif isinstance(value, float):
        try:
            if float(value).is_integer():
                raw = str(int(value))
        except (TypeError, ValueError):
            pass
    normalized = utils.normalizar_rut_con_dv(raw)
    if not normalized or len(normalized) < 2:
        return raw.replace(".0", "").strip()
    cuerpo, dv = normalized[:-1], normalized[-1]
    rev = cuerpo[::-1]
    chunks = [rev[i : i + 3] for i in range(0, len(rev), 3)]
    cuerpo_fmt = ".".join(chunk[::-1] for chunk in chunks[::-1])
    return f"{cuerpo_fmt}-{dv}"


def format_rut_sin_dv(value: Any) -> str:
    if _is_blank(value):
        return ""
    digits = utils.normalizar_rut_digits(str(value))
    if not digits:
        return str(value).strip().replace(".0", "")
    try:
        return str(int(digits))
    except ValueError:
        return digits
