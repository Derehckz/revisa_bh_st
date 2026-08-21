"""Capa de servicios de lectura para API."""
from __future__ import annotations

import os

from fastapi import HTTPException
from sqlalchemy import String, func, or_, select, update
from sqlalchemy.orm import aliased

from db.models import Boleta, BoletaXmlData, Docente, EnvioEmail, Periodo, PipelineRun, PipelineStageRun
from db.period_sync import ensure_periods_from_disk
from settings import get_setting

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _normalized_rut_expr(column):
    cleaned = func.upper(func.regexp_replace(func.coalesce(column, ""), r"[^0-9Kk]", "", "g"))
    return func.regexp_replace(cleaned, r"^0+", "")


def get_period_or_404(session, year: int, month: str) -> Periodo:
    month_norm = month.strip().capitalize()
    periodo = session.execute(
        select(Periodo).where(Periodo.anio == year, Periodo.mes_nombre == month_norm)
    ).scalar_one_or_none()
    if periodo is None:
        raise HTTPException(status_code=404, detail=f"Periodo {year}-{month_norm} no encontrado")
    return periodo


def list_periods(session) -> list[dict]:
    raiz = os.path.abspath(get_setting("BH_RAIZ", _REPO_ROOT))
    ensure_periods_from_disk(raiz)
    rows = session.execute(select(Periodo).order_by(Periodo.anio.desc(), Periodo.mes_num.desc())).scalars().all()
    return [{"id": p.id, "year": p.anio, "month_num": p.mes_num, "month_name": p.mes_nombre, "status": p.estado, "closed_at": p.closed_at.isoformat() if getattr(p, "closed_at", None) else None, "closed_by": getattr(p, "closed_by", None), "informe_frozen_at": p.informe_frozen_at.isoformat() if getattr(p, "informe_frozen_at", None) else None} for p in rows]


def get_period_summary(session, year: int, month: str) -> dict:
    periodo = get_period_or_404(session, year, month)
    total_boletas = session.execute(select(func.count(Boleta.id)).where(Boleta.periodo_id == periodo.id)).scalar_one()
    total_xml = session.execute(
        select(func.count(BoletaXmlData.id)).join(Boleta, BoletaXmlData.boleta_id == Boleta.id).where(Boleta.periodo_id == periodo.id)
    ).scalar_one()
    total_emails = session.execute(select(func.count(EnvioEmail.id)).where(EnvioEmail.periodo_id == periodo.id)).scalar_one()
    recibidos = session.execute(
        select(func.count(Boleta.id)).where(Boleta.periodo_id == periodo.id, Boleta.estado_recepcion.in_(["RECIBIDO", "RECIBIDO CON ERROR"]))
    ).scalar_one()
    no_recibidos = session.execute(
        select(func.count(Boleta.id)).where(Boleta.periodo_id == periodo.id, func.coalesce(Boleta.estado_recepcion, "") == "NO RECIBIDO")
    ).scalar_one()
    con_error = session.execute(
        select(func.count(Boleta.id)).where(Boleta.periodo_id == periodo.id, func.coalesce(Boleta.estado_recepcion, "") == "RECIBIDO CON ERROR")
    ).scalar_one()
    emails_enviados = session.execute(
        select(func.count(EnvioEmail.id)).where(EnvioEmail.periodo_id == periodo.id, EnvioEmail.estado == "ENVIADO")
    ).scalar_one()
    emails_error = session.execute(
        select(func.count(EnvioEmail.id)).where(EnvioEmail.periodo_id == periodo.id, EnvioEmail.estado == "ERROR")
    ).scalar_one()
    data_freshness: dict | None
    try:
        import sync_status as sync_status_module

        sync = sync_status_module.period_sync_status(year, month)
        data_freshness = {
            "status": sync.get("status", "unknown"),
            "message": sync.get("message", ""),
            "details": sync.get("details") or None,
        }
    except Exception as exc:
        data_freshness = {
            "status": "unknown",
            "message": f"No se pudo evaluar frescura de datos: {exc}",
            "details": None,
        }
    return {
        "period": {"id": periodo.id, "year": periodo.anio, "month_num": periodo.mes_num, "month_name": periodo.mes_nombre, "status": periodo.estado},
        "metrics": {
            "total_boletas": total_boletas,
            "total_xml": total_xml,
            "xml_coverage_pct": round((total_xml / total_boletas * 100), 2) if total_boletas else 0.0,
            "total_emails": total_emails,
            "email_coverage_pct": round((total_emails / total_boletas * 100), 2) if total_boletas else 0.0,
            "recibidos": recibidos,
            "no_recibidos": no_recibidos,
            "recibidos_con_error": con_error,
            "emails_enviados": emails_enviados,
            "emails_error": emails_error,
        },
        "data_freshness": data_freshness,
    }


def list_period_boletas(session, year: int, month: str, estado: str | None, limit: int, offset: int) -> dict:
    periodo = get_period_or_404(session, year, month)
    safe_limit = max(1, min(limit, 500))
    safe_offset = max(0, offset)
    docente_by_id = aliased(Docente)
    docente_by_rut = aliased(Docente)

    query = (
        select(
            Boleta,
            func.coalesce(docente_by_id.nombre_completo, docente_by_rut.nombre_completo).label("docente_nombre"),
            func.coalesce(docente_by_id.sede, docente_by_rut.sede).label("docente_sede"),
        )
        .outerjoin(docente_by_id, Boleta.docente_id == docente_by_id.id)
        .outerjoin(docente_by_rut, _normalized_rut_expr(Boleta.emplid) == _normalized_rut_expr(docente_by_rut.rut))
        .where(Boleta.periodo_id == periodo.id)
    )
    total_query = select(func.count(Boleta.id)).where(Boleta.periodo_id == periodo.id)
    estado_norm = estado.strip().upper() if estado else None
    if estado_norm:
        query = query.where(func.coalesce(Boleta.estado_recepcion, "") == estado_norm)
        total_query = total_query.where(func.coalesce(Boleta.estado_recepcion, "") == estado_norm)

    total = session.execute(total_query).scalar_one()
    rows = session.execute(query.order_by(Boleta.id.asc()).limit(safe_limit).offset(safe_offset)).all()
    data = [{
        "id": b.id,
        "boleta_key": b.boleta_key,
        "emplid": b.emplid,
        "docente_nombre": docente_nombre,
        "sede": docente_sede,
        "year": year,
        "month_name": periodo.mes_nombre,
        "estado_recepcion": b.estado_recepcion,
        "observaciones_recepcion": b.observaciones_recepcion,
        "glosa": b.glosa,
        "monto_bruto": float(b.monto_bruto) if b.monto_bruto is not None else None,
        "archivo_xml": b.descripcion,
    } for b, docente_nombre, docente_sede in rows]
    return {
        "period": {"year": year, "month": periodo.mes_nombre, "period_id": periodo.id},
        "pagination": {"total": total, "limit": safe_limit, "offset": safe_offset, "returned": len(data)},
        "filters": {"estado": estado_norm},
        "data": data,
    }


def search_period_boletas(
    session,
    year: int,
    month: str,
    query_text: str,
    limit: int,
    offset: int,
) -> dict:
    periodo = get_period_or_404(session, year, month)
    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)
    q = query_text.strip()
    if len(q) < 2:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "Parametro q debe tener al menos 2 caracteres",
                "details": {"field": "q", "min_length": 2},
            },
        )

    pattern = f"%{q}%"
    docente_by_id = aliased(Docente)
    docente_by_rut = aliased(Docente)
    xml_alias = aliased(BoletaXmlData)
    criteria = or_(
        Boleta.emplid.ilike(pattern),
        Boleta.boleta_key.ilike(pattern),
        func.coalesce(Boleta.glosa, "").ilike(pattern),
        func.coalesce(Boleta.observaciones_recepcion, "").ilike(pattern),
        func.coalesce(docente_by_id.nombre_completo, docente_by_rut.nombre_completo, "").ilike(pattern),
        func.coalesce(xml_alias.numero_boleta, "").ilike(pattern),
    )
    total = session.execute(
        select(func.count(func.distinct(Boleta.id)))
        .outerjoin(docente_by_id, Boleta.docente_id == docente_by_id.id)
        .outerjoin(docente_by_rut, _normalized_rut_expr(Boleta.emplid) == _normalized_rut_expr(docente_by_rut.rut))
        .outerjoin(xml_alias, xml_alias.boleta_id == Boleta.id)
        .where(Boleta.periodo_id == periodo.id, criteria)
    ).scalar_one()
    rows = (
        session.execute(
            select(
                Boleta,
                func.coalesce(docente_by_id.nombre_completo, docente_by_rut.nombre_completo).label("docente_nombre"),
                func.coalesce(docente_by_id.sede, docente_by_rut.sede).label("docente_sede"),
            )
            .outerjoin(docente_by_id, Boleta.docente_id == docente_by_id.id)
            .outerjoin(docente_by_rut, _normalized_rut_expr(Boleta.emplid) == _normalized_rut_expr(docente_by_rut.rut))
            .outerjoin(xml_alias, xml_alias.boleta_id == Boleta.id)
            .where(Boleta.periodo_id == periodo.id, criteria)
            .group_by(Boleta.id, docente_by_id.nombre_completo, docente_by_rut.nombre_completo, docente_by_id.sede, docente_by_rut.sede)
            .order_by(Boleta.id.asc())
            .limit(safe_limit)
            .offset(safe_offset)
        )
        .all()
    )
    data = [
        {
            "id": b.id,
            "boleta_key": b.boleta_key,
            "emplid": b.emplid,
            "docente_nombre": docente_nombre,
            "sede": docente_sede,
            "year": year,
            "month_name": periodo.mes_nombre,
            "estado_recepcion": b.estado_recepcion,
            "observaciones_recepcion": b.observaciones_recepcion,
            "glosa": b.glosa,
            "monto_bruto": float(b.monto_bruto) if b.monto_bruto is not None else None,
            "archivo_xml": b.descripcion,
        }
        for b, docente_nombre, docente_sede in rows
    ]
    return {
        "period": {"year": year, "month": periodo.mes_nombre, "period_id": periodo.id},
        "pagination": {"total": total, "limit": safe_limit, "offset": safe_offset, "returned": len(data)},
        "filters": {"q": q},
        "data": data,
    }


def get_boleta_detail(session, year: int, month: str, boleta_id: int) -> dict:
    periodo = get_period_or_404(session, year, month)
    docente_by_id = aliased(Docente)
    docente_by_rut = aliased(Docente)
    boleta_row = session.execute(
        select(
            Boleta,
            func.coalesce(docente_by_id.nombre_completo, docente_by_rut.nombre_completo).label("docente_nombre"),
            func.coalesce(docente_by_id.sede, docente_by_rut.sede).label("docente_sede"),
        )
        .outerjoin(docente_by_id, Boleta.docente_id == docente_by_id.id)
        .outerjoin(docente_by_rut, _normalized_rut_expr(Boleta.emplid) == _normalized_rut_expr(docente_by_rut.rut))
        .where(Boleta.id == boleta_id, Boleta.periodo_id == periodo.id)
    ).one_or_none()
    boleta = boleta_row[0] if boleta_row else None
    docente_nombre = boleta_row[1] if boleta_row else None
    docente_sede = boleta_row[2] if boleta_row else None
    if boleta is None:
        raise HTTPException(status_code=404, detail=f"Boleta {boleta_id} no encontrada en el período")
    xml = session.execute(select(BoletaXmlData).where(BoletaXmlData.boleta_id == boleta.id)).scalar_one_or_none()
    emails = session.execute(select(EnvioEmail).where(EnvioEmail.periodo_id == periodo.id).order_by(EnvioEmail.id.desc())).scalars().all()
    return {
        "boleta": {
            "id": boleta.id,
            "boleta_key": boleta.boleta_key,
            "emplid": boleta.emplid,
            "docente_nombre": docente_nombre,
            "sede": docente_sede,
            "year": periodo.anio,
            "month_name": periodo.mes_nombre,
            "estado_recepcion": boleta.estado_recepcion,
            "observaciones_recepcion": boleta.observaciones_recepcion,
            "glosa": boleta.glosa,
            "monto_bruto": float(boleta.monto_bruto) if boleta.monto_bruto is not None else None,
            "archivo_xml": boleta.descripcion,
        },
        "xml_data": None if xml is None else {
            "rut_emisor": xml.rut_emisor,
            "rut_receptor": xml.rut_receptor,
            "numero_boleta": xml.numero_boleta,
            "fecha_boleta": xml.fecha_boleta,
            "total_honorarios": float(xml.total_honorarios) if xml.total_honorarios is not None else None,
            "liquido_honorarios": float(xml.liquido_honorarios) if xml.liquido_honorarios is not None else None,
            "impuesto_honorarios": float(xml.impuesto_honorarios) if xml.impuesto_honorarios is not None else None,
            "porcentaje_impuesto": float(xml.porcentaje_impuesto) if xml.porcentaje_impuesto is not None else None,
            "descripcion_linea": xml.descripcion_linea,
            "observaciones_xml": xml.observaciones_xml,
        },
        "emails_period_sample": [{
            "id": e.id, "tipo_envio": e.tipo_envio, "to_email": e.to_email, "cc_email": e.cc_email,
            "subject": e.subject, "estado": e.estado, "error_detalle": e.error_detalle,
            "sent_at": e.sent_at.isoformat() if e.sent_at else None,
        } for e in emails[:50]],
    }


def get_boleta_file_path(session, year: int, month: str, boleta_id: int, file_type: str) -> tuple[str, str]:
    periodo = get_period_or_404(session, year, month)
    boleta = session.execute(select(Boleta).where(Boleta.id == boleta_id, Boleta.periodo_id == periodo.id)).scalar_one_or_none()
    if boleta is None:
        raise HTTPException(status_code=404, detail=f"Boleta {boleta_id} no encontrada en el período")

    xml_name = (boleta.descripcion or "").strip()
    if file_type == "xml":
        file_name = xml_name
    elif file_type == "pdf":
        file_name = xml_name.replace(".xml", ".pdf").replace(".XML", ".pdf") if xml_name.lower().endswith(".xml") else ""
    else:
        raise HTTPException(status_code=422, detail="Tipo de archivo inválido")

    if not file_name:
        raise HTTPException(status_code=404, detail=f"No hay archivo {file_type.upper()} para esta boleta")

    base_name = os.path.basename(file_name)
    base_dir = get_setting("BH_RAIZ", os.getcwd())
    full_path = os.path.join(base_dir, str(year), periodo.mes_nombre, base_name)
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail=f"Archivo {base_name} no existe en disco")
    return full_path, base_name


def list_period_emails(session, year: int, month: str, estado: str | None, tipo: str | None, limit: int, offset: int) -> dict:
    periodo = get_period_or_404(session, year, month)
    safe_limit = max(1, min(limit, 500))
    safe_offset = max(0, offset)
    estado_norm = estado.strip().upper() if estado else None
    tipo_norm = tipo.strip().upper() if tipo else None
    query = select(EnvioEmail).where(EnvioEmail.periodo_id == periodo.id)
    total_query = select(func.count(EnvioEmail.id)).where(EnvioEmail.periodo_id == periodo.id)
    if estado_norm:
        query = query.where(EnvioEmail.estado == estado_norm)
        total_query = total_query.where(EnvioEmail.estado == estado_norm)
    if tipo_norm:
        query = query.where(EnvioEmail.tipo_envio == tipo_norm)
        total_query = total_query.where(EnvioEmail.tipo_envio == tipo_norm)
    total = session.execute(total_query).scalar_one()
    rows = session.execute(query.order_by(EnvioEmail.id.desc()).limit(safe_limit).offset(safe_offset)).scalars().all()
    return {
        "period": {"year": year, "month": periodo.mes_nombre, "period_id": periodo.id},
        "pagination": {"total": total, "limit": safe_limit, "offset": safe_offset, "returned": len(rows)},
        "filters": {"estado": estado_norm, "tipo": tipo_norm},
        "data": [{
            "id": e.id, "tipo_envio": e.tipo_envio, "to_email": e.to_email, "cc_email": e.cc_email,
            "subject": e.subject, "estado": e.estado, "error_detalle": e.error_detalle,
            "periodo_label": e.periodo_label, "sent_at": e.sent_at.isoformat() if e.sent_at else None,
        } for e in rows],
    }


def get_period_insights(session, year: int, month: str) -> dict:
    periodo = get_period_or_404(session, year, month)
    docente_by_id = aliased(Docente)
    docente_by_rut = aliased(Docente)
    monto_total = session.execute(
        select(func.coalesce(func.sum(Boleta.monto_bruto), 0)).where(Boleta.periodo_id == periodo.id)
    ).scalar_one()
    monto_promedio = session.execute(
        select(func.coalesce(func.avg(Boleta.monto_bruto), 0)).where(Boleta.periodo_id == periodo.id)
    ).scalar_one()
    docentes_unicos = session.execute(
        select(
            func.count(
                func.distinct(
                    func.coalesce(
                        func.cast(docente_by_id.id, String),
                        func.cast(docente_by_rut.id, String),
                        _normalized_rut_expr(Boleta.emplid),
                    )
                )
            )
        )
        .select_from(Boleta)
        .outerjoin(docente_by_id, Boleta.docente_id == docente_by_id.id)
        .outerjoin(docente_by_rut, _normalized_rut_expr(Boleta.emplid) == _normalized_rut_expr(docente_by_rut.rut))
        .where(Boleta.periodo_id == periodo.id)
    ).scalar_one()
    boletas_con_xml = session.execute(
        select(func.count(Boleta.id)).where(
            Boleta.periodo_id == periodo.id,
            Boleta.descripcion.is_not(None),
            func.length(func.btrim(Boleta.descripcion)) > 0,
        )
    ).scalar_one()
    total_boletas = session.execute(select(func.count(Boleta.id)).where(Boleta.periodo_id == periodo.id)).scalar_one()

    sede_expr = func.coalesce(docente_by_id.sede, docente_by_rut.sede, "SIN SEDE")
    by_sede_rows = session.execute(
        select(
            sede_expr,
            func.count(Boleta.id),
            func.coalesce(func.sum(Boleta.monto_bruto), 0),
        )
        .select_from(Boleta)
        .outerjoin(docente_by_id, Boleta.docente_id == docente_by_id.id)
        .outerjoin(docente_by_rut, _normalized_rut_expr(Boleta.emplid) == _normalized_rut_expr(docente_by_rut.rut))
        .where(Boleta.periodo_id == periodo.id)
        .group_by(sede_expr)
        .order_by(func.count(Boleta.id).desc())
    ).all()

    docente_expr = func.coalesce(docente_by_id.nombre_completo, docente_by_rut.nombre_completo, Boleta.emplid, "SIN DOCENTE")
    top_docentes_rows = session.execute(
        select(
            docente_expr,
            func.count(Boleta.id),
            func.coalesce(func.sum(Boleta.monto_bruto), 0),
        )
        .select_from(Boleta)
        .outerjoin(docente_by_id, Boleta.docente_id == docente_by_id.id)
        .outerjoin(docente_by_rut, _normalized_rut_expr(Boleta.emplid) == _normalized_rut_expr(docente_by_rut.rut))
        .where(Boleta.periodo_id == periodo.id)
        .group_by(docente_expr)
        .order_by(func.count(Boleta.id).desc())
        .limit(10)
    ).all()

    return {
        "period": {"year": year, "month": periodo.mes_nombre, "period_id": periodo.id},
        "kpis": {
            "monto_total": float(monto_total or 0),
            "monto_promedio": float(monto_promedio or 0),
            "docentes_unicos": int(docentes_unicos or 0),
            "boletas_con_xml": int(boletas_con_xml or 0),
            "boletas_sin_xml": int(total_boletas - boletas_con_xml),
        },
        "by_sede": [{"sede": s, "boletas": int(c), "monto_total": float(m or 0)} for s, c, m in by_sede_rows],
        "top_docentes": [{"docente": d, "boletas": int(c), "monto_total": float(m or 0)} for d, c, m in top_docentes_rows],
    }


def list_period_xml(session, year: int, month: str, limit: int, offset: int) -> dict:
    periodo = get_period_or_404(session, year, month)
    safe_limit = max(1, min(limit, 500))
    safe_offset = max(0, offset)
    total = session.execute(
        select(func.count(BoletaXmlData.id)).join(Boleta, BoletaXmlData.boleta_id == Boleta.id).where(Boleta.periodo_id == periodo.id)
    ).scalar_one()
    rows = session.execute(
        select(BoletaXmlData, Boleta).join(Boleta, BoletaXmlData.boleta_id == Boleta.id).where(Boleta.periodo_id == periodo.id)
        .order_by(BoletaXmlData.id.desc()).limit(safe_limit).offset(safe_offset)
    ).all()
    return {
        "period": {"year": year, "month": periodo.mes_nombre, "period_id": periodo.id},
        "pagination": {"total": total, "limit": safe_limit, "offset": safe_offset, "returned": len(rows)},
        "data": [{
            "xml_id": x.id, "boleta_id": b.id, "emplid": b.emplid, "numero_boleta": x.numero_boleta,
            "rut_emisor": x.rut_emisor, "rut_receptor": x.rut_receptor,
            "total_honorarios": float(x.total_honorarios) if x.total_honorarios is not None else None,
            "observaciones_xml": x.observaciones_xml,
        } for x, b in rows],
    }


def list_runs(session, limit: int, offset: int) -> dict:
    safe_limit = max(1, min(limit, 500))
    safe_offset = max(0, offset)
    total = session.execute(select(func.count(PipelineRun.id))).scalar_one()
    rows = session.execute(select(PipelineRun).order_by(PipelineRun.id.desc()).limit(safe_limit).offset(safe_offset)).scalars().all()
    return {
        "pagination": {"total": total, "limit": safe_limit, "offset": safe_offset, "returned": len(rows)},
        "data": [{
            "id": r.id, "run_id": r.run_id, "period_label": r.period_label, "triggered_by": r.triggered_by,
            "mode": r.mode, "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        } for r in rows],
    }


def get_run_stages(session, run_id: str) -> dict:
    run = session.execute(select(PipelineRun).where(PipelineRun.run_id == run_id)).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} no encontrado")
    stages = session.execute(
        select(PipelineStageRun).where(PipelineStageRun.pipeline_run_id == run.id).order_by(PipelineStageRun.stage_num.asc())
    ).scalars().all()
    return {
        "run": {"id": run.id, "run_id": run.run_id, "status": run.status, "period_label": run.period_label},
        "stages": [{
            "id": s.id, "stage_num": s.stage_num, "stage_name": s.stage_name, "correlation_id": s.correlation_id,
            "status": s.status, "rows_read": s.rows_read, "rows_ok": s.rows_ok, "rows_error": s.rows_error,
            "message": s.message,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "finished_at": s.finished_at.isoformat() if s.finished_at else None,
        } for s in stages],
    }


def get_year_stats(session, year: int) -> dict:
    periodos = session.execute(select(Periodo).where(Periodo.anio == year).order_by(Periodo.mes_num.asc())).scalars().all()
    if not periodos:
        raise HTTPException(status_code=404, detail=f"No hay periodos para el año {year}")
    items = []
    total_boletas = total_xml = total_emails = 0
    total_monto = 0.0
    for p in periodos:
        boletas = session.execute(select(func.count(Boleta.id)).where(Boleta.periodo_id == p.id)).scalar_one()
        xml = session.execute(
            select(func.count(BoletaXmlData.id)).join(Boleta, BoletaXmlData.boleta_id == Boleta.id).where(Boleta.periodo_id == p.id)
        ).scalar_one()
        emails = session.execute(select(func.count(EnvioEmail.id)).where(EnvioEmail.periodo_id == p.id)).scalar_one()
        monto = session.execute(
            select(func.coalesce(func.sum(Boleta.monto_bruto), 0)).where(Boleta.periodo_id == p.id)
        ).scalar_one()
        monto_f = float(monto or 0)
        total_boletas += boletas
        total_xml += xml
        total_emails += emails
        total_monto += monto_f
        items.append({
            "period_id": p.id, "month_num": p.mes_num, "month_name": p.mes_nombre,
            "boletas": boletas, "xml": xml, "emails": emails,
            "monto_total": monto_f,
            "xml_coverage_pct": round((xml / boletas * 100), 2) if boletas else 0.0,
            "email_coverage_pct": round((emails / boletas * 100), 2) if boletas else 0.0,
        })
    return {
        "year": year,
        "totals": {
            "boletas": total_boletas,
            "xml": total_xml,
            "emails": total_emails,
            "monto_total": total_monto,
            "xml_coverage_pct": round((total_xml / total_boletas * 100), 2) if total_boletas else 0.0,
            "email_coverage_pct": round((total_emails / total_boletas * 100), 2) if total_boletas else 0.0,
        },
        "periods": items,
    }


def list_docentes(session, q: str | None, limit: int, offset: int) -> dict:
    safe_limit = max(1, min(limit, 500))
    safe_offset = max(0, offset)
    query = (
        select(
            Docente,
            func.count(Boleta.id).label("boletas_count"),
            func.coalesce(func.sum(Boleta.monto_bruto), 0).label("monto_total"),
        )
        .outerjoin(Boleta, or_(Boleta.docente_id == Docente.id, _normalized_rut_expr(Boleta.emplid) == _normalized_rut_expr(Docente.rut)))
        .group_by(Docente.id)
    )
    total_query = select(func.count(Docente.id))
    q_norm = q.strip() if q else None
    if q_norm:
        pattern = f"%{q_norm}%"
        filters = or_(
            Docente.nombre_completo.ilike(pattern),
            Docente.rut.ilike(pattern),
            func.coalesce(Docente.sede, "").ilike(pattern),
        )
        query = query.where(filters)
        total_query = total_query.where(filters)
    total = session.execute(total_query).scalar_one()
    rows = session.execute(query.order_by(Docente.nombre_completo.asc()).limit(safe_limit).offset(safe_offset)).all()
    return {
        "pagination": {"total": total, "limit": safe_limit, "offset": safe_offset, "returned": len(rows)},
        "filters": {"q": q_norm},
        "data": [
            {
                "id": d.id,
                "rut": d.rut,
                "nombre_completo": d.nombre_completo,
                "sede": d.sede,
                "email_personal": d.email_personal,
                "email_dp": d.email_dp,
                "activo": d.activo,
                "boletas_count": int(boletas_count or 0),
                "monto_total": float(monto_total or 0),
            }
            for d, boletas_count, monto_total in rows
        ],
    }


def get_docente_profile(session, docente_id: int, limit: int) -> dict:
    safe_limit = max(1, min(limit, 500))
    docente = session.execute(select(Docente).where(Docente.id == docente_id)).scalar_one_or_none()
    if docente is None:
        raise HTTPException(status_code=404, detail=f"Docente {docente_id} no encontrado")

    boletas_rows = session.execute(
        select(Boleta, Periodo)
        .outerjoin(Periodo, Boleta.periodo_id == Periodo.id)
        .where(or_(Boleta.docente_id == docente.id, _normalized_rut_expr(Boleta.emplid) == _normalized_rut_expr(docente.rut)))
        .order_by(Boleta.id.desc())
        .limit(safe_limit)
    ).all()
    period_stats_rows = session.execute(
        select(
            Periodo.id,
            Periodo.anio,
            Periodo.mes_num,
            Periodo.mes_nombre,
            func.count(Boleta.id),
            func.coalesce(func.sum(Boleta.monto_bruto), 0),
        )
        .select_from(Boleta)
        .join(Periodo, Boleta.periodo_id == Periodo.id)
        .where(or_(Boleta.docente_id == docente.id, _normalized_rut_expr(Boleta.emplid) == _normalized_rut_expr(docente.rut)))
        .group_by(Periodo.id, Periodo.anio, Periodo.mes_num, Periodo.mes_nombre)
        .order_by(Periodo.anio.desc(), Periodo.mes_num.desc())
    ).all()
    docente_emails = {
        (docente.email_personal or "").strip().lower(),
        (docente.email_dp or "").strip().lower(),
    }
    docente_emails.discard("")
    email_filters = [EnvioEmail.docente_id == docente.id]
    if docente_emails:
        email_filters.append(func.lower(func.coalesce(EnvioEmail.to_email, "")).in_(docente_emails))
    email_rows = session.execute(
        select(EnvioEmail)
        .where(or_(*email_filters))
        .order_by(EnvioEmail.id.desc())
        .limit(200)
    ).scalars().all()
    email_total = len(email_rows)
    email_enviados = len([e for e in email_rows if (e.estado or "").upper() == "ENVIADO"])
    email_error = len([e for e in email_rows if (e.estado or "").upper() == "ERROR"])
    tipos: dict[str, int] = {}
    for e in email_rows:
        k = (e.tipo_envio or "DESCONOCIDO").upper()
        tipos[k] = tipos.get(k, 0) + 1
    ultimo_envio = next((e.sent_at for e in email_rows if e.sent_at is not None), None)
    boletas_count = len(boletas_rows)
    monto_total = sum(float(b.monto_bruto or 0) for b, _ in boletas_rows)
    return {
        "docente": {
            "id": docente.id,
            "rut": docente.rut,
            "nombre_completo": docente.nombre_completo,
            "sede": docente.sede,
            "email_personal": docente.email_personal,
            "email_dp": docente.email_dp,
            "activo": docente.activo,
            "boletas_count": boletas_count,
            "monto_total": monto_total,
        },
        "boletas": [
            {
                "id": b.id,
                "boleta_key": b.boleta_key,
                "emplid": b.emplid,
                "docente_nombre": docente.nombre_completo,
                "sede": docente.sede,
                "year": p.anio if p else None,
                "month_name": p.mes_nombre if p else None,
                "estado_recepcion": b.estado_recepcion,
                "observaciones_recepcion": b.observaciones_recepcion,
                "glosa": b.glosa,
                "monto_bruto": float(b.monto_bruto) if b.monto_bruto is not None else None,
                "archivo_xml": b.descripcion,
            }
            for b, p in boletas_rows
        ],
        "period_stats": [
            {
                "period_id": period_id,
                "year": year,
                "month_num": month_num,
                "month_name": month_name,
                "boletas": int(count or 0),
                "monto_total": float(total or 0),
            }
            for period_id, year, month_num, month_name, count, total in period_stats_rows
        ],
        "email_summary": {
            "total": email_total,
            "enviados": email_enviados,
            "error": email_error,
            "pendientes": max(0, email_total - email_enviados - email_error),
            "ultimo_envio": ultimo_envio.isoformat() if ultimo_envio else None,
            "tipos": tipos,
        },
        "recent_emails": [
            {
                "id": e.id,
                "tipo_envio": e.tipo_envio,
                "to_email": e.to_email,
                "cc_email": e.cc_email,
                "subject": e.subject,
                "estado": e.estado,
                "error_detalle": e.error_detalle,
                "periodo_label": e.periodo_label,
                "sent_at": e.sent_at.isoformat() if e.sent_at else None,
            }
            for e in email_rows[:20]
        ],
    }


def list_docente_boletas(
    session,
    docente_id: int,
    year: int | None,
    month: str | None,
    estado: str | None,
    limit: int,
    offset: int,
) -> dict:
    safe_limit = max(1, min(limit, 500))
    safe_offset = max(0, offset)
    docente = session.execute(select(Docente).where(Docente.id == docente_id)).scalar_one_or_none()
    if docente is None:
        raise HTTPException(status_code=404, detail=f"Docente {docente_id} no encontrado")
    query = (
        select(Boleta, Periodo, BoletaXmlData)
        .join(Periodo, Boleta.periodo_id == Periodo.id, isouter=True)
        .outerjoin(BoletaXmlData, BoletaXmlData.boleta_id == Boleta.id)
        .where(or_(Boleta.docente_id == docente.id, _normalized_rut_expr(Boleta.emplid) == _normalized_rut_expr(docente.rut)))
    )
    total_query = select(func.count(Boleta.id)).where(
        or_(Boleta.docente_id == docente.id, _normalized_rut_expr(Boleta.emplid) == _normalized_rut_expr(docente.rut))
    )
    estado_norm = estado.strip().upper() if estado else None
    total_uses_period = False
    if year:
        query = query.where(Periodo.anio == year)
        if not total_uses_period:
            total_query = total_query.join(Periodo, Boleta.periodo_id == Periodo.id)
            total_uses_period = True
        total_query = total_query.where(Periodo.anio == year)
    if month:
        month_norm = month.strip().capitalize()
        query = query.where(Periodo.mes_nombre == month_norm)
        if not total_uses_period:
            total_query = total_query.join(Periodo, Boleta.periodo_id == Periodo.id)
            total_uses_period = True
        total_query = total_query.where(Periodo.mes_nombre == month_norm)
    if estado_norm:
        query = query.where(func.coalesce(Boleta.estado_recepcion, "") == estado_norm)
        total_query = total_query.where(func.coalesce(Boleta.estado_recepcion, "") == estado_norm)

    total = session.execute(total_query).scalar_one()
    rows = session.execute(query.order_by(Boleta.id.desc()).limit(safe_limit).offset(safe_offset)).all()
    return {
        "period": {
            "year": year or 0,
            "month": month or "",
            "period_id": 0,
        },
        "pagination": {"total": total, "limit": safe_limit, "offset": safe_offset, "returned": len(rows)},
        "filters": {"year": year, "month": month, "estado": estado_norm},
        "data": [
            {
                "id": b.id,
                "boleta_key": b.boleta_key,
                "emplid": b.emplid,
                "docente_nombre": docente.nombre_completo,
                "sede": docente.sede,
                "year": p.anio if p else None,
                "month_name": p.mes_nombre if p else None,
                "estado_recepcion": b.estado_recepcion,
                "observaciones_recepcion": b.observaciones_recepcion,
                "glosa": b.glosa,
                "monto_bruto": float(b.monto_bruto) if b.monto_bruto is not None else None,
                "archivo_xml": b.descripcion,
                "has_xml_file": bool(
                    (xml and (xml.numero_boleta or xml.descripcion_linea or xml.total_honorarios))
                    or (b.descripcion and str(b.descripcion).strip())
                )
                and (str(b.estado_recepcion or "").upper() in {"RECIBIDO", "RECIBIDO CON ERROR"}),
            }
            for b, p, xml in rows
        ],
    }


def get_docente_metrics(session, docente_id: int, year: int | None, month: str | None) -> dict:
    docente = session.execute(select(Docente).where(Docente.id == docente_id)).scalar_one_or_none()
    if docente is None:
        raise HTTPException(status_code=404, detail=f"Docente {docente_id} no encontrado")
    query = (
        select(Boleta)
        .join(Periodo, Boleta.periodo_id == Periodo.id, isouter=True)
        .where(or_(Boleta.docente_id == docente.id, _normalized_rut_expr(Boleta.emplid) == _normalized_rut_expr(docente.rut)))
    )
    if year:
        query = query.where(Periodo.anio == year)
    if month:
        query = query.where(Periodo.mes_nombre == month.strip().capitalize())
    rows = session.execute(query).scalars().all()
    total = len(rows)
    recibidas = len([b for b in rows if (b.estado_recepcion or "").upper() in {"RECIBIDO", "RECIBIDO CON ERROR"}])
    con_error = len([b for b in rows if (b.estado_recepcion or "").upper() == "RECIBIDO CON ERROR"])
    sin_xml = len([b for b in rows if not (b.descripcion or "").strip()])
    monto_total = sum(float(b.monto_bruto or 0) for b in rows)
    return {
        "docente": {
            "id": docente.id,
            "rut": docente.rut,
            "nombre_completo": docente.nombre_completo,
            "sede": docente.sede,
            "email_personal": docente.email_personal,
            "email_dp": docente.email_dp,
            "activo": docente.activo,
            "boletas_count": total,
            "monto_total": monto_total,
        },
        "metrics": {
            "total_boletas": total,
            "recibidas": recibidas,
            "con_error": con_error,
            "sin_xml": sin_xml,
            "monto_total": monto_total,
            "monto_promedio": round(monto_total / total, 2) if total else 0.0,
        },
    }


def list_docente_emails(
    session,
    docente_id: int,
    *,
    tipo: str | None,
    estado: str | None,
    limit: int,
    offset: int,
) -> dict:
    safe_limit = max(1, min(limit, 500))
    safe_offset = max(0, offset)
    docente = session.execute(select(Docente).where(Docente.id == docente_id)).scalar_one_or_none()
    if docente is None:
        raise HTTPException(status_code=404, detail=f"Docente {docente_id} no encontrado")

    docente_emails = {
        (docente.email_personal or "").strip().lower(),
        (docente.email_dp or "").strip().lower(),
    }
    docente_emails.discard("")
    base_filters = [EnvioEmail.docente_id == docente.id]
    if docente_emails:
        base_filters.append(func.lower(func.coalesce(EnvioEmail.to_email, "")).in_(docente_emails))

    query = select(EnvioEmail).where(or_(*base_filters))
    total_query = select(func.count(EnvioEmail.id)).where(or_(*base_filters))

    tipo_norm = tipo.strip().upper() if tipo else None
    estado_norm = estado.strip().upper() if estado else None
    if tipo_norm:
        query = query.where(func.coalesce(EnvioEmail.tipo_envio, "") == tipo_norm)
        total_query = total_query.where(func.coalesce(EnvioEmail.tipo_envio, "") == tipo_norm)
    if estado_norm:
        query = query.where(func.coalesce(EnvioEmail.estado, "") == estado_norm)
        total_query = total_query.where(func.coalesce(EnvioEmail.estado, "") == estado_norm)

    total = session.execute(total_query).scalar_one()
    rows = session.execute(query.order_by(EnvioEmail.id.desc()).limit(safe_limit).offset(safe_offset)).scalars().all()

    docente_payload = {
        "id": docente.id,
        "rut": docente.rut,
        "nombre_completo": docente.nombre_completo,
        "sede": docente.sede,
        "email_personal": docente.email_personal,
        "email_dp": docente.email_dp,
        "activo": docente.activo,
        "boletas_count": 0,
        "monto_total": 0.0,
    }
    return {
        "docente": docente_payload,
        "pagination": {"total": total, "limit": safe_limit, "offset": safe_offset, "returned": len(rows)},
        "filters": {"tipo": tipo_norm, "estado": estado_norm},
        "data": [
            {
                "id": e.id,
                "tipo_envio": e.tipo_envio,
                "to_email": e.to_email,
                "cc_email": e.cc_email,
                "subject": e.subject,
                "estado": e.estado,
                "error_detalle": e.error_detalle,
                "periodo_label": e.periodo_label,
                "sent_at": e.sent_at.isoformat() if e.sent_at else None,
            }
            for e in rows
        ],
    }


def _docente_payload_with_stats(session, docente: Docente) -> dict:
    boletas_count = session.execute(
        select(func.count(Boleta.id)).where(
            or_(Boleta.docente_id == docente.id, _normalized_rut_expr(Boleta.emplid) == _normalized_rut_expr(docente.rut))
        )
    ).scalar_one()
    monto_total = session.execute(
        select(func.coalesce(func.sum(Boleta.monto_bruto), 0)).where(
            or_(Boleta.docente_id == docente.id, _normalized_rut_expr(Boleta.emplid) == _normalized_rut_expr(docente.rut))
        )
    ).scalar_one()
    return {
        "id": docente.id,
        "rut": docente.rut,
        "nombre_completo": docente.nombre_completo,
        "sede": docente.sede,
        "email_personal": docente.email_personal,
        "email_dp": docente.email_dp,
        "activo": docente.activo,
        "boletas_count": int(boletas_count or 0),
        "monto_total": float(monto_total or 0),
    }


def create_docente(session, payload: dict) -> dict:
    rut = str(payload.get("rut") or "").strip()
    nombre = str(payload.get("nombre_completo") or "").strip()
    if not rut or not nombre:
        raise HTTPException(status_code=422, detail="rut y nombre_completo son obligatorios")
    exists = session.execute(select(Docente).where(func.lower(Docente.rut) == rut.lower())).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail=f"Ya existe docente con RUT {rut}")
    row = Docente(
        rut=rut,
        rut_sin_dv=(str(payload.get("rut_sin_dv") or "").strip() or None),
        nombre_completo=nombre,
        email_personal=(str(payload.get("email_personal") or "").strip() or None),
        email_dp=(str(payload.get("email_dp") or "").strip() or None),
        telefono=(str(payload.get("telefono") or "").strip() or None),
        direccion=(str(payload.get("direccion") or "").strip() or None),
        sede=(str(payload.get("sede") or "").strip() or None),
        activo=str(payload.get("activo") or "true"),
    )
    session.add(row)
    session.flush()
    _apply_dp_from_sede(session, row)
    session.commit()
    session.refresh(row)
    _sync_docente_excel(row)
    return {"ok": True, "docente": _docente_payload_with_stats(session, row)}


def update_docente(session, docente_id: int, payload: dict) -> dict:
    row = session.execute(select(Docente).where(Docente.id == docente_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Docente {docente_id} no encontrado")
    rut = str(payload.get("rut") or row.rut).strip()
    nombre = str(payload.get("nombre_completo") or row.nombre_completo).strip()
    if not rut or not nombre:
        raise HTTPException(status_code=422, detail="rut y nombre_completo son obligatorios")
    conflict = session.execute(
        select(Docente).where(func.lower(Docente.rut) == rut.lower(), Docente.id != docente_id)
    ).scalar_one_or_none()
    if conflict is not None:
        raise HTTPException(status_code=409, detail=f"Ya existe docente con RUT {rut}")
    row.rut = rut
    row.rut_sin_dv = (str(payload.get("rut_sin_dv") or "").strip() or None)
    row.nombre_completo = nombre
    row.email_personal = (str(payload.get("email_personal") or "").strip() or None)
    row.email_dp = (str(payload.get("email_dp") or "").strip() or None)
    row.telefono = (str(payload.get("telefono") or "").strip() or None)
    row.direccion = (str(payload.get("direccion") or "").strip() or None)
    row.sede = (str(payload.get("sede") or "").strip() or None)
    row.activo = str(payload.get("activo") or row.activo or "true")
    _apply_dp_from_sede(session, row)
    session.commit()
    session.refresh(row)
    _sync_docente_excel(row)
    return {"ok": True, "docente": _docente_payload_with_stats(session, row)}


def disable_docente(session, docente_id: int) -> dict:
    row = session.execute(select(Docente).where(Docente.id == docente_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Docente {docente_id} no encontrado")
    row.activo = "false"
    session.commit()
    session.refresh(row)
    return {"ok": True, "docente": _docente_payload_with_stats(session, row)}


def delete_docente(session, docente_id: int) -> dict:
    row = session.execute(select(Docente).where(Docente.id == docente_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Docente {docente_id} no encontrado")
    payload = _docente_payload_with_stats(session, row)
    session.execute(update(Boleta).where(Boleta.docente_id == docente_id).values(docente_id=None))
    session.execute(update(EnvioEmail).where(EnvioEmail.docente_id == docente_id).values(docente_id=None))
    session.delete(row)
    session.commit()
    return {"ok": True, "docente": payload}


def _apply_dp_from_sede(session, row: Docente) -> None:
    import director_catalog

    if not row.sede:
        return
    sede = director_catalog.canonical_sede(row.sede) or row.sede
    row.sede = sede
    auto = director_catalog.email_dp_for_sede(sede, session=session)
    if auto:
        row.email_dp = auto


def _sync_docente_excel(row: Docente) -> None:
    try:
        import director_catalog

        director_catalog.patch_bd_docentes_row(
            {
                "RUT": row.rut,
                "NOMBRE_COMPLETO": row.nombre_completo,
                "Correo_Personal": row.email_personal or "",
                "Telefono_Personal": row.telefono or "",
                "Direccion": row.direccion or "",
                "SEDE": row.sede or "",
                "Email_DP": row.email_dp or "",
            }
        )
    except Exception:
        pass


def list_directores(session) -> dict:
    import director_catalog

    return {"data": director_catalog.list_directores(session)}


def upsert_director(session, payload: dict, *, director_id: int | None = None) -> dict:
    import director_catalog

    try:
        director = director_catalog.upsert_director(
            session,
            director_id=director_id,
            nombre=payload.get("nombre"),
            email=str(payload.get("email") or ""),
            sedes=list(payload.get("sedes") or []),
            activo=str(payload.get("activo") or "true"),
            propagate=True,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return {"ok": True, "director": director}


def delete_director(session, director_id: int) -> dict:
    import director_catalog

    try:
        director_catalog.delete_director(session, director_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return {"ok": True}


def seed_directores(session) -> dict:
    import director_catalog

    stats = director_catalog.seed_from_excel(session)
    session.commit()
    return {
        "ok": True,
        "created": int(stats.get("directores") or 0),
        "sedes": int(stats.get("sedes") or 0),
        "mapping": int(stats.get("mapping") or 0),
    }
