#!/usr/bin/env python3
"""
Script maestro para ejecutar el flujo de procesamiento de boletas de honorarios por etapas.
Permite ejecutar scripts en orden con pausas interactivas para control manual.
"""

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_REPO_ROOT, "lib")
for _p in (_LIB, _REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import subprocess
import argparse
import getpass
from datetime import datetime
import config
import utils
import idempotency_store
from period_lock import PeriodLock, PeriodLockError, break_stale
from db import pipeline_repository
from pipeline_stages import MAX_STEP, MIN_STEP, SCRIPTS
import stage_commands

console = utils.console


def get_stage(step_num):
    for s in SCRIPTS:
        if s["num"] == step_num:
            return s
    return None


def build_script_args(stage, year, month):
    return stage_commands.build_period_args(stage, year, month)


def check_prerequisites(stage_num, year=None, month=None):
    stage_commands.check_prerequisites(stage_num, year, month)


def run_script(stage, year=None, month=None, run_db_id=None, non_interactive=False):
    """Ejecuta un script con el contrato de argumentos correcto."""
    script_name = stage["file"]
    description = stage["desc"]
    step_num = stage["num"]

    stage_key = f"{script_name}|{year or 'NA'}|{month or 'NA'}"
    utils.set_correlation_id(stage_key)
    if idempotency_store.report_duplicate("main.run_script", stage_key):
        utils.print_warning(f"Duplicado detectado (solo reporte): {stage_key}")

    stage_db_id = None
    if run_db_id is not None:
        stage_db_id = pipeline_repository.create_stage_run(
            run_db_id=run_db_id,
            stage_num=step_num,
            stage_name=description,
            correlation_id=utils.get_correlation_id(),
        )

    script_path = (
        script_name
        if os.path.isabs(script_name)
        else os.path.join(_REPO_ROOT, script_name)
    )
    cmd = [sys.executable, script_path] + build_script_args(stage, year, month)

    utils.print_info(f"Ejecutando paso {step_num}: {description}")
    utils.print_info(f"Comando: {' '.join(cmd)}")
    env = os.environ.copy()
    if non_interactive:
        env["BH_NON_INTERACTIVE"] = "1"
    if year:
        env["BH_YEAR"] = str(year)
    if month:
        env["BH_MONTH"] = str(month)
    result = subprocess.run(cmd, cwd=_REPO_ROOT, env=env)
    if result.returncode != 0:
        if stage_db_id is not None:
            pipeline_repository.finish_stage_run(
                stage_db_id,
                status="ERROR",
                message=f"returncode={result.returncode}",
            )
        raise RuntimeError(f"Error en {script_name}: {result.returncode}")
    if stage_db_id is not None:
        pipeline_repository.finish_stage_run(stage_db_id, status="OK")
    utils.print_success(f"Completado paso {step_num}: {description}")


def main():
    parser = argparse.ArgumentParser(
        description="Flujo maestro de boletas de honorarios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Flujo estándar (pasos 1-10, sin paso 0)
  python main.py --year 2026 --month Abril

  # Incluir paso 0 (regenera Solicitud.xlsx desde maestro)
  python main.py --year 2026 --month Abril --start-from 0

  # Solo un tramo del pipeline
  python main.py --year 2026 --month Abril --start-from 3 --end-at 6

  # No interactivo (sin pausas entre etapas)
  python main.py --year 2026 --month Abril --non-interactive
        """,
    )
    parser.add_argument("--year", type=str, help="Año específico (ej: 2026)")
    parser.add_argument("--month", type=str, help="Mes específico (ej: Abril)")
    parser.add_argument(
        "--start-from",
        type=int,
        choices=range(MIN_STEP, MAX_STEP + 1),
        help=f"Iniciar desde script N ({MIN_STEP}-{MAX_STEP})",
    )
    parser.add_argument(
        "--end-at",
        type=int,
        choices=range(MIN_STEP, MAX_STEP + 1),
        help=f"Terminar en script N ({MIN_STEP}-{MAX_STEP})",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Ejecutar sin pausas interactivas entre etapas",
    )
    parser.add_argument(
        "--no-lock",
        action="store_true",
        help="Desactiva el lock por período (no recomendado en operación normal).",
    )
    parser.add_argument(
        "--force-lock",
        action="store_true",
        help="Fuerza adquisición del lock aunque exista uno previo (libera stale).",
    )
    args = parser.parse_args()

    utils.print_header("FLUJO MAESTRO DE BOLETAS DE HONORARIOS")

    # Por defecto: NO incluye paso 0 para no romper el flujo histórico.
    # Para incluirlo, el operador debe usar explícitamente --start-from 0.
    start = args.start_from if args.start_from is not None else 1
    end = args.end_at if args.end_at is not None else MAX_STEP

    if start > end:
        utils.print_error(f"--start-from ({start}) no puede ser mayor que --end-at ({end}).")
        sys.exit(2)

    period_label = f"{args.year or 'NA'}-{args.month or 'NA'}"
    run_db_id = pipeline_repository.create_pipeline_run(
        run_id=utils.get_run_id(),
        period_label=period_label,
        triggered_by=getpass.getuser(),
        mode="NON_INTERACTIVE" if args.non_interactive else "INTERACTIVO",
    )

    # Adquirir lock por período (Fase 4) salvo desactivación explícita.
    lock: PeriodLock | None = None
    if not args.no_lock:
        if args.force_lock:
            liberado = break_stale(args.year or "NA", args.month or "NA")
            if liberado:
                utils.print_warning("Se liberó un lock previo huérfano (--force-lock).")
        lock = PeriodLock(args.year, args.month, script="main.py")
        try:
            lock.acquire(force=args.force_lock)
            utils.print_success(f"Lock adquirido para período {period_label}: {lock.lock_path}")
        except PeriodLockError as e:
            utils.print_error(str(e))
            if run_db_id is not None:
                pipeline_repository.finish_pipeline_run(run_db_id, status="LOCKED")
            sys.exit(2)

    # Mostrar plan de ejecución
    plan_rows = []
    for s in SCRIPTS:
        if s["num"] < start or s["num"] > end:
            continue
        modo = {
            "year_month": "--year/--month",
            "mes_ano": "--mes/--año",
            "none": "interactivo",
        }[s["accepts"]]
        plan_rows.append((f"Paso {s['num']}", f"{s['desc']} ({modo})"))
    utils.print_table("Plan de ejecución", plan_rows)

    next_steps = [s for s in SCRIPTS if start <= s["num"] <= end]
    started_at = datetime.utcnow().isoformat() + "Z"
    stages_summary: list[dict] = []
    final_status = "OK"

    try:
        for i, stage in enumerate(next_steps):
            stage_started = datetime.utcnow().isoformat() + "Z"
            stage_record = {
                "num": stage["num"],
                "file": stage["file"],
                "desc": stage["desc"],
                "started_at": stage_started,
            }
            try:
                check_prerequisites(stage["num"], args.year, args.month)
                run_script(
                    stage,
                    args.year,
                    args.month,
                    run_db_id=run_db_id,
                    non_interactive=args.non_interactive,
                )
                stage_record.update(
                    status="OK",
                    finished_at=datetime.utcnow().isoformat() + "Z",
                )
                stages_summary.append(stage_record)

                if not args.non_interactive and i < len(next_steps) - 1:
                    siguiente = next_steps[i + 1]
                    utils.print_info(
                        f"¿Continuar al siguiente paso ({siguiente['num']}: {siguiente['desc']})?"
                    )
                    respuesta = utils.prompt_optional("Presione Enter para continuar, 'n' para detener")
                    if respuesta.lower() == 'n':
                        utils.print_warning("Flujo detenido por el usuario.")
                        if run_db_id is not None:
                            pipeline_repository.finish_pipeline_run(run_db_id, status="STOPPED")
                        final_status = "STOPPED"
                        break
            except Exception as e:
                stage_record.update(
                    status="ERROR",
                    error=str(e),
                    finished_at=datetime.utcnow().isoformat() + "Z",
                )
                stages_summary.append(stage_record)
                if run_db_id is not None:
                    pipeline_repository.finish_pipeline_run(run_db_id, status="ERROR")
                utils.print_error(f"Error en paso {stage['num']}: {e}")
                final_status = "ERROR"
                # Persistimos el resumen incluso ante error y luego salimos.
                _persist_summary(period_label, started_at, final_status, stages_summary, args)
                sys.exit(1)
    finally:
        if lock is not None:
            lock.release()

    if run_db_id is not None and final_status == "OK":
        pipeline_repository.finish_pipeline_run(run_db_id, status="OK")
    summary_path = _persist_summary(period_label, started_at, final_status, stages_summary, args)
    utils.print_info(f"Resumen consolidado: {summary_path}")
    utils.print_header("FLUJO COMPLETADO EXITOSAMENTE" if final_status == "OK" else "FLUJO FINALIZADO")


def _persist_summary(period_label, started_at, status, stages_summary, args):
    return utils.write_run_summary(
        utils.get_run_id(),
        {
            "period": period_label,
            "started_at": started_at,
            "finished_at": datetime.utcnow().isoformat() + "Z",
            "status": status,
            "year": args.year,
            "month": args.month,
            "non_interactive": args.non_interactive,
            "stages": stages_summary,
        },
    )


if __name__ == "__main__":
    main()
