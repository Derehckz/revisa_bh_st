"""Inserta en sys.path el directorio `lib/` y la raíz del repo (para `db/` y datos)."""
from __future__ import annotations

import os
import sys


def _ensure() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, ".."))
    lib = os.path.join(root, "lib")
    for p in (lib, root):
        if p not in sys.path:
            sys.path.insert(0, p)


_ensure()
