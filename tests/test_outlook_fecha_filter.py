"""Tests del filtro de fechas Outlook (etapa 2) — sin COM real."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import outlook_utils as ou


class _FakeItems(list):
    def Sort(self, *_a, **_k):
        return None

    def Restrict(self, _filtro):
        # Simula Restrict incompleto: solo la mitad (omite correos).
        return list(self)[::2]


def _mail(eid: str, received: datetime) -> SimpleNamespace:
    return SimpleNamespace(Class=43, EntryID=eid, ReceivedTime=received)


def test_barrido_incluye_bordes_y_omite_fuera_de_rango():
    inicio = datetime(2026, 7, 23, 0, 0, 0)
    fin = datetime(2026, 7, 31, 23, 59, 59)
    # Orden como Outlook Sort descendente
    msgs = [
        _mail("nuevo", datetime(2026, 8, 1, 10, 0)),  # fuera (después de fin)
        _mail("andaur", datetime(2026, 7, 24, 17, 23)),  # debe entrar
        _mail("borde_fin", datetime(2026, 7, 31, 23, 59, 59)),
        _mail("borde_ini", datetime(2026, 7, 23, 0, 0, 0)),
        _mail("viejo", datetime(2026, 7, 22, 23, 0)),  # corta barrido
        _mail("nunca", datetime(2026, 7, 20, 12, 0)),  # no debe verse tras corte
    ]
    # El barrido itera en el orden de Items (ya "ordenado")
    folder = SimpleNamespace(Items=_FakeItems(msgs))
    got = ou._filtrar_correos_barrido(folder, inicio, fin)
    ids = [m.EntryID for m in got]
    assert "andaur" in ids
    assert "borde_fin" in ids
    assert "borde_ini" in ids
    assert "nuevo" not in ids
    assert "viejo" not in ids
    assert "nunca" not in ids


def test_union_recupera_correo_que_restrict_omite():
    inicio = datetime(2026, 7, 23, 0, 0, 0)
    fin = datetime(2026, 7, 31, 23, 59, 59)
    # Solo correos dentro del rango, orden desc
    msgs = [
        _mail("a", datetime(2026, 7, 27, 12, 0)),
        _mail("andaur", datetime(2026, 7, 24, 17, 23)),
        _mail("b", datetime(2026, 7, 23, 15, 0)),
    ]
    folder = SimpleNamespace(Items=_FakeItems(msgs))
    # Restrict (::2) omite "andaur"
    restrict_ids = [m.EntryID for m in ou._filtrar_correos_restrict(folder, inicio, fin)]
    assert "andaur" not in restrict_ids

    unidos = ou.filtrar_correos_por_fecha(folder, inicio, fin)
    ids = {m.EntryID for m in unidos}
    assert ids == {"a", "andaur", "b"}


def test_restrict_descarta_fuera_de_rango_por_receivedtime():
    """Restrict Jet puede devolver basura de locale; se recorta en Python."""
    inicio = datetime(2026, 7, 1, 0, 0, 0)
    fin = datetime(2026, 7, 31, 23, 59, 59)

    class _JunkRestrict(_FakeItems):
        def Restrict(self, _filtro):
            # Incluye junio y mayo aunque el filtro diga julio
            return list(self)

    msgs = [
        _mail("julio", datetime(2026, 7, 27, 14, 45)),
        _mail("junio", datetime(2026, 6, 24, 9, 26)),
        _mail("mayo", datetime(2026, 5, 25, 13, 8)),
    ]
    folder = SimpleNamespace(Items=_JunkRestrict(msgs))
    got = ou._filtrar_correos_restrict(folder, inicio, fin)
    ids = [m.EntryID for m in got]
    assert ids == ["julio"]


def test_as_naive_local_strip_tz():
    from zoneinfo import ZoneInfo

    aware = datetime(2026, 7, 24, 17, 23, tzinfo=ZoneInfo("America/Santiago"))
    naive = ou._as_naive_local(aware)
    assert naive.tzinfo is None
    assert naive.hour == 17
