"""Proyección de estado canónico por boleta."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

def _norm(value: Any) -> str:
    return str(value or "").strip()


def _normalizar_glosa(texto: object) -> str:
    s = str(texto or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _normalizar_glosa_compacta(texto: object) -> str:
    compact = _normalizar_glosa(texto).replace(" ", "")
    return re.sub(r"20\d{2}$", "", compact)


def _extraer_prefijo(glosa_compacta: str) -> tuple[str | None, str]:
    for pref in ("ipst", "cftst"):
        if glosa_compacta.startswith(pref):
            return pref, glosa_compacta[len(pref):]
    return None, glosa_compacta


def _clasificar_coincidencia_glosa(glosa_excel: object, glosa_xml: object) -> str:
    g_excel = _normalizar_glosa_compacta(glosa_excel)
    g_xml = _normalizar_glosa_compacta(glosa_xml)
    if not g_xml:
        return "exacta"
    if g_excel == g_xml:
        return "exacta"
    pref_excel, body_excel = _extraer_prefijo(g_excel)
    pref_xml, body_xml = _extraer_prefijo(g_xml)
    if pref_excel and not pref_xml and body_excel == body_xml:
        return "prefijo_omitido"
    if pref_xml and not pref_excel and body_excel == body_xml:
        return "prefijo_omitido"
    return "distinta"


def classify_recepcion_status(row: dict[str, Any]) -> tuple[str, str | None, str]:
    """
    Retorna (recepcion_status, effective_reason, glosa_match_mode).
    """
    estado = _norm(row.get("Estado_Recepcion")).upper()
    glosa_excel = _norm(row.get("GLOSA"))
    glosa_xml = _norm(row.get("descripcionLinea_XML"))
    glosa_mode = _clasificar_coincidencia_glosa(glosa_excel, glosa_xml) if glosa_xml else "exacta"

    if estado == "NO RECIBIDO":
        return "NO_RECIBIDO", "no_recibido", glosa_mode
    if estado == "RECIBIDO CON ERROR":
        return "RECIBIDO_ERROR", "recibido_con_error", glosa_mode
    if estado == "RECIBIDO":
        if glosa_xml and glosa_mode == "distinta":
            return "RECIBIDO_ERROR", "glosa_incorrecta", glosa_mode
        return "RECIBIDO_OK", None, glosa_mode
    if not estado:
        return "NO_RECIBIDO", "sin_estado", glosa_mode
    return "RECIBIDO_ERROR", "estado_no_valido", glosa_mode


def classify_xml_status(row: dict[str, Any]) -> str:
    obs_xml = _norm(row.get("Observaciones_XML")).upper()
    for a, b in (("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U")):
        obs_xml = obs_xml.replace(a, b)
    archivo_xml = _norm(row.get("archivo_xml"))
    if not archivo_xml:
        return "PENDIENTE"
    if obs_xml == "DATOS EXTRAIDOS OK":
        return "OK"
    if obs_xml:
        return "ERROR"
    return "PENDIENTE"


def classify_mail_recepcion_status(row: dict[str, Any]) -> str:
    marker = _norm(row.get("Correo_Recepcion_Enviado")).lower()
    if not marker:
        return "PENDIENTE"
    if "confirmación" in marker or "confirmacion" in marker:
        return "ENVIADO_OK"
    if "observación" in marker or "observacion" in marker or "reenvío" in marker or "reenvio" in marker:
        return "ENVIADO_PROBLEMA"
    if "enviado" in marker:
        return "ENVIADO_OK"
    return "PENDIENTE"
