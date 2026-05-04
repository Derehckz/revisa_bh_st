#!/usr/bin/env python3
"""CLI para la bitácora de correos (`email_outbox`): consulta, re-apertura de failed, watch y dispatch COM.

- `dispatch-com` / `watch-dispatch` reutilizan el `id` outbox `pending` y llaman a Outlook vía `outbox_com_dispatch`.
- `watch --exec-cmd` sigue disponible para re-ejecutar scripts completos si se prefiere.
"""
from __future__ import annotations

import _sys_path  # noqa: E402

import argparse
import shlex
import subprocess
import sys
import time

import email_outbox


def _cmd_dispatch_com(a: argparse.Namespace) -> int:
    from outbox_com_dispatch import dispatch_pending_com

    o, f, s = dispatch_pending_com(limit=a.limit, dry_run=a.dry_run)
    print(f"dispatch-com: ok={o} failed={f} dry_skipped={s}")
    return 0 if f == 0 else 1


def _cmd_watch_dispatch(a: argparse.Namespace) -> int:
    from outbox_com_dispatch import dispatch_pending_com

    while True:
        failed = email_outbox.stats_by_status().get("failed", 0)
        pending = email_outbox.stats_by_status().get("pending", 0)
        if failed > 0 or pending > 0:
            print(f"[outbox_worker] failed={failed} pending={pending} -> dispatch-com")
            o, f, s = dispatch_pending_com(limit=a.limit, dry_run=False)
            print(f"[outbox_worker] resultado ok={o} failed={f} skipped={s}")
        time.sleep(max(5, a.interval))


def _cmd_stats(_a: argparse.Namespace) -> int:
    s = email_outbox.stats_by_status()
    if not s:
        print("(outbox vacío)")
        return 0
    for k in sorted(s.keys()):
        print(f"{k}: {s[k]}")
    return 0


def _cmd_list(a: argparse.Namespace) -> int:
    rows = email_outbox.list_rows(
        status=a.status,
        stage_prefix=a.stage_prefix,
        limit=a.limit,
    )
    for r in rows:
        print(
            f"id={r['id']} status={r['status']} stage={r['stage']} attempts={r['attempts']} "
            f"key={r['item_key']!r} err={str(r.get('last_error') or '')[:120]}"
        )
    return 0


def _cmd_reopen_failed(a: argparse.Namespace) -> int:
    n = email_outbox.reopen_failed_as_pending(max_attempts=a.max_attempts, limit=a.limit)
    print(f"Filas reabiertas a pending: {n}")
    return 0


def _cmd_watch(a: argparse.Namespace) -> int:
    if not a.exec_cmd:
        print("Error: --watch requiere --exec-cmd", file=sys.stderr)
        return 2
    parts = shlex.split(a.exec_cmd)
    while True:
        failed = email_outbox.stats_by_status().get("failed", 0)
        pending = email_outbox.stats_by_status().get("pending", 0)
        if failed > 0 or pending > 0:
            print(f"[outbox_worker] failed={failed} pending={pending} -> ejecutando: {a.exec_cmd}")
            subprocess.run(parts, check=False)
        time.sleep(max(5, a.interval))


def main() -> int:
    p = argparse.ArgumentParser(description="Utilidades del outbox de correos")
    sub = p.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("stats", help="Conteos por estado")
    s1.set_defaults(func=_cmd_stats)

    s2 = sub.add_parser("list", help="Últimas filas del journal")
    s2.add_argument("--status", type=str, default=None)
    s2.add_argument("--stage-prefix", type=str, default=None)
    s2.add_argument("--limit", type=int, default=40)
    s2.set_defaults(func=_cmd_list)

    s3 = sub.add_parser("reopen-failed", help="Marca failed elegibles como pending (reintento manual)")
    s3.add_argument("--max-attempts", type=int, default=5)
    s3.add_argument("--limit", type=int, default=200)
    s3.set_defaults(func=_cmd_reopen_failed)

    s4 = sub.add_parser("watch", help="Bucle: si hay pending/failed, ejecuta un comando (no bloquea Outlook aquí)")
    s4.add_argument("--interval", type=int, default=300, help="Segundos entre comprobaciones")
    s4.add_argument(
        "--exec-cmd",
        type=str,
        required=True,
        help='Comando a ejecutar (ej: python etapas/7.-Envia_mail_pagos.py --year 2026 --month Abril --yes --send --fecha-pago 01/04/2026)',
    )
    s4.set_defaults(func=_cmd_watch)

    s5 = sub.add_parser(
        "dispatch-com",
        help="Reintenta envíos COM solo para filas outbox en estado pending (scripts 1/5/7)",
    )
    s5.add_argument("--limit", type=int, default=30)
    s5.add_argument("--dry-run", action="store_true", help="No llama a Outlook; solo traza")
    s5.set_defaults(func=_cmd_dispatch_com)

    s6 = sub.add_parser(
        "watch-dispatch",
        help="Bucle: si hay pending/failed en outbox, ejecuta dispatch-com (Outlook en este proceso)",
    )
    s6.add_argument("--interval", type=int, default=300, help="Segundos entre comprobaciones")
    s6.add_argument("--limit", type=int, default=30, help="Máx. filas pending por ciclo")
    s6.set_defaults(func=_cmd_watch_dispatch)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
