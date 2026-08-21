"""Proyector idempotente por período: DataFrame -> estado canónico en DB."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

from db import boleta_repository, file_repository
from db.key_builder import build_boleta_key
from db.state_projection import (
    classify_mail_recepcion_status,
    classify_recepcion_status,
    classify_xml_status,
)


def project_solicitud_rows(
    *,
    year: int,
    month_num: int,
    month_name: str,
    rows: Iterable[dict[str, Any]],
) -> dict[str, int]:
    periodo_id = file_repository.get_or_create_periodo(
        anio=year,
        mes_num=month_num,
        mes_nombre=month_name,
    )
    if periodo_id is None:
        return {"projected": 0, "failed": 0}

    projected = 0
    failed = 0
    for row in rows:
        recepcion_status, reason, glosa_mode = classify_recepcion_status(row)
        xml_status = classify_xml_status(row)
        mail_recepcion_status = classify_mail_recepcion_status(row)
        ok = boleta_repository.upsert_boleta_recepcion(
            periodo_id=periodo_id,
            boleta_key=build_boleta_key(row),
            emplid=str(row.get("EMPLID", "")).strip() or None,
            rut_sin_dv=str(row.get("RUT_SIN_DV", "")).strip() or None,
            rut_razon=str(row.get("RUT RAZON", "")).strip() or None,
            estado_recepcion=str(row.get("Estado_Recepcion", "")).strip() or None,
            observaciones_recepcion=str(row.get("Observaciones", "")).strip() or None,
            glosa=str(row.get("GLOSA", "")).strip() or None,
            monto_bruto=row.get("CUS_TOT_HON", None),
            archivo_xml=str(row.get("archivo_xml", "")).strip() or None,
            recepcion_status=recepcion_status,
            xml_status=xml_status,
            mail_recepcion_status=mail_recepcion_status,
            glosa_match_mode=glosa_mode,
            effective_status_reason=reason,
            solicitud_row=row,
            empl_rcd=str(row.get("EMPL_RCD", "")).strip() or None,
        )
        if ok:
            projected += 1
        else:
            failed += 1
    return {"projected": projected, "failed": failed}


def project_dataframe(
    *,
    year: int,
    month_num: int,
    month_name: str,
    df: pd.DataFrame,
) -> dict[str, int]:
    if df is None or df.empty:
        return {"projected": 0, "failed": 0}
    rows = [r.to_dict() for _, r in df.iterrows()]
    return project_solicitud_rows(
        year=year,
        month_num=month_num,
        month_name=month_name,
        rows=rows,
    )
