"""Orquestador de jobs de etapas del pipeline (consola equivalente vía subprocess)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

import config
import stage_commands
from settings import get_setting

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()
_LOADED = False


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

    prereq = stage_commands.describe_prerequisites(stage_num, year, month)
    base: dict[str, Any] = {
        "stage_num": stage_num,
        "year": year,
        "month": month,
        "prerequisites": prereq,
        "enabled_for_api": stage_num in stage_commands.API_ENABLED_STAGES,
    }

    if stage_num == 0:
        opts = list_step0_options(year, month)
        base.update(opts)
    else:
        base["month_dir"] = _month_path(year, month)
        base["params_schema"] = stage_commands.params_schema_for_stage(stage_num)
        base["is_email_stage"] = stage_num in stage_commands.EMAIL_STAGES

    return base


def list_step0_options(year: int, month: str) -> dict:
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
            if f.lower().endswith(".xlsx") and os.path.isfile(os.path.join(month_dir, f))
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

    stage_commands.check_prerequisites(stage_num, year, month)

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
        "params": {k: v for k, v in merged.items() if k not in ("ruta_bd",)},
        "cmd": cmd,
        "created_at": datetime.now(UTC).isoformat(),
        "log_path": log_path,
        "pid": None,
        "return_code": None,
        "finished_at": None,
        # Campos legacy paso 0 (compatibilidad front)
        "maestro_file": merged.get("maestro_file", ""),
        "bd_file": merged.get("bd_file", ""),
        "output_file": merged.get("output_file") or "Solicitud.xlsx",
    }

    out_path = stage_commands.primary_output_for_stage(stage_num, year, month, merged)
    if out_path:
        job["output_path"] = out_path
        job["output_file"] = os.path.basename(out_path)

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


def list_jobs(limit: int = 20, stage_num: int | None = None) -> list[dict]:
    _ensure_jobs_loaded()
    with _JOBS_LOCK:
        jobs = list(_JOBS.values())
    jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
    if stage_num is not None:
        jobs = [j for j in jobs if j.get("stage_num") == stage_num]
    return [dict(j) for j in jobs[:limit]]


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
