"""Estado de sincronización Excel (Solicitud.xlsx) ↔ PostgreSQL para un período.

Comparación liviana pensada para mostrarse como indicador en la UI de Operación:
no reemplaza una auditoría completa, solo compara conteos totales para detectar
desalineaciones evidentes entre el Excel de trabajo y lo que quedó persistido en BD.

Contrato de salida: ``{"status": "ok" | "degraded" | "unknown", "message": str,
"details": dict}``. Cualquier error (BD no disponible, Excel bloqueado, etc.) se
traduce en ``status="unknown"`` para no romper la UI ni bloquear operación.
"""
from __future__ import annotations

from typing import Any

STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_UNKNOWN = "unknown"


def _significant_diff(excel_total: int, db_total: int) -> bool:
    diff = abs(excel_total - db_total)
    if diff == 0:
        return False
    threshold = max(3, round(0.05 * max(excel_total, db_total, 1)))
    return diff > threshold


def period_sync_status(year: int | str, month: str) -> dict[str, Any]:
    """Compara total de filas en Solicitud.xlsx vs. total de boletas en PostgreSQL.

    No lanza excepciones: cualquier problema (BD caída, período sin sincronizar,
    Excel abierto/corrupto, etc.) se refleja como ``status="unknown"``.
    """
    try:
        import stage_operations

        excel_summary = stage_operations.period_summary(year, month)
    except Exception as exc:
        return {
            "status": STATUS_UNKNOWN,
            "message": f"No se pudo leer Solicitud.xlsx: {exc}",
            "details": {},
        }

    excel_total = int(excel_summary.get("total_rows") or 0)
    solicitud_exists = bool(excel_summary.get("solicitud_exists"))

    try:
        db_total = _db_boleta_count(year, month)
    except Exception as exc:
        return {
            "status": STATUS_UNKNOWN,
            "message": f"No se pudo consultar PostgreSQL: {exc}",
            "details": {"excel_total_rows": excel_total},
        }

    if db_total is None:
        return {
            "status": STATUS_UNKNOWN,
            "message": "Período aún no sincronizado en PostgreSQL (sin registro Periodo).",
            "details": {"excel_total_rows": excel_total, "solicitud_exists": solicitud_exists},
        }

    if not solicitud_exists and db_total == 0:
        return {
            "status": STATUS_UNKNOWN,
            "message": "Sin datos: no existe Solicitud.xlsx ni boletas en BD para este período.",
            "details": {"excel_total_rows": excel_total, "db_total_boletas": db_total},
        }

    details = {"excel_total_rows": excel_total, "db_total_boletas": db_total}
    if _significant_diff(excel_total, db_total):
        return {
            "status": STATUS_DEGRADED,
            "message": (
                f"Diferencia entre Excel ({excel_total} filas) y PostgreSQL "
                f"({db_total} boletas). Revisa si falta sincronizar."
            ),
            "details": details,
        }

    return {
        "status": STATUS_OK,
        "message": "Excel y PostgreSQL están alineados en total de filas/boletas.",
        "details": details,
    }


def _db_boleta_count(year: int | str, month: str) -> int | None:
    """Devuelve el conteo de boletas en BD para el período, o None si no existe el Periodo."""
    from sqlalchemy import func, select

    from db.models import Boleta, Periodo
    from db.session import SessionLocal

    month_norm = str(month).strip().capitalize()
    year_int = int(year)
    with SessionLocal() as session:
        periodo = session.execute(
            select(Periodo).where(Periodo.anio == year_int, Periodo.mes_nombre == month_norm)
        ).scalar_one_or_none()
        if periodo is None:
            return None
        total = session.execute(
            select(func.count(Boleta.id)).where(Boleta.periodo_id == periodo.id)
        ).scalar_one()
        return int(total)
