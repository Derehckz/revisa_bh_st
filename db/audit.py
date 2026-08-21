"""Bitácora de auditoría operativa."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from db.models import AuditEvent
from db.session import SessionLocal


def record_event(
    *,
    action: str,
    operator: str | None = None,
    period_year: int | None = None,
    period_month: str | None = None,
    entity: str | None = None,
    entity_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with SessionLocal() as session:
        row = AuditEvent(
            action=str(action or "").strip()[:64] or "unknown",
            operator=(str(operator).strip()[:128] if operator else None) or None,
            period_year=period_year,
            period_month=(str(period_month).strip().capitalize() if period_month else None),
            entity=(str(entity).strip()[:64] if entity else None),
            entity_id=(str(entity_id).strip()[:128] if entity_id is not None else None),
            detail=detail or None,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "ts": row.ts.isoformat() if row.ts else None,
            "action": row.action,
            "operator": row.operator,
        }


def list_events(
    *,
    year: int | None = None,
    month: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 100), 500))
    with SessionLocal() as session:
        stmt = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
        if year is not None:
            stmt = stmt.where(AuditEvent.period_year == int(year))
        if month:
            stmt = stmt.where(AuditEvent.period_month == str(month).strip().capitalize())
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "ts": r.ts.isoformat() if r.ts else None,
                "operator": r.operator,
                "action": r.action,
                "period_year": r.period_year,
                "period_month": r.period_month,
                "entity": r.entity,
                "entity_id": r.entity_id,
                "detail": r.detail or {},
            }
            for r in rows
        ]
