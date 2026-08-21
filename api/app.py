"""API de lectura para métricas de boletas."""
from __future__ import annotations

import os
import sys

_repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (os.path.join(_repo, "lib"), _repo):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import logging
import time
import uuid
import json
from datetime import datetime, UTC

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Path, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse

from api import operations, schemas, security, services
from api.interactive.router import router as interactive_router
from api.spa import is_api_or_docs_path, mount_frontend_spa
from db.session import SessionLocal
from settings import get_setting

app = FastAPI(
    title="Boletas Honorarios",
    version="0.2.0",
    description="API + interfaz web de Boletas Honorarios.",
)

app.include_router(interactive_router)
security.install_cors(app)
logger = logging.getLogger("boletas.api")
_ACCESS_LOGGER = logging.getLogger("boletas.api.access")


class _AccessJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "method": getattr(record, "method", None),
            "path": getattr(record, "path", None),
            "status_code": getattr(record, "status_code", None),
            "duration_ms": getattr(record, "duration_ms", None),
            "client_ip": getattr(record, "client_ip", None),
        }
        return json.dumps(payload, ensure_ascii=False)


def _configure_access_logger() -> None:
    if _ACCESS_LOGGER.handlers:
        return
    raiz = get_setting("BH_RAIZ", os.getcwd())
    log_path = get_setting("BH_API_ACCESS_LOG_PATH", os.path.join(raiz, ".logs", "api_access.jsonl"))
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(_AccessJsonFormatter())
    _ACCESS_LOGGER.setLevel(logging.INFO)
    _ACCESS_LOGGER.propagate = False
    _ACCESS_LOGGER.addHandler(handler)


_configure_access_logger()


@app.on_event("startup")
def _record_startup_time() -> None:
    app.state.started_at = datetime.now(UTC).isoformat()


def _build_error_payload(
    code: str, message: str, details: dict | list | None = None, request_id: str | None = None
) -> dict:
    payload_details = details if details is not None else {}
    if isinstance(payload_details, dict) and request_id:
        payload_details = {**payload_details, "request_id": request_id}
    return {"code": code, "message": message, "details": payload_details}


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", "").strip() or uuid.uuid4().hex
    request.state.request_id = request_id
    request.state.client_ip = request.client.host if request.client else "unknown"
    started = time.perf_counter()

    if request.url.path != "/health" and is_api_or_docs_path(request.url.path):
        rate = security.check_rate_limit(
            client_ip=request.state.client_ip,
            api_key=request.headers.get("x-api-key"),
        )
        if rate.get("limited"):
            payload = _build_error_payload(
                "RATE_LIMIT_EXCEEDED",
                "Demasiadas solicitudes. Intente nuevamente mas tarde.",
                {
                    "limit": rate.get("limit"),
                    "window_seconds": rate.get("window_seconds"),
                    "retry_after_seconds": rate.get("retry_after"),
                },
                request_id=request_id,
            )
            response = JSONResponse(status_code=429, content=payload)
            response.headers["x-request-id"] = request_id
            response.headers["retry-after"] = str(rate.get("retry_after", 1))
            return response

    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "api.unhandled_exception",
            extra={"request_id": request_id, "method": request.method, "path": request.url.path},
        )
        raise

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["x-request-id"] = request_id
    logger.info(
        "api.request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": elapsed_ms,
        },
    )
    _ACCESS_LOGGER.info(
        "api.access",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": elapsed_ms,
            "client_ip": request.state.client_ip,
        },
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None)
    detail = exc.detail
    if isinstance(detail, dict) and {"code", "message", "details"}.issubset(detail.keys()):
        if isinstance(detail.get("details"), dict) and request_id:
            detail = {**detail, "details": {**detail["details"], "request_id": request_id}}
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_payload("HTTP_ERROR", str(detail), {}, request_id=request_id),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    errs = exc.errors()
    # Mensaje corto legible (el detalle completo va en details.errors).
    parts: list[str] = []
    for err in errs[:3]:
        loc = ".".join(str(x) for x in err.get("loc", ()) if x not in ("body", "query", "path"))
        msg = str(err.get("msg") or "inválido")
        parts.append(f"{loc}: {msg}" if loc else msg)
    summary = "; ".join(parts) if parts else "Parámetros de entrada inválidos"
    return JSONResponse(
        status_code=422,
        content=_build_error_payload(
            "VALIDATION_ERROR",
            summary,
            {"errors": errs},
            request_id=request_id,
        ),
    )

@app.get("/health", response_model=schemas.HealthResponse)
def health() -> dict:
    from api.spa import frontend_dist_ready
    import app_capabilities
    from settings import get_bool_setting

    return {
        "status": "ok",
        "ui": "embedded" if frontend_dist_ready() else "api_only",
        "capabilities_version": app_capabilities.CAPABILITIES_VERSION,
        "capabilities": dict(app_capabilities.CAPABILITIES),
        "read_from_db": get_bool_setting("BH_READ_FROM_DB", True),
        "started_at": getattr(app.state, "started_at", None),
    }


@app.get("/periods", response_model=list[schemas.PeriodItem])
def list_periods(_: None = Depends(security.require_api_key)) -> list[dict]:
    with SessionLocal() as session:
        return services.list_periods(session)


@app.get("/period/{year}/{month}", response_model=schemas.PeriodSummaryResponse)
def period_summary(
    year: int = Path(..., ge=2000, le=2100),
    month: str = Path(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    _: None = Depends(security.require_api_key),
) -> dict:
    with SessionLocal() as session:
        return services.get_period_summary(session, year, month)


@app.get("/period/{year}/{month}/insights", response_model=schemas.PeriodInsightsResponse)
def period_insights(
    year: int = Path(..., ge=2000, le=2100),
    month: str = Path(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    _: None = Depends(security.require_api_key),
) -> dict:
    with SessionLocal() as session:
        return services.get_period_insights(session, year, month)


@app.get("/period/{year}/{month}/boletas", response_model=schemas.BoletaListResponse)
def period_boletas(
    year: int = Path(..., ge=2000, le=2100),
    month: str = Path(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    estado: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
    _: None = Depends(security.require_api_key),
) -> dict:
    with SessionLocal() as session:
        return services.list_period_boletas(session, year, month, estado, limit, offset)


@app.get("/period/{year}/{month}/search/boletas", response_model=schemas.BoletaSearchResponse)
def search_period_boletas(
    year: int = Path(..., ge=2000, le=2100),
    month: str = Path(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100000),
    _: None = Depends(security.require_api_key),
) -> dict:
    with SessionLocal() as session:
        return services.search_period_boletas(session, year, month, q, limit, offset)


@app.get("/period/{year}/{month}/boletas/{boleta_id}", response_model=schemas.BoletaDetailResponse)
def boleta_detail(
    year: int = Path(..., ge=2000, le=2100),
    month: str = Path(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    boleta_id: int = Path(..., ge=1),
    _: None = Depends(security.require_api_key),
) -> dict:
    with SessionLocal() as session:
        return services.get_boleta_detail(session, year, month, boleta_id)


@app.get("/period/{year}/{month}/boletas/{boleta_id}/files/{file_type}")
def boleta_file(
    year: int = Path(..., ge=2000, le=2100),
    month: str = Path(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    boleta_id: int = Path(..., ge=1),
    file_type: str = Path(..., pattern=r"^(xml|pdf)$"),
    _: None = Depends(security.require_api_key),
):
    with SessionLocal() as session:
        full_path, base_name = services.get_boleta_file_path(session, year, month, boleta_id, file_type)
    media_type = "application/xml" if file_type == "xml" else "application/pdf"
    return FileResponse(path=full_path, filename=base_name, media_type=media_type)


@app.get("/period/{year}/{month}/emails", response_model=schemas.PeriodEmailsResponse)
def period_emails(
    year: int = Path(..., ge=2000, le=2100),
    month: str = Path(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    estado: str | None = None,
    tipo: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
    _: None = Depends(security.require_api_key),
) -> dict:
    with SessionLocal() as session:
        return services.list_period_emails(session, year, month, estado, tipo, limit, offset)


@app.get("/period/{year}/{month}/xml", response_model=schemas.PeriodXmlResponse)
def period_xml(
    year: int = Path(..., ge=2000, le=2100),
    month: str = Path(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
    _: None = Depends(security.require_api_key),
) -> dict:
    with SessionLocal() as session:
        return services.list_period_xml(session, year, month, limit, offset)


@app.get("/runs", response_model=schemas.RunsResponse)
def list_runs(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
    _: None = Depends(security.require_api_key),
) -> dict:
    with SessionLocal() as session:
        return services.list_runs(session, limit, offset)


@app.get("/runs/{run_id}/stages", response_model=schemas.RunStagesResponse)
def run_stages(
    run_id: str = Path(..., min_length=8, max_length=128),
    _: None = Depends(security.require_api_key),
) -> dict:
    with SessionLocal() as session:
        return services.get_run_stages(session, run_id)


@app.get("/stats/year/{year}", response_model=schemas.YearStatsResponse)
def year_stats(
    year: int = Path(..., ge=2000, le=2100),
    _: None = Depends(security.require_api_key),
) -> dict:
    with SessionLocal() as session:
        return services.get_year_stats(session, year)


@app.get("/docentes", response_model=schemas.DocenteListResponse)
def docentes(
    q: str | None = Query(default=None, min_length=2, max_length=100),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
    _: None = Depends(security.require_api_key),
) -> dict:
    with SessionLocal() as session:
        return services.list_docentes(session, q, limit, offset)


@app.get("/docentes/{docente_id}", response_model=schemas.DocenteProfileResponse)
def docente_profile(
    docente_id: int = Path(..., ge=1),
    limit: int = Query(default=200, ge=1, le=500),
    _: None = Depends(security.require_api_key),
) -> dict:
    with SessionLocal() as session:
        return services.get_docente_profile(session, docente_id, limit)


@app.get("/docentes/{docente_id}/boletas", response_model=schemas.BoletaListResponse)
def docente_boletas(
    docente_id: int = Path(..., ge=1),
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: str | None = Query(default=None, min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    estado: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
    _: None = Depends(security.require_api_key),
) -> dict:
    with SessionLocal() as session:
        return services.list_docente_boletas(session, docente_id, year, month, estado, limit, offset)


@app.get("/docentes/{docente_id}/metrics", response_model=schemas.DocenteMetricsResponse)
def docente_metrics(
    docente_id: int = Path(..., ge=1),
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: str | None = Query(default=None, min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    _: None = Depends(security.require_api_key),
) -> dict:
    with SessionLocal() as session:
        return services.get_docente_metrics(session, docente_id, year, month)


@app.get("/docentes/{docente_id}/emails", response_model=schemas.DocenteEmailsResponse)
def docente_emails(
    docente_id: int = Path(..., ge=1),
    tipo: str | None = Query(default=None, min_length=3, max_length=32),
    estado: str | None = Query(default=None, min_length=3, max_length=16),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100000),
    _: None = Depends(security.require_api_key),
) -> dict:
    with SessionLocal() as session:
        return services.list_docente_emails(
            session,
            docente_id,
            tipo=tipo,
            estado=estado,
            limit=limit,
            offset=offset,
        )


@app.post("/docentes", response_model=schemas.DocenteActionResponse)
def docente_create(
    body: schemas.DocenteUpsertRequest = Body(...),
    _: None = Depends(security.require_api_key),
    operator: str | None = Depends(security.get_operator_name),
) -> dict:
    with SessionLocal() as session:
        result = services.create_docente(session, body.model_dump())
    try:
        from db import audit

        audit.record_event(
            action="docente.create",
            operator=operator,
            entity="docente",
            entity_id=str((result.get("docente") or {}).get("id") or ""),
            detail={"rut": getattr(body, "rut", None)},
        )
    except Exception:
        pass
    return result


@app.put("/docentes/{docente_id}", response_model=schemas.DocenteActionResponse)
def docente_update(
    docente_id: int = Path(..., ge=1),
    body: schemas.DocenteUpsertRequest = Body(...),
    _: None = Depends(security.require_api_key),
    operator: str | None = Depends(security.get_operator_name),
) -> dict:
    with SessionLocal() as session:
        result = services.update_docente(session, docente_id, body.model_dump())
    try:
        from db import audit

        audit.record_event(
            action="docente.update",
            operator=operator,
            entity="docente",
            entity_id=str(docente_id),
        )
    except Exception:
        pass
    return result


@app.post("/docentes/{docente_id}/disable", response_model=schemas.DocenteActionResponse)
def docente_disable(
    docente_id: int = Path(..., ge=1),
    _: None = Depends(security.require_api_key),
    operator: str | None = Depends(security.get_operator_name),
) -> dict:
    with SessionLocal() as session:
        result = services.disable_docente(session, docente_id)
    try:
        from db import audit

        audit.record_event(
            action="docente.disable",
            operator=operator,
            entity="docente",
            entity_id=str(docente_id),
        )
    except Exception:
        pass
    return result


@app.delete("/docentes/{docente_id}", response_model=schemas.DocenteActionResponse)
def docente_delete(
    docente_id: int = Path(..., ge=1),
    _: None = Depends(security.require_api_key),
    operator: str | None = Depends(security.get_operator_name),
) -> dict:
    with SessionLocal() as session:
        result = services.delete_docente(session, docente_id)
    try:
        from db import audit

        audit.record_event(
            action="docente.delete",
            operator=operator,
            entity="docente",
            entity_id=str(docente_id),
        )
    except Exception:
        pass
    return result


@app.get("/directores", response_model=schemas.DirectorListResponse)
def directores_list(
    _: None = Depends(security.require_api_key),
) -> dict:
    with SessionLocal() as session:
        return services.list_directores(session)


@app.post("/directores", response_model=schemas.DirectorActionResponse)
def director_create(
    body: schemas.DirectorUpsertRequest = Body(...),
    _: None = Depends(security.require_api_key),
    operator: str | None = Depends(security.get_operator_name),
) -> dict:
    with SessionLocal() as session:
        result = services.upsert_director(session, body.model_dump())
    try:
        from db import audit

        audit.record_event(
            action="director.create",
            operator=operator,
            entity="director",
            entity_id=str((result.get("director") or {}).get("id") or ""),
            detail={"email": body.email, "sedes": body.sedes},
        )
    except Exception:
        pass
    return result


@app.put("/directores/{director_id}", response_model=schemas.DirectorActionResponse)
def director_update(
    director_id: int = Path(..., ge=1),
    body: schemas.DirectorUpsertRequest = Body(...),
    _: None = Depends(security.require_api_key),
    operator: str | None = Depends(security.get_operator_name),
) -> dict:
    with SessionLocal() as session:
        result = services.upsert_director(session, body.model_dump(), director_id=director_id)
    try:
        from db import audit

        audit.record_event(
            action="director.update",
            operator=operator,
            entity="director",
            entity_id=str(director_id),
            detail={"email": body.email, "sedes": body.sedes},
        )
    except Exception:
        pass
    return result


@app.delete("/directores/{director_id}")
def director_delete(
    director_id: int = Path(..., ge=1),
    _: None = Depends(security.require_api_key),
    operator: str | None = Depends(security.get_operator_name),
) -> dict:
    with SessionLocal() as session:
        result = services.delete_director(session, director_id)
    try:
        from db import audit

        audit.record_event(
            action="director.delete",
            operator=operator,
            entity="director",
            entity_id=str(director_id),
        )
    except Exception:
        pass
    return result


@app.post("/directores/seed-from-excel", response_model=schemas.DirectorSeedResponse)
def directores_seed(
    _: None = Depends(security.require_api_key),
    operator: str | None = Depends(security.get_operator_name),
) -> dict:
    with SessionLocal() as session:
        result = services.seed_directores(session)
    try:
        from db import audit

        audit.record_event(
            action="director.seed",
            operator=operator,
            entity="director",
            detail=result,
        )
    except Exception:
        pass
    return result


@app.get("/operations/stages")
def operations_stages_list(_: None = Depends(security.require_api_key)) -> dict:
    return operations.list_stages()


@app.get("/operations/period/overview")
def operations_period_overview(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    _: None = Depends(security.require_api_key),
) -> dict:
    return operations.period_overview(year, month)


@app.get("/operations/period/excel-avance")
def operations_period_excel_avance(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    row_limit: int = Query(500, ge=0, le=2000),
    _: None = Depends(security.require_api_key),
) -> dict:
    return operations.excel_avance(year, month, row_limit=row_limit)


@app.get("/operations/period/final-report")
def operations_period_final_report(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    _: None = Depends(security.require_api_key),
) -> dict:
    return operations.final_report(year, month)


@app.get("/operations/period/pagos-report")
def operations_period_pagos_report(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    _: None = Depends(security.require_api_key),
) -> dict:
    return operations.pagos_report(year, month)


@app.post("/operations/period/backfill")
def operations_period_backfill(
    body: dict = Body(...),
    _: None = Depends(security.require_api_key),
) -> dict:
    """Sincroniza uno o todos los meses de un año (Excel → DB + snapshots)."""
    try:
        year = int(body.get("year"))
        month = body.get("month")
        month_s = str(month).strip() if month else None
        if year < 2000 or year > 2100:
            raise ValueError("year inválido")
        run_migrations = bool(body.get("run_migrations", True))
        return operations.backfill_periods(
            year=year,
            month=month_s or None,
            run_migrations=run_migrations,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"No se pudo hacer backfill: {exc}")


@app.get("/operations/period/monthly-checklist")
def operations_period_monthly_checklist(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    _: None = Depends(security.require_api_key),
) -> dict:
    return operations.monthly_checklist(year, month)


@app.post("/operations/period/close")
def operations_period_close(
    body: dict = Body(...),
    _: None = Depends(security.require_api_key),
    operator: str | None = Depends(security.get_operator_name),
) -> dict:
    try:
        year = int(body.get("year"))
        month = str(body.get("month") or "").strip()
        force = bool(body.get("force", False))
        return operations.close_period(year, month, operator=operator or body.get("operator"), force=force)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/operations/period/reopen")
def operations_period_reopen(
    body: dict = Body(...),
    _: None = Depends(security.require_api_key),
    operator: str | None = Depends(security.get_operator_name),
) -> dict:
    try:
        year = int(body.get("year"))
        month = str(body.get("month") or "").strip()
        return operations.reopen_period(year, month, operator=operator or body.get("operator"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/operations/period/contabilidad-validate")
def operations_period_contabilidad_validate(
    body: dict = Body(...),
    _: None = Depends(security.require_api_key),
    operator: str | None = Depends(security.get_operator_name),
) -> dict:
    """Marca validación de Contabilidad sobre el informe (ok | con_observaciones | pendiente)."""
    try:
        year = int(body.get("year"))
        month = str(body.get("month") or "").strip()
        status = str(body.get("status") or "").strip()
        notes = body.get("notes")
        return operations.mark_contabilidad(
            year,
            month,
            status=status,
            operator=operator or body.get("operator"),
            notes=str(notes) if notes is not None else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/operations/period/inbox-gaps")
def operations_period_inbox_gaps(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    fecha_inicio: str | None = Query(default=None, description="dd/mm/yyyy opcional"),
    fecha_fin: str | None = Query(default=None, description="dd/mm/yyyy opcional"),
    _: None = Depends(security.require_api_key),
) -> dict:
    """Detecta boletas bhe_ en Inbox para filas NO RECIBIDO que aún no están en carpeta."""
    try:
        return operations.inbox_gaps_scan(
            year,
            month,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.post("/operations/period/verify")
def operations_period_verify(
    body: dict = Body(...),
    _: None = Depends(security.require_api_key),
) -> dict:
    """Verifica período completo desde la web (migración + import + proyección + comparación)."""
    try:
        year = int(body.get("year"))
        month = str(body.get("month") or "").strip()
        if year < 2000 or year > 2100 or not month:
            raise ValueError("Parámetros year/month inválidos.")
        run_migrations = bool(body.get("run_migrations", True))
        run_consistency = bool(body.get("run_consistency", True))
        consistency_limit = int(body.get("consistency_limit", 20))
        return operations.period_verify(
            year,
            month,
            run_migrations=run_migrations,
            run_consistency=run_consistency,
            consistency_limit=consistency_limit,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"No se pudo verificar período: {exc}")


@app.post("/operations/db/migrate")
def operations_db_migrate(_: None = Depends(security.require_api_key)) -> dict:
    """Aplica migraciones Alembic pendientes."""
    try:
        return operations.db_migrate()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"No se pudo migrar la base de datos: {exc}")


@app.post("/operations/db/consistency-check")
def operations_db_consistency_check(
    body: dict = Body(default_factory=dict),
    _: None = Depends(security.require_api_key),
) -> dict:
    """Chequeo global de integridad del dominio."""
    try:
        limit = int(body.get("limit", 20))
        return operations.db_consistency_check(limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"No se pudo revisar consistencia: {exc}")


@app.post("/operations/db/backup")
def operations_db_backup(
    _: None = Depends(security.require_api_key),
    operator: str | None = Depends(security.get_operator_name),
) -> dict:
    try:
        return operations.create_db_backup(operator=operator)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"No se pudo crear backup: {exc}")


@app.get("/operations/db/backups")
def operations_db_backups_list(_: None = Depends(security.require_api_key)) -> dict:
    return operations.list_db_backups()


@app.get("/audit/events")
def audit_events_list(
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: str | None = Query(default=None, min_length=3, max_length=20),
    limit: int = Query(default=100, ge=1, le=500),
    _: None = Depends(security.require_api_key),
) -> dict:
    return operations.list_audit_events(year=year, month=month, limit=limit)


@app.get("/operations/period/validate-maestro")
def operations_validate_maestro(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    filename: str | None = Query(default=None),
    _: None = Depends(security.require_api_key),
) -> dict:
    import config
    import os

    month_dir = os.path.join(config.RAIZ, str(year), str(month).strip().capitalize())
    if filename:
        path = os.path.join(month_dir, os.path.basename(filename))
    else:
        files = [
            f
            for f in (os.listdir(month_dir) if os.path.isdir(month_dir) else [])
            if f.lower().endswith(".xlsx") and f.casefold() != "solicitud.xlsx"
        ]
        if not files:
            raise HTTPException(status_code=404, detail="No hay maestro en la carpeta del mes.")
        path = os.path.join(month_dir, files[0])
    return operations.validate_maestro_file(path)


@app.post("/operations/server/restart")
def operations_server_restart(
    body: dict = Body(default_factory=dict),
    _: None = Depends(security.require_api_key),
) -> dict:
    """Reinicia el servidor BH (solo Windows, misma máquina)."""
    try:
        port = int(body.get("port", 8000))
        return operations.server_restart(port=port)
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"No se pudo reiniciar el servidor: {exc}")


@app.get("/operations/periods/missing")
def operations_periods_missing(
    year: int = Query(..., ge=2000, le=2100),
    _: None = Depends(security.require_api_key),
) -> dict:
    """Meses del año que aún no tienen carpeta en disco."""
    import period_bootstrap

    try:
        return period_bootstrap.list_missing_months(year)
    except period_bootstrap.PeriodBootstrapError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@app.post("/operations/periods")
def operations_create_period(
    body: schemas.CreatePeriodRequest = Body(...),
    _: None = Depends(security.require_api_key),
) -> dict:
    """Crea carpeta RAIZ/{año}/{Mes} y registra el período abierto en BD."""
    import period_bootstrap

    try:
        return period_bootstrap.create_period(body.year, body.month_name)
    except period_bootstrap.PeriodBootstrapError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@app.get("/operations/period/setup")
def operations_period_setup(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    _: None = Depends(security.require_api_key),
) -> dict:
    """Checklist de preparación del mes (maestro, BD, PDF, Outlook)."""
    import period_bootstrap

    try:
        return period_bootstrap.period_setup(year, month)
    except period_bootstrap.PeriodBootstrapError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@app.post("/operations/period/upload")
async def operations_period_upload(
    year: int = Form(..., ge=2000, le=2100),
    month: str = Form(..., min_length=3, max_length=20),
    kind: str = Form(...),
    file: UploadFile = File(...),
    _: None = Depends(security.require_api_key),
) -> dict:
    """Sube maestro, BD-DOCENTES, PDF de ejemplo o Excel de pagos Contabilidad (kind=pagos)."""
    import period_bootstrap

    data = await file.read()
    try:
        return period_bootstrap.upload_period_file(
            year,
            month,
            kind,
            filename=file.filename or "upload.bin",
            data=data,
        )
    except period_bootstrap.PeriodBootstrapError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@app.post("/operations/stages/7/import-pagos")
async def operations_stage7_import_pagos(
    year: int = Form(..., ge=2000, le=2100),
    month: str = Form(..., min_length=3, max_length=20),
    paste: str | None = Form(None),
    file: UploadFile | None = File(None),
    _: None = Depends(security.require_api_key),
) -> dict:
    """Importa tabla Contabilidad (pegar HTML/TSV/CSV o subir archivo) → hoja Pagos + MAIL/SEDE."""
    import pagos_import
    import period_bootstrap

    paste_txt = (paste or "").strip()
    file_bytes = await file.read() if file is not None else b""
    filename = (file.filename if file is not None else "") or ""

    if not paste_txt and not file_bytes:
        raise HTTPException(
            status_code=422,
            detail="Pegá la tabla del correo de Contabilidad o subí un .csv/.xlsx.",
        )

    try:
        if file_bytes:
            # Reutiliza bootstrap: guarda y escribe Pagos
            return period_bootstrap.upload_period_file(
                year,
                month,
                "pagos",
                filename=filename or "Contabilidad_Pagos.csv",
                data=file_bytes,
            )
        result = pagos_import.import_pagos_from_paste(
            year=year,
            month=month,
            paste=paste_txt,
            write=True,
        )
        return result
    except period_bootstrap.PeriodBootstrapError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo importar pagos: {exc}") from exc


@app.post("/operations/stages/7/preview-pagos")
def operations_stage7_preview_pagos(
    body: schemas.PagosPreviewRequest = Body(...),
    _: None = Depends(security.require_api_key),
) -> dict:
    """Previsualiza correos de pago desde la hoja Pagos (sin enviar)."""
    import pagos_import

    try:
        return pagos_import.preview_pagos_emails(
            year=body.year,
            month=body.month,
            fecha_pago=body.fecha_pago,
            force_resend=body.force_resend,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo previsualizar: {exc}") from exc


@app.post("/operations/local/open")
def operations_local_open(
    body: schemas.LocalOpenRequest = Body(...),
    _: None = Depends(security.require_api_key),
) -> dict:
    """Abre Solicitud.xlsx (u otro archivo) o la carpeta del mes en este equipo."""
    import local_open

    try:
        target = (body.target or "file").strip().lower()
        if target == "folder":
            path = local_open.resolve_period_dir(body.year, body.month)
            return local_open.open_local_folder(path)
        if body.stage_num is not None:
            return local_open.open_stage_primary(body.year, body.month, body.stage_num)
        name = (body.filename or "Solicitud.xlsx").strip() or "Solicitud.xlsx"
        if "/" in name or "\\" in name or ".." in name:
            raise ValueError("Nombre de archivo inválido.")
        path = local_open.resolve_period_file(body.year, body.month, name=name)
        return local_open.open_local_file(path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/operations/period/file")
def operations_period_file(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    filename: str = Query("Solicitud.xlsx", min_length=1, max_length=200),
    _: None = Depends(security.require_api_key),
):
    """Descarga un archivo del mes (p. ej. Solicitud.xlsx con el informe)."""
    import local_open

    try:
        if "/" in filename or "\\" in filename or ".." in filename:
            raise ValueError("Nombre de archivo inválido.")
        path = local_open.resolve_period_file(year, month, name=filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return FileResponse(
        path,
        filename=os.path.basename(path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/operations/period/export-db")
def operations_period_export_db(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    _: None = Depends(security.require_api_key),
    operator: str | None = Depends(security.get_operator_name),
):
    """Exporta snapshot Excel del período generado desde PostgreSQL."""
    try:
        filename, content = operations.export_period_snapshot_excel(year, month)
        from db import audit

        audit.record_event(
            action="period.export_solicitud",
            operator=operator,
            period_year=year,
            period_month=month,
            entity="solicitud",
            detail={"filename": filename},
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/operations/period/sync-status")
def operations_period_sync_status(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    refresh: bool = Query(default=False),
    _: None = Depends(security.require_api_key),
) -> dict:
    return operations.period_sync_status(year, month, refresh=refresh)


@app.get("/operations/stages/{stage_num}/options")
def operations_stage_options(
    stage_num: int = Path(..., ge=0, le=10),
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    _: None = Depends(security.require_api_key),
) -> dict:
    try:
        return operations.list_stage_options(stage_num, year, month)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/operations/stages/{stage_num}/start")
def operations_stage_start(
    stage_num: int = Path(..., ge=0, le=10),
    body: schemas.StageStartRequest = Body(...),
    _: None = Depends(security.require_api_key),
    operator: str | None = Depends(security.get_operator_name),
) -> dict:
    payload = body.model_dump(exclude_none=True)
    if operator:
        payload["operator"] = operator
    try:
        return operations.start_stage_job(stage_num, payload)
    except operations.StageNotEnabledError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except operations.PeriodLockError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/operations/step0/options")
def step0_options(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    _: None = Depends(security.require_api_key),
) -> dict:
    return operations.list_stage_options(0, year, month)


@app.get("/operations/step0/arrastre-preview")
def step0_arrastre_preview(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    _: None = Depends(security.require_api_key),
) -> dict:
    try:
        return operations.preview_step0_arrastre(year, month)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/operations/step0/start")
def step0_start(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query(..., min_length=3, max_length=20, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$"),
    maestro_file: str = Query(..., min_length=5, max_length=255),
    bd_file: str = Query(..., min_length=5, max_length=255),
    output_file: str | None = Query(default=None, min_length=5, max_length=255),
    _: None = Depends(security.require_api_key),
) -> dict:
    try:
        return operations.start_step0_job(
            year=year,
            month=month,
            maestro_file=maestro_file,
            bd_file=bd_file,
            output_file=output_file,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except operations.StageNotEnabledError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except operations.PeriodLockError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/operations/history")
def operations_execution_history(
    year: int = Query(default=2026, ge=2000, le=2100),
    from_month: str = Query(default="Enero"),
    to_month: str = Query(default="Mayo"),
    limit: int = Query(default=500, ge=1, le=2000),
    _: None = Depends(security.require_api_key),
) -> dict:
    return operations.list_execution_history(
        year=year,
        from_month=from_month,
        to_month=to_month,
        limit=limit,
    )


@app.get("/operations/history/{entry_id}/logs")
def operations_history_logs(
    entry_id: str = Path(..., min_length=4, max_length=128),
    year: int = Query(default=2026, ge=2000, le=2100),
    from_month: str = Query(default="Enero"),
    to_month: str = Query(default="Mayo"),
    max_chars: int = Query(default=12000, ge=1000, le=50000),
    _: None = Depends(security.require_api_key),
) -> dict:
    return {
        "entry_id": entry_id,
        "logs": operations.read_history_logs(
            entry_id,
            year=year,
            from_month=from_month,
            to_month=to_month,
            max_chars=max_chars,
        ),
    }


@app.get("/operations/jobs")
def operations_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    stage_num: int | None = Query(default=None, ge=0, le=10),
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: str | None = Query(default=None),
    _: None = Depends(security.require_api_key),
) -> dict:
    return {
        "data": operations.list_jobs(
            limit=limit,
            stage_num=stage_num,
            year=year,
            month=month,
        )
    }


@app.get("/operations/jobs/{job_id}")
def operations_job_detail(
    job_id: str = Path(..., min_length=4, max_length=64),
    _: None = Depends(security.require_api_key),
) -> dict:
    job = operations.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} no encontrado")
    return job


@app.get("/operations/jobs/{job_id}/logs")
def operations_job_logs(
    job_id: str = Path(..., min_length=4, max_length=64),
    max_chars: int = Query(default=12000, ge=1000, le=50000),
    _: None = Depends(security.require_api_key),
) -> dict:
    job = operations.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} no encontrado")
    return {"job_id": job_id, "logs": operations.read_job_log(job_id, max_chars=max_chars)}


@app.get("/operations/jobs/{job_id}/log-file")
def operations_job_log_file(
    job_id: str = Path(..., min_length=4, max_length=64),
    _: None = Depends(security.require_api_key),
):
    job = operations.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} no encontrado")
    log_path = job.get("log_path")
    if not log_path or not os.path.isfile(log_path):
        raise HTTPException(status_code=404, detail="Log no disponible")
    stage = job.get("stage_num", 0)
    return FileResponse(
        path=log_path,
        filename=f"stage{stage}_{job_id}.log",
        media_type="text/plain",
    )


@app.get("/operations/jobs/{job_id}/artifacts")
def operations_job_artifacts(
    job_id: str = Path(..., min_length=4, max_length=64),
    _: None = Depends(security.require_api_key),
) -> dict:
    job = operations.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} no encontrado")
    return {"job_id": job_id, "artifacts": operations.get_job_artifacts(job_id)}


@app.get("/operations/jobs/{job_id}/artifacts/{artifact_id}")
def operations_job_artifact_file(
    job_id: str = Path(..., min_length=4, max_length=64),
    artifact_id: str = Path(..., min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$"),
    _: None = Depends(security.require_api_key),
):
    job = operations.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} no encontrado")
    path = operations.get_job_artifact_path(job_id, artifact_id)
    if not path:
        raise HTTPException(status_code=404, detail="Artefacto no disponible")
    media = "application/octet-stream"
    if path.lower().endswith(".xlsx"):
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif path.lower().endswith(".csv"):
        media = "text/csv"
    elif path.lower().endswith(".log"):
        media = "text/plain"
    return FileResponse(path=path, filename=os.path.basename(path), media_type=media)


@app.get("/operations/jobs/{job_id}/output")
def operations_job_output_file(
    job_id: str = Path(..., min_length=4, max_length=64),
    _: None = Depends(security.require_api_key),
):
    """Legacy: descarga artefacto primary."""
    job = operations.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} no encontrado")
    output_path = operations.get_job_artifact_path(job_id, "primary") or operations.get_job_primary_output_path(job_id)
    if not output_path:
        raise HTTPException(status_code=404, detail="Archivo de salida no disponible")
    return FileResponse(path=output_path, filename=os.path.basename(output_path), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/operations/outbox/stats")
def operations_outbox_stats(_: None = Depends(security.require_api_key)) -> dict:
    return operations.outbox_stats()


@app.get("/operations/outbox/rows")
def operations_outbox_rows(
    status: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=50, ge=1, le=200),
    _: None = Depends(security.require_api_key),
) -> dict:
    return {"data": operations.outbox_list_rows(status=status, limit=limit)}


@app.post("/operations/outbox/dispatch-com")
def operations_outbox_dispatch(
    limit: int = Query(default=30, ge=1, le=200),
    dry_run: bool = Query(default=False),
    _: None = Depends(security.require_api_key),
) -> dict:
    return operations.outbox_dispatch_com(limit=limit, dry_run=dry_run)


@app.post("/operations/outbox/reopen-failed")
def operations_outbox_reopen(
    limit: int = Query(default=200, ge=1, le=500),
    _: None = Depends(security.require_api_key),
) -> dict:
    return operations.outbox_reopen_failed(limit=limit)


# SPA al final: no debe tapar rutas API registradas arriba.
_SPA_MOUNTED = mount_frontend_spa(app)
