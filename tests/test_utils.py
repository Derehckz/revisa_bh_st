# -*- coding: utf-8 -*-
"""Tests para utils: funciones puras sin Outlook/Excel."""
import re
import os
import zipfile
import xml.etree.ElementTree as ET
import pytest


# Importar utils desde la raíz del proyecto
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import utils


# --- validar_email ---
@pytest.mark.parametrize("email,esperado", [
    ("user@domain.com", True),
    ("a.b@correo.cl", True),
    ("achocano@santotomas.cl", True),
    ("", False),
    (None, False),
    ("sin_arroba", False),
    ("@sinlocal.cl", False),
    ("sin_dominio@", False),
    ("  user@x.cl  ", True),
])
def test_validar_email(email, esperado):
    assert utils.validar_email(email) is esperado


# --- normalizar_rut_digits ---
@pytest.mark.parametrize("rut,esperado", [
    ("12.345.678-9", "123456789"),
    ("12345678-9", "123456789"),
    (None, ""),
    ("  1.234-5  ", "12345"),
    ("12345678K", "12345678"),
])
def test_normalizar_rut_digits(rut, esperado):
    assert utils.normalizar_rut_digits(rut) == esperado


# --- normalizar_rut_con_dv ---
@pytest.mark.parametrize("rut,esperado", [
    ("12.345.678-9", "123456789"),
    ("12.345.678-k", "12345678K"),
    (None, ""),
    ("  1.234-5  ", "12345"),
])
def test_normalizar_rut_con_dv(rut, esperado):
    assert utils.normalizar_rut_con_dv(rut) == esperado


# --- find_element_ignore_ns ---
def test_find_element_ignore_ns_sin_namespace():
    xml_str = """<?xml version="1.0"?><root><rutEmisor>12345678</rutEmisor><dvEmisor>9</dvEmisor></root>"""
    root = ET.fromstring(xml_str)
    elem = utils.find_element_ignore_ns(root, "rutEmisor")
    assert elem is not None
    assert elem.text == "12345678"
    assert utils.find_element_ignore_ns(root, "noExiste") is None


def test_find_element_ignore_ns_con_namespace():
    xml_str = """<?xml version="1.0"?><doc xmlns="http://ejemplo.cl"><rutEmisor>11111111</rutEmisor></doc>"""
    root = ET.fromstring(xml_str)
    elem = utils.find_element_ignore_ns(root, "rutEmisor")
    assert elem is not None
    assert elem.text == "11111111"


# --- resolver_conflicto ---
def test_resolver_conflicto_archivo_no_existe(tmp_path):
    ruta = tmp_path / "no_existe.txt"
    assert utils.resolver_conflicto(str(ruta)) == str(ruta)


def test_resolver_conflicto_sobrescribir(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    ruta = tmp_path / "a.txt"
    assert utils.resolver_conflicto(str(ruta), "S") == str(ruta)


def test_resolver_conflicto_ignorar(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    ruta = tmp_path / "a.txt"
    assert utils.resolver_conflicto(str(ruta), "I") is None


def test_resolver_conflicto_renombrar(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    ruta = tmp_path / "a.txt"
    res = utils.resolver_conflicto(str(ruta), None)
    assert res == str(tmp_path / "a_1.txt")
    (tmp_path / "a_1.txt").write_text("y")
    res2 = utils.resolver_conflicto(str(ruta), None)
    assert res2 == str(tmp_path / "a_2.txt")


# --- backup_file ---
def test_backup_file_crea_zip(tmp_path):
    archivo = tmp_path / "test.xlsx"
    archivo.write_text("contenido fake")
    dest = utils.backup_file(str(archivo))
    assert dest is not None
    assert dest.endswith(".zip")
    assert os.path.isfile(dest)
    with zipfile.ZipFile(dest, "r") as zf:
        names = zf.namelist()
        assert "test.xlsx" in names


def test_backup_file_no_existe():
    assert utils.backup_file("/ruta/que/no/existe.xlsx") is None


def test_backup_file_path_vacio():
    assert utils.backup_file("") is None
    assert utils.backup_file(None) is None
