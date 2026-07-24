"""Persistencia y sincronizacion de docentes."""
from __future__ import annotations

from typing import Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from db.models import Docente
from db.session import SessionLocal


def _clean(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _pick(row: dict, *keys: str) -> str:
    for key in keys:
        if key in row:
            value = _clean(row.get(key))
            if value:
                return value
    return ""


def sync_docentes_from_excel(path: str) -> dict:
    stats = {"inserted": 0, "updated": 0, "total_rows": 0}
    try:
        with pd.ExcelFile(path, engine="openpyxl") as xls:
            sheet = "Solicitud" if "Solicitud" in xls.sheet_names else xls.sheet_names[0]
    except Exception:
        return stats

    try:
        df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
    except Exception:
        return stats

    rows = [
        {str(col).strip().upper(): value for col, value in record.items()}
        for record in df.to_dict(orient="records")
    ]

    try:
        with SessionLocal() as session:
            for row in rows:
                rut = _pick(row, "RUT", "EMPLID")
                nombre = _pick(row, "NAME", "NOMBRE DOCENTE", "NOMBRE_COMPLETO")
                if not rut or not nombre:
                    continue

                stats["total_rows"] += 1
                sede = _pick(row, "SEDE", "NOMBRE SEDE", "SEDE_DOCENTE")
                email = _pick(row, "EMAIL_DOCENTE", "EMAIL PERSONAL", "EMAIL")
                email_dp = _pick(row, "EMAIL_DP", "EMAIL DP")

                docente = session.execute(select(Docente).where(Docente.rut == rut)).scalar_one_or_none()
                if docente is None:
                    session.add(
                        Docente(
                            rut=rut,
                            nombre_completo=nombre,
                            sede=sede or None,
                            email_personal=email or None,
                            email_dp=email_dp or None,
                            activo="true",
                        )
                    )
                    stats["inserted"] += 1
                else:
                    changed = False
                    if nombre and docente.nombre_completo != nombre:
                        docente.nombre_completo = nombre
                        changed = True
                    if sede and not docente.sede:
                        docente.sede = sede
                        changed = True
                    if email and not docente.email_personal:
                        docente.email_personal = email
                        changed = True
                    if email_dp and not docente.email_dp:
                        docente.email_dp = email_dp
                        changed = True
                    if changed:
                        stats["updated"] += 1
            session.commit()
    except SQLAlchemyError:
        return stats

    return stats

