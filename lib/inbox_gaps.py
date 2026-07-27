"""Detector de huecos: boletas en Inbox Outlook que faltan en la carpeta del mes.

Caso Maass: la solicitud queda NO RECIBIDO aunque el docente ya envió bhe_ PDF+XML
y el paso 2 no los bajó (rango, COM, o corrida anterior al mail).
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Any

import pandas as pd

import config
import utils
from outlook_utils import (
    check_outlook_health,
    conectar_outlook_ns,
    filtrar_correos_por_fecha,
)

PREFIJO = (config.PREFIJO or "bhe_").lower()
_BHE_NAME_RE = re.compile(
    rf"^{re.escape(PREFIJO)}(?P<rut>\d+)[-_](?P<folio>\d+)\.(?P<ext>pdf|xml)$",
    re.IGNORECASE,
)


def _rut_cuerpo(value: object) -> str:
    raw = str(value or "").strip().upper().replace(".", "").replace(" ", "")
    if not raw or raw in {"NAN", "NONE"}:
        return ""
    if "-" in raw:
        return re.sub(r"\D", "", raw.split("-", 1)[0])
    d = re.sub(r"\D", "", raw)
    if len(d) >= 8:
        return d[:-1]
    return d


def _parse_fecha_cl(value: str, *, end_of_day: bool = False) -> datetime:
    dt = datetime.strptime(value.strip(), "%d/%m/%Y").replace(tzinfo=config.ZONA_HORARIA)
    if end_of_day:
        return dt.replace(hour=23, minute=59, second=59)
    return dt


def _default_range(year: int, month: str) -> tuple[datetime, datetime]:
    mes = str(month).strip()
    if mes not in config.MESES_ES:
        raise ValueError(f"Mes inválido: {month}")
    mes_num = config.MESES_ES.index(mes) + 1
    inicio = datetime(int(year), mes_num, 1, tzinfo=config.ZONA_HORARIA)
    if mes_num == 12:
        fin = datetime(int(year), 12, 31, 23, 59, 59, tzinfo=config.ZONA_HORARIA)
    else:
        next_month = datetime(int(year), mes_num + 1, 1, tzinfo=config.ZONA_HORARIA)
        from datetime import timedelta

        fin = next_month - timedelta(seconds=1)
    return inicio, fin


def _archivos_en_carpeta(carpeta: str) -> set[str]:
    if not os.path.isdir(carpeta):
        return set()
    return {f.lower() for f in os.listdir(carpeta) if f.lower().startswith(PREFIJO)}


def _no_recibido_por_rut(ruta_excel: str) -> dict[str, dict[str, Any]]:
    """RUT cuerpo → datos de la primera fila NO RECIBIDO."""
    if not os.path.isfile(ruta_excel):
        return {}
    df = pd.read_excel(ruta_excel, engine="openpyxl")
    if "Estado_Recepcion" not in df.columns:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        estado = str(row.get("Estado_Recepcion") or "").strip().upper()
        if estado != "NO RECIBIDO":
            continue
        rut = _rut_cuerpo(row.get("RUT_SIN_DV"))
        if not rut or rut in out:
            continue
        out[rut] = {
            "rut": rut,
            "name": str(row.get("NAME") or "").strip(),
            "email": str(row.get("Email_Docente") or "").strip(),
            "monto": row.get("CUS_TOT_HON"),
        }
    return out


def detectar_huecos_inbox(
    year: int | str,
    month: str,
    *,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
) -> dict[str, Any]:
    """Compara Inbox (rango) vs carpeta del período para filas NO RECIBIDO."""
    año = str(year).strip()
    mes = str(month).strip()
    if mes not in config.MESES_ES:
        raise ValueError(f"Mes inválido: {month}")

    carpeta = os.path.join(config.CARPETA_BASE, año, mes)
    ruta_excel = os.path.join(carpeta, "Solicitud.xlsx")
    pendientes = _no_recibido_por_rut(ruta_excel)

    if fecha_inicio and fecha_fin:
        inicio = _parse_fecha_cl(fecha_inicio)
        fin = _parse_fecha_cl(fecha_fin, end_of_day=True)
    elif fecha_inicio or fecha_fin:
        raise ValueError("Indique ambas fechas (inicio y fin) o ninguna.")
    else:
        inicio, fin = _default_range(int(año), mes)

    health = check_outlook_health(probe_com=True)
    if not health.get("ready"):
        return {
            "ok": False,
            "error": health.get("message") or "Outlook no está listo.",
            "outlook_health": health,
            "year": int(año),
            "month": mes,
            "fecha_inicio": inicio.strftime("%d/%m/%Y"),
            "fecha_fin": fin.strftime("%d/%m/%Y"),
            "no_recibidos": len(pendientes),
            "emails_scanned": 0,
            "gaps": [],
            "gap_count": 0,
        }

    if not pendientes:
        return {
            "ok": True,
            "year": int(año),
            "month": mes,
            "fecha_inicio": inicio.strftime("%d/%m/%Y"),
            "fecha_fin": fin.strftime("%d/%m/%Y"),
            "carpeta": carpeta,
            "no_recibidos": 0,
            "emails_scanned": 0,
            "gaps": [],
            "gap_count": 0,
            "message": "No hay filas NO RECIBIDO en Solicitud.xlsx.",
            "outlook_health": health,
        }

    en_disco = _archivos_en_carpeta(carpeta)
    ns = conectar_outlook_ns(ensure_running=True, wait_s=45)
    bandeja = ns.GetDefaultFolder(6)
    mensajes = filtrar_correos_por_fecha(bandeja, inicio, fin)

    # folio → gap info (dedupe)
    gaps_by_key: dict[str, dict[str, Any]] = {}

    for msg in mensajes:
        try:
            names = [str(att.FileName) for att in msg.Attachments]
        except Exception as e:
            logging.debug("Adjuntos ilegibles: %s", e)
            continue

        bhe = [n for n in names if "bhe_" in n.lower()]
        if not bhe:
            continue
        parsed: list[tuple[str, str, str]] = []
        for n in bhe:
            m = _BHE_NAME_RE.match(n.strip())
            if not m:
                continue
            parsed.append((m.group("rut"), m.group("folio"), m.group("ext").lower()))
        if not parsed:
            continue

        ruts_in_mail = {p[0] for p in parsed}
        target_ruts = ruts_in_mail & set(pendientes.keys())
        if not target_ruts:
            continue

        # Exigir par pdf+xml por folio (como etapa 2)
        by_folio: dict[tuple[str, str], set[str]] = {}
        for rut, folio, ext in parsed:
            if rut not in target_ruts:
                continue
            by_folio.setdefault((rut, folio), set()).add(ext)

        try:
            rt = msg.ReceivedTime
            rt_s = str(rt)
        except Exception:
            rt_s = ""
        try:
            subject = str(getattr(msg, "Subject", "") or "")
        except Exception:
            subject = ""
        try:
            sender = str(getattr(msg, "SenderEmailAddress", "") or "")
        except Exception:
            sender = ""

        for (rut, folio), exts in by_folio.items():
            if not ({"pdf", "xml"} <= exts):
                continue
            pdf_name = f"{config.PREFIJO}{rut}-{folio}.pdf"
            xml_name = f"{config.PREFIJO}{rut}-{folio}.xml"
            # También aceptar guión bajo en disco
            pdf_ok = pdf_name.lower() in en_disco or f"{PREFIJO}{rut}_{folio}.pdf" in en_disco
            xml_ok = xml_name.lower() in en_disco or f"{PREFIJO}{rut}_{folio}.xml" in en_disco
            if pdf_ok and xml_ok:
                continue
            key = f"{rut}-{folio}"
            info = pendientes[rut]
            gaps_by_key[key] = {
                "rut": rut,
                "folio": folio,
                "name": info.get("name") or "",
                "email": info.get("email") or "",
                "monto_solicitud": info.get("monto"),
                "received_time": rt_s,
                "subject": subject,
                "sender": sender,
                "attachments": [pdf_name, xml_name],
                "missing_pdf": not pdf_ok,
                "missing_xml": not xml_ok,
                "suggested_action": "Ejecutar paso 2 en un rango que incluya la fecha del correo, luego paso 3.",
            }

    gaps = sorted(gaps_by_key.values(), key=lambda g: (g.get("received_time") or ""), reverse=True)
    return {
        "ok": True,
        "year": int(año),
        "month": mes,
        "fecha_inicio": inicio.strftime("%d/%m/%Y"),
        "fecha_fin": fin.strftime("%d/%m/%Y"),
        "carpeta": carpeta,
        "excel": ruta_excel,
        "no_recibidos": len(pendientes),
        "emails_scanned": len(mensajes),
        "gaps": gaps,
        "gap_count": len(gaps),
        "message": (
            f"Hay {len(gaps)} boleta(s) en Inbox para filas NO RECIBIDO que aún no están en la carpeta."
            if gaps
            else "No se detectaron huecos: ningún NO RECIBIDO tiene par bhe_ en Inbox fuera de carpeta."
        ),
        "outlook_health": health,
    }
