"""Contexto operativo para la UI de Operación (prerequisitos, KPIs, artefactos)."""
from __future__ import annotations

import glob
import os
from datetime import datetime
from typing import Any

import config
import ops_execution_history
import stage_commands
import inbox_gaps

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
            vc = df["Estado_Recepcion"].astype(str).str.upper().str.strip()
            summary["recibidos"] = int(vc.isin({"RECIBIDO", "RECIBIDO CON ERROR"}).sum())
            summary["no_recibidos"] = int((vc == "NO RECIBIDO").sum())
    except Exception as e:
        summary["read_error"] = str(e)
    return summary


def _cell_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        import pandas as pd

        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in {"nan", "none", "nat"}:
        return ""
    return text


def _classify_mail_flag(value: Any) -> str:
    text = _cell_str(value)
    if not text:
        return "pendiente"
    low = text.lower()
    if "❌" in text or "error" in low or "inválido" in low or "invalido" in low:
        return "error"
    if "omitido" in low:
        return "omitido"
    if "✅" in text or "enviado" in low:
        return "enviado"
    return "otro"


def _classify_xml_obs(value: Any) -> str:
    text = _cell_str(value)
    if not text:
        return "pendiente"
    low = text.upper()
    if "DATOS EXTRAIDOS OK" in low or low.endswith(" OK") or "EXTRAIDOS OK" in low:
        return "ok"
    return "observacion"


def _read_solicitud_workbook(path: str):
    """Lee hojas útiles de Solicitud.xlsx; si Excel lo tiene abierto, copia a temp."""
    import shutil
    import tempfile

    import pandas as pd
    from openpyxl import load_workbook
    from schema_validator import find_sheet

    def _load(src: str):
        wb = load_workbook(src, read_only=True, data_only=True)
        try:
            sheet_names = list(wb.sheetnames)
        finally:
            wb.close()
        solicitud_sheet = find_sheet(sheet_names, "Solicitud") or sheet_names[0]
        df = pd.read_excel(src, sheet_name=solicitud_sheet, engine="openpyxl")
        pagos_sheet = find_sheet(sheet_names, "Pagos")
        df_pagos = None
        if pagos_sheet:
            df_pagos = pd.read_excel(src, sheet_name=pagos_sheet, engine="openpyxl")
        return df, sheet_names, solicitud_sheet, pagos_sheet, df_pagos

    try:
        return _load(path)
    except PermissionError:
        fd, tmp = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        try:
            shutil.copy2(path, tmp)
            return _load(tmp)
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass


def excel_avance(year: int | str, month: str, *, row_limit: int = 500) -> dict[str, Any]:
    """Avance vivo leído de Solicitud.xlsx (sin abrir el archivo en Excel)."""
    month_path = _month_dir(year, month)
    out: dict[str, Any] = {
        "year": int(year) if str(year).isdigit() else year,
        "month": month,
        "month_dir": month_path,
        "solicitud_path": os.path.join(month_path, "Solicitud.xlsx"),
        "solicitud_exists": False,
        "sheets": [],
        "solicitud_sheet": None,
        "total_rows": 0,
        "recepcion": {
            "recibido": 0,
            "recibido_con_error": 0,
            "no_recibido": 0,
            "pendiente": 0,
            "otro": 0,
        },
        "correo_solicitud": {"enviado": 0, "omitido": 0, "error": 0, "pendiente": 0, "otro": 0},
        "recordatorios": {"con_recordatorio": 0, "total_envios": 0},
        "xml_extract": {"ok": 0, "observacion": 0, "pendiente": 0, "con_archivo": 0},
        "archivos_mes": {"xml": 0, "pdf": 0},
        "pagos": {
            "sheet_exists": False,
            "total_rows": 0,
            "enviado": 0,
            "pendiente": 0,
            "error": 0,
            "omitido": 0,
            "otro": 0,
        },
        "rows": [],
        "rows_truncated": False,
        "read_error": None,
        "mtime": None,
    }

    if not os.path.isdir(month_path):
        return out

    out["archivos_mes"]["xml"] = len(
        [f for f in os.listdir(month_path) if f.lower().endswith(".xml")]
    )
    out["archivos_mes"]["pdf"] = len(
        [f for f in os.listdir(month_path) if f.lower().endswith(".pdf")]
    )

    solicitud = out["solicitud_path"]
    if not os.path.isfile(solicitud):
        return out

    out["solicitud_exists"] = True
    try:
        out["mtime"] = datetime.fromtimestamp(os.path.getmtime(solicitud)).isoformat(timespec="seconds")
    except OSError:
        pass

    try:
        df, sheet_names, sheet, pagos_sheet, df_pagos = _read_solicitud_workbook(solicitud)
        out["sheets"] = sheet_names
        out["solicitud_sheet"] = sheet
        out["total_rows"] = int(len(df))

        if "Estado_Recepcion" in df.columns:
            for raw in df["Estado_Recepcion"]:
                estado = _cell_str(raw).upper()
                if estado == "RECIBIDO":
                    out["recepcion"]["recibido"] += 1
                elif estado == "RECIBIDO CON ERROR":
                    out["recepcion"]["recibido_con_error"] += 1
                elif estado == "NO RECIBIDO":
                    out["recepcion"]["no_recibido"] += 1
                elif not estado:
                    out["recepcion"]["pendiente"] += 1
                else:
                    out["recepcion"]["otro"] += 1

        if "Correo Enviado" in df.columns:
            for raw in df["Correo Enviado"]:
                out["correo_solicitud"][_classify_mail_flag(raw)] += 1

        if "Recordatorios Enviados" in df.columns:
            for raw in df["Recordatorios Enviados"]:
                text = _cell_str(raw)
                if not text:
                    continue
                try:
                    n = int(float(text.replace(",", ".")))
                except ValueError:
                    digits = "".join(ch for ch in text if ch.isdigit())
                    n = int(digits) if digits else 0
                if n > 0:
                    out["recordatorios"]["con_recordatorio"] += 1
                    out["recordatorios"]["total_envios"] += n

        if "Observaciones_XML" in df.columns:
            for raw in df["Observaciones_XML"]:
                out["xml_extract"][_classify_xml_obs(raw)] += 1
        else:
            out["xml_extract"]["pendiente"] = out["total_rows"]

        if "archivo_xml" in df.columns:
            out["xml_extract"]["con_archivo"] = int(
                sum(1 for raw in df["archivo_xml"] if _cell_str(raw))
            )

        if pagos_sheet and df_pagos is not None:
            out["pagos"]["sheet_exists"] = True
            out["pagos"]["total_rows"] = int(len(df_pagos))
            if "Correo Enviado" in df_pagos.columns:
                for raw in df_pagos["Correo Enviado"]:
                    out["pagos"][_classify_mail_flag(raw)] += 1
            else:
                out["pagos"]["pendiente"] = out["pagos"]["total_rows"]

        if row_limit > 0:
            limit = min(int(row_limit), len(df))
            out["rows_truncated"] = len(df) > limit
            rows: list[dict[str, Any]] = []

            def _f(row_obj: Any, *names: str) -> str:
                for name in names:
                    if name in df.columns:
                        return _cell_str(row_obj.get(name))
                return ""

            for idx in range(limit):
                row = df.iloc[idx]
                correo_raw = row.get("Correo Enviado") if "Correo Enviado" in df.columns else ""
                obs_xml_raw = (
                    row.get("Observaciones_XML") if "Observaciones_XML" in df.columns else ""
                )
                rows.append(
                    {
                        "row": int(idx) + 2,
                        "emplid": _f(row, "EMPLID"),
                        "rut_sin_dv": _f(row, "RUT_SIN_DV"),
                        "name": _f(row, "NAME"),
                        "sede": _f(row, "SEDE"),
                        "location": _f(row, "LOCATION"),
                        "email": _f(row, "Email_Docente"),
                        "email_dp": _f(row, "Email_DP"),
                        "rut_razon": _f(row, "RUT RAZON"),
                        "nombre_razon": _f(row, "NOMBRE RAZON"),
                        "direccion_razon": _f(row, "DireccionRazon"),
                        "glosa": _f(row, "GLOSA"),
                        "estado_recepcion": _f(row, "Estado_Recepcion"),
                        "correo_enviado": _f(row, "Correo Enviado"),
                        "correo_clase": _classify_mail_flag(correo_raw),
                        "recordatorios": _f(row, "Recordatorios Enviados"),
                        "observaciones": _f(row, "Observaciones"),
                        "observacion_descartes": _f(row, "Observacion_Descartes"),
                        "archivo_xml": _f(row, "archivo_xml"),
                        "archivo_xml_usado": _f(row, "Archivo_XML_Usado"),
                        "observaciones_xml": _f(row, "Observaciones_XML"),
                        "xml_clase": _classify_xml_obs(obs_xml_raw),
                        "numero_boleta_xml": _f(row, "numeroBoleta_XML"),
                        "fecha_boleta_xml": _f(row, "fechaBoleta_XML"),
                        "rut_emisor_xml": _f(row, "rutEmisorCompleto_XML"),
                        "rut_receptor_xml": _f(row, "rutReceptorCompleto_XML"),
                        "nombre_receptor_xml": _f(row, "nombreReceptor_XML"),
                        "total_honorarios_xml": _f(row, "totalHonorarios_XML"),
                        "liquido_honorarios_xml": _f(row, "liquidoHonorarios_XML"),
                        "impuesto_honorarios_xml": _f(row, "impuestoHonorarios_XML"),
                        "descripcion_xml": _f(row, "descripcionLinea_XML"),
                        "correo_recepcion_enviado": _f(row, "Correo_Recepcion_Enviado"),
                        "monto": _f(row, "CUS_TOT_HON"),
                    }
                )
            out["rows"] = rows
    except Exception as e:
        out["read_error"] = str(e)

    return out


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


def inbox_gaps_scan(
    year: int | str,
    month: str,
    *,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
) -> dict[str, Any]:
    """Huecos Inbox↔carpeta para filas NO RECIBIDO (detector Maass)."""
    return inbox_gaps.detectar_huecos_inbox(
        year,
        month,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )


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
    period_status = None
    try:
        import period_policy

        period_status = period_policy.get_period_status(year, month)
    except Exception:
        period_status = None

    try:
        import sync_status

        sync_status_out = sync_status.period_sync_status(year, month)
    except Exception as exc:
        sync_status_out = {"status": "unknown", "message": f"No se pudo evaluar sync_status: {exc}", "details": {}}

    return {
        "period": {"year": year, "month": month, "status": period_status or "abierto"},
        "kpis": kpis,
        "stages": stages_out,
        "running_job": (
            {"id": running["id"], "stage_num": running.get("stage_num"), "type": running.get("type")}
            if running
            else None
        ),
        "outbox_stats": outbox_stats,
        "sync_status": sync_status_out,
        "recommendation": recommend_next_action(
            stages_out,
            kpis=kpis,
            running_job=running,
            outbox_stats=outbox_stats,
            period_status=period_status,
        ),
    }


def recommend_next_action(
    stages: list[dict[str, Any]],
    *,
    kpis: dict[str, Any],
    running_job: dict[str, Any] | None = None,
    outbox_stats: dict[str, int] | None = None,
    period_status: str | None = None,
) -> dict[str, Any]:
    """Sugerencia del siguiente paso operativo (misma lógica que la UI)."""
    outbox_stats = outbox_stats or {}
    try:
        import period_policy

        if period_policy.is_closed_status(period_status):
            return {
                "kind": "review",
                "stage_num": None,
                "title": "Período cerrado",
                "message": (
                    "Este período está cerrado en la base de datos. "
                    "La API no permite jobs ni sesiones interactivas. "
                    "Selecciona un mes abierto o usa la consola con supervisión manual."
                ),
                "action_label": "Cambiar período",
            }
    except Exception:
        pass

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

    no_recibidos = int(kpis.get("no_recibidos") or 0)
    stage3 = next((s for s in sorted_stages if int(s.get("stage_num", -1)) == 3), None)
    stage3_ok = bool(stage3 and stage3.get("ui_status") == "OK")

    def _reminders_recommendation() -> dict[str, Any]:
        return {
            "kind": "reminders",
            "stage_num": 1,
            "title": "Recordatorios a pendientes",
            "message": (
                f"Hay {no_recibidos} fila(s) NO RECIBIDO. "
                "Vuelve al paso 1 en modo solo recordatorios (no reenvía solicitudes originales)."
            ),
            "action_label": "Paso 1 · solo recordatorios",
            "params": {"reminders_only": True},
        }

    # Tras validar (paso 3 OK), si ya no hay trabajo de recepción 2–5 pendiente
    # y aún faltan boletas → priorizar recordatorios antes de pasos ≥6 o “completo”.
    if no_recibidos > 0 and stage3_ok:
        inbound_ready = (
            ready is not None and int(ready.get("stage_num", -1)) in (2, 3, 4, 5)
        )
        if not inbound_ready:
            return _reminders_recommendation()

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
        if no_recibidos > 0 and stage3_ok:
            return _reminders_recommendation()
        return {
            "kind": "complete",
            "stage_num": 10,
            "title": "Pipeline API al día",
            "message": "Todos los pasos 0–10 muestran última ejecución OK. Revisa carpeta/revisión o consola si falta algo manual.",
            "action_label": "Ver paso 10",
        }

    if no_recibidos > 0 and stage3_ok:
        return _reminders_recommendation()

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
