"""Repositorio simple para registrar runs/etapas del pipeline en PostgreSQL."""
from __future__ import annotations

from datetime import datetime, UTC
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError

from db.models import PipelineRun, PipelineStageRun
from db.session import SessionLocal


def create_pipeline_run(
    run_id: str,
    period_label: Optional[str] = None,
    triggered_by: Optional[str] = None,
    mode: str = "INTERACTIVO",
) -> Optional[int]:
    try:
        with SessionLocal() as session:
            row = PipelineRun(
                run_id=run_id,
                period_label=period_label,
                triggered_by=triggered_by,
                mode=mode,
                status="RUNNING",
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.id
    except SQLAlchemyError:
        return None


def finish_pipeline_run(run_db_id: int, status: str = "OK") -> bool:
    try:
        with SessionLocal() as session:
            row = session.get(PipelineRun, run_db_id)
            if row is None:
                return False
            row.status = status
            row.finished_at = datetime.now(UTC)
            session.commit()
            return True
    except SQLAlchemyError:
        return False


def create_stage_run(
    run_db_id: int,
    stage_num: int,
    stage_name: str,
    correlation_id: Optional[str] = None,
) -> Optional[int]:
    try:
        with SessionLocal() as session:
            row = PipelineStageRun(
                pipeline_run_id=run_db_id,
                stage_num=stage_num,
                stage_name=stage_name,
                correlation_id=correlation_id,
                status="RUNNING",
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.id
    except SQLAlchemyError:
        return None


def finish_stage_run(
    stage_run_id: int,
    status: str = "OK",
    message: Optional[str] = None,
) -> bool:
    try:
        with SessionLocal() as session:
            row = session.get(PipelineStageRun, stage_run_id)
            if row is None:
                return False
            row.status = status
            row.message = message
            row.finished_at = datetime.now(UTC)
            session.commit()
            return True
    except SQLAlchemyError:
        return False
