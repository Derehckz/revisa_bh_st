"""Formato de presentación para UI."""
from __future__ import annotations

import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import display_format as fmt  # noqa: E402


class TestDisplayFormat(unittest.TestCase):
    def test_folio_sin_decimal(self):
        self.assertEqual(fmt.format_folio(433.0), "433")
        self.assertEqual(fmt.format_folio("434.0"), "434")

    def test_monto_cl(self):
        self.assertEqual(fmt.format_monto_cl(101916), "$101.916.-")
        self.assertEqual(fmt.format_monto_cl("101916.0"), "$101.916.-")

    def test_rut_cl(self):
        self.assertEqual(fmt.format_rut_cl("651752396.0"), "65.175.239-6")
        self.assertEqual(fmt.format_rut_cl("15651725-9"), "15.651.725-9")


if __name__ == "__main__":
    unittest.main()
