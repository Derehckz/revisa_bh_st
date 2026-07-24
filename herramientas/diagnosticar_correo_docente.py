#!/usr/bin/env python3
"""Diagnóstico Outlook: ¿llegaron boletas de un docente y por qué no las tomó el pipeline?

Revisa la bandeja de entrada en un rango de fechas y reporta:
- correos del remitente / con el RUT en asunto o adjuntos
- si los adjuntos tienen prefijo bhe_ (requerido por etapa 2)
- si hay par PDF+XML

Ejemplo:
  python herramientas/diagnosticar_correo_docente.py \\
    --email c.bustosmoreira@gmail.com --rut 17255004 \\
    --fecha-inicio 01/05/2026 --fecha-fin 30/06/2026
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config
from outlook_utils import conectar_outlook_ns, filtrar_correos_por_fecha


def _parse_fecha(value: str) -> datetime:
    return datetime.strptime(value.strip(), "%d/%m/%Y").replace(tzinfo=config.ZONA_HORARIA)


def _sender_email(msg) -> str:
    ea = ""
    try:
        ea = str(getattr(msg, "SenderEmailAddress", None) or "").strip()
        if ea and "@" in ea and not ea.upper().startswith("/O="):
            return ea.lower()
        # Exchange DN → intentar SMTP
        sender = getattr(msg, "Sender", None)
        if sender is not None:
            try:
                ex = sender.GetExchangeUser()
                if ex is not None and ex.PrimarySmtpAddress:
                    return str(ex.PrimarySmtpAddress).strip().lower()
            except Exception:
                pass
        # Fallback: SenderName a veces trae el display; PropertyAccessor SMTP
        try:
            pa = msg.PropertyAccessor
            smtp = pa.GetProperty("http://schemas.microsoft.com/mapi/proptag/0x5D01001F")
            if smtp and "@" in str(smtp):
                return str(smtp).strip().lower()
        except Exception:
            pass
    except Exception:
        pass
    return ea.lower() if ea else ""


def _sender_blob(msg) -> str:
    """Texto rápido para filtrar sin resolver SMTP Exchange en cada correo."""
    parts: list[str] = []
    for attr in ("SenderEmailAddress", "SenderName", "Subject"):
        try:
            parts.append(str(getattr(msg, attr, "") or ""))
        except Exception:
            pass
    return " ".join(parts).lower()


def _attachments(msg) -> list[str]:
    names: list[str] = []
    try:
        for att in msg.Attachments:
            names.append(str(att.FileName))
    except Exception:
        pass
    return names


def main() -> int:
    p = argparse.ArgumentParser(description="Diagnóstico de correo Outlook por docente")
    p.add_argument("--email", required=True, help="Email del docente (remitente)")
    p.add_argument("--rut", required=True, help="RUT sin DV o con DV (ej. 17255004)")
    p.add_argument("--fecha-inicio", required=True, help="dd/mm/yyyy")
    p.add_argument("--fecha-fin", required=True, help="dd/mm/yyyy")
    args = p.parse_args()

    email = args.email.strip().lower()
    email_local = email.split("@")[0]
    rut_digits = "".join(ch for ch in args.rut if ch.isdigit())
    inicio = _parse_fecha(args.fecha_inicio)
    fin = _parse_fecha(args.fecha_fin).replace(hour=23, minute=59, second=59)

    print("=" * 72)
    print("Diagnóstico Outlook — boletas docente")
    print(f"  Remitente buscado : {email}")
    print(f"  RUT buscado       : {rut_digits} (también en nombres de adjunto)")
    print(f"  Rango             : {inicio:%d/%m/%Y} → {fin:%d/%m/%Y}")
    print("=" * 72)

    ns = conectar_outlook_ns()
    bandeja = ns.GetDefaultFolder(6)
    mensajes = filtrar_correos_por_fecha(bandeja, inicio, fin)
    print(f"\nCorreos en bandeja (rango): {len(mensajes)}")
    print("Escaneando (filtro rápido por remitente/asunto; adjuntos solo en candidatos)…")

    hits: list[dict] = []
    scanned = 0
    for msg in mensajes:
        scanned += 1
        if scanned % 500 == 0:
            print(f"  … {scanned}/{len(mensajes)}")
        try:
            blob = _sender_blob(msg)
            # Candidato barato: email, parte local, rut en asunto, o "bustos"
            cheap = (
                email in blob
                or email_local in blob
                or rut_digits in blob.replace("-", "")
                or "bustos" in blob
            )
            if not cheap:
                # Solo mirar adjuntos si hay pocos o si Class ok — skip heavy path
                continue

            from_addr = _sender_email(msg)
            subject = str(getattr(msg, "Subject", "") or "")
            atts = _attachments(msg)
            att_low = " ".join(a.lower() for a in atts)
            subj_low = subject.lower()
            match_from = email in from_addr or email_local in from_addr
            match_rut = rut_digits in att_low.replace("-", "") or rut_digits in subj_low.replace("-", "")
            match_bustos = "bustos" in subj_low or "bustos" in from_addr or "bustos" in blob
            if not (match_from or match_rut or match_bustos):
                continue

            bhe = [a for a in atts if "bhe_" in a.lower()]
            pdfs = [a for a in atts if a.lower().endswith(".pdf")]
            xmls = [a for a in atts if a.lower().endswith(".xml")]
            bhe_pdf = [a for a in bhe if a.lower().endswith(".pdf")]
            bhe_xml = [a for a in bhe if a.lower().endswith(".xml")]
            received = getattr(msg, "ReceivedTime", None)

            hits.append(
                {
                    "received": received,
                    "from": from_addr or "(sin smtp)",
                    "subject": subject,
                    "atts": atts,
                    "bhe": bhe,
                    "pdfs": pdfs,
                    "xmls": xmls,
                    "bhe_pdf": bhe_pdf,
                    "bhe_xml": bhe_xml,
                    "usable": bool(bhe_pdf and bhe_xml),
                }
            )
        except Exception as e:
            print(f"  (omitido correo por error: {e})")

    if not hits:
        print("\nCONCLUSIÓN:")
        print("  No hay correos en la bandeja de entrada que coincidan con ese")
        print("  remitente / RUT / 'bustos' en el rango indicado.")
        print("  → O no envió a este buzón, o el correo está en otra carpeta")
        print("    (spam, otra cuenta, o aún no llegó).")
        print("  Sin esos adjuntos en disco, la etapa 3 marca NO RECIBIDO y")
        print("  no hay pago (etapa 7) porque no hay boleta recepcionada.")
        return 0

    print(f"\nCorreos coincidentes: {len(hits)}\n")
    usable = 0
    sin_bhe = 0
    incompletos = 0
    for i, h in enumerate(hits, 1):
        rec = h["received"]
        rec_s = rec.strftime("%d/%m/%Y %H:%M") if rec else "?"
        print(f"--- #{i} {rec_s} ---")
        print(f"  De     : {h['from']}")
        print(f"  Asunto : {h['subject'][:100]}")
        print(f"  Adjuntos ({len(h['atts'])}): {', '.join(h['atts']) or '(ninguno)'}")
        if h["usable"]:
            usable += 1
            print("  Estado : OK para etapa 2 (hay bhe_ PDF + bhe_ XML)")
        elif h["atts"] and not h["bhe"]:
            sin_bhe += 1
            print("  Estado : Adjuntos SIN prefijo bhe_ → etapa 2 los IGNORA")
        elif h["bhe"] and not (h["bhe_pdf"] and h["bhe_xml"]):
            incompletos += 1
            print("  Estado : Tiene bhe_ pero falta par PDF+XML completo")
        else:
            print("  Estado : Sin adjuntos útiles")
        print()

    print("=" * 72)
    print("CONCLUSIÓN (para responder a la docente / pagos)")
    print("=" * 72)
    print(f"  Correos encontrados     : {len(hits)}")
    print(f"  Usables por etapa 2     : {usable}  (bhe_ PDF + XML)")
    print(f"  Con adjuntos sin bhe_   : {sin_bhe}")
    print(f"  bhe_ incompletos        : {incompletos}")
    print()
    if usable == 0 and sin_bhe > 0:
        print("  Causa probable del NO PAGO:")
        print("  Envió boletas, pero los archivos NO se llaman bhe_….pdf / bhe_….xml.")
        print("  La etapa 2 no los guarda → etapa 3 deja NO RECIBIDO → no entra a Pagos.")
        print("  Acción: pedir reenvío con nombres bhe_17255004-NNN.pdf/.xml, o renombrar")
        print("  manualmente, copiar a la carpeta del mes y re-correr etapa 3.")
    elif usable == 0:
        print("  Causa probable del NO PAGO:")
        print("  Hay correos relacionados, pero sin par PDF+XML usable.")
        print("  Acción: pedir reenvío de PDF y XML juntos con prefijo bhe_.")
    else:
        print("  Hay correos USABLES en Outlook que la etapa 2 debería haber bajado.")
        print("  Acción: correr etapa 2 en el rango de esas fechas (sin dry-run),")
        print("  luego etapa 3, y verificar que pase a RECIBIDO antes de pagos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
