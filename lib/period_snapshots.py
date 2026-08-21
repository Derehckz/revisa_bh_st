"""Snapshots de informe final y pagos en PostgreSQL (lectura histórica SoT)."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

import config
from db.models import Periodo
from db.session import SessionLocal


def _month_norm(month: str) -> str:
    return str(month).strip().capitalize()


def _get_periodo(session, year: int, month: str) -> Periodo | None:
    return session.execute(
        select(Periodo).where(Periodo.anio == int(year), Periodo.mes_nombre == _month_norm(month))
    ).scalar_one_or_none()


def _sha256_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_informe_payload_from_excel(year: int | str, month: str) -> dict[str, Any] | None:
    """Lee Resumen Boletas desde Excel (sin pasar por period_final_report para evitar ciclos)."""
    import final_report

    month_n = _month_norm(month)
    year_int = int(year)
    path = os.path.join(config.RAIZ, str(year_int), month_n, "Solicitud.xlsx")
    if not os.path.isfile(path):
        return None
    try:
        rows, sheet = final_report._read_resumen_sheet(path)
    except Exception:
        return None
    if not sheet:
        return None
    safe_rows = [{k: _json_safe(v) for k, v in row.items()} for row in rows]
    total_monto = 0
    for row in safe_rows:
        try:
            total_monto += int(float(row.get("monto_bruto") or 0))
        except (TypeError, ValueError):
            continue
    generated_at, _ = final_report._generation_timestamp(year_int, month_n)
    return {
        "year": year_int,
        "month": month_n,
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "total_rows": len(safe_rows),
        "total_monto": total_monto,
        "sheet_name": sheet,
        "rows": safe_rows,
    }


def build_informe_payload_from_freeze(year: int | str, month: str) -> dict[str, Any] | None:
    import period_close

    frozen = period_close.load_frozen_informe(year, month)
    if not frozen or not frozen.get("exists"):
        return None
    rows = frozen.get("rows") or []
    safe_rows = [{k: _json_safe(v) for k, v in dict(row).items()} for row in rows]
    return {
        "year": int(year),
        "month": _month_norm(month),
        "generated_at": frozen.get("generated_at"),
        "total_rows": frozen.get("total_rows") or len(safe_rows),
        "total_monto": frozen.get("total_monto") or 0,
        "sheet_name": frozen.get("sheet_name") or "Resumen Boletas",
        "rows": safe_rows,
    }


def _json_safe(val: Any) -> Any:
    if val is None:
        return ""
    if isinstance(val, (str, int, bool)):
        return val
    if isinstance(val, float):
        if val != val:  # NaN
            return ""
        return int(val) if val == int(val) else val
    # pandas / numpy
    try:
        import pandas as pd

        if isinstance(val, pd.Timestamp):
            if pd.isna(val):
                return ""
            return val.isoformat()
        if pd.isna(val):
            return ""
    except Exception:
        pass
    if hasattr(val, "item"):
        try:
            return _json_safe(val.item())
        except Exception:
            pass
    s = str(val).strip()
    return "" if s.lower() in {"nan", "none", "nat", "natype"} else s


def pagos_rows_from_dataframe(df) -> list[dict[str, Any]]:
    """Normaliza filas de hoja Pagos a dicts JSON-serializables."""
    rows: list[dict[str, Any]] = []
    if df is None or getattr(df, "empty", True):
        return rows
    for _, row in df.iterrows():
        item: dict[str, Any] = {}
        for col in df.columns:
            key = str(col).strip()
            if not key or key.lower().startswith("unnamed"):
                continue
            item[key] = _json_safe(row.get(col))
        rows.append(item)
    return rows


def build_pagos_payload_from_excel(year: int | str, month: str) -> dict[str, Any] | None:
    import pandas as pd

    month_n = _month_norm(month)
    year_int = int(year)
    path = os.path.join(config.RAIZ, str(year_int), month_n, "Solicitud.xlsx")
    if not os.path.isfile(path):
        return None
    try:
        with pd.ExcelFile(path, engine="openpyxl") as xl:
            if "Pagos" not in xl.sheet_names:
                return None
        df = pd.read_excel(path, sheet_name="Pagos", engine="openpyxl")
    except Exception:
        return None
    rows = pagos_rows_from_dataframe(df)
    return {
        "year": year_int,
        "month": month_n,
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": len(rows),
        "source": "excel_pagos_sheet",
        "rows": rows,
    }


def build_pagos_payload_from_df(
    year: int | str,
    month: str,
    df,
    *,
    source: str = "pagos_df",
) -> dict[str, Any]:
    rows = pagos_rows_from_dataframe(df)
    return {
        "year": int(year),
        "month": _month_norm(month),
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": len(rows),
        "source": source,
        "rows": rows,
    }


def save_informe_snapshot(
    year: int | str,
    month: str,
    payload: dict[str, Any],
    *,
    frozen_at: datetime | None = None,
    mark_frozen: bool = False,
) -> dict[str, Any]:
    month_n = _month_norm(month)
    year_int = int(year)
    digest = _sha256_payload(payload)
    with SessionLocal() as session:
        periodo = _get_periodo(session, year_int, month_n)
        if periodo is None:
            raise ValueError(f"Período no existe en DB: {year_int}-{month_n}")
        periodo.informe_snapshot = payload
        periodo.informe_sha256 = digest
        if mark_frozen or frozen_at is not None:
            periodo.informe_frozen_at = frozen_at or datetime.now(UTC)
        session.commit()
    return {"ok": True, "sha256": digest, "total_rows": payload.get("total_rows"), "year": year_int, "month": month_n}


def save_pagos_snapshot(
    year: int | str,
    month: str,
    payload: dict[str, Any],
    *,
    frozen_at: datetime | None = None,
    mark_frozen: bool = False,
) -> dict[str, Any]:
    month_n = _month_norm(month)
    year_int = int(year)
    with SessionLocal() as session:
        periodo = _get_periodo(session, year_int, month_n)
        if periodo is None:
            raise ValueError(f"Período no existe en DB: {year_int}-{month_n}")
        periodo.pagos_snapshot = payload
        if mark_frozen or frozen_at is not None:
            periodo.pagos_frozen_at = frozen_at or datetime.now(UTC)
        session.commit()
    return {"ok": True, "total_rows": payload.get("total_rows"), "year": year_int, "month": month_n}


def load_informe_snapshot(year: int | str, month: str) -> dict[str, Any] | None:
    month_n = _month_norm(month)
    year_int = int(year)
    try:
        with SessionLocal() as session:
            periodo = _get_periodo(session, year_int, month_n)
            if periodo is None or not periodo.informe_snapshot:
                return None
            payload = dict(periodo.informe_snapshot)
            return {
                "year": year_int,
                "month": month_n,
                "exists": True,
                "frozen": bool(periodo.informe_frozen_at),
                "frozen_at": periodo.informe_frozen_at.isoformat() if periodo.informe_frozen_at else None,
                "generated_at": payload.get("generated_at"),
                "generated_at_source": "db_snapshot",
                "sheet_name": payload.get("sheet_name") or "Resumen Boletas",
                "source_file": None,
                "source": "postgresql",
                "total_rows": int(payload.get("total_rows") or len(payload.get("rows") or [])),
                "total_monto": int(payload.get("total_monto") or 0),
                "rows": payload.get("rows") or [],
                "read_error": None,
                "sha256": periodo.informe_sha256,
                "period_status": periodo.estado,
            }
    except Exception:
        return None


def load_pagos_snapshot(year: int | str, month: str) -> dict[str, Any] | None:
    month_n = _month_norm(month)
    year_int = int(year)
    try:
        with SessionLocal() as session:
            periodo = _get_periodo(session, year_int, month_n)
            if periodo is None or not periodo.pagos_snapshot:
                return None
            payload = dict(periodo.pagos_snapshot)
            rows = payload.get("rows") or []
            return {
                "year": year_int,
                "month": month_n,
                "exists": True,
                "frozen": bool(periodo.pagos_frozen_at),
                "frozen_at": periodo.pagos_frozen_at.isoformat() if periodo.pagos_frozen_at else None,
                "generated_at": payload.get("generated_at"),
                "source": payload.get("source") or "postgresql",
                "source_kind": "postgresql",
                "total_rows": int(payload.get("total_rows") or len(rows)),
                "rows": rows,
                "read_error": None,
                "period_status": periodo.estado,
            }
    except Exception:
        return None


def refresh_informe_from_excel(year: int | str, month: str) -> dict[str, Any] | None:
    payload = build_informe_payload_from_excel(year, month)
    if not payload:
        return None
    try:
        return save_informe_snapshot(year, month, payload, mark_frozen=False)
    except ValueError:
        return None


def refresh_pagos_from_excel(year: int | str, month: str) -> dict[str, Any] | None:
    payload = build_pagos_payload_from_excel(year, month)
    if not payload:
        return None
    try:
        return save_pagos_snapshot(year, month, payload, mark_frozen=False)
    except ValueError:
        return None


def sync_snapshots_for_period(year: int | str, month: str, *, prefer_freeze: bool = True) -> dict[str, Any]:
    """Backfill/sync: informe (freeze o Excel) + pagos (Excel)."""
    out: dict[str, Any] = {"year": int(year), "month": _month_norm(month), "informe": None, "pagos": None}
    informe_payload = None
    if prefer_freeze:
        informe_payload = build_informe_payload_from_freeze(year, month)
    if not informe_payload:
        informe_payload = build_informe_payload_from_excel(year, month)
    if informe_payload:
        mark = prefer_freeze and build_informe_payload_from_freeze(year, month) is not None
        try:
            out["informe"] = save_informe_snapshot(
                year, month, informe_payload, mark_frozen=mark
            )
        except ValueError as exc:
            out["informe"] = {"ok": False, "error": str(exc)}
    pagos_payload = build_pagos_payload_from_excel(year, month)
    if pagos_payload:
        try:
            out["pagos"] = save_pagos_snapshot(year, month, pagos_payload, mark_frozen=False)
        except ValueError as exc:
            out["pagos"] = {"ok": False, "error": str(exc)}
    return out
