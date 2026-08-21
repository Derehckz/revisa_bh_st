"""Cierre de período e informe congelado."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import UTC, datetime
from typing import Any

import config
import final_report
import monthly_checklist
from db import audit
from db.models import Periodo
from db.session import SessionLocal
from period_policy import is_closed_status
from sqlalchemy import select


def _month_dir(year: int, month: str) -> str:
    return os.path.join(config.RAIZ, str(year), str(month).strip())


def _freeze_dir(year: int, month: str) -> str:
    return os.path.join(_month_dir(year, month), "informe_congelado")


def freeze_informe(
    year: int,
    month: str,
    *,
    operator: str | None = None,
    closed_at: str | None = None,
) -> dict[str, Any]:
    """Persiste snapshot inmutable del informe final del período."""
    month_norm = str(month).strip().capitalize()
    year_int = int(year)

    # Leer Excel fresco (no snapshot DB) para congelar el estado real al cerrar.
    import period_snapshots

    payload = period_snapshots.build_informe_payload_from_excel(year_int, month_norm)
    if not payload or not payload.get("rows"):
        # Fallback: report API (puede venir de freeze previo / Excel)
        report = final_report.period_final_report(year_int, month_norm)
        if not report.get("exists"):
            raise ValueError(report.get("read_error") or "No hay informe final para congelar.")
        payload = {
            "year": year_int,
            "month": month_norm,
            "generated_at": report.get("generated_at"),
            "total_rows": report.get("total_rows"),
            "total_monto": report.get("total_monto"),
            "sheet_name": report.get("sheet_name"),
            "rows": report.get("rows") or [],
        }
        excel_src = report.get("source_file")
    else:
        excel_src = os.path.join(_month_dir(year_int, month_norm), "Solicitud.xlsx")

    dest = _freeze_dir(year_int, month_norm)
    os.makedirs(dest, exist_ok=True)
    rows_path = os.path.join(dest, "informe_rows.json")
    meta_path = os.path.join(dest, "meta.json")
    excel_dst = os.path.join(dest, f"Informe_Final_{year_int}_{month_norm}.xlsx")

    with open(rows_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    if excel_src and os.path.isfile(excel_src):
        try:
            shutil.copy2(excel_src, excel_dst)
        except OSError:
            excel_dst = ""

    now = closed_at or datetime.now(UTC).isoformat()
    meta = {
        "year": year_int,
        "month": month_norm,
        "frozen_at": now,
        "frozen_by": operator,
        "generated_at": payload.get("generated_at"),
        "total_rows": payload.get("total_rows"),
        "total_monto": payload.get("total_monto"),
        "sha256": digest,
        "rows_path": rows_path,
        "excel_path": excel_dst if excel_dst and os.path.isfile(excel_dst) else None,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # Persistencia primaria en PostgreSQL (disco queda como backup).
    try:
        now_dt = datetime.fromisoformat(now.replace("Z", "+00:00")) if isinstance(now, str) else datetime.now(UTC)
        period_snapshots.save_informe_snapshot(
            year_int,
            month_norm,
            payload,
            frozen_at=now_dt,
            mark_frozen=True,
        )
        pagos_payload = period_snapshots.build_pagos_payload_from_excel(year_int, month_norm)
        if not pagos_payload:
            existing = period_snapshots.load_pagos_snapshot(year_int, month_norm)
            if existing and existing.get("rows") is not None:
                pagos_payload = {
                    "year": year_int,
                    "month": month_norm,
                    "generated_at": existing.get("generated_at"),
                    "total_rows": existing.get("total_rows"),
                    "source": existing.get("source") or "db",
                    "rows": existing.get("rows") or [],
                }
        if pagos_payload:
            period_snapshots.save_pagos_snapshot(
                year_int,
                month_norm,
                pagos_payload,
                frozen_at=now_dt,
                mark_frozen=True,
            )
            meta["pagos_rows"] = pagos_payload.get("total_rows")
    except Exception as exc:
        meta["db_snapshot_error"] = str(exc)

    return meta


def load_frozen_informe(year: int | str, month: str) -> dict[str, Any] | None:
    month_norm = str(month).strip().capitalize()
    year_int = int(year)
    meta_path = os.path.join(_freeze_dir(year_int, month_norm), "meta.json")
    rows_path = os.path.join(_freeze_dir(year_int, month_norm), "informe_rows.json")
    if not os.path.isfile(meta_path) or not os.path.isfile(rows_path):
        return None
    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        with open(rows_path, encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return {
        "year": year_int,
        "month": month_norm,
        "exists": True,
        "frozen": True,
        "generated_at": payload.get("generated_at") or meta.get("generated_at"),
        "generated_at_source": "frozen",
        "frozen_at": meta.get("frozen_at"),
        "frozen_by": meta.get("frozen_by"),
        "sheet_name": payload.get("sheet_name") or "Resumen Boletas",
        "source_file": meta.get("excel_path"),
        "total_rows": int(payload.get("total_rows") or len(payload.get("rows") or [])),
        "total_monto": int(payload.get("total_monto") or 0),
        "rows": payload.get("rows") or [],
        "read_error": None,
        "sha256": meta.get("sha256"),
    }


def close_period(year: int, month: str, *, operator: str | None = None, force: bool = False) -> dict[str, Any]:
    month_norm = str(month).strip().capitalize()
    year_int = int(year)
    checklist = monthly_checklist.monthly_checklist(year_int, month_norm)
    if checklist.get("closed"):
        raise ValueError(f"El período {month_norm} {year_int} ya está cerrado.")
    if not force and not checklist.get("can_close"):
        blockers = [i["label"] for i in checklist.get("items") or [] if i.get("status") == "block"]
        raise ValueError(
            "No se puede cerrar: " + (", ".join(blockers) if blockers else "checklist incompleto")
        )

    now = datetime.now(UTC)
    freeze_meta = freeze_informe(
        year_int,
        month_norm,
        operator=operator,
        closed_at=now.isoformat(),
    )

    with SessionLocal() as session:
        periodo = session.execute(
            select(Periodo).where(Periodo.anio == year_int, Periodo.mes_nombre == month_norm)
        ).scalar_one_or_none()
        if periodo is None:
            raise ValueError(f"Período no existe: {year_int}-{month_norm}")
        periodo.estado = "cerrado"
        periodo.closed_at = now
        periodo.closed_by = (operator or "").strip() or None
        periodo.informe_frozen_at = now
        session.commit()

    audit.record_event(
        action="period.close",
        operator=operator,
        period_year=year_int,
        period_month=month_norm,
        entity="periodo",
        detail={"freeze": freeze_meta, "checklist_warns": checklist.get("warn_count")},
    )
    return {
        "ok": True,
        "year": year_int,
        "month": month_norm,
        "status": "cerrado",
        "closed_at": now.isoformat(),
        "closed_by": operator,
        "freeze": freeze_meta,
        "checklist": checklist,
    }


def reopen_period(year: int, month: str, *, operator: str | None = None) -> dict[str, Any]:
    month_norm = str(month).strip().capitalize()
    year_int = int(year)
    with SessionLocal() as session:
        periodo = session.execute(
            select(Periodo).where(Periodo.anio == year_int, Periodo.mes_nombre == month_norm)
        ).scalar_one_or_none()
        if periodo is None:
            raise ValueError(f"Período no existe: {year_int}-{month_norm}")
        if not is_closed_status(periodo.estado):
            raise ValueError(f"El período {month_norm} {year_int} no está cerrado.")
        periodo.estado = "abierto"
        # Conservamos closed_at/informe_frozen_at históricos como rastro; el estado manda.
        session.commit()

    audit.record_event(
        action="period.reopen",
        operator=operator,
        period_year=year_int,
        period_month=month_norm,
        entity="periodo",
    )
    return {
        "ok": True,
        "year": year_int,
        "month": month_norm,
        "status": "abierto",
        "reopened_by": operator,
    }
