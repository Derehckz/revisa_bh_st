"""Validación Contabilidad post-informe (fase 2 del ciclo mensual)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from db import audit
from db.models import Periodo
from db.session import SessionLocal

VALID_STATUSES = frozenset({"pendiente", "ok", "con_observaciones"})


def mark_contabilidad(
    year: int,
    month: str,
    *,
    status: str,
    operator: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Marca el resultado de Contabilidad sobre el informe del período."""
    status_norm = str(status or "").strip().lower()
    if status_norm not in VALID_STATUSES:
        raise ValueError("status debe ser pendiente | ok | con_observaciones")
    month_norm = str(month).strip().capitalize()
    year_int = int(year)
    now = datetime.now(UTC)

    with SessionLocal() as session:
        periodo = session.execute(
            select(Periodo).where(Periodo.anio == year_int, Periodo.mes_nombre == month_norm)
        ).scalar_one_or_none()
        if periodo is None:
            raise ValueError(f"No existe período {month_norm} {year_int} en BD.")

        periodo.contabilidad_status = status_norm
        periodo.contabilidad_notes = (str(notes).strip() if notes else None) or None
        if status_norm == "pendiente":
            periodo.contabilidad_validated_at = None
            periodo.contabilidad_validated_by = None
        else:
            periodo.contabilidad_validated_at = now
            periodo.contabilidad_validated_by = (str(operator).strip() if operator else None) or None
        session.commit()
        session.refresh(periodo)
        payload = {
            "year": year_int,
            "month": month_norm,
            "contabilidad_status": periodo.contabilidad_status,
            "contabilidad_validated_at": (
                periodo.contabilidad_validated_at.isoformat() if periodo.contabilidad_validated_at else None
            ),
            "contabilidad_validated_by": periodo.contabilidad_validated_by,
            "contabilidad_notes": periodo.contabilidad_notes,
        }

    audit.record_event(
        action=f"period.contabilidad_{status_norm}",
        operator=operator,
        period_year=year_int,
        period_month=month_norm,
        entity="periodo",
        detail={"notes": notes},
    )
    return payload


def reset_contabilidad_after_informe(year: int, month: str) -> None:
    """Tras regenerar informe, Contabilidad debe volver a validar."""
    try:
        mark_contabilidad(year, month, status="pendiente", operator="sistema", notes="Informe regenerado")
    except Exception:
        pass


def contabilidad_snapshot(periodo: Periodo | None) -> dict[str, Any]:
    if periodo is None:
        return {
            "contabilidad_status": None,
            "contabilidad_validated_at": None,
            "contabilidad_validated_by": None,
            "contabilidad_notes": None,
        }
    return {
        "contabilidad_status": getattr(periodo, "contabilidad_status", None),
        "contabilidad_validated_at": (
            periodo.contabilidad_validated_at.isoformat()
            if getattr(periodo, "contabilidad_validated_at", None)
            else None
        ),
        "contabilidad_validated_by": getattr(periodo, "contabilidad_validated_by", None),
        "contabilidad_notes": getattr(periodo, "contabilidad_notes", None),
    }
