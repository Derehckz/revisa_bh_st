"""Construcción de claves de boleta para evitar colisiones por docente."""
from __future__ import annotations


def _clean(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s.lower() == "nan" else s


def build_boleta_key(row: dict, row_index: int | None = None) -> str:
    emplid = _clean(row.get("EMPLID")) or _clean(row.get("RUT_SIN_DV"))
    numero = _clean(row.get("numeroBoleta_XML"))
    archivo = _clean(row.get("archivo_xml")) or _clean(row.get("Archivo_XML_Usado"))
    monto = _clean(row.get("CUS_TOT_HON")) or _clean(row.get("totalHonorarios_XML"))
    rut_razon = _clean(row.get("RUT RAZON"))

    if numero:
        return f"{emplid}|NB|{numero}"
    if archivo:
        return f"{emplid}|XML|{archivo}"
    if row_index is not None:
        return f"{emplid}|MTO|{monto}|RR|{rut_razon}|IDX|{row_index}"
    return f"{emplid}|MTO|{monto}|RR|{rut_razon}"
