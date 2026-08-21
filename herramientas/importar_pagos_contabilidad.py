#!/usr/bin/env python3
"""Importa Excel/CSV de Contabilidad a la hoja Pagos del mes.

Si Contabilidad solo envió la tabla en el correo, usá el paso 7 de la web
(pegar HTML/TSV). Este script es para cuando ya tenés un .xlsx/.csv:

  python herramientas/importar_pagos_contabilidad.py --year 2026 --month Julio --file "ruta\\pagos_contabilidad.xlsx"
"""
from __future__ import annotations

import argparse
import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB = os.path.join(_REPO, "lib")
for _p in (_LIB, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pagos_import  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Importa pagos Contabilidad → hoja Pagos")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--month", required=True)
    p.add_argument("--file", required=True, help="Excel/CSV de Contabilidad")
    p.add_argument("--dry-run", action="store_true", help="Solo valida, no escribe")
    args = p.parse_args()

    try:
        result = pagos_import.import_pagos_into_period(
            year=args.year,
            month=args.month,
            source_path=args.file,
            write=not args.dry_run,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(result.get("message") or result)
    if result.get("missing_mail"):
        print(f"Aviso: {result['missing_mail']} fila(s) sin MAIL (completa desde Solicitud/BD).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
