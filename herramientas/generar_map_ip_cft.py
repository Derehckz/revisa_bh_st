#!/usr/bin/env python3
"""Genera CSV RUT_SIN_DV,IP|CFT desde Solicitud.xlsx del período."""
from __future__ import annotations

import argparse
import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from map_ip_cft import generate_map_ip_cft


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--year", required=True)
    p.add_argument("--month", required=True)
    p.add_argument("--output", default=None)
    args = p.parse_args()

    try:
        out, n = generate_map_ip_cft(args.year, args.month, output=args.output)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Mapa escrito: {out} ({n} RUTs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
