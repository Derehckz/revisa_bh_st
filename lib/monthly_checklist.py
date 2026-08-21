"""Checklist mensual previo al cierre de período."""
from __future__ import annotations

import os
from typing import Any

from sqlalchemy import func, select

import final_report
import stage_operations
from db.models import Boleta, Periodo
from db.session import SessionLocal
from period_policy import is_closed_status


def _item(
    item_id: str,
    label: str,
    *,
    status: str,
    message: str = "",
    blocking: bool = False,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "label": label,
        "status": status,  # ok | warn | block
        "blocking": blocking and status == "block",
        "message": message,
    }


def monthly_checklist(year: int | str, month: str) -> dict[str, Any]:
    year_int = int(year)
    month_norm = str(month).strip().capitalize()
    items: list[dict[str, Any]] = []
    n_incomp = 0

    with SessionLocal() as session:
        periodo = session.execute(
            select(Periodo).where(Periodo.anio == year_int, Periodo.mes_nombre == month_norm)
        ).scalar_one_or_none()

        if periodo is None:
            items.append(
                _item(
                    "period_db",
                    "Mes creado en BD",
                    status="block",
                    message="No existe el período en PostgreSQL.",
                    blocking=True,
                )
            )
            return {
                "year": year_int,
                "month": month_norm,
                "closed": False,
                "can_close": False,
                "blocking_count": 1,
                "warn_count": 0,
                "items": items,
            }

        closed = is_closed_status(periodo.estado)
        closed_at = periodo.closed_at.isoformat() if getattr(periodo, "closed_at", None) else None
        closed_by = getattr(periodo, "closed_by", None)
        informe_frozen_at = (
            periodo.informe_frozen_at.isoformat() if getattr(periodo, "informe_frozen_at", None) else None
        )
        contab_status = str(getattr(periodo, "contabilidad_status", None) or "").strip().lower()
        contab_by = getattr(periodo, "contabilidad_validated_by", None)
        contab_at = getattr(periodo, "contabilidad_validated_at", None)
        contab_notes = getattr(periodo, "contabilidad_notes", None)
        items.append(
            _item(
                "period_db",
                "Mes creado en BD",
                status="ok",
                message=f"Estado: {periodo.estado}",
            )
        )

        total = session.execute(
            select(func.count(Boleta.id)).where(Boleta.periodo_id == periodo.id)
        ).scalar_one()
        with_row = session.execute(
            select(func.count(Boleta.id)).where(
                Boleta.periodo_id == periodo.id,
                Boleta.solicitud_row.isnot(None),
            )
        ).scalar_one()
        try:
            import maestro_contacto

            n_incomp = maestro_contacto.count_fichas_incompletas_periodo(session, periodo.id)
        except Exception:
            n_incomp = 0

    kpis = stage_operations.period_summary(year_int, month_norm)
    total_rows = int(kpis.get("total_rows") or total or 0)

    if total_rows <= 0:
        items.append(
            _item(
                "solicitud_sync",
                "Solicitud sincronizada",
                status="block",
                message="No hay boletas/solicitudes en BD. Ejecuta el paso 0.",
                blocking=True,
            )
        )
    elif int(with_row or 0) < total_rows:
        items.append(
            _item(
                "solicitud_sync",
                "Solicitud sincronizada",
                status="warn",
                message=f"{with_row}/{total_rows} filas con snapshot completo (solicitud_row).",
            )
        )
    else:
        items.append(
            _item(
                "solicitud_sync",
                "Solicitud sincronizada",
                status="ok",
                message=f"{total_rows} solicitudes con detalle completo.",
            )
        )

    if total_rows > 0:
        if n_incomp:
            items.append(
                _item(
                    "fichas",
                    "Fichas de contacto",
                    status="warn",
                    message=f"{n_incomp} fila(s) sin correo o sede. Completa Docentes; al guardar se actualiza la Solicitud.",
                )
            )
        else:
            items.append(
                _item("fichas", "Fichas de contacto", status="ok", message="Correo y sede en las filas del mes.")
            )

    overview = stage_operations.period_overview(year_int, month_norm, jobs=[])
    stages = {int(s.get("stage_num", -1)): s for s in overview.get("stages") or []}
    stage0 = stages.get(0)
    if stage0 and stage0.get("ui_status") == "OK":
        items.append(_item("step0", "Paso 0 OK", status="ok", message="Solicitud generada."))
    elif total_rows > 0:
        items.append(
            _item("step0", "Paso 0 OK", status="warn", message="Hay datos en BD pero el paso 0 no figura OK.")
        )
    else:
        items.append(
            _item(
                "step0",
                "Paso 0 OK",
                status="block",
                message="Falta generar la solicitud del mes.",
                blocking=True,
            )
        )

    recibidos = int(kpis.get("recibidos") or 0)
    no_recibidos = int(kpis.get("no_recibidos") or 0)
    xml_files = int(kpis.get("xml_files_in_month") or 0)
    items.append(
        _item(
            "recepcion",
            "Recepción",
            status="ok" if recibidos > 0 or total_rows == 0 else "warn",
            message=f"Recibidos {recibidos} · Pendientes {no_recibidos}",
        )
    )
    items.append(
        _item(
            "xml",
            "XML en período",
            status="ok" if xml_files > 0 or recibidos == 0 else "warn",
            message=f"{xml_files} archivo(s) XML/evidencia.",
        )
    )

    if no_recibidos > 0:
        items.append(
            _item(
                "pendientes",
                "Pendientes NO RECIBIDO",
                status="warn",
                message=f"Hay {no_recibidos} pendiente(s). Se pueden cerrar dejando constancia.",
            )
        )
    else:
        items.append(
            _item("pendientes", "Pendientes NO RECIBIDO", status="ok", message="Sin pendientes.")
        )

    report = final_report.period_final_report(year_int, month_norm)
    if report.get("exists") and int(report.get("total_rows") or 0) > 0:
        items.append(
            _item(
                "informe",
                "Informe final generado",
                status="ok",
                message=f"{report['total_rows']} boleta(s) · generado {report.get('generated_at') or '—'}",
            )
        )
    else:
        items.append(
            _item(
                "informe",
                "Informe final generado",
                status="block",
                message=report.get("read_error") or "Ejecuta el paso 6 antes de cerrar.",
                blocking=True,
            )
        )

    informe_ok = bool(report.get("exists") and int(report.get("total_rows") or 0) > 0)
    if informe_ok:
        try:
            import pagos_informe_cruzado

            cruz = pagos_informe_cruzado.cruzar_periodo(year=year_int, month=month_norm)
            errn = int(cruz.get("errors_count") or 0)
            msg = str(cruz.get("message") or "")
            if cruz.get("ok") and errn == 0:
                items.append(
                    _item("pagos_cruzado", "Pagos vs informe", status="ok", message=msg or "Cuadra con Contabilidad.")
                )
            elif int(cruz.get("pagos_rows") or 0) == 0:
                items.append(
                    _item(
                        "pagos_cruzado",
                        "Pagos vs informe",
                        status="warn",
                        message="Aún no hay hoja Pagos (cárgala en el paso 7). No cierra el mes por sí solo.",
                    )
                )
            else:
                items.append(
                    _item(
                        "pagos_cruzado",
                        "Pagos vs informe",
                        status="warn",
                        message=f"{errn} diferencia(s) informe vs Contabilidad. Revisa el informe cruzado.",
                    )
                )
        except Exception:
            pass
    if not informe_ok:
        items.append(
            _item(
                "contabilidad",
                "Validación Contabilidad",
                status="warn",
                message="Primero genera el informe (paso 6) y envíalo a Contabilidad.",
            )
        )
    elif contab_status == "ok":
        items.append(
            _item(
                "contabilidad",
                "Validación Contabilidad",
                status="ok",
                message=(
                    f"OK Contabilidad"
                    + (f" · {contab_by}" if contab_by else "")
                    + (f" · {contab_at.isoformat()}" if contab_at else "")
                ),
            )
        )
    elif contab_status == "con_observaciones":
        items.append(
            _item(
                "contabilidad",
                "Validación Contabilidad",
                status="block",
                message=(
                    "Contabilidad con observaciones: rectifica (paso 5 error → paso 3 → informe) "
                    "y vuelve a marcar OK."
                    + (f" Notas: {contab_notes}" if contab_notes else "")
                ),
                blocking=True,
            )
        )
    else:
        items.append(
            _item(
                "contabilidad",
                "Validación Contabilidad",
                status="block",
                message="Pendiente: tras enviar el informe, marca OK Contabilidad (o «con observaciones»).",
                blocking=True,
            )
        )

    try:
        import email_outbox

        outbox = email_outbox.stats_by_status()
    except Exception:
        outbox = {}
    failed = int(outbox.get("failed") or 0)
    if failed > 0:
        items.append(
            _item(
                "outbox",
                "Outbox sin fallos críticos",
                status="warn",
                message=f"{failed} correo(s) en failed.",
            )
        )
    else:
        items.append(
            _item("outbox", "Outbox sin fallos críticos", status="ok", message="Sin fallos.")
        )

    if closed:
        items.append(
            _item(
                "closed",
                "Período cerrado",
                status="ok",
                message=f"Cerrado por {closed_by or '—'} el {closed_at or '—'}",
            )
        )

    blocking_count = sum(1 for i in items if i["status"] == "block")
    warn_count = sum(1 for i in items if i["status"] == "warn")
    return {
        "year": year_int,
        "month": month_norm,
        "closed": closed,
        "closed_at": closed_at,
        "closed_by": closed_by,
        "informe_frozen_at": informe_frozen_at,
        "contabilidad_status": contab_status or None,
        "contabilidad_validated_at": contab_at.isoformat() if contab_at else None,
        "contabilidad_validated_by": contab_by,
        "contabilidad_notes": contab_notes,
        "can_close": (not closed) and blocking_count == 0,
        "blocking_count": blocking_count,
        "warn_count": warn_count,
        "items": items,
        "kpis": {
            "total_rows": total_rows,
            "recibidos": recibidos,
            "no_recibidos": no_recibidos,
            "xml_files_in_month": xml_files,
        },
        "outbox_stats": outbox,
    }
