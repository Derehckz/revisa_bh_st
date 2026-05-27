"""Tests de adaptadores de interacción."""
from __future__ import annotations

import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for p in (_REPO, _LIB):
    if p not in sys.path:
        sys.path.insert(0, p)

from interaction.auto_adapter import AutoAdapter
from interaction.port import PromptRequest
from interaction.types import InteractionKind


class TestAutoAdapter(unittest.TestCase):
    def test_confirm_reject_without_send(self):
        ui = AutoAdapter(allow_send=False, auto_accept_confirm=False)
        resp = ui.ask(
            PromptRequest(
                kind=InteractionKind.CONFIRM,
                title="t",
                message="m",
            )
        )
        self.assertEqual(resp.action, "reject")

    def test_confirm_accept_with_send_flag(self):
        ui = AutoAdapter(allow_send=True, auto_accept_confirm=True)
        resp = ui.ask(
            PromptRequest(
                kind=InteractionKind.CONFIRM,
                title="t",
                message="m",
            )
        )
        self.assertEqual(resp.action, "accept")


if __name__ == "__main__":
    unittest.main()
