"""Orquestador de jobs de etapas del pipeline (consola equivalente vía subprocess)."""
from __future__ import annotations

import json
import io
import os
import subprocess
import sys
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

import config
import ops_execution_history
import stage_commands
import stage_interactive_options
import stage_operations
import stage_ui_guides
from settings import get_setting
from period_lock import PeriodLock, PeriodLockError

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()
_LOADED = False
# Locks de período por job_id (no persistidos; viven mientras el proceso API esté arriba).
_JOB_LOCKS: dict[str, PeriodLock] = {}
_JOB_LOCKS_LOCK = threading.Lock()


def _store_job_lock(job_id: str, lock: PeriodLock) -> None:
    with _JOB_LOCKS_LOCK:
        _JOB_LOCKS[job_id] = lock


def _release_job_lock(job_id: str) -> None:
    with _JOB_LOCKS_LOCK:
        lock = _JOB_LOCKS.pop(job_id, None)
    if lock is not None:
        try:
            lock.release()
        except Exception:
            pass


class StageNotEnabledError(ValueError):
    """La etapa existe pero aún no está habilitada para arranque vía API."""


def _state_root() -> str:
    return os.path.abspath(get_setting("BH_RAIZ", _REPO_ROOT))


def _jobs_dir() -> str:
    path = os.path.join(_state_root(), ".state", "ops-jobs")
    os.makedirs(path, exist_ok=True)
    return path


def _job_meta_path(job_id: str) -> str:
    return os.path.join(_jobs_dir(), f"{job_id}.json")


def _ensure_jobs_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    jobs_dir = _jobs_dir()
    for name in os.listdir(jobs_dir):
        if not name.endswith(".json"):
            continue
        path = os.path.join(jobs_dir, name)
        try:
            with open(path, encoding="utf-8") as f:
                job = json.load(f)
            if job.get("status") == "running":
                pid = job.get("pid")
                if pid and _pid_alive(pid):
                    pass
                else:
                    job["status"] = "failed"
                    job["finished_at"] = job.get("finished_at") or datetime.now(UTC).isoformat()
                    job["return_code"] = job.get("return_code") if job.get("return_code") is not None else -1
                    _persist_job(job)
            _JOBS[job["id"]] = job
        except (OSError, json.JSONDecodeError, KeyError):
            continue
    _LOADED = True


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        try:
            import ctypes

            kernel = ctypes.windll.kernel32
            handle = kernel.OpenProcess(0x1000, False, int(pid))
            if handle:
                kernel.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _persist_job(job: dict) -> None:
    path = _job_meta_path(job["id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=2)


def _month_path(year: int, month: str) -> str:
    return os.path.join(config.RAIZ, str(year), month)


def list_stages() -> dict:
    _ensure_jobs_loaded()
    return {"stages": stage_commands.list_stages_metadata()}


def list_stage_options(stage_num: int, year: int, month: str) -> dict:
    _ensure_jobs_loaded()
    stage = stage_commands.get_stage(stage_num)
    if not stage:
        raise ValueError(f"Etapa inválida: {stage_num}")

    checklist = stage_operations.prerequisite_checklist(stage_num, year, month)
    prereq = stage_operations.prerequisites_summary(checklist)
    period_jobs = _jobs_for_period(year, month)
    running = _running_job_for_period(year, month, jobs=period_jobs)

    base: dict[str, Any] = {
        "stage_num": stage_num,
        "year": year,
        "month": month,
        "prerequisites": prereq,
        "checklist": checklist,
        "warnings": stage_operations.warnings_for_stage(stage_num, year, month),
        "estimated_outputs": stage_operations.estimated_outputs_for_stage(stage_num, year, month),
        "ui_status": stage_operations.ui_status_for_stage(
            stage_num, year, month, jobs=period_jobs, running_job=running
        ),
        "enabled_for_api": stage_num in stage_commands.API_ENABLED_STAGES,
        "period_kpis": stage_operations.period_summary(year, month),
        "running_job": (
            {"id": running["id"], "stage_num": running.get("stage_num")}
            if running
            else None
        ),
    }

    base["guide"] = stage_ui_guides.get_stage_guide(stage_num)
    base["choices"] = stage_interactive_options.build_interactive_choices(stage_num, year, month)

    if stage_num in stage_commands.EMAIL_STAGES or stage_num == 2:
        try:
            from outlook_utils import check_outlook_health

            base["outlook_health"] = check_outlook_health(probe_com=True)
        except Exception as e:
            base["outlook_health"] = {
                "ready": False,
                "process_running": False,
                "exe_found": False,
                "com_ok": None,
                "can_auto_launch": False,
                "message": f"No se pudo comprobar Outlook: {e}",
                "required_for_stages": [1, 2, 5, 7],
            }

    if stage_num == 0:
        opts = list_step0_options(year, month)
        base.update(opts)
        try:
            base["arrastre_preview"] = preview_step0_arrastre(int(year), str(month))
        except Exception as exc:
            base["arrastre_preview"] = {
                "year": int(year),
                "month": str(month).strip().capitalize(),
                "lookback": [],
                "previous_closed": False,
                "count": 0,
                "total_monto": 0,
                "rows": [],
                "message": f"No se pudo calcular el arrastre de provisionados: {exc}",
                "error": str(exc),
            }
    else:
        base["month_dir"] = _month_path(year, month)
        schema = stage_commands.params_schema_for_stage(stage_num)
        base["params_schema"] = stage_interactive_options.enrich_params_schema(
            stage_num, year, month, schema
        )
        base["is_email_stage"] = stage_num in stage_commands.EMAIL_STAGES

    return base


def period_overview(year: int, month: str) -> dict:
    _ensure_jobs_loaded()
    jobs = _jobs_for_period(year, month, limit=80)
    return stage_operations.period_overview(year, month, jobs=jobs)


def excel_avance(year: int, month: str, *, row_limit: int = 500) -> dict:
    return stage_operations.excel_avance(year, month, row_limit=row_limit)


def final_report(year: int, month: str) -> dict:
    import final_report as final_report_module

    return final_report_module.period_final_report(year, month)


def pagos_report(year: int, month: str) -> dict:
    import pagos_report as pagos_report_module

    return pagos_report_module.period_pagos_report(year, month)


def backfill_periods(
    *,
    year: int,
    month: str | None = None,
    run_migrations: bool = True,
) -> dict:
    """Importa Excel→DB + snapshots informe/pagos para uno o todos los meses del año."""
    import period_snapshots
    from db import db_maintenance

    migration = db_maintenance.run_alembic_upgrade() if run_migrations else None
    months: list[str] = []
    if month:
        months = [str(month).strip().capitalize()]
    else:
        year_dir = os.path.join(config.RAIZ, str(year))
        if os.path.isdir(year_dir):
            for name in sorted(os.listdir(year_dir)):
                sol = os.path.join(year_dir, name, "Solicitud.xlsx")
                if os.path.isfile(sol):
                    months.append(name)

    results: list[dict] = []
    for m in months:
        try:
            verify = period_verify(
                year,
                m,
                run_migrations=False,
                run_consistency=False,
            )
            snaps = verify.get("snapshots") or {}
            has_data = bool(
                (snaps.get("informe") or {}).get("ok")
                or (snaps.get("pagos") or {}).get("ok")
                or (verify.get("import_stats") or {}).get("boletas_upserted")
                or (verify.get("projection") or {}).get("projected")
            )
            # Compare Excel/DB puede tener diferencias sin impedir lectura histórica.
            results.append(
                {
                    "month": m,
                    "ok": bool(has_data or verify.get("ok")),
                    "aligned": bool(verify.get("ok")),
                    "verify": verify,
                }
            )
        except Exception as exc:
            # Aún intentar snapshots si el período existe
            try:
                snaps = period_snapshots.sync_snapshots_for_period(year, m, prefer_freeze=True)
                has_snap = bool(
                    (snaps.get("informe") or {}).get("ok")
                    or (snaps.get("pagos") or {}).get("ok")
                )
            except Exception as snap_exc:
                snaps = {"error": str(snap_exc)}
                has_snap = False
            results.append(
                {
                    "month": m,
                    "ok": has_snap,
                    "aligned": False,
                    "error": str(exc),
                    "snapshots": snaps,
                }
            )

    ok_count = sum(1 for r in results if r.get("ok"))
    return {
        "ok": ok_count == len(results) and len(results) > 0,
        "year": year,
        "months": months,
        "ok_count": ok_count,
        "total": len(results),
        "migration": migration,
        "results": results,
    }


def monthly_checklist(year: int, month: str) -> dict:
    import monthly_checklist as mc

    return mc.monthly_checklist(year, month)


def close_period(year: int, month: str, *, operator: str | None = None, force: bool = False) -> dict:
    import period_close

    return period_close.close_period(year, month, operator=operator, force=force)


def reopen_period(year: int, month: str, *, operator: str | None = None) -> dict:
    import period_close

    return period_close.reopen_period(year, month, operator=operator)


def mark_contabilidad(
    year: int,
    month: str,
    *,
    status: str,
    operator: str | None = None,
    notes: str | None = None,
) -> dict:
    import contabilidad_validation

    return contabilidad_validation.mark_contabilidad(
        year, month, status=status, operator=operator, notes=notes
    )


def list_audit_events(*, year: int | None = None, month: str | None = None, limit: int = 100) -> dict:
    from db import audit

    return {"events": audit.list_events(year=year, month=month, limit=limit)}


def create_db_backup(*, operator: str | None = None) -> dict:
    from db import db_maintenance

    result = db_maintenance.create_postgres_backup()
    from db import audit

    audit.record_event(
        action="db.backup",
        operator=operator,
        entity="postgres",
        detail={"path": result.get("path"), "size_bytes": result.get("size_bytes")},
    )
    return result


def list_db_backups() -> dict:
    from db import db_maintenance

    return db_maintenance.list_postgres_backups()


def validate_maestro_file(path: str) -> dict:
    import maestro_validation

    return maestro_validation.validate_maestro_path(path)


def period_sync_status(year: int, month: str, *, refresh: bool = False) -> dict:
    """E5/E11: estado de sincronización Excel↔PostgreSQL, con refresco opcional."""
    if refresh:
        import sync_projector

        return sync_projector.apply_hints(year, month, {"ensure_periods_from_disk": True})
    import sync_status

    return sync_status.period_sync_status(year, month)


def db_migrate() -> dict:
    """Aplica migraciones Alembic pendientes."""
    from db import db_maintenance

    return db_maintenance.run_alembic_upgrade()


def db_consistency_check(*, limit: int = 20) -> dict:
    """Chequeo global de integridad del dominio."""
    from db import db_maintenance

    return db_maintenance.consistency_check(limit=limit)


def server_restart(*, port: int = 8000) -> dict:
    """Reinicia el servidor BH (Windows, misma máquina)."""
    import server_restart as server_restart_mod

    return server_restart_mod.restart_server(port=port)


def period_verify(
    year: int,
    month: str,
    *,
    run_migrations: bool = True,
    run_consistency: bool = True,
    consistency_limit: int = 20,
) -> dict:
    """
    Verificación web de período:
    - migraciones DB (opcional)
    - importa snapshot Excel->DB
    - reproyecta estado canónico
    - compara Excel vs DB
    - métricas del período y consistencia global (opcional)
    """
    import pandas as pd
    from db import compare_excel_db
    from db import db_maintenance
    from db import import_excel_snapshot
    from db.period_projector import project_dataframe

    migration: dict[str, Any] | None = None
    if run_migrations:
        migration = db_maintenance.run_alembic_upgrade()

    month_dir = _month_path(year, month)
    solicitud = os.path.join(month_dir, "Solicitud.xlsx")
    if not os.path.isfile(solicitud):
        raise FileNotFoundError(f"No existe {solicitud}")

    sheet = import_excel_snapshot.detect_solicitud_sheet(solicitud)
    import_stats = import_excel_snapshot.run_import(
        path=solicitud,
        sheet_solicitud=sheet,
        sheet_resumen="Resumen Boletas",
        anio=year,
        mes_nombre=month,
    )
    df = pd.read_excel(solicitud, sheet_name=sheet, engine="openpyxl")
    mes_num = config.MESES_ES.index(month) + 1 if month in config.MESES_ES else 0
    projection = {"projected": 0, "failed": 0}
    if mes_num > 0 and df is not None:
        projection = project_dataframe(
            year=year,
            month_num=mes_num,
            month_name=month,
            df=df,
        )
    dedupe = db_maintenance.dedupe_period_boletas(year=year, month=month)
    compare_stats = compare_excel_db.compare_period(year=year, month=month, sheet=sheet)
    period_stats = db_maintenance.period_check(year, month)
    consistency: dict[str, Any] | None = None
    if run_consistency:
        consistency = db_maintenance.consistency_check(limit=consistency_limit)

    aligned = compare_stats.get("differences", 0) == 0
    snapshots: dict[str, Any] | None = None
    try:
        import period_snapshots

        snapshots = period_snapshots.sync_snapshots_for_period(year, month, prefer_freeze=True)
    except Exception as exc:
        snapshots = {"ok": False, "error": str(exc)}

    return {
        "ok": aligned and (consistency is None or consistency.get("ok", True)),
        "year": year,
        "month": month,
        "solicitud": solicitud,
        "sheet": sheet,
        "migration": migration,
        "import_stats": import_stats,
        "projection": projection,
        "dedupe": dedupe,
        "compare": compare_stats,
        "period_check": period_stats,
        "consistency": consistency,
        "snapshots": snapshots,
    }


def export_period_snapshot_excel(year: int, month: str) -> tuple[str, bytes]:
    """Exporta Solicitud.xlsx detallada desde PostgreSQL."""
    import solicitud_export

    return solicitud_export.export_solicitud_excel(year, month)


def _jobs_for_period(year: int | str, month: str, limit: int = 80) -> list[dict]:
    with _JOBS_LOCK:
        jobs = list(_JOBS.values())
    jobs = [
        j
        for j in jobs
        if str(j.get("year")) == str(year) and str(j.get("month")) == month
    ]
    jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
    return [dict(j) for j in jobs[:limit]]


def _running_job_for_period(
    year: int | str,
    month: str,
    *,
    jobs: list[dict] | None = None,
) -> dict | None:
    jobs = jobs if jobs is not None else _jobs_for_period(year, month)
    for j in jobs:
        if j.get("status") == "running":
            return j
    return None


def get_job_artifacts(job_id: str) -> list[dict]:
    job = get_job(job_id)
    if not job:
        return []
    return stage_operations.artifacts_for_job(job)


def get_job_artifact_path(job_id: str, artifact_id: str) -> str | None:
    job = get_job(job_id)
    if not job:
        return None
    return stage_operations.resolve_job_artifact_path(job, artifact_id)


def outbox_stats() -> dict:
    import email_outbox

    return {"by_status": email_outbox.stats_by_status()}


def outbox_list_rows(*, status: str | None = None, limit: int = 50) -> list[dict]:
    import email_outbox

    return email_outbox.list_rows(status=status or None, limit=limit)


def outbox_dispatch_com(*, limit: int = 30, dry_run: bool = False) -> dict:
    import outbox_com_dispatch

    ok, fail, skip = outbox_com_dispatch.dispatch_pending_com(limit=limit, dry_run=dry_run)
    return {"ok": ok, "failed": fail, "dry_skipped": skip}


def outbox_reopen_failed(*, limit: int = 200) -> dict:
    import email_outbox

    n = email_outbox.reopen_failed_as_pending(limit=limit)
    return {"reopened": n}


def preview_step0_arrastre(year: int, month: str) -> dict:
    import arrastre_provisionados

    return arrastre_provisionados.preview_arrastre_provisionados(str(month), int(year))


def list_step0_options(year: int, month: str) -> dict:
    import period_bootstrap

    month_dir = _month_path(year, month)
    if not os.path.isdir(month_dir):
        return {
            "year": year,
            "month": month,
            "month_dir": month_dir,
            "maestro_files": [],
            "bd_candidates": [],
        }

    maestro_files = sorted(
        [
            f
            for f in os.listdir(month_dir)
            if f.lower().endswith(".xlsx")
            and os.path.isfile(os.path.join(month_dir, f))
            and not period_bootstrap._is_excluded_maestro_name(f)
        ]
    )
    root_files = sorted(
        [
            f
            for f in os.listdir(config.RAIZ)
            if f.lower().endswith(".xlsx") and os.path.isfile(os.path.join(config.RAIZ, f))
        ]
    )
    bd_candidates = [f for f in root_files if "bd" in f.lower() or "docentes" in f.lower()]
    return {
        "year": year,
        "month": month,
        "month_dir": month_dir,
        "maestro_files": maestro_files,
        "bd_candidates": bd_candidates,
    }


def _run_job(job_id: str, cmd: list[str], cwd: str, log_path: str, env: dict[str, str]) -> None:
    with open(log_path, "w", encoding="utf-8") as log_file:
        log_file.write(f"[{datetime.now(UTC).isoformat()}] START {' '.join(cmd)}\n")
        child_env = env.copy()
        child_env["PYTHONIOENCODING"] = "utf-8:replace"
        child_env["PYTHONUTF8"] = "1"
        child_env["RICH_DISABLE_LEGACY_WINDOWS"] = "1"
        child_env["TERM"] = "xterm-256color"
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
            if job:
                job["pid"] = process.pid
                _persist_job(job)
        if process.stdout is not None:
            for line in process.stdout:
                log_file.write(line)
                log_file.flush()
        return_code = process.wait()
        finished = datetime.now(UTC).isoformat()
        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
            if job:
                job["status"] = "success" if return_code == 0 else "failed"
                job["return_code"] = return_code
                job["finished_at"] = finished
                _persist_job(job)
                try:
                    from db import audit

                    audit.record_event(
                        action=f"job.{job['status']}",
                        operator=job.get("operator") or job.get("triggered_by"),
                        period_year=int(job["year"]) if job.get("year") is not None else None,
                        period_month=job.get("month"),
                        entity="job",
                        entity_id=job_id,
                        detail={
                            "stage_num": job.get("stage_num"),
                            "return_code": return_code,
                            "type": job.get("type"),
                        },
                    )
                except Exception:
                    pass
        _release_job_lock(job_id)
        log_file.write(f"\n[{finished}] END return_code={return_code}\n")


def _job_type(stage_num: int) -> str:
    stage = stage_commands.get_stage(stage_num)
    if not stage:
        return f"stage_{stage_num}"
    base = os.path.basename(stage["file"]).replace(".py", "")
    return f"stage{stage_num}_{base}"


def start_stage_job(stage_num: int, params: dict[str, Any]) -> dict:
    _ensure_jobs_loaded()

    if stage_num not in stage_commands.API_ENABLED_STAGES:
        raise StageNotEnabledError(
            f"La etapa {stage_num} aún no está habilitada para ejecución desde la API. "
            f"Use la consola: python etapas/... o python main.py"
        )

    year = params.get("year")
    month = params.get("month")
    if year is None or not month:
        raise ValueError("params debe incluir year y month")

    operator = (params.pop("operator", None) or params.pop("triggered_by", None) or None)
    if isinstance(operator, str):
        operator = operator.strip() or None

    if stage_num == 0:
        maestro_name = str(params.get("maestro_file") or "").strip()
        if maestro_name:
            import config as _cfg
            import maestro_validation

            maestro_path = os.path.join(
                _cfg.RAIZ, str(year), str(month).strip().capitalize(), os.path.basename(maestro_name)
            )
            validation = maestro_validation.validate_maestro_path(maestro_path)
            if not validation.get("ok"):
                errs = "; ".join(validation.get("errors") or ["Maestro inválido"])
                raise ValueError(f"Maestro no válido: {errs}")

    stage_commands.check_prerequisites(stage_num, year, month)

    running = _running_job_for_period(year, month)
    if running:
        raise ValueError(
            f"Ya hay un job en ejecución para {month} {year} "
            f"(id={running['id']}, paso {running.get('stage_num')}). Espere a que termine."
        )

    period_lock = PeriodLock(year, month, script=f"job-stage{stage_num}")
    try:
        period_lock.acquire()
    except PeriodLockError as exc:
        raise PeriodLockError(
            f"No se puede iniciar el job: período {month} {year} está bloqueado "
            f"por otra ejecución en curso ({exc})"
        ) from exc

    try:
        merged = dict(params)
        merged.setdefault("year", year)
        merged.setdefault("month", month)

        cmd = stage_commands.build_stage_command(
            _REPO_ROOT,
            stage_num,
            year=year,
            month=month,
            params=merged,
            api_mode=True,
        )

        jobs_dir = _jobs_dir()
        job_id = uuid.uuid4().hex[:12]
        log_path = os.path.join(jobs_dir, f"{job_id}.log")

        env = os.environ.copy()
        env["BH_NON_INTERACTIVE"] = "1"
        env["BH_YEAR"] = str(year)
        env["BH_MONTH"] = str(month)

        job = {
            "id": job_id,
            "stage_num": stage_num,
            "type": _job_type(stage_num),
            "status": "running",
            "year": int(year) if str(year).isdigit() else year,
            "month": month,
            "params": {k: v for k, v in merged.items() if k not in ("ruta_bd", "operator", "triggered_by")},
            "cmd": cmd,
            "created_at": datetime.now(UTC).isoformat(),
            "log_path": log_path,
            "pid": None,
            "return_code": None,
            "finished_at": None,
            "operator": operator,
            "triggered_by": operator,
            # Campos legacy paso 0 (compatibilidad front)
            "maestro_file": merged.get("maestro_file", ""),
            "bd_file": merged.get("bd_file", ""),
            "output_file": merged.get("output_file") or "Solicitud.xlsx",
        }
        try:
            from db import audit

            audit.record_event(
                action="job.started",
                operator=operator,
                period_year=int(year) if str(year).isdigit() else None,
                period_month=str(month),
                entity="job",
                entity_id=job_id,
                detail={"stage_num": stage_num, "type": job["type"]},
            )
        except Exception:
            pass

        out_path = stage_commands.primary_output_for_stage(stage_num, year, month, merged)
        if out_path:
            job["output_path"] = out_path
            job["output_file"] = os.path.basename(out_path)
    except Exception:
        period_lock.release()
        raise

    _store_job_lock(job_id, period_lock)

    with _JOBS_LOCK:
        _JOBS[job_id] = job
        _persist_job(job)

    worker = threading.Thread(
        target=_run_job,
        args=(job_id, cmd, _REPO_ROOT, log_path, env),
        daemon=True,
    )
    worker.start()
    return dict(job)


def start_step0_job(
    *,
    year: int,
    month: str,
    maestro_file: str,
    bd_file: str,
    output_file: str | None = None,
) -> dict:
    """Compatibilidad con POST /operations/step0/start."""
    params: dict[str, Any] = {
        "year": year,
        "month": month,
        "maestro_file": maestro_file,
        "bd_file": bd_file,
    }
    if output_file:
        params["output_file"] = output_file
    return start_stage_job(0, params)


def get_job(job_id: str) -> dict | None:
    _ensure_jobs_loaded()
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if job:
        return dict(job)
    path = _job_meta_path(job_id)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        job = json.load(f)
    with _JOBS_LOCK:
        _JOBS[job_id] = job
    return dict(job)


def list_jobs(
    limit: int = 20,
    stage_num: int | None = None,
    year: int | str | None = None,
    month: str | None = None,
) -> list[dict]:
    _ensure_jobs_loaded()
    with _JOBS_LOCK:
        jobs = list(_JOBS.values())
    jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
    if stage_num is not None:
        jobs = [j for j in jobs if j.get("stage_num") == stage_num]
    if year is not None and month:
        jobs = [
            j
            for j in jobs
            if str(j.get("year")) == str(year) and str(j.get("month")) == month
        ]
    return [dict(j) for j in jobs[:limit]]


def list_execution_history(
    *,
    year: int,
    from_month: str,
    to_month: str,
    limit: int = 500,
) -> dict:
    _ensure_jobs_loaded()
    with _JOBS_LOCK:
        all_jobs = list(_JOBS.values())
    return ops_execution_history.list_execution_history(
        year=year,
        from_month=from_month,
        to_month=to_month,
        api_jobs=all_jobs,
        limit=limit,
    )


def read_history_logs(
    entry_id: str,
    *,
    year: int = 2026,
    from_month: str = "Enero",
    to_month: str = "Diciembre",
    max_chars: int = 50000,
) -> str:
    job = get_job(entry_id)
    if job:
        return read_job_log(entry_id, max_chars=max_chars)
    hist = list_execution_history(
        year=year,
        from_month=from_month,
        to_month=to_month,
        limit=2000,
    )
    entry = next((e for e in hist["data"] if e["id"] == entry_id), None)
    if entry and entry.get("artifact_path", "").lower().endswith(".xlsx"):
        return "(Archivo Excel — descárgalo desde Resultados del período o la carpeta del mes.)"
    return ops_execution_history.read_history_log(entry_id, hist["data"], max_chars=max_chars)


def read_job_log(job_id: str, max_chars: int = 12000) -> str:
    job = get_job(job_id)
    if not job:
        return ""
    log_path = job.get("log_path")
    if not log_path or not os.path.isfile(log_path):
        return ""
    with open(log_path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    if len(content) <= max_chars:
        return content
    return content[-max_chars:]


def get_job_primary_output_path(job_id: str) -> str | None:
    job = get_job(job_id)
    if not job:
        return None
    stage_num = job.get("stage_num", 0)
    year = job.get("year")
    month = job.get("month")
    if year is None or not month:
        return None
    path = stage_commands.primary_output_for_stage(
        stage_num,
        year,
        month,
        job.get("params") or {},
    )
    if path and os.path.isfile(path):
        return path
    stored = job.get("output_path")
    if stored and os.path.isfile(stored):
        return stored
    return None


def get_step0_output_path(job_id: str) -> str | None:
    """Alias legacy."""
    return get_job_primary_output_path(job_id)
