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

from fastapi import Body, Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse

from api import operations, schemas, security, services
from db.session import SessionLocal
from settings import get_setting

app = FastAPI(
    title="Boletas Honorarios API",
    version="0.1.0",
    description="API read-only para consultar periodos y métricas del pipeline.",
)
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

    if request.url.path != "/health":
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
    return JSONResponse(
        status_code=422,
        content=_build_error_payload(
            "VALIDATION_ERROR",
            "Parametros de entrada invalidos",
            {"errors": exc.errors()},
            request_id=request_id,
        ),
    )

@app.get("/health", response_model=schemas.HealthResponse)
def health() -> dict:
    return {"status": "ok"}


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
) -> dict:
    payload = body.model_dump(exclude_none=True)
    try:
        return operations.start_stage_job(stage_num, payload)
    except operations.StageNotEnabledError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
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
