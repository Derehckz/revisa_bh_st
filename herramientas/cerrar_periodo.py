#!/usr/bin/env python3
"""Orquesta cierre de un período (pasos 2–10) con flags no interactivos."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import stage_commands


def _run_step(stage_num: int, year: str, month: str, extra: dict) -> int:
    params = {"year": int(year), "month": month, **extra}
    cmd = stage_commands.build_stage_command(
        _REPO, stage_num, year=year, month=month, params=params, api_mode=True
    )
    print(f"\n>>> Paso {stage_num}: {' '.join(cmd)}\n", flush=True)
    env = os.environ.copy()
    env["BH_NON_INTERACTIVE"] = "1"
    env["BH_YEAR"] = str(year)
    env["BH_MONTH"] = month
    env.setdefault("BH_DUPLICADOS", "S")
    return subprocess.run(cmd, cwd=_REPO, env=env).returncode


def main() -> int:
    p = argparse.ArgumentParser(description="Cierre operativo de un período (etapas 2–10)")
    p.add_argument("--year", required=True)
    p.add_argument("--month", required=True)
    p.add_argument("--fecha-inicio", required=True, help="dd/mm/aaaa para paso 2")
    p.add_argument("--fecha-fin", required=True, help="dd/mm/aaaa para paso 2")
    p.add_argument("--start-from", type=int, default=2)
    p.add_argument("--end-at", type=int, default=10)
    p.add_argument("--skip-email", action="store_true", help="No ejecuta pasos 5 y 7")
    p.add_argument("--send-email", action="store_true", help="Paso 5/7 con --send (correos reales)")
    p.add_argument("--fecha-pago", default=None, help="Obligatorio si --send-email y llega al paso 7")
    p.add_argument("--step8-dry-run", action="store_true", help="Paso 8 solo simulación")
    args = p.parse_args()

    steps = list(range(args.start_from, args.end_at + 1))
    if args.skip_email:
        steps = [s for s in steps if s not in (5, 7)]

    for n in steps:
        extra: dict = {}
        if n == 2:
            extra = {"fecha_inicio": args.fecha_inicio, "fecha_fin": args.fecha_fin}
        elif n in (5, 7) and args.send_email:
            extra = {"send": True}
            if n == 7:
                if not args.fecha_pago:
                    print("ERROR: --fecha-pago requerido con --send-email en paso 7", file=sys.stderr)
                    return 2
                extra["fecha_pago"] = args.fecha_pago
        elif n == 8 and args.step8_dry_run:
            extra = {"dry_run": True}
        elif n == 9:
            extra = {"agrupar_archivos": True}

        try:
            stage_commands.check_prerequisites(n, args.year, args.month)
        except (ValueError, OSError) as e:
            print(f"ERROR prerequisitos paso {n}: {e}", file=sys.stderr)
            return 1

        rc = _run_step(n, args.year, args.month, extra)
        if rc != 0:
            print(f"ERROR paso {n} terminó con código {rc}", file=sys.stderr)
            return rc

    print("\nCierre de período completado sin errores de proceso.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
