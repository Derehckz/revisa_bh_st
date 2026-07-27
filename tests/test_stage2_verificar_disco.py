"""Verificación post-guardado etapa 2."""
from __future__ import annotations

import os
from types import SimpleNamespace

from stages.stage2 import extraction as ext


def test_verificar_pares_reporta_faltantes(tmp_path, monkeypatch):
    monkeypatch.setattr(ext, "CARPETA_BASE", str(tmp_path))
    monkeypatch.setattr(ext, "MESES_ES", [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ])

    class _Att:
        def __init__(self, name: str):
            self.FileName = name

    from datetime import datetime

    msg_ok = SimpleNamespace(
        ReceivedTime=datetime(2026, 7, 27, 14, 45),
        Attachments=[_Att("bhe_7819594-511.pdf"), _Att("bhe_7819594-511.xml")],
    )
    mes = tmp_path / "2026" / "Julio"
    mes.mkdir(parents=True)
    (mes / "bhe_7819594-511.pdf").write_bytes(b"%PDF")
    (mes / "bhe_7819594-511.xml").write_text("<xml/>", encoding="utf-8")

    msg_missing = SimpleNamespace(
        ReceivedTime=datetime(2026, 7, 27, 15, 0),
        Attachments=[_Att("bhe_11111111-1.pdf"), _Att("bhe_11111111-1.xml")],
    )

    faltantes = ext.verificar_pares_en_disco([msg_ok, msg_missing])
    assert len(faltantes) == 2
    assert any("bhe_11111111-1.pdf" in f for f in faltantes)
    assert any("bhe_11111111-1.xml" in f for f in faltantes)
    assert not any("7819594" in f for f in faltantes)
