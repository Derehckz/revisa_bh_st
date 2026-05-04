"""Orquestador seguro para operaciones de scripts legacy."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime, UTC

import config
from settings import get_setting

_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def _month_path(year: int, month: str) -> str:
    return os.path.join(config.RAIZ, str(year), month)


def list_step0_options(year: int, month: str) -> dict:
    month_dir = _month_path(year, month)
    if not os.path.isdir(month_dir):
        return {"year": year, "month": month, "month_dir": month_dir, "maestro_files": [], "bd_candidates": []}

    maestro_files = sorted(
        [f for f in os.listdir(month_dir) if f.lower().endswith(".xlsx") and os.path.isfile(os.path.join(month_dir, f))]
    )
    root_files = sorted(
        [f for f in os.listdir(config.RAIZ) if f.lower().endswith(".xlsx") and os.path.isfile(os.path.join(config.RAIZ, f))]
    )
    bd_candidates = [f for f in root_files if "bd" in f.lower() or "docentes" in f.lower()]
    return {
        "year": year,
        "month": month,
        "month_dir": month_dir,
        "maestro_files": maestro_files,
        "bd_candidates": bd_candidates,
    }


def _run_step0_job(job_id: str, cmd: list[str], cwd: str, log_path: str) -> None:
    with open(log_path, "w", encoding="utf-8") as log_file:
        log_file.write(f"[{datetime.now(UTC).isoformat()}] START {' '.join(cmd)}\n")
        child_env = os.environ.copy()
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
            _JOBS[job_id]["pid"] = process.pid
        if process.stdout is not None:
            for line in process.stdout:
                log_file.write(line)
                log_file.flush()
        return_code = process.wait()
        finished = datetime.now(UTC).isoformat()
        with _JOBS_LOCK:
            _JOBS[job_id]["status"] = "success" if return_code == 0 else "failed"
            _JOBS[job_id]["return_code"] = return_code
            _JOBS[job_id]["finished_at"] = finished
        log_file.write(f"\n[{finished}] END return_code={return_code}\n")


def start_step0_job(*, year: int, month: str, maestro_file: str, bd_file: str, output_file: str | None = None) -> dict:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    month_dir = _month_path(year, month)
    maestro_path = os.path.join(month_dir, maestro_file)
    bd_path = os.path.join(config.RAIZ, bd_file)
    if not os.path.isfile(maestro_path):
        raise FileNotFoundError(f"No existe archivo maestro: {maestro_path}")
    if not os.path.isfile(bd_path):
        raise FileNotFoundError(f"No existe BD docentes: {bd_path}")

    state_root = get_setting("BH_RAIZ", os.getcwd())
    jobs_dir = os.path.join(state_root, ".state", "ops-jobs")
    os.makedirs(jobs_dir, exist_ok=True)
    job_id = uuid.uuid4().hex[:12]
    log_path = os.path.join(jobs_dir, f"{job_id}.log")
    script0 = os.path.join(repo_root, "etapas", "0.-generar_solicitud.py")
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        script0,
        "--mes",
        month,
        "--año",
        str(year),
        "--archivo-maestro",
        maestro_file,
        "--ruta-bd",
        bd_path,
    ]
    if output_file:
        cmd.extend(["--ruta-salida", os.path.join(month_dir, output_file)])
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "id": job_id,
            "type": "step0_generar_solicitud",
            "status": "running",
            "year": year,
            "month": month,
            "maestro_file": maestro_file,
            "bd_file": bd_file,
            "output_file": output_file or "Solicitud.xlsx",
            "created_at": datetime.now(UTC).isoformat(),
            "log_path": log_path,
            "pid": None,
            "return_code": None,
            "finished_at": None,
        }
    worker = threading.Thread(
        target=_run_step0_job,
        args=(job_id, cmd, repo_root, log_path),
        daemon=True,
    )
    worker.start()
    return _JOBS[job_id]


def get_job(job_id: str) -> dict | None:
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


def list_jobs(limit: int = 20) -> list[dict]:
    with _JOBS_LOCK:
        jobs = sorted(_JOBS.values(), key=lambda j: j["created_at"], reverse=True)
    return jobs[:limit]


def read_job_log(job_id: str, max_chars: int = 12000) -> str:
    job = get_job(job_id)
    if not job:
        return ""
    log_path = job.get("log_path")
    if not log_path or not os.path.isfile(log_path):
        return ""
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    if len(content) <= max_chars:
        return content
    return content[-max_chars:]


def get_step0_output_path(job_id: str) -> str | None:
    job = get_job(job_id)
    if not job:
        return None
    month_dir = _month_path(job["year"], job["month"])
    output_name = job.get("output_file") or "Solicitud.xlsx"
    path = os.path.join(month_dir, output_name)
    if not os.path.isfile(path):
        return None
    return path

