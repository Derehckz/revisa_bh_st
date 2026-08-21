"""Sincroniza marcas de correo de recepción cuando cambia la validación (paso 3)."""
from __future__ import annotations

from typing import Any

import mail_ledger
from stages.stage5 import mail as mail_ops

STAGE_ID = mail_ops.STAGE_ID

_TRACK_COLS = (
    "Estado_Recepcion",
    "Observaciones",
    "Observacion_Descartes",
    "archivo_xml",
)


def recepcion_row_fingerprint(row: Any) -> str:
    parts = [str(row.get(col, "") or "").strip().upper() for col in _TRACK_COLS]
    return "|".join(parts)


def _is_sent_marker(value: object) -> bool:
    return mail_ops._is_sent_marker(value)


def _ledger_keys_for_row(row: Any, *, año: str, mes: str) -> set[str]:
    correo = str(row.get("Email_Docente", "") or "").strip()
    if not correo:
        return set()
    emplid = str(row.get("EMPLID", "") or "").strip()
    rut_razon = str(row.get("RUT RAZON", "") or "").strip()
    boleta = mail_ops.format_entero(row.get("numeroBoleta_XML", "N/A"))
    keys: set[str] = set()
    for kind in ("ok", "problema"):
        keys.add(
            mail_ops.build_item_key(
                año, mes, boleta, correo, kind=kind, emplid=emplid, rut_razon=rut_razon
            )
        )
        if boleta.upper() not in {"N/A", "NAN", "NONE", ""}:
            keys.add(
                mail_ops.build_item_key(
                    año, mes, "N/A", correo, kind=kind, emplid=emplid, rut_razon=rut_razon
                )
            )
    return keys


def reconcile_correo_recepcion_markers(df, *, año: str, mes: str) -> dict[str, int]:
    """Limpia marcas/idempotencia si el tipo de correo ya no corresponde al estado."""
    cleared_markers = 0
    cleared_ledger = 0

    if "Correo_Recepcion_Enviado" not in df.columns:
        df["Correo_Recepcion_Enviado"] = ""

    for idx, row in df.iterrows():
        marker = row.get("Correo_Recepcion_Enviado", "")
        if not _is_sent_marker(marker):
            continue
        if mail_ops.correo_recepcion_cubierto(row):
            continue

        df.at[idx, "Correo_Recepcion_Enviado"] = ""
        cleared_markers += 1
        for key in _ledger_keys_for_row(row, año=año, mes=mes):
            if mail_ledger.was_sent(STAGE_ID, key):
                mail_ledger.clear_sent(STAGE_ID, key)
                cleared_ledger += 1

    return {"cleared_markers": cleared_markers, "cleared_ledger": cleared_ledger}


def sync_correo_recepcion_after_revision(
    df_before,
    df_after,
    *,
    año: str,
    mes: str,
) -> dict[str, int]:
    """
    Si el paso 3 cambió estado/archivo/observaciones, limpia marcas de envío
    desactualizadas para que el paso 5 pueda enviar el tipo correcto.
    """
    stats = reconcile_correo_recepcion_markers(df_after, año=año, mes=mes)

    for idx in df_after.index:
        if idx not in df_before.index:
            continue
        before = df_before.loc[idx]
        after = df_after.loc[idx]
        if recepcion_row_fingerprint(before) == recepcion_row_fingerprint(after):
            continue
        for key in _ledger_keys_for_row(before, año=año, mes=mes):
            if mail_ledger.was_sent(STAGE_ID, key):
                mail_ledger.clear_sent(STAGE_ID, key)
                stats["cleared_ledger"] += 1

    return stats
