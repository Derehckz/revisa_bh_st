"""Historial de ejecuciones desde jobs API y logs en carpetas año/mes."""
from __future__ import annotations

import glob
import hashlib
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

import config

# Carpeta relativa al mes → paso(s) del pipeline
_DIR_STAGE_RULES: list[tuple[str, int | tuple[int, ...]]] = [
    ("logs_envios", 1),
    ("logs_extraccion", 2),
    ("logs_revision", 3),
    ("logs_extraccion_xml_excel", 4),
    ("logs_envio_recepcion", 5),
    ("logs_informe", 6),
    ("logs_envios_pagos", 7),
    ("logs_separa", 8),
    ("logs_agrupa", 9),
    ("logs_cierre", "cierre"),  # rango en nombre de archivo
]

_TS_RE = re.compile(r"(?:^|_)(\d{8})_(\d{6})")
_CIERRE_RE = re.compile(r"cierre_([\d\-]+)_(\d{8})_(\d{6})")


def _month_index(name: str) -> int:
    try:
        return config.MESES_ES.index(name) + 1
    except ValueError:
        return 0


def _months_in_range(year: int, from_month: str, to_month: str) -> list[str]:
    i0 = _month_index(from_month)
    i1 = _month_index(to_month)
    if i0 < 1 or i1 < 1:
        return []
    if i0 > i1:
        i0, i1 = i1, i0
    return config.MESES_ES[i0 - 1 : i1]


def _parse_ts_from_name(filename: str) -> Optional[str]:
    m = _TS_RE.search(filename)
    if not m:
        return None
    d, t = m.group(1), m.group(2)
    try:
        dt = datetime(
            int(d[0:4]), int(d[4:6]), int(d[6:8]),
            int(t[0:2]), int(t[2:4]), int(t[4:6]),
            tzinfo=timezone.utc,
        )
        return dt.isoformat()
    except ValueError:
        return None


_API_NOISE_RE = re.compile(r"api\.request|api\.access|\"message\":\s*\"api\.request\"")
_STAGE_SUCCESS_MARKERS = (
    "return_code=0",
    "completado",
    "exitos",
    "sin errores",
    "outcome_send outcome=ok",
    "outcome=ok",
    "excel guardado",
    "correo (",
)


def _read_log_sample(path: str, max_bytes: int = 80_000) -> str:
    try:
        size = os.path.getsize(path)
        with open(path, encoding="utf-8", errors="replace") as f:
            if size <= max_bytes:
                return f.read()
            head = f.read(max_bytes // 2)
            f.seek(max(0, size - max_bytes // 2))
            return head + "\n" + f.read()
    except OSError:
        return ""


def _stage_log_body(text: str) -> str:
    """Quita tráfico HTTP de la API que a veces se filtra al log del paso."""
    lines = [ln for ln in text.splitlines() if ln.strip() and not _API_NOISE_RE.search(ln)]
    return "\n".join(lines)


def _infer_status_from_log(path: str) -> Optional[str]:
    """None = el archivo no evidencia una ejecución del paso (no marcar OK)."""
    body = _stage_log_body(_read_log_sample(path))
    if not body.strip():
        return None
    low = body.lower()
    if any(marker in low for marker in _STAGE_SUCCESS_MARKERS):
        return "success"
    if re.search(r"return_code=(?!0)\d+", low) or "traceback" in low:
        return "failed"
    if "finaliz" in low and "error" not in low[-500:]:
        return "success"
    return None


def _stable_id(*parts: str) -> str:
    h = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"hist_{h}"


def _stage_from_cierre_filename(name: str) -> list[int]:
    m = _CIERRE_RE.match(name)
    if not m:
        return []
    spec = m.group(1)
    if "-" in spec:
        a, b = spec.split("-", 1)
        try:
            return list(range(int(a), int(b) + 1))
        except ValueError:
            return []
    try:
        return [int(spec)]
    except ValueError:
        return []


def _scan_log_file(
    *,
    path: str,
    year: int,
    month: str,
    stage_num: int,
    label: str,
) -> dict[str, Any] | None:
    status = _infer_status_from_log(path)
    if not status:
        return None
    name = os.path.basename(path)
    created = _parse_ts_from_name(name)
    if not created:
        created = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).isoformat()
    eid = _stable_id(str(year), month, str(stage_num), path)
    return {
        "id": eid,
        "source": "filesystem",
        "stage_num": stage_num,
        "status": status,
        "year": year,
        "month": month,
        "type": label,
        "created_at": created,
        "finished_at": created,
        "log_path": path,
        "label": f"Paso {stage_num} — {label}",
        "pid": None,
        "return_code": 0 if status == "success" else 1,
    }


def _maybe_append(entries: list[dict[str, Any]], entry: dict[str, Any] | None) -> None:
    if entry:
        entries.append(entry)


def scan_month_logs(year: int, month: str) -> list[dict[str, Any]]:
    month_dir = os.path.join(config.RAIZ, str(year), month)
    if not os.path.isdir(month_dir):
        return []

    entries: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for dir_name, stage_rule in _DIR_STAGE_RULES:
        if stage_rule == "cierre":
            cierre_dir = os.path.join(month_dir, dir_name)
            if not os.path.isdir(cierre_dir):
                continue
            for path in glob.glob(os.path.join(cierre_dir, "cierre_*")):
                if not os.path.isfile(path) or path in seen_paths:
                    continue
                seen_paths.add(path)
                name = os.path.basename(path)
                stages = _stage_from_cierre_filename(name)
                if not stages:
                    stages = [0]
                for sn in stages:
                    _maybe_append(
                        entries,
                        _scan_log_file(
                            path=path,
                            year=year,
                            month=month,
                            stage_num=sn,
                            label=f"cierre ({name})",
                        ),
                    )
            continue

        base = os.path.join(month_dir, dir_name)
        if not os.path.isdir(base):
            continue
        sn = int(stage_rule)  # type: ignore[arg-type]

        # Archivos con timestamp en el nombre
        for path in glob.glob(os.path.join(base, "*")):
            if not os.path.isfile(path) or path in seen_paths:
                continue
            bn = os.path.basename(path).lower()
            if bn.endswith((".log", ".txt", ".jsonl")):
                if _parse_ts_from_name(os.path.basename(path)) or sn in (1, 5, 7):
                    seen_paths.add(path)
                    _maybe_append(
                        entries,
                        _scan_log_file(
                            path=path,
                            year=year,
                            month=month,
                            stage_num=sn,
                            label=os.path.basename(path),
                        ),
                    )

        # Logs “rolling” sin fecha en nombre (un registro por archivo/mes)
        for rolling in ("envio_boletas.log", "envio_recepcion.log", "envio_pagos.log"):
            path = os.path.join(base, rolling)
            if os.path.isfile(path) and path not in seen_paths:
                seen_paths.add(path)
                _maybe_append(
                    entries,
                    _scan_log_file(
                        path=path,
                        year=year,
                        month=month,
                        stage_num=sn,
                        label=rolling,
                    ),
                )

    # Paso 10: reportes de revisión
    reporte_dir = os.path.join(month_dir, "reporte_avance")
    for path in glob.glob(os.path.join(reporte_dir, "reporte_revision_*.txt")):
        if os.path.isfile(path) and path not in seen_paths:
            seen_paths.add(path)
            _maybe_append(
                entries,
                _scan_log_file(
                    path=path,
                    year=year,
                    month=month,
                    stage_num=10,
                    label=os.path.basename(path),
                ),
            )
    rev_xlsx = os.path.join(month_dir, "revision_carpetas.xlsx")
    if os.path.isfile(rev_xlsx) and rev_xlsx not in seen_paths:
        seen_paths.add(rev_xlsx)
        created = datetime.fromtimestamp(os.path.getmtime(rev_xlsx), tz=timezone.utc).isoformat()
        entries.append(
            {
                "id": _stable_id(str(year), month, "10", rev_xlsx),
                "source": "filesystem",
                "stage_num": 10,
                "status": "success",
                "year": year,
                "month": month,
                "type": "revision_carpetas.xlsx",
                "created_at": created,
                "finished_at": created,
                "log_path": rev_xlsx,
                "label": "Paso 10 — revision_carpetas.xlsx",
                "pid": None,
                "return_code": 0,
                "artifact_path": rev_xlsx,
            }
        )

    return entries


def _execution_summary(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entry["id"],
        "status": entry.get("status", "unknown"),
        "created_at": entry.get("created_at"),
        "finished_at": entry.get("finished_at"),
        "source": entry.get("source", "filesystem"),
        "label": entry.get("label"),
        "log_path": entry.get("log_path"),
    }


def _api_job_summary(job: dict[str, Any]) -> dict[str, Any]:
    sn = job.get("stage_num", 0)
    return {
        "id": job["id"],
        "status": job.get("status", "unknown"),
        "created_at": job.get("created_at"),
        "finished_at": job.get("finished_at"),
        "source": "api",
        "label": f"Paso {sn} — web",
        "log_path": job.get("log_path"),
    }


def last_executions_by_stage(
    year: int,
    month: str,
    api_jobs: list[dict[str, Any]] | None = None,
) -> dict[int, dict[str, Any]]:
    """Última ejecución conocida por paso (jobs API + logs del mes)."""
    by_stage: dict[int, dict[str, Any]] = {}

    period_jobs = [
        j
        for j in (api_jobs or [])
        if str(j.get("year")) == str(year) and str(j.get("month")) == month
    ]
    for job in period_jobs:
        try:
            sn = int(job.get("stage_num", -1))
        except (TypeError, ValueError):
            continue
        if sn < 0:
            continue
        summary = _api_job_summary(job)
        cur = by_stage.get(sn)
        if not cur or (summary.get("created_at") or "") > (cur.get("created_at") or ""):
            by_stage[sn] = summary

    for entry in scan_month_logs(year, month):
        try:
            sn = int(entry.get("stage_num", -1))
        except (TypeError, ValueError):
            continue
        if sn < 0:
            continue
        summary = _execution_summary(entry)
        cur = by_stage.get(sn)
        if not cur or (summary.get("created_at") or "") > (cur.get("created_at") or ""):
            by_stage[sn] = summary

    return by_stage


def merge_api_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for j in jobs:
        out.append(
            {
                "id": j["id"],
                "source": "api",
                "stage_num": j.get("stage_num", 0),
                "status": j.get("status", "unknown"),
                "year": j.get("year"),
                "month": j.get("month"),
                "type": j.get("type", ""),
                "created_at": j.get("created_at"),
                "finished_at": j.get("finished_at"),
                "log_path": j.get("log_path"),
                "label": f"Paso {j.get('stage_num', 0)} — API",
                "pid": j.get("pid"),
                "return_code": j.get("return_code"),
            }
        )
    return out


def list_execution_history(
    *,
    year: int,
    from_month: str,
    to_month: str,
    api_jobs: list[dict[str, Any]] | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    months = _months_in_range(year, from_month, to_month)
    fs_entries: list[dict[str, Any]] = []
    for month in months:
        fs_entries.extend(scan_month_logs(year, month))

    api_entries = merge_api_jobs(api_jobs or [])
    # Preferir jobs API si comparten log_path con histórico
    api_paths = {e.get("log_path") for e in api_entries if e.get("log_path")}
    merged = list(api_entries)
    for e in fs_entries:
        if e.get("log_path") and e["log_path"] in api_paths:
            continue
        merged.append(e)

    merged.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    total = len(merged)
    merged = merged[:limit]

    by_month: dict[str, int] = {}
    for e in merged:
        key = f"{e.get('month')} {e.get('year')}"
        by_month[key] = by_month.get(key, 0) + 1

    return {
        "year": year,
        "from_month": from_month,
        "to_month": to_month,
        "total": total,
        "returned": len(merged),
        "by_month": [{"period": k, "count": v} for k, v in sorted(by_month.items())],
        "data": merged,
    }


def read_history_log(entry_id: str, entries: list[dict[str, Any]], max_chars: int = 50000) -> str:
    entry = next((e for e in entries if e["id"] == entry_id), None)
    if not entry:
        return ""
    path = entry.get("log_path")
    if not path or not os.path.isfile(path):
        return ""
    root = os.path.abspath(config.RAIZ)
    abspath = os.path.abspath(path)
    if not (abspath == root or abspath.startswith(root + os.sep)):
        return ""
    with open(abspath, encoding="utf-8", errors="replace") as f:
        content = f.read()
    if len(content) <= max_chars:
        return content
    return content[-max_chars:]
