"""Contexto operativo para la UI de Operación (prerequisitos, KPIs, artefactos)."""
from __future__ import annotations

import glob
import os
from datetime import datetime
from typing import Any

import config
import ops_execution_history
import stage_commands

def _month_dir(year: int | str, month: str) -> str:
    return os.path.join(config.RAIZ, str(year), month)


def _check_item(item_id: str, label: str, ok: bool, message: str = "", *, blocking: bool = True) -> dict[str, Any]:
    return {
        "id": item_id,
        "label": label,
        "ok": ok,
        "blocking": blocking,
        "message": message,
    }


def prerequisite_checklist(stage_num: int, year: int | str, month: str) -> list[dict[str, Any]]:
    """Checklist detallado para la UI (bloqueo si algún ítem blocking falla)."""
    items: list[dict[str, Any]] = []
    month_path = _month_dir(year, month)
    month_exists = os.path.isdir(month_path)

    items.append(
        _check_item(
            "period_folder",
            "Carpeta del período existe",
            month_exists,
            "" if month_exists else f"No existe: {month_path}",
        )
    )

    if stage_num == 0:
        if month_exists:
            maestros = [
                f
                for f in os.listdir(month_path)
                if f.lower().endswith(".xlsx") and os.path.isfile(os.path.join(month_path, f))
            ]
            items.append(
                _check_item(
                    "maestro",
                    "Hay al menos un Excel maestro en la carpeta del mes",
                    len(maestros) > 0,
                    "Sube el archivo maestro (.xlsx) a la carpeta del mes.",
                )
            )
        root_xlsx = [
            f
            for f in os.listdir(config.RAIZ)
            if f.lower().endswith(".xlsx") and os.path.isfile(os.path.join(config.RAIZ, f))
        ]
        bd_ok = any("bd" in f.lower() or "docentes" in f.lower() for f in root_xlsx)
        items.append(
            _check_item(
                "bd_docentes",
                "BD-DOCENTES (o similar) en la raíz del proyecto",
                bd_ok,
                "Coloca BD-DOCENTES.xlsx en la raíz del repositorio.",
            )
        )
        return items

    if stage_num == 1:
        items.append(
            _check_item(
                "adjunto_ejemplo",
                "PDF de ejemplo para correos (EjemploEnvioBoleta.pdf)",
                os.path.isfile(config.ARCHIVO_ADJUNTO),
                f"No encontrado: {config.ARCHIVO_ADJUNTO}",
            )
        )

    solicitud = os.path.join(month_path, "Solicitud.xlsx")
    if stage_num in (1, 3, 4, 5, 6, 7, 8, 9, 10):
        items.append(
            _check_item(
                "solicitud",
                "Solicitud.xlsx en la carpeta del mes",
                os.path.isfile(solicitud),
                f"Ejecuta paso 0 o copia Solicitud.xlsx a {month_path}",
            )
        )

    if stage_num == 2:
        items.append(
            _check_item(
                "outlook_hint",
                "Outlook debe estar disponible en esta máquina",
                True,
                "",
                blocking=False,
            )
        )
        items.append(
            _check_item(
                "fechas_ui",
                "Indica fecha inicio y fin en el formulario",
                True,
                "",
                blocking=False,
            )
        )

    if stage_num == 8:
        items.append(
            _check_item(
                "map_csv_hint",
                "Para paso 8 sin prompts: indica CSV de mapeo o usa consola",
                True,
                "Recomendado: --map con RUT,IP|CFT",
                blocking=False,
            )
        )

    if stage_num in (5, 7):
        items.append(
            _check_item(
                "send_confirm",
                "Envío real requiere confirmación explícita en la UI",
                True,
                "",
                blocking=False,
            )
        )

    return items


def prerequisites_summary(checklist: list[dict[str, Any]]) -> dict[str, Any]:
    blocking = [c for c in checklist if c.get("blocking", True)]
    failed = [c for c in blocking if not c.get("ok")]
    return {
        "ok": len(failed) == 0,
        "message": failed[0]["message"] if failed else "",
        "failed_ids": [c["id"] for c in failed],
    }


def warnings_for_stage(stage_num: int, year: int | str, month: str) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    month_path = _month_dir(year, month)
    if stage_num in stage_commands.EMAIL_STAGES:
        warnings.append(
            {
                "code": "EMAIL_STAGE",
                "message": "Etapa de correo: sin «Enviar correos reales» solo analiza/previsualiza.",
            }
        )
    if stage_num == 2:
        warnings.append(
            {
                "code": "OUTLOOK_COM",
                "message": "Requiere Outlook en ejecución en este equipo.",
            }
        )
    if stage_num == 8 and os.path.isdir(month_path):
        warnings.append(
            {
                "code": "STEP8_MAP",
                "message": "Paso 8: sin CSV de mapeo puede pedir datos en consola.",
            }
        )
    xml_count = 0
    if os.path.isdir(month_path):
        xml_count = len([f for f in os.listdir(month_path) if f.lower().endswith(".xml")])
    if stage_num == 3 and xml_count == 0:
        warnings.append(
            {
                "code": "NO_XML",
                "message": "No hay XML en la raíz del mes; ejecuta paso 2 primero.",
            }
        )
    return warnings


def estimated_outputs_for_stage(stage_num: int, year: int | str, month: str) -> list[dict[str, str]]:
    month_path = _month_dir(year, month)
    outputs: list[dict[str, str]] = [
        {"id": "job_log", "label": "Log del job (.log)"},
    ]
    if stage_num == 0:
        outputs.append({"id": "primary", "label": "Solicitud.xlsx generado"})
    elif stage_num == 10:
        outputs.append({"id": "revision_carpetas", "label": "revision_carpetas.xlsx"})
    elif stage_num == 9:
        outputs.append({"id": "resumen_agrupa", "label": "CSV resumen en logs_agrupa/"})
        outputs.append({"id": "primary", "label": "Carpetas IP/CFT por docente"})
    else:
        outputs.append({"id": "primary", "label": "Solicitud.xlsx actualizado"})
    if stage_num in stage_commands.EMAIL_STAGES:
        outputs.append({"id": "outbox", "label": "Entradas en outbox de correo (sqlite)"})
    return outputs


def period_summary(year: int | str, month: str) -> dict[str, Any]:
    """KPIs leídos de Solicitud.xlsx y carpeta del mes."""
    month_path = _month_dir(year, month)
    summary: dict[str, Any] = {
        "year": int(year) if str(year).isdigit() else year,
        "month": month,
        "month_dir": month_path,
        "solicitud_exists": False,
        "total_rows": 0,
        "recibidos": 0,
        "no_recibidos": 0,
        "xml_files_in_month": 0,
        "pdf_files_in_month": 0,
    }
    if not os.path.isdir(month_path):
        return summary

    summary["xml_files_in_month"] = len(
        [f for f in os.listdir(month_path) if f.lower().endswith(".xml")]
    )
    summary["pdf_files_in_month"] = len(
        [f for f in os.listdir(month_path) if f.lower().endswith(".pdf")]
    )
    solicitud = os.path.join(month_path, "Solicitud.xlsx")
    if not os.path.isfile(solicitud):
        return summary

    summary["solicitud_exists"] = True
    try:
        import pandas as pd

        df = pd.read_excel(solicitud, sheet_name=0, engine="openpyxl")
        summary["total_rows"] = int(len(df))
        if "Estado_Recepcion" in df.columns:
            vc = df["Estado_Recepcion"].astype(str).str.upper()
            summary["recibidos"] = int(vc.str.contains("RECIBIDO", na=False).sum())
            summary["no_recibidos"] = int(vc.str.contains("NO RECIBIDO", na=False).sum())
    except Exception as e:
        summary["read_error"] = str(e)
    return summary


def _last_job_for_stage(jobs: list[dict[str, Any]], stage_num: int) -> dict[str, Any] | None:
    filtered = [j for j in jobs if j.get("stage_num") == stage_num]
    if not filtered:
        return None
    filtered.sort(key=lambda j: j.get("created_at", ""), reverse=True)
    return filtered[0]


def _status_from_last_execution(last: dict[str, Any] | None) -> str | None:
    if not last:
        return None
    st = str(last.get("status", "")).lower()
    if st == "running":
        return "RUNNING"
    if st == "failed":
        return "ERROR"
    if st in ("success", "unknown"):
        return "OK"
    return None


def ui_status_for_stage(
    stage_num: int,
    year: int | str,
    month: str,
    *,
    jobs: list[dict[str, Any]] | None = None,
    running_job: dict[str, Any] | None = None,
    last_execution: dict[str, Any] | None = None,
) -> str:
    if running_job and running_job.get("stage_num") == stage_num:
        return "RUNNING"
    last = last_execution
    if not last:
        job = _last_job_for_stage(jobs or [], stage_num)
        if job:
            last = ops_execution_history._api_job_summary(job)
    from_last = _status_from_last_execution(last)
    if from_last:
        return from_last
    if stage_num == 0:
        solicitud = os.path.join(_month_dir(year, month), "Solicitud.xlsx")
        if os.path.isfile(solicitud):
            return "OK"
    checklist = prerequisite_checklist(stage_num, year, month)
    if not prerequisites_summary(checklist)["ok"]:
        return "BLOCKED"
    return "READY"


def period_overview(
    year: int,
    month: str,
    *,
    jobs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    jobs = jobs or []
    period_jobs = [
        j
        for j in jobs
        if str(j.get("year")) == str(year) and str(j.get("month")) == month
    ]
    running = next((j for j in period_jobs if j.get("status") == "running"), None)
    history_by_stage = ops_execution_history.last_executions_by_stage(
        year, month, api_jobs=jobs
    )

    stages_out: list[dict[str, Any]] = []
    for meta in stage_commands.list_stages_metadata():
        sn = meta["stage_num"]
        checklist = prerequisite_checklist(sn, year, month)
        prereq = prerequisites_summary(checklist)
        last = history_by_stage.get(sn)
        stages_out.append(
            {
                **meta,
                "ui_status": ui_status_for_stage(
                    sn,
                    year,
                    month,
                    jobs=period_jobs,
                    running_job=running,
                    last_execution=last,
                ),
                "prerequisites": prereq,
                "checklist": checklist,
                "warnings": warnings_for_stage(sn, year, month),
                "estimated_outputs": estimated_outputs_for_stage(sn, year, month),
                "last_job": last,
            }
        )

    try:
        import email_outbox

        outbox_stats = email_outbox.stats_by_status()
    except Exception:
        outbox_stats = {}

    kpis = period_summary(year, month)
    return {
        "period": {"year": year, "month": month},
        "kpis": kpis,
        "stages": stages_out,
        "running_job": (
            {"id": running["id"], "stage_num": running.get("stage_num"), "type": running.get("type")}
            if running
            else None
        ),
        "outbox_stats": outbox_stats,
        "recommendation": recommend_next_action(
            stages_out, kpis=kpis, running_job=running, outbox_stats=outbox_stats
        ),
    }


def recommend_next_action(
    stages: list[dict[str, Any]],
    *,
    kpis: dict[str, Any],
    running_job: dict[str, Any] | None = None,
    outbox_stats: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Sugerencia del siguiente paso operativo (misma lógica que la UI)."""
    outbox_stats = outbox_stats or {}
    sorted_stages = sorted(stages, key=lambda s: int(s["stage_num"]))

    if running_job:
        sn = int(running_job.get("stage_num", -1))
        return {
            "kind": "wait",
            "stage_num": sn,
            "title": "Job en ejecución",
            "message": f"Espera a que termine el paso {sn} (job {running_job.get('id', '')}).",
            "action_label": "Ver seguimiento",
        }

    pending_outbox = int(outbox_stats.get("pending", 0))
    if pending_outbox > 0:
        return {
            "kind": "outbox",
            "stage_num": None,
            "title": "Correos pendientes en outbox",
            "message": f"Hay {pending_outbox} envío(s) pending. Revisa pestaña Avanzado → Outbox o ejecuta dispatch COM.",
            "action_label": "Ir a Avanzado",
        }

    failed = next(
        (s for s in sorted_stages if s.get("ui_status") == "ERROR" and s.get("enabled_for_api")),
        None,
    )
    if failed:
        sn = int(failed["stage_num"])
        return _recommend_run(
            failed,
            title=f"Reintentar paso {sn}",
            message=f"La última ejecución del paso {sn} falló. Revisa logs y vuelve a ejecutar.",
        )

    if not kpis.get("solicitud_exists"):
        step0 = next((s for s in sorted_stages if s.get("stage_num") == 0), None)
        if step0 and step0.get("ui_status") != "OK":
            return _recommend_run(
                step0,
                title="Generar Solicitud",
                message="No hay Solicitud.xlsx en la carpeta del mes. Empieza por el paso 0.",
            )

    blocked = next((s for s in sorted_stages if s.get("ui_status") == "BLOCKED"), None)
    if blocked:
        sn = int(blocked["stage_num"])
        prereq = blocked.get("prerequisites") or {}
        msg = prereq.get("message") or "Completa los requisitos del checklist."
        return {
            "kind": "fix",
            "stage_num": sn,
            "title": f"Desbloquear paso {sn}",
            "message": msg,
            "action_label": f"Ver paso {sn}",
        }

    def _is_ready_stage(s: dict[str, Any]) -> bool:
        return s.get("ui_status") == "READY" and s.get("enabled_for_api")

    ready = next((s for s in sorted_stages if _is_ready_stage(s)), None)
    if ready and int(ready.get("stage_num", -1)) == 0 and kpis.get("solicitud_exists"):
        ready = next(
            (s for s in sorted_stages if _is_ready_stage(s) and int(s["stage_num"]) > 0),
            None,
        )
    if ready:
        sn = int(ready["stage_num"])
        hint = _stage_run_hint(ready, kpis)
        return _recommend_run(
            ready,
            title=f"Siguiente: paso {sn}",
            message=hint,
        )

    api_stages = [s for s in sorted_stages if s.get("enabled_for_api")]

    def _effectively_complete(s: dict[str, Any]) -> bool:
        if int(s["stage_num"]) == 0 and kpis.get("solicitud_exists"):
            return s.get("ui_status") in ("OK", "READY")
        return s.get("ui_status") == "OK"

    if api_stages and all(_effectively_complete(s) for s in api_stages):
        return {
            "kind": "complete",
            "stage_num": 10,
            "title": "Pipeline API al día",
            "message": "Todos los pasos 0–10 muestran última ejecución OK. Revisa carpeta/revisión o consola si falta algo manual.",
            "action_label": "Ver paso 10",
        }

    return {
        "kind": "review",
        "stage_num": 0,
        "title": "Revisar estado",
        "message": "Revisa el listado de pasos en la barra lateral.",
        "action_label": "Ver paso 0",
    }


def _recommend_run(stage: dict[str, Any], *, title: str, message: str) -> dict[str, Any]:
    sn = int(stage["stage_num"])
    extra = ""
    if stage.get("is_email_stage"):
        extra = " En pasos de correo, marca «Enviar correos reales» solo si corresponde."
    return {
        "kind": "run",
        "stage_num": sn,
        "title": title,
        "message": message + extra,
        "action_label": f"Ir a paso {sn}",
    }


def _stage_run_hint(stage: dict[str, Any], kpis: dict[str, Any]) -> str:
    sn = int(stage["stage_num"])
    desc = str(stage.get("description", ""))
    if sn == 2:
        return f"Extraer boletas del correo ({desc})."
    if sn == 3:
        rec = int(kpis.get("recibidos", 0))
        xml = int(kpis.get("xml_files_in_month", 0))
        return f"Validar recepción ({desc}). Hay {xml} XML y {rec} filas recibidas en Excel."
    if sn == 4:
        return f"Volcar datos XML al Excel ({desc})."
    if sn in (5, 7):
        return f"{desc}. Sin envío real solo previsualiza/analiza."
    if sn == 8:
        return f"{desc}. Usa map_ip_cft.csv en la carpeta del mes (generar con herramienta)."
    return desc or f"Ejecutar paso {sn}."


def _safe_under_roots(path: str) -> bool:
    path = os.path.abspath(path)
    roots = [os.path.abspath(config.RAIZ), os.path.abspath(os.path.join(config.RAIZ, ".state"))]
    return any(path == r or path.startswith(r + os.sep) for r in roots)


def discover_period_artifacts(stage_num: int, year: int | str, month: str) -> list[dict[str, Any]]:
    """Artefactos conocidos en disco para un período/paso."""
    month_path = _month_dir(year, month)
    found: list[dict[str, Any]] = []

    def add(aid: str, label: str, path: str, kind: str) -> None:
        if path and os.path.isfile(path) and _safe_under_roots(path):
            found.append(
                {
                    "id": aid,
                    "label": label,
                    "path": path,
                    "filename": os.path.basename(path),
                    "kind": kind,
                    "exists": True,
                    "size_bytes": os.path.getsize(path),
                }
            )

    solicitud = os.path.join(month_path, "Solicitud.xlsx")
    add("solicitud", "Solicitud.xlsx", solicitud, "xlsx")
    revision = os.path.join(month_path, "revision_carpetas.xlsx")
    add("revision_carpetas", "revision_carpetas.xlsx", revision, "xlsx")

    agrupa_dir = os.path.join(month_path, "logs_agrupa")
    if os.path.isdir(agrupa_dir):
        csvs = sorted(glob.glob(os.path.join(agrupa_dir, "resumen_agrupa_*.csv")))
        if csvs:
            add("resumen_agrupa", "Resumen agrupación (último CSV)", csvs[-1], "csv")

    return found


def artifacts_for_job(job: dict[str, Any]) -> list[dict[str, Any]]:
    """Artefactos descargables asociados a un job."""
    artifacts: list[dict[str, Any]] = []
    job_id = job.get("id", "")

    def add(aid: str, label: str, path: str, kind: str) -> None:
        if not path or not os.path.isfile(path):
            return
        if not _safe_under_roots(path):
            return
        artifacts.append(
            {
                "id": aid,
                "label": label,
                "path": path,
                "filename": os.path.basename(path),
                "kind": kind,
                "exists": True,
                "size_bytes": os.path.getsize(path),
                "download_url": f"/operations/jobs/{job_id}/artifacts/{aid}",
            }
        )

    log_path = job.get("log_path")
    add("job_log", f"Log del job ({job_id})", log_path, "log")

    stage_num = int(job.get("stage_num", 0))
    year = job.get("year")
    month = job.get("month")
    params = job.get("params") or {}

    primary = job.get("output_path")
    if not primary and year and month:
        primary = stage_commands.primary_output_for_stage(stage_num, year, month, params)
    if primary:
        add("primary", os.path.basename(primary), primary, "xlsx")

    if year and month:
        for art in discover_period_artifacts(stage_num, year, month):
            if art["id"] == "primary" and any(a["id"] == "primary" for a in artifacts):
                continue
            if art["id"] not in {a["id"] for a in artifacts}:
                art = dict(art)
                art["download_url"] = f"/operations/jobs/{job_id}/artifacts/{art['id']}"
                artifacts.append(art)

    return artifacts


def resolve_job_artifact_path(job: dict[str, Any], artifact_id: str) -> str | None:
    for art in artifacts_for_job(job):
        if art["id"] == artifact_id and art.get("exists"):
            return art["path"]
    return None
