import pandas as pd

import reminder_policy


def test_parse_recordatorio_count():
    assert reminder_policy.parse_recordatorio_count(None) == 0
    assert reminder_policy.parse_recordatorio_count("2") == 2
    assert reminder_policy.parse_recordatorio_count(1.0) == 1


def test_indices_recordatorio_without_cap():
    df = pd.DataFrame(
        {
            "Estado_Recepcion": ["NO RECIBIDO", "NO RECIBIDO", "NO RECIBIDO", "RECIBIDO"],
            "Recordatorios Enviados": [0, 1, 2, 0],
        }
    )
    idx = reminder_policy.indices_recordatorio(
        df, "Estado_Recepcion", "Recordatorios Enviados", force_resend=False
    )
    assert set(idx.tolist()) == {0, 1, 2}
    res = reminder_policy.resumen_recordatorios(df, "Estado_Recepcion", "Recordatorios Enviados")
    assert res["cand_1"] == 1
    assert res["cand_reiterados"] == 2
    assert res["total_elegibles"] == 3


def test_indices_recordatorio_force_resend():
    df = pd.DataFrame(
        {
            "Estado_Recepcion": ["NO RECIBIDO"],
            "Recordatorios Enviados": [99],
        }
    )
    idx = reminder_policy.indices_recordatorio(
        df, "Estado_Recepcion", "Recordatorios Enviados", force_resend=True
    )
    assert len(idx) == 1
