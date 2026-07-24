"""SyncProjector: puente mínimo entre "pistas" de sincronización y el estado real.

Stub inicial (E11): no proyecta eventos incrementales todavía, pero centraliza el
punto de entrada para que la API pueda "refrescar" el estado de sincronización de
un período bajo demanda (por ejemplo tras cerrar un job o guardar el Excel).

``apply_hints`` acepta un diccionario de pistas abierto a futuro (p.ej.
``{"reason": "job_finished", "stage_num": 5}``) que hoy no cambia el cálculo,
pero deja el contrato listo para lógica incremental posterior.
"""
from __future__ import annotations

from typing import Any


def apply_hints(year: int | str, month: str, hints: dict[str, Any] | None = None) -> dict[str, Any]:
    """Refresca (recalcula) el sync_status del período, opcionalmente registrando el período en BD.

    Devuelve ``{"ok": bool, "status": "ok"|"degraded"|"unknown", "message": str}``.
    """
    hints = hints or {}
    ensured = None
    if hints.get("ensure_periods_from_disk"):
        try:
            import os

            import config
            from db.period_sync import ensure_periods_from_disk

            ensured = ensure_periods_from_disk(config.RAIZ if hasattr(config, "RAIZ") else os.getcwd())
        except Exception:
            ensured = None

    try:
        import sync_status as sync_status_module

        result = sync_status_module.period_sync_status(year, month)
    except Exception as exc:
        return {"ok": False, "status": "unknown", "message": f"No se pudo evaluar sync_status: {exc}"}

    out = {
        "ok": result.get("status") == "ok",
        "status": result.get("status", "unknown"),
        "message": result.get("message", ""),
    }
    if result.get("details"):
        out["details"] = result["details"]
    if ensured is not None:
        out["periods_created"] = ensured
    return out
