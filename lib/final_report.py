"""Consulta del informe final (hoja Resumen Boletas) por período."""
from __future__ import annotations

import glob
import json
import os
import re
from datetime import datetime
from typing import Any

import config
import ops_execution_history

_SHEET_CANDIDATES = ("Resumen Boletas", "Resumen de Boletas", "ResumenBoletas")
_COL_MAP = {
    "RUT": "rut",
    "Nombre Docente": "nombre_docente",
    "Reg empleo": "reg_empleo",
    "LOCATION": "location",
    "INS": "ins",
    "Nombre Sede": "nombre_sede",
    "N° Boleta": "numero_boleta",
    "Nº Boleta": "numero_boleta",
    "Tipo Doc": "tipo_doc",
    "Tipo de Pago": "tipo_pago",
    "Fecha emisión": "fecha_emision",
    "Fecha emision": "fecha_emision",
    "Monto Bruto": "monto_bruto",
}


def _month_dir(year: int | str, month: str) -> str:
    return os.path.join(config.RAIZ, str(year), str(month).strip())


def _parse_log_ts(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as f:
            line = f.readline().strip()
        if not line:
            return None
        row = json.loads(line)
        ts = row.get("ts")
        if ts:
            return str(ts)
    except (OSError, json.JSONDecodeError):
        pass
    m = re.search(r"informe_(\d{8})_(\d{6})", os.path.basename(path))
    if not m:
        return None
    d, t = m.group(1), m.group(2)
    try:
        dt = datetime(
            int(d[0:4]),
            int(d[4:6]),
            int(d[6:8]),
            int(t[0:2]),
            int(t[2:4]),
            int(t[4:6]),
        )
        return dt.isoformat()
    except ValueError:
        return None


def _generation_timestamp(year: int | str, month: str) -> tuple[str | None, str | None]:
    month_dir = _month_dir(year, month)
    best_ts: str | None = None
    best_source: str | None = None

    log_dir = os.path.join(month_dir, "logs_informe")
    if os.path.isdir(log_dir):
        for path in sorted(glob.glob(os.path.join(log_dir, "informe_*.jsonl")), reverse=True):
            ts = _parse_log_ts(path)
            if ts and (not best_ts or ts > best_ts):
                best_ts = ts
                best_source = "logs_informe"

    last = ops_execution_history.last_executions_by_stage(int(year), str(month)).get(6)
    if last:
        ts = str(last.get("finished_at") or last.get("created_at") or "")
        if ts and (not best_ts or ts > best_ts):
            best_ts = ts
            best_source = "execution_history"

    solicitud = os.path.join(month_dir, "Solicitud.xlsx")
    if os.path.isfile(solicitud):
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(solicitud)).isoformat(timespec="seconds")
            if not best_ts or mtime > best_ts:
                best_ts = mtime
                if not best_source:
                    best_source = "excel_mtime"
        except OSError:
            pass

    return best_ts, best_source


def _normalize_row(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for src, dst in _COL_MAP.items():
        if src in raw:
            val = raw.get(src)
            if val is None or str(val).strip().lower() in {"", "nan", "none"}:
                out[dst] = ""
            else:
                out[dst] = val
    if "monto_bruto" in out:
        try:
            out["monto_bruto"] = int(float(out["monto_bruto"]))
        except (TypeError, ValueError):
            out["monto_bruto"] = str(out["monto_bruto"])
    if "numero_boleta" in out:
        try:
            out["numero_boleta"] = str(int(float(out["numero_boleta"])))
        except (TypeError, ValueError):
            out["numero_boleta"] = str(out["numero_boleta"] or "").strip()
    return out


def _read_resumen_sheet(path: str) -> tuple[list[dict[str, Any]], str | None]:
    import pandas as pd

    xl = pd.ExcelFile(path, engine="openpyxl")
    sheet = next((s for s in xl.sheet_names if s.strip().lower() in {c.lower() for c in _SHEET_CANDIDATES}), None)
    if not sheet:
        return [], None
    df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
    rows = [_normalize_row(dict(r)) for r in df.to_dict(orient="records")]
    return rows, sheet


def period_final_report(year: int | str, month: str) -> dict[str, Any]:
    """Devuelve el informe final persistido para un período.

    Orden: snapshot PostgreSQL → freeze en disco (si cerrado) → Excel.
    """
    month_name = str(month).strip()
    year_int = int(year)

    try:
        import period_snapshots

        db_snap = period_snapshots.load_informe_snapshot(year_int, month_name)
        if db_snap and db_snap.get("exists") and db_snap.get("rows"):
            return db_snap
    except Exception:
        pass

    try:
        from period_close import load_frozen_informe
        from period_policy import get_period_status, is_closed_status

        frozen = load_frozen_informe(year_int, month_name)
        if frozen and is_closed_status(get_period_status(year_int, month_name)):
            return frozen
        # Si hay freeze aunque esté reabierto, anexamos metadata sin forzar.
    except Exception:
        frozen = None

    month_dir = _month_dir(year_int, month_name)
    solicitud = os.path.join(month_dir, "Solicitud.xlsx")
    generated_at, generated_at_source = _generation_timestamp(year_int, month_name)

    out: dict[str, Any] = {
        "year": year_int,
        "month": month_name,
        "exists": False,
        "frozen": False,
        "generated_at": generated_at,
        "generated_at_source": generated_at_source,
        "sheet_name": None,
        "source_file": solicitud if os.path.isfile(solicitud) else None,
        "source": "excel" if os.path.isfile(solicitud) else None,
        "total_rows": 0,
        "total_monto": 0,
        "rows": [],
        "read_error": None,
    }

    if not os.path.isfile(solicitud):
        if frozen:
            return frozen
        out["read_error"] = "Aún no se ha generado el informe final para este período."
        return out

    try:
        rows, sheet = _read_resumen_sheet(solicitud)
    except Exception as exc:
        out["read_error"] = f"No se pudo leer el informe: {exc}"
        return out

    if not sheet:
        if frozen:
            return frozen
        out["read_error"] = "No existe la hoja «Resumen Boletas». Ejecuta el paso 6."
        return out

    out["exists"] = True
    out["sheet_name"] = sheet
    out["rows"] = rows
    out["total_rows"] = len(rows)
    total_monto = 0
    for row in rows:
        m = row.get("monto_bruto")
        try:
            total_monto += int(float(m))
        except (TypeError, ValueError):
            continue
    out["total_monto"] = total_monto
    if frozen:
        out["frozen_at"] = frozen.get("frozen_at")
        out["previous_freeze"] = True
    return out
