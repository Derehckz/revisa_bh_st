"""Tests del mapa IP/CFT (paso 8)."""
from __future__ import annotations

import os
import sys

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import map_ip_cft


def test_load_map_utf8(tmp_path):
    p = tmp_path / "map_ip_cft.csv"
    p.write_text("RUT_SIN_DV,Categoria\n12345678,IP\n87654321,CFT\n", encoding="utf-8")
    m = map_ip_cft.load_map_ip_cft(str(p))
    assert m == {"12345678": "IP", "87654321": "CFT"}


def test_load_map_cp1252(tmp_path):
    p = tmp_path / "map_ip_cft.csv"
    # byte 0x97 is en-dash in cp1252 — previously crashed utf-8 loader
    raw = "RUT_SIN_DV,Categoria\n12345678,IP\n".encode("ascii") + b"\x97 note\n"
    # still need a valid IP/CFT row; write proper cp1252 map
    p.write_bytes("RUT_SIN_DV,Categoria\r\n12345678,IP\r\n".encode("cp1252") + b"note\x97\r\n")
    m = map_ip_cft.load_map_ip_cft(str(p))
    assert m.get("12345678") == "IP"


def test_rejects_contabilidad_name(tmp_path):
    p = tmp_path / "Contabilidad_pagos.csv"
    p.write_text("RUT;BRUTO\n1;100\n", encoding="cp1252")
    assert map_ip_cft.looks_like_map_csv(str(p)) is False


def test_ensure_rejects_non_map(tmp_path, monkeypatch):
    monkeypatch.setattr(map_ip_cft.config, "RAIZ", str(tmp_path))
    month = tmp_path / "2026" / "Julio"
    month.mkdir(parents=True)
    bad = month / "Contabilidad_pagos.csv"
    bad.write_text("a;b\n1;2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no parece un mapa"):
        map_ip_cft.ensure_map_for_period(2026, "Julio", "2026/Julio/Contabilidad_pagos.csv")
