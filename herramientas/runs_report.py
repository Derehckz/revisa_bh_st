#!/usr/bin/env python3
"""Lista y muestra resúmenes JSON de corridas en `.state/runs/`."""
from __future__ import annotations

import _sys_path  # noqa: E402

import argparse
import glob
import json
import os
import textwrap

import config


def _runs_dir() -> str:
    d = os.path.join(config.RAIZ, ".state", "runs")
    os.makedirs(d, exist_ok=True)
    return d


def _print_stages_table(data: dict) -> None:
    stages = data.get("stages") or []
    if not stages:
        print("(sin etapas en JSON)")
        return
    rows = []
    for s in stages:
        err = s.get("error") or ""
        if err:
            err = textwrap.shorten(str(err), width=56, placeholder="…")
        rows.append(
            (
                str(s.get("num", "")),
                str(s.get("file", ""))[:28],
                str(s.get("status", ""))[:10],
                err,
            )
        )
    w = (4, 30, 10, 58)
    hdr = f"{'#':<{w[0]}}  {'script':<{w[1]}}  {'estado':<{w[2]}}  error"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r[0]:<{w[0]}}  {r[1]:<{w[1]}}  {r[2]:<{w[2]}}  {r[3]}")


def main() -> int:
    p = argparse.ArgumentParser(description="Reportes de corridas (main.py y similares)")
    p.add_argument("--list", action="store_true", help="Listar archivos recientes (ruta + mtime)")
    p.add_argument(
        "--last",
        type=int,
        default=0,
        metavar="N",
        help="Mostrar JSON completo de los N archivos más recientes",
    )
    p.add_argument("--path", type=str, default=None, help="Mostrar un archivo JSON concreto")
    p.add_argument(
        "--table",
        action="store_true",
        help="Tabla resumida por etapa (última corrida o la de --path)",
    )
    args = p.parse_args()

    if args.path:
        with open(args.path, encoding="utf-8") as fh:
            data = json.load(fh)
        if args.table:
            _print_stages_table(data)
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    pattern = os.path.join(_runs_dir(), "*.json")
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    if not files:
        print("(sin archivos en .state/runs/)")
        return 0

    if args.last and args.last > 0:
        for fp in files[: args.last]:
            print("---", fp)
            with open(fp, encoding="utf-8") as fh:
                print(json.dumps(json.load(fh), indent=2, ensure_ascii=False))
        return 0

    if args.list:
        for fp in files[:50]:
            print(f"{os.path.getmtime(fp):.0f}\t{fp}")
        return 0

    with open(files[0], encoding="utf-8") as fh:
        data = json.load(fh)
    if args.table:
        print(files[0])
        print(
            f"period={data.get('period')!r} status={data.get('status')!r} "
            f"started={data.get('started_at')} finished={data.get('finished_at')}"
        )
        _print_stages_table(data)
        return 0
    resumen = {
        "archivo": files[0],
        "period": data.get("period"),
        "status": data.get("status"),
        "started_at": data.get("started_at"),
        "finished_at": data.get("finished_at"),
        "etapas": len(data.get("stages", [])),
    }
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
