"""Informe de pagos (hoja Pagos) por período — lectura preferente desde DB."""
from __future__ import annotations

import os
import re
from typing import Any

import config
import period_snapshots


def _month_dir(year: int | str, month: str) -> str:
    return os.path.join(config.RAIZ, str(year), str(month).strip().capitalize())


def _classify_correo(val: Any) -> str:
    s = str(val or "").strip().lower()
    if not s:
        return "pendiente"
    if "error" in s:
        return "error"
    if "omit" in s:
        return "omitido"
    if "enviad" in s or "✅" in str(val or ""):
        return "enviado"
    return "otro"


def _correo_label(status: str, raw: Any) -> str:
    raw_s = str(raw or "").strip()
    if status == "enviado":
        return "Enviado"
    if status == "omitido":
        return "Omitido"
    if status == "error":
        return "Error"
    if status == "pendiente":
        return "Pendiente"
    return raw_s or "Otro"


def _pick(row: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    # case-insensitive
    lower = {str(k).lower(): v for k, v in row.items()}
    for k in keys:
        v = lower.get(k.lower())
        if v not in (None, ""):
            return v
    return None


def _rut_digits(value: Any) -> str:
    s = re.sub(r"\D", "", str(value or ""))
    return s


def _normalize_item(row: dict[str, Any], *, docente_by_rut: dict[str, dict[str, Any]]) -> dict[str, Any]:
    from stages.stage7.mail import normalizar_monto_liquido

    rut = str(_pick(row, "ID", "RUT", "EMPLID") or "").strip()
    nombre = str(_pick(row, "Nombre", "NOMBRE", "Nombre Docente") or "").strip()
    boleta = _pick(row, "Número Boleta", "Numero Boleta", "BOLETA", "N° Boleta", "Nº Boleta")
    try:
        boleta_s = str(int(float(boleta))) if boleta not in (None, "") else ""
    except (TypeError, ValueError):
        boleta_s = str(boleta or "").strip()

    bruto_raw = _pick(row, "Bruto $", "BRUTO", "Bruto")
    ret_raw = _pick(row, "RETENCIÓN", "RETENCION", "Retención")
    liq_raw = _pick(row, "LÍQUIDO", "LIQUIDO", "Liquido Final", "Líquido")

    bruto = int(normalizar_monto_liquido(bruto_raw))
    retencion = int(normalizar_monto_liquido(ret_raw))
    liquido = int(normalizar_monto_liquido(liq_raw))

    # Si retención vacía pero hay bruto/líquido coherentes, derivar.
    if retencion == 0 and bruto > 0 and liquido > 0 and bruto >= liquido:
        retencion = bruto - liquido

    pct = None
    if bruto > 0 and retencion >= 0:
        pct = round(100.0 * retencion / bruto, 1)

    correo_raw = _pick(row, "Correo Enviado", "correo_enviado")
    mail_status = _classify_correo(correo_raw)

    digits = _rut_digits(rut)
    # Match con o sin DV
    docente = docente_by_rut.get(digits) or docente_by_rut.get(digits[:-1] if len(digits) > 1 else "")

    return {
        "rut": rut,
        "rut_digits": digits,
        "nombre": nombre,
        "boleta": boleta_s,
        "empresa": str(_pick(row, "Empr", "EMPR", "INS") or "").strip(),
        "sede": str(_pick(row, "SEDE", "Sede", "Nombre Sede") or "").strip(),
        "mail": str(_pick(row, "MAIL", "Mail", "Email") or "").strip(),
        "banco": str(_pick(row, "BANCO", "Banco") or "").strip(),
        "tipo_cuenta": str(_pick(row, "FORMA PAGO", "Tipo Cuenta") or "").strip(),
        "nro_cuenta": str(_pick(row, "NªCUENTA", "N°CUENTA", "Nro Cuenta") or "").strip(),
        "descripcion": str(_pick(row, "Descripción", "Descripcion", "Descripción") or "").strip(),
        "estado_boleta": str(_pick(row, "Estado Boleta") or "").strip(),
        "fecha_emision": str(_pick(row, "Fecha Emisión", "Fecha Emision") or "").strip(),
        "tipo_documento": str(_pick(row, "Tipo Documento") or "").strip(),
        "bruto": bruto,
        "retencion": retencion,
        "liquido": liquido,
        "retencion_pct": pct,
        "mail_status": mail_status,
        "mail_status_label": _correo_label(mail_status, correo_raw),
        "mail_raw": str(correo_raw or "").strip(),
        "docente_id": (docente or {}).get("id"),
        "docente_nombre": (docente or {}).get("nombre_completo") or nombre,
        "raw": row,
    }


def _docente_index(year: int, month: str) -> dict[str, dict[str, Any]]:
    """Mapa rut_digits → {id, nombre_completo} para el período (y fallback global)."""
    out: dict[str, dict[str, Any]] = {}
    try:
        from sqlalchemy import select

        from db.models import Boleta, Docente, Periodo
        from db.session import SessionLocal

        with SessionLocal() as session:
            periodo = session.execute(
                select(Periodo).where(Periodo.anio == year, Periodo.mes_nombre == month)
            ).scalar_one_or_none()
            if periodo is not None:
                rows = session.execute(
                    select(Docente.id, Docente.rut, Docente.rut_sin_dv, Docente.nombre_completo)
                    .join(Boleta, Boleta.docente_id == Docente.id)
                    .where(Boleta.periodo_id == periodo.id)
                ).all()
                for did, rut, rut_sin, nombre in rows:
                    for key in (_rut_digits(rut), _rut_digits(rut_sin)):
                        if key:
                            out[key] = {"id": did, "nombre_completo": nombre}
            # Complemento: todos los docentes (por si no hay boletas enlazadas)
            if len(out) < 5:
                for d in session.execute(select(Docente)).scalars().all():
                    for key in (_rut_digits(d.rut), _rut_digits(d.rut_sin_dv)):
                        if key and key not in out:
                            out[key] = {"id": d.id, "nombre_completo": d.nombre_completo}
    except Exception:
        pass
    return out


def _enrich_rows(raw_rows: list[dict[str, Any]], *, year: int, month: str) -> dict[str, Any]:
    docente_by_rut = _docente_index(year, month)
    items = [_normalize_item(dict(r), docente_by_rut=docente_by_rut) for r in raw_rows]
    counts = {"enviado": 0, "pendiente": 0, "error": 0, "omitido": 0, "otro": 0}
    total_bruto = total_ret = total_liq = 0
    for it in items:
        counts[it["mail_status"]] = counts.get(it["mail_status"], 0) + 1
        total_bruto += int(it["bruto"] or 0)
        total_ret += int(it["retencion"] or 0)
        total_liq += int(it["liquido"] or 0)
    return {
        "items": items,
        "counts": counts,
        "totals": {
            "bruto": total_bruto,
            "retencion": total_ret,
            "liquido": total_liq,
            "rows": len(items),
        },
    }


def period_pagos_report(year: int | str, month: str) -> dict[str, Any]:
    month_name = str(month).strip().capitalize()
    year_int = int(year)

    db_snap = period_snapshots.load_pagos_snapshot(year_int, month_name)
    if db_snap and db_snap.get("exists"):
        rows = db_snap.get("rows") or []
        enriched = _enrich_rows(rows, year=year_int, month=month_name)
        return {
            **db_snap,
            "rows": rows,
            **enriched,
        }

    payload = period_snapshots.build_pagos_payload_from_excel(year_int, month_name)
    out: dict[str, Any] = {
        "year": year_int,
        "month": month_name,
        "exists": False,
        "frozen": False,
        "generated_at": None,
        "source": None,
        "source_kind": "excel",
        "total_rows": 0,
        "rows": [],
        "items": [],
        "counts": {"enviado": 0, "pendiente": 0, "error": 0, "omitido": 0, "otro": 0},
        "totals": {"bruto": 0, "retencion": 0, "liquido": 0, "rows": 0},
        "read_error": None,
        "period_status": None,
    }
    if not payload:
        solicitud = os.path.join(_month_dir(year_int, month_name), "Solicitud.xlsx")
        if not os.path.isfile(solicitud):
            out["read_error"] = "No hay Solicitud.xlsx ni snapshot de pagos en BD."
        else:
            out["read_error"] = "No existe la hoja «Pagos». Cárgala en el paso 7."
        return out

    rows = payload.get("rows") or []
    enriched = _enrich_rows(rows, year=year_int, month=month_name)
    out.update(
        {
            "exists": True,
            "generated_at": payload.get("generated_at"),
            "source": payload.get("source"),
            "total_rows": len(rows),
            "rows": rows,
            **enriched,
        }
    )
    return out
