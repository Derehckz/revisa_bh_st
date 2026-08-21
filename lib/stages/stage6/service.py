"""Etapa 6 — Informe final de boletas (envoltorio delgado sobre el script legacy).

Ver ``stages.stage0.service`` para el patrón: la lógica sigue en
``etapas/6.-Informe_final_boletas.py`` y se ejecuta vía
:func:`stages.bridged_runner.run_bridged_stage`.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import config
from interaction.port import InteractionPort
from stages.bridged_runner import run_bridged_stage
from stages.context import Stage6Context


def _write_informe_log(year: str, month: str, report_path: str) -> str | None:
    """Deja rastro en disco para el historial / badge OK del overview."""
    try:
        log_dir = os.path.join(config.RAIZ, year, month, "logs_informe")
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(log_dir, f"informe_{ts}.jsonl")
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "stage": 6,
            "status": "success",
            "message": "Informe final generado correctamente (hoja Resumen Boletas).",
            "report_path": report_path,
            "return_code": 0,
        }
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return path
    except OSError:
        return None


class Stage6Service:
    def run(self, ctx: Stage6Context, ui: InteractionPort) -> dict:
        result = run_bridged_stage(ctx, ui)
        if not result.get("ok"):
            return result

        year = str(ctx.year or "").strip()
        month = str(ctx.month or "").strip()
        report_path = ""
        if year and month:
            candidate = os.path.join(config.RAIZ, year, month, "Solicitud.xlsx")
            if os.path.isfile(candidate):
                report_path = os.path.abspath(candidate)

        if report_path:
            log_path = _write_informe_log(year, month, report_path)
            ui.emit(
                "report.ready",
                {
                    "path": report_path,
                    "filename": "Solicitud.xlsx",
                    "sheet": "Resumen Boletas",
                    "label": "Informe final (hoja Resumen Boletas en Solicitud.xlsx)",
                    "year": year,
                    "month": month,
                    "stage_num": 6,
                    "log_path": log_path,
                },
            )
            ui.log(
                f"Informe listo: {report_path} (hoja «Resumen Boletas»). "
                "Envíalo a Contabilidad y marca OK en el checklist antes de cerrar.",
                level="success",
            )
            try:
                import contabilidad_validation

                contabilidad_validation.reset_contabilidad_after_informe(int(year), month)
            except Exception:
                pass
            try:
                import period_snapshots

                snap = period_snapshots.refresh_informe_from_excel(year, month)
                if snap:
                    result = {**result, "informe_snapshot": snap}
            except Exception:
                pass
            result = {
                **result,
                "report_path": report_path,
                "report_sheet": "Resumen Boletas",
                "log_path": log_path,
            }
            ui.emit("session.summary", result)
        return result
