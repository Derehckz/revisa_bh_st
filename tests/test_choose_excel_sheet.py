"""Tests de selección de hoja Excel."""
from __future__ import annotations

import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for p in (_REPO, _LIB):
    if p not in sys.path:
        sys.path.insert(0, p)

import utils  # noqa: E402
import terminal_ui  # noqa: E402


class TestChooseExcelSheet(unittest.TestCase):
    def setUp(self):
        terminal_ui.set_non_interactive(True)

    def test_explicit_sheet(self):
        hoja = utils.choose_excel_sheet(["Solicitud", "Pagos"], sheet="Pagos")
        self.assertEqual(hoja, "Pagos")

    def test_invalid_sheet_raises(self):
        with self.assertRaises(ValueError):
            utils.choose_excel_sheet(["Solicitud"], sheet="NoExiste")

    def test_canonical_fallback(self):
        hoja = utils.choose_excel_sheet(["datos", "Solicitud"], sheet=None)
        self.assertEqual(hoja, "Solicitud")


if __name__ == "__main__":
    unittest.main()
