"""Tests de serialización solicitud_row."""
from __future__ import annotations

from db.solicitud_row import SOLICITUD_COLUMNS, merge_solicitud_row, serialize_solicitud_row


def test_serialize_keeps_canonical_columns():
    row = serialize_solicitud_row(
        {
            "EMPLID": "15651725-9",
            "CUS_TOT_HON": 101916,
            "DESCR": "HONORARIOS",
            "CUS_INCIDENCIA": "X",
            "unknown": float("nan"),
        }
    )
    assert set(SOLICITUD_COLUMNS).issubset(row.keys())
    assert row["EMPLID"] == "15651725-9"
    assert row["CUS_TOT_HON"] == 101916
    assert row["DESCR"] == "HONORARIOS"
    assert row["CUS_INCIDENCIA"] == "X"
    assert row["unknown"] is None


def test_merge_preserves_existing_when_incoming_empty():
    existing = serialize_solicitud_row({"DESCR": "A", "CUS_MTO_CTA": 10, "Estado_Recepcion": "NO RECIBIDO"})
    incoming = serialize_solicitud_row({"DESCR": "", "Estado_Recepcion": "RECIBIDO", "CUS_MTO_CTA": None})
    merged = merge_solicitud_row(existing, incoming)
    assert merged["DESCR"] == "A"
    assert merged["CUS_MTO_CTA"] == 10
    assert merged["Estado_Recepcion"] == "RECIBIDO"
