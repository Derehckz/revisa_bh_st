from __future__ import annotations

import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for p in (_REPO, _LIB):
    if p not in sys.path:
        sys.path.insert(0, p)

import email_templates  # noqa: E402


class TestEmailTemplatesMonto(unittest.TestCase):
    def test_format_monto_with_thousands_comma(self):
        self.assertEqual(email_templates._format_monto("206,000"), "$206.000")

    def test_format_monto_with_thousands_dot(self):
        self.assertEqual(email_templates._format_monto("206.000"), "$206.000")

    def test_format_monto_with_decimal_comma(self):
        self.assertEqual(email_templates._format_monto("206,5"), "$206")


if __name__ == "__main__":
    unittest.main()

