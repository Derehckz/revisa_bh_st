"""Serialización de la fila completa de Solicitud.xlsx hacia/desde BD."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd

# Columnas canónicas del Solicitud operativo (orden de exportación).
SOLICITUD_COLUMNS: list[str] = [
    "EMPLID",
    "RUT_SIN_DV",
    "NAME",
    "EMPL_RCD",
    "HR_STATUS",
    "LOCATION",
    "RUT RAZON",
    "NOMBRE RAZON",
    "DireccionRazon",
    "LOCATION.1",
    "GLOSA",
    "DESCR",
    "MONTH",
    "YEAR",
    "CUS_INCIDENCIA",
    "CUS_MTO_CTA",
    "CUS_MTO_BONO",
    "CUS_MTO_DAPTO",
    "CUS_TOT_HON",
    "Email_Docente",
    "SEDE",
    "Email_DP",
    "Correo Enviado",
    "Estado_Recepcion",
    "Recordatorios Enviados",
    "Observaciones",
    "Observacion_Descartes",
    "archivo_xml",
    "rutEmisorCompleto_XML",
    "rutReceptorCompleto_XML",
    "nombreReceptor_XML",
    "porcentajeImpuesto_XML",
    "totalHonorarios_XML",
    "liquidoHonorarios_XML",
    "impuestoHonorarios_XML",
    "descripcionLinea_XML",
    "fechaBoleta_XML",
    "numeroBoleta_XML",
    "Archivo_XML_Usado",
    "Observaciones_XML",
    "Correo_Recepcion_Enviado",
]


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, float):
        return value
    if isinstance(value, (int, bool)):
        return value
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "nat"}:
        return None
    return text


def serialize_solicitud_row(row: dict[str, Any] | None) -> dict[str, Any]:
    """Normaliza un dict/Series de Excel a JSON serializable con columnas canónicas."""
    src = dict(row or {})
    out: dict[str, Any] = {}
    for col in SOLICITUD_COLUMNS:
        if col in src:
            out[col] = _json_safe(src.get(col))
        else:
            out[col] = None
    # Conserva extras conocidas si aparecen (sin contaminar el orden principal).
    for key, value in src.items():
        k = str(key)
        if k in out:
            continue
        if k.startswith("_"):
            continue
        out[k] = _json_safe(value)
    return out


def merge_solicitud_row(
    existing: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
    *,
    prefer_incoming: bool = True,
) -> dict[str, Any]:
    """
    Fusiona filas: por defecto el incoming no-vacío pisa al existente.
    Campos vacíos del incoming no borran valores ya guardados.
    """
    base = serialize_solicitud_row(existing)
    nxt = serialize_solicitud_row(incoming)
    for key, value in nxt.items():
        if value is None or value == "":
            continue
        if prefer_incoming or base.get(key) in (None, ""):
            base[key] = value
    return base


def apply_live_overrides(payload: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Aplica overrides operativos (estado/XML/correo) sobre el snapshot guardado."""
    out = dict(payload or {})
    for key, value in (overrides or {}).items():
        if value is None:
            continue
        out[key] = value
    return out
