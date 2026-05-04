"""Persistencia mínima de eventos de correo en PostgreSQL."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError

from db.models import EnvioEmail
from db.session import SessionLocal


def save_email_event(
    *,
    tipo_envio: str,
    to_email: str,
    cc_email: Optional[str] = None,
    subject: Optional[str] = None,
    estado: str = "PENDIENTE",
    error_detalle: Optional[str] = None,
    periodo_label: Optional[str] = None,
) -> bool:
    try:
        with SessionLocal() as session:
            row = EnvioEmail(
                tipo_envio=tipo_envio,
                to_email=to_email,
                cc_email=cc_email,
                subject=subject,
                estado=estado,
                error_detalle=error_detalle,
                periodo_label=periodo_label,
                sent_at=datetime.now(UTC) if estado == "ENVIADO" else None,
            )
            session.add(row)
            session.commit()
            return True
    except SQLAlchemyError:
        return False
