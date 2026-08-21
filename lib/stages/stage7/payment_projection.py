"""Proyecta estado de pago desde la hoja Pagos hacia boletas en BD."""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select

from db.models import Boleta, Periodo
from db.session import SessionLocal


def _digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def project_pagos_dataframe(*, year: int | str, month: str, df) -> dict[str, int]:
    """Actualiza estado_pago / observaciones_pago según columna Correo Enviado de Pagos."""
    month_norm = str(month).strip().capitalize()
    year_int = int(year)
    updated = 0
    skipped = 0
    with SessionLocal() as session:
        periodo = session.execute(
            select(Periodo).where(Periodo.anio == year_int, Periodo.mes_nombre == month_norm)
        ).scalar_one_or_none()
        if periodo is None:
            return {"updated": 0, "skipped": 0, "failed": 1}

        boletas = session.execute(select(Boleta).where(Boleta.periodo_id == periodo.id)).scalars().all()
        by_emplid: dict[str, list[Boleta]] = {}
        for b in boletas:
            key = _digits(b.emplid)
            if key:
                by_emplid.setdefault(key, []).append(b)

        for _, row in df.iterrows():
            emplid = _digits(row.get("EMPLID") or row.get("RUT") or row.get("MAIL"))
            if not emplid:
                skipped += 1
                continue
            correo = str(row.get("Correo Enviado") or "").strip()
            obs = str(row.get("Observaciones") or row.get("OBS") or "").strip() or None
            if not correo and not obs:
                skipped += 1
                continue
            estado = "ENVIADO" if "enviado" in correo.lower() else ("ERROR" if "error" in correo.lower() else "PENDIENTE")
            candidates = by_emplid.get(emplid) or []
            if not candidates:
                skipped += 1
                continue
            for b in candidates:
                b.estado_pago = estado
                if obs:
                    b.observaciones_pago = obs
                elif correo:
                    b.observaciones_pago = correo
                updated += 1
        session.commit()
    return {"updated": updated, "skipped": skipped, "failed": 0}
