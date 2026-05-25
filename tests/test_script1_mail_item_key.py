import importlib.util
import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
_ETAPAS = os.path.join(_REPO, "etapas")
for p in (_LIB, _REPO, _ETAPAS):
    if p not in sys.path:
        sys.path.insert(0, p)

_spec = importlib.util.spec_from_file_location(
    "script1_bh",
    os.path.join(_ETAPAS, "1.-envia_correo_mensual_bh.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_item_key_differs_by_rut_razon_same_email():
    k_ip = _mod._build_mail_item_key(
        2026, "5", "19389494-1", "76.123.456-7", "docente@example.com"
    )
    k_cft = _mod._build_mail_item_key(
        2026, "5", "19389494-1", "77.987.654-3", "docente@example.com"
    )
    assert k_ip != k_cft


def test_item_key_same_for_identical_boleta():
    args = (2026, "5", "19389494-1", "76.123.456-7", "docente@example.com")
    assert _mod._build_mail_item_key(*args) == _mod._build_mail_item_key(*args)
