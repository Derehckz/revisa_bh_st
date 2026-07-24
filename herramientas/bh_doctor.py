#!/usr/bin/env python3
"""Comprobaciones rápidas de entorno antes de correr el pipeline (checklist)."""
from __future__ import annotations

import _sys_path  # noqa: E402

import argparse
import glob
import os
import sqlite3

import config
import utils


def _ok(msg: str) -> None:
    print(f"[ok]   {msg}")


def _warn(msg: str) -> None:
    print(f"[warn] {msg}")


def _fail(msg: str) -> None:
    print(f"[fail] {msg}")


def main() -> int:
    p = argparse.ArgumentParser(description="Checklist de entorno pipeline BH")
    p.add_argument("--year", type=str, default=None)
    p.add_argument("--month", type=str, default=None)
    args = p.parse_args()

    errors = 0
    if not os.path.isdir(config.RAIZ):
        _fail(f"config.RAIZ no existe o no es carpeta: {config.RAIZ}")
        errors += 1
    else:
        _ok(f"RAIZ {config.RAIZ}")

    adj = getattr(config, "ARCHIVO_ADJUNTO", None)
    if adj and not os.path.isfile(adj):
        _warn(f"Adjunto script 1 no encontrado: {adj}")
    elif adj:
        _ok(f"Adjunto script 1: {adj}")

    state = os.path.join(config.RAIZ, ".state")
    outbox_db = os.path.join(state, "email_outbox.sqlite3")
    if os.path.isfile(outbox_db):
        try:
            con = sqlite3.connect(outbox_db)
            n = con.execute("SELECT COUNT(*) FROM email_outbox").fetchone()[0]
            con.close()
            _ok(f"Outbox sqlite legible ({n} filas)")
        except sqlite3.Error as e:
            _fail(f"Outbox sqlite ilegible: {e}")
            errors += 1
    else:
        _warn("Sin email_outbox.sqlite3 (se creará al primer envío)")

    runs_dir = os.path.join(state, "runs")
    if os.path.isdir(runs_dir):
        njson = len(glob.glob(os.path.join(runs_dir, "*.json")))
        _ok(f".state/runs con {njson} JSON")
    else:
        _warn("Sin .state/runs (se creará al usar main.py)")

    if args.year and args.month:
        try:
            y, m = utils.resolve_año_mes(config.RAIZ, args.year, args.month)
        except ValueError as e:
            _fail(str(e))
            errors += 1
        else:
            base = os.path.join(config.RAIZ, y, m)
            sol = os.path.join(base, "Solicitud.xlsx")
            if os.path.isfile(sol):
                _ok(f"Solicitud.xlsx en período {y}/{m}")
            else:
                _warn(f"No hay Solicitud.xlsx en {base}")

    if os.name == "nt":
        try:
            from outlook_utils import check_outlook_health

            oh = check_outlook_health(probe_com=False)
            if oh.get("ready") or oh.get("process_running"):
                _ok(f"Outlook: {oh.get('message')}")
            elif oh.get("exe_found"):
                _warn(f"Outlook: {oh.get('message')}")
            else:
                _warn(f"Outlook: {oh.get('message')}")
        except Exception as e:
            _warn(f"No se pudo comprobar Outlook: {e}")

    if errors:
        print(f"\nResultado: {errors} error(es) críticos.")
        return 1
    print("\nResultado: sin errores críticos (revisar advertencias).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
