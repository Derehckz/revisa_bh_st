"""Política de recordatorios para script 1 (reutilizable y testeable)."""
from __future__ import annotations

from typing import Any

import pandas as pd

def parse_recordatorio_count(value: Any) -> int:
    try:
        if pd.isna(value):
            return 0
        as_int = int(float(str(value).strip()))
        return max(0, as_int)
    except (TypeError, ValueError):
        return 0


def _estado_norm(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().str.strip()


def indices_recordatorio(
    df: pd.DataFrame,
    columna_estado: str,
    columna_recordatorios: str,
    *,
    force_resend: bool,
) -> pd.Index:
    """Filas elegibles para recordatorio según estado NO RECIBIDO."""
    estado_col = _estado_norm(df[columna_estado])
    _ = force_resend  # compat: mantener firma pública aunque ya no hay tope
    return df[estado_col.str.contains(r"no\s*recibido", na=False)].index


def resumen_recordatorios(
    df: pd.DataFrame,
    columna_estado: str,
    columna_recordatorios: str,
) -> dict[str, int]:
    """Conteos para tabla de consola de recordatorios."""
    estado_col = _estado_norm(df[columna_estado])
    rec_count = df[columna_recordatorios].apply(parse_recordatorio_count)
    no_recibido_mask = estado_col.str.contains(r"no\s*recibido", na=False)
    cand_1 = int((no_recibido_mask & (rec_count == 0)).sum())
    cand_reiterados = int((no_recibido_mask & (rec_count >= 1)).sum())
    return {
        "cand_1": cand_1,
        "cand_reiterados": cand_reiterados,
        "total_elegibles": cand_1 + cand_reiterados,
    }
