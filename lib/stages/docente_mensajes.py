"""Mensajes de observación orientados al docente (sin jerga de Excel/XML)."""
from __future__ import annotations

import re
from typing import Any


def format_monto_cl(valor: object) -> str:
    try:
        n = int(float(str(valor).replace(",", ".")))
        return f"${n:,}".replace(",", ".")
    except (TypeError, ValueError):
        s = str(valor or "").strip()
        return s if s else "N/A"


def folio_desde_archivo(archivo: str) -> str:
    base = str(archivo or "").rsplit(".", 1)[0]
    m = re.search(r"[-_](\d+)$", base)
    return m.group(1) if m else base


def _es_provisionado(texto: object) -> bool:
    t = str(texto or "").lower()
    return any(p in t for p in ("provisionado", "provisonado", "provs"))


def _institucion_corta(glosa: str) -> str:
    g = str(glosa or "").strip()
    gu = g.upper()
    if "CFT" in gu or "CST" in gu:
        return "CFT"
    if "IPST" in gu or "IP " in gu or gu.startswith("IP"):
        return "IP"
    return ""


def explicar_descarte_docente(
    archivo: str,
    motivo: str,
    *,
    monto_solicitado: object = None,
    glosa_solicitada: str = "",
    monto_boleta: object = None,
) -> str:
    """Una frase que el docente entiende (monto + glosa pedida)."""
    folio = folio_desde_archivo(archivo)
    motivo_l = str(motivo or "").lower()
    monto_ped = format_monto_cl(monto_solicitado) if monto_solicitado not in (None, "") else ""
    monto_bh = format_monto_cl(monto_boleta) if monto_boleta not in (None, "") else ""
    glosa = str(glosa_solicitada or "").strip()
    inst = _institucion_corta(glosa)
    pedida = f" ({inst})" if inst else ""

    # Extraer montos del motivo técnico si vienen embebidos
    if not monto_bh:
        m = re.search(r"monto xml\s*\(([^)]+)\)", motivo_l)
        if m:
            monto_bh = format_monto_cl(m.group(1))
    if not monto_ped:
        m = re.search(r"monto de esta línea\s*\(([^)]+)\)", motivo_l)
        if m:
            monto_ped = format_monto_cl(m.group(1))
        else:
            m2 = re.search(r"distinto al monto[^(]*\(([^)]+)\)", motivo_l)
            if m2:
                monto_ped = format_monto_cl(m2.group(1))

    if "glosa/provisión" in motivo_l or "provision" in motivo_l and "inconsistente" in motivo_l:
        if _es_provisionado(glosa):
            return (
                f"La boleta nº {folio}"
                + (f" por {monto_bh}" if monto_bh and monto_bh != "N/A" else "")
                + " no incluye «PROVISIONADO» en la glosa. "
                f"La solicitud{pedida} pedía la glosa: «{glosa or 'PROVISIONADO'}»."
            )
        return (
            f"La boleta nº {folio} indica PROVISIONADO en la glosa, "
            f"pero la solicitud{pedida} no lo pedía"
            + (f" (glosa: «{glosa}»)" if glosa else "")
            + "."
        )

    if "glosa distinta" in motivo_l:
        return (
            f"La boleta nº {folio} tiene una glosa distinta a la solicitada"
            + (f" (pedida: «{glosa}»)." if glosa else ". Debe regenerar con la glosa exacta del correo de solicitud.")
        )

    if "monto" in motivo_l and ("distinto" in motivo_l or "diferente" in motivo_l):
        return (
            f"Recibimos la boleta nº {folio} por {monto_bh or 'otro monto'}, "
            f"pero esta solicitud{pedida} es por {monto_ped or 'el monto indicado en el correo'}."
        )

    if "ya asignada" in motivo_l or "otra línea" in motivo_l:
        return (
            f"La boleta nº {folio}"
            + (f" ({monto_bh})" if monto_bh and monto_bh != "N/A" else "")
            + " ya quedó asociada a otra solicitud suya del mismo período."
        )

    if "rut receptor" in motivo_l or "razón" in motivo_l:
        return (
            f"La boleta nº {folio} está emitida a otra razón social / RUT receptor "
            f"distinto al de esta solicitud{pedida}."
        )

    if "rut emisor" in motivo_l:
        return f"La boleta nº {folio} no coincide con su RUT de emisor."

    if "falta pdf" in motivo_l or "pdf pareado" in motivo_l:
        return f"Llegó el XML de la boleta nº {folio} pero falta el PDF correspondiente."

    if "pdf sin xml" in motivo_l:
        return f"Llegó el PDF de la boleta nº {folio} pero falta el XML correspondiente."

    return f"La boleta nº {folio} no pudo validarse contra lo solicitado{pedida}."


def observacion_principal_docente(
    descartes: list[str],
    fila: dict[str, Any] | Any,
) -> str:
    """Texto corto de Observaciones (correo + Excel) en voz del docente."""
    glosa = str(getattr(fila, "get", lambda k, d=None: fila.get(k, d) if hasattr(fila, "get") else d)("GLOSA", "") or "")
    if hasattr(fila, "get"):
        glosa = str(fila.get("GLOSA", "") or "")
        monto = fila.get("CUS_TOT_HON", "")
    else:
        glosa = str(getattr(fila, "GLOSA", "") or "")
        monto = getattr(fila, "CUS_TOT_HON", "")

    monto_txt = format_monto_cl(monto)
    inst = _institucion_corta(glosa)
    pedida = f" de {inst}" if inst else ""
    joined = " | ".join(descartes).lower()

    if "glosa/provisión" in joined or ("provision" in joined and "inconsistente" in joined):
        if _es_provisionado(glosa):
            return (
                f"Recibimos su boleta{pedida} por {monto_txt}, pero la glosa no incluye "
                f"«PROVISIONADO» como pedimos. Debe anular y regenerar con la glosa: «{glosa}»."
            )
        return (
            f"Recibimos su boleta{pedida} por {monto_txt} con glosa PROVISIONADO, "
            f"pero esa solicitud no pedía PROVISIONADO. Regenerar con la glosa: «{glosa}»."
        )

    if "glosa distinta" in joined:
        return (
            f"Recibimos su boleta{pedida} por {monto_txt}, pero la glosa no coincide "
            f"con la solicitada. Debe anular y regenerar con la glosa exacta: «{glosa}»."
        )

    if "ya asignada" in joined or "otra línea" in joined:
        return (
            f"La boleta que envió ya quedó asociada a otra solicitud suya del período "
            f"(esta es por {monto_txt}{pedida})."
        )

    if "monto" in joined and "distinto" in joined:
        return (
            f"Recibimos boleta(s) suyas, pero ninguna por el monto de esta solicitud "
            f"({monto_txt}{pedida}). Revise el monto del correo de solicitud y regenere."
        )

    if "rut receptor" in joined:
        return (
            f"La boleta no está emitida a la razón social / RUT de esta solicitud "
            f"({monto_txt}{pedida})."
        )

    if not descartes:
        return (
            f"Aún no recibimos una boleta válida por {monto_txt}{pedida} "
            f"con la glosa solicitada."
        )

    return (
        f"La boleta enviada no coincide con la solicitud{pedida} por {monto_txt}. "
        f"Revise monto, glosa y razón social del correo de solicitud."
    )


def detalle_descartes_docente(
    descartes_raw: str | list[str],
    fila: dict[str, Any] | Any,
) -> str:
    """Lista legible para el correo (una frase por archivo revisado)."""
    if isinstance(descartes_raw, str):
        parts = [p.strip() for p in descartes_raw.split(";") if p.strip()]
    else:
        parts = [str(p).strip() for p in (descartes_raw or []) if str(p).strip()]

    if hasattr(fila, "get"):
        glosa = str(fila.get("GLOSA", "") or "")
        monto = fila.get("CUS_TOT_HON", "")
    else:
        glosa = str(getattr(fila, "GLOSA", "") or "")
        monto = getattr(fila, "CUS_TOT_HON", "")

    lines: list[str] = []
    for part in parts:
        if ":" in part:
            archivo, motivo = part.split(":", 1)
            archivo, motivo = archivo.strip(), motivo.strip()
        else:
            archivo, motivo = "boleta", part
        # monto boleta desde motivo si viene
        m = re.search(r"monto XML\s*\(([^)]+)\)", motivo, re.I)
        monto_bh = m.group(1) if m else None
        lines.append(
            explicar_descarte_docente(
                archivo,
                motivo,
                monto_solicitado=monto,
                glosa_solicitada=glosa,
                monto_boleta=monto_bh,
            )
        )
    return "\n".join(f"• {ln}" for ln in lines)
