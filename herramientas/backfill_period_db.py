#!/usr/bin/env python3
"""Backfill Excel → PostgreSQL (boletas canónicas + snapshots informe/pagos)."""
from __future__ import annotations

import argparse
import json
import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def main() -> int:
    p = argparse.ArgumentParser(description="Sincroniza períodos a PostgreSQL")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--month", default=None, help="Mes específico (ej. Julio). Si omite, todos con Solicitud.")
    p.add_argument("--no-migrate", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    from api import operations

    result = operations.backfill_periods(
        year=args.year,
        month=args.month,
        run_migrations=not args.no_migrate,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(
            f"Backfill {args.year}: {result.get('ok_count')}/{result.get('total')} OK "
            f"({', '.join(result.get('months') or [])})"
        )
        for row in result.get("results") or []:
            status = "OK" if row.get("ok") else "FAIL"
            extra = row.get("error") or ""
            snaps = (row.get("verify") or {}).get("snapshots") or row.get("snapshots") or {}
            print(f"  [{status}] {row.get('month')} {extra} snaps={snaps}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
