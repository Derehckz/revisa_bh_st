"""Operaciones de mantenimiento DB invocables desde API o CLI."""
from __future__ import annotations

import os
from typing import Any

from sqlalchemy import func, select

from db.models import Boleta, BoletaXmlData, EnvioEmail, Periodo
from db.session import SessionLocal

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

VALID_ESTADOS_RECEPCION = {"RECIBIDO", "RECIBIDO CON ERROR", "NO RECIBIDO", ""}
VALID_ESTADOS_EMAIL = {"ENVIADO", "ERROR", "PENDIENTE"}


def run_alembic_upgrade() -> dict[str, Any]:
    """Aplica migraciones pendientes (alembic upgrade head)."""
    from alembic import command
    from alembic.config import Config

    ini_path = os.path.join(_REPO_ROOT, "alembic.ini")
    if not os.path.isfile(ini_path):
        raise FileNotFoundError(f"No se encontró {ini_path}")

    cfg = Config(ini_path)
    cfg.set_main_option("script_location", os.path.join(_REPO_ROOT, "alembic"))
    command.upgrade(cfg, "head")
    return {"ok": True, "message": "Migraciones aplicadas (head)"}


def dedupe_period_boletas(*, year: int, month: str) -> dict[str, Any]:
    """
    Elimina duplicados lógicos MTO cuando ya existe su par NB en el período.

    Causa típica: una boleta primero se guarda como `|MTO|...` (sin folio XML)
    y luego reaparece como `|NB|...` al obtener `numeroBoleta_XML`.
    """
    month_norm = (month or "").strip().capitalize()
    with SessionLocal() as session:
        periodo = session.execute(
            select(Periodo).where(Periodo.anio == year, Periodo.mes_nombre == month_norm)
        ).scalar_one_or_none()
        if periodo is None:
            return {"ok": False, "message": f"No existe período {year}-{month_norm} en DB.", "deleted": 0}

        rows = session.execute(select(Boleta).where(Boleta.periodo_id == periodo.id)).scalars().all()
        xml_boleta_ids = set(
            session.execute(
                select(BoletaXmlData.boleta_id)
                .join(Boleta, Boleta.id == BoletaXmlData.boleta_id)
                .where(Boleta.periodo_id == periodo.id)
            ).scalars().all()
        )
        nb_fingerprints = {
            (str(r.emplid or "").strip(), str(r.monto_bruto or ""), str(r.rut_razon or "").strip())
            for r in rows
            if "|NB|" in str(r.boleta_key or "") and r.id in xml_boleta_ids
        }
        to_delete = [
            r
            for r in rows
            if "|MTO|" in str(r.boleta_key or "")
            and r.id not in xml_boleta_ids
            and (
                str(r.emplid or "").strip(),
                str(r.monto_bruto or ""),
                str(r.rut_razon or "").strip(),
            )
            in nb_fingerprints
        ]
        deleted = 0
        for row in to_delete:
            session.delete(row)
            deleted += 1
        session.commit()
        return {
            "ok": True,
            "year": year,
            "month": month_norm,
            "periodo_id": periodo.id,
            "deleted": deleted,
        }


def period_check(year: int, month: str) -> dict[str, Any]:
    """Métricas operativas de un período en PostgreSQL."""
    month_norm = (month or "").strip().capitalize()

    with SessionLocal() as session:
        periodo = session.execute(
            select(Periodo).where(Periodo.anio == year, Periodo.mes_nombre == month_norm)
        ).scalar_one_or_none()
        if periodo is None:
            return {
                "ok": False,
                "year": year,
                "month": month_norm,
                "message": f"No existe período {year}-{month_norm} en DB.",
            }

        total_boletas = session.execute(
            select(func.count(Boleta.id)).where(Boleta.periodo_id == periodo.id)
        ).scalar_one()
        total_xml = session.execute(
            select(func.count(BoletaXmlData.id))
            .join(Boleta, BoletaXmlData.boleta_id == Boleta.id)
            .where(Boleta.periodo_id == periodo.id)
        ).scalar_one()
        total_emails = session.execute(
            select(func.count(EnvioEmail.id)).where(EnvioEmail.periodo_id == periodo.id)
        ).scalar_one()
        recibidos = session.execute(
            select(func.count(Boleta.id)).where(
                Boleta.periodo_id == periodo.id,
                Boleta.estado_recepcion.in_(["RECIBIDO", "RECIBIDO CON ERROR"]),
            )
        ).scalar_one()
        no_recibidos = session.execute(
            select(func.count(Boleta.id)).where(
                Boleta.periodo_id == periodo.id,
                func.coalesce(Boleta.estado_recepcion, "") == "NO RECIBIDO",
            )
        ).scalar_one()
        con_error = session.execute(
            select(func.count(Boleta.id)).where(
                Boleta.periodo_id == periodo.id,
                func.coalesce(Boleta.estado_recepcion, "") == "RECIBIDO CON ERROR",
            )
        ).scalar_one()
        emails_enviados = session.execute(
            select(func.count(EnvioEmail.id)).where(
                EnvioEmail.periodo_id == periodo.id,
                EnvioEmail.estado == "ENVIADO",
            )
        ).scalar_one()
        emails_error = session.execute(
            select(func.count(EnvioEmail.id)).where(
                EnvioEmail.periodo_id == periodo.id,
                EnvioEmail.estado == "ERROR",
            )
        ).scalar_one()

        top_estados = session.execute(
            select(Boleta.estado_recepcion, func.count(Boleta.id))
            .where(Boleta.periodo_id == periodo.id)
            .group_by(Boleta.estado_recepcion)
            .order_by(func.count(Boleta.id).desc())
        ).all()

        pct_xml = (total_xml / total_boletas * 100) if total_boletas else 0.0
        pct_emails = (total_emails / total_boletas * 100) if total_boletas else 0.0
        pct_recibidos = (recibidos / total_boletas * 100) if total_boletas else 0.0

        return {
            "ok": True,
            "year": year,
            "month": month_norm,
            "periodo_id": periodo.id,
            "total_boletas": total_boletas,
            "total_xml": total_xml,
            "xml_coverage_pct": round(pct_xml, 2),
            "total_emails": total_emails,
            "email_coverage_pct": round(pct_emails, 2),
            "recibidos": recibidos,
            "recibidos_pct": round(pct_recibidos, 2),
            "no_recibidos": no_recibidos,
            "recibidos_con_error": con_error,
            "emails_enviados": emails_enviados,
            "emails_error": emails_error,
            "estados_recepcion": [
                {"estado": estado or "(vacío)", "count": cnt} for estado, cnt in top_estados
            ],
        }


def consistency_check(*, limit: int = 20) -> dict[str, Any]:
    """Chequeos de integridad global del dominio."""
    limit = max(1, min(int(limit), 200))
    findings: list[dict[str, Any]] = []
    samples: dict[str, list[str]] = {}

    with SessionLocal() as session:
        boletas_sin_xml = session.execute(
            select(func.count(Boleta.id)).where(~Boleta.id.in_(select(BoletaXmlData.boleta_id)))
        ).scalar_one()
        findings.append({"name": "Boletas sin XML", "severity": "warning", "count": boletas_sin_xml})

        xml_huerfanos = session.execute(
            select(func.count(BoletaXmlData.id)).where(~BoletaXmlData.boleta_id.in_(select(Boleta.id)))
        ).scalar_one()
        findings.append({"name": "XML huérfanos", "severity": "critical", "count": xml_huerfanos})

        estados_invalidos = session.execute(
            select(func.count(Boleta.id)).where(
                ~func.coalesce(Boleta.estado_recepcion, "").in_(VALID_ESTADOS_RECEPCION)
            )
        ).scalar_one()
        findings.append(
            {"name": "Boletas con estado recepción inválido", "severity": "warning", "count": estados_invalidos}
        )

        estados_email_invalidos = session.execute(
            select(func.count(EnvioEmail.id)).where(~EnvioEmail.estado.in_(VALID_ESTADOS_EMAIL))
        ).scalar_one()
        findings.append(
            {"name": "Emails con estado inválido", "severity": "warning", "count": estados_email_invalidos}
        )

        boletas_sin_periodo = session.execute(
            select(func.count(Boleta.id)).where(Boleta.periodo_id.is_(None))
        ).scalar_one()
        findings.append({"name": "Boletas sin período", "severity": "warning", "count": boletas_sin_periodo})

        periodos_sin_boletas = session.execute(
            select(func.count(Periodo.id)).where(~Periodo.id.in_(select(Boleta.periodo_id)))
        ).scalar_one()
        findings.append({"name": "Períodos sin boletas", "severity": "info", "count": periodos_sin_boletas})

        total_boletas = session.execute(select(func.count(Boleta.id))).scalar_one()
        total_emails = session.execute(select(func.count(EnvioEmail.id))).scalar_one()
        total_xml = session.execute(select(func.count(BoletaXmlData.id))).scalar_one()
        cobertura = (total_emails / total_boletas * 100) if total_boletas else 0.0

        if boletas_sin_xml > 0:
            rows = session.execute(
                select(Boleta.id, Boleta.emplid, Boleta.estado_recepcion)
                .where(~Boleta.id.in_(select(BoletaXmlData.boleta_id)))
                .limit(limit)
            ).all()
            samples["boletas_sin_xml"] = [
                f"id={r.id} emplid={r.emplid} estado={r.estado_recepcion}" for r in rows
            ]

        if xml_huerfanos > 0:
            rows = session.execute(
                select(BoletaXmlData.id, BoletaXmlData.boleta_id)
                .where(~BoletaXmlData.boleta_id.in_(select(Boleta.id)))
                .limit(limit)
            ).all()
            samples["xml_huerfanos"] = [f"id={r.id} boleta_id={r.boleta_id}" for r in rows]

    critical = sum(1 for f in findings if f["severity"] == "critical" and f["count"] > 0)
    warnings = sum(1 for f in findings if f["severity"] == "warning" and f["count"] > 0)

    return {
        "ok": critical == 0,
        "total_boletas": total_boletas,
        "total_xml": total_xml,
        "total_emails": total_emails,
        "email_coverage_pct": round(cobertura, 2),
        "findings": findings,
        "critical_count": critical,
        "warning_count": warnings,
        "samples": samples,
    }


def _backup_root() -> str:
    path = os.path.join(_REPO_ROOT, ".backups", "postgres")
    os.makedirs(path, exist_ok=True)
    return path


def create_postgres_backup(*, keep: int = 14) -> dict[str, Any]:
    """Ejecuta pg_dump hacia .backups/postgres/."""
    import subprocess
    from datetime import datetime

    from db.session import _get_db_setting

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(_backup_root(), f"bh_{stamp}.dump")
    env = os.environ.copy()
    password = _get_db_setting("PASSWORD", "")
    if password:
        env["PGPASSWORD"] = password
    cmd = [
        "pg_dump",
        "-h",
        _get_db_setting("HOST", "localhost"),
        "-p",
        str(_get_db_setting("PORT", "5432")),
        "-U",
        _get_db_setting("USER", "boletas_app"),
        "-d",
        _get_db_setting("NAME", "boletas_honorarios"),
        "-Fc",
        "-f",
        out_path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "No se encontró pg_dump en PATH. Instala cliente PostgreSQL o agrega bin/ al PATH."
        ) from exc
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "pg_dump falló")

    size = os.path.getsize(out_path) if os.path.isfile(out_path) else 0
    # Retención
    dumps = sorted(
        (
            os.path.join(_backup_root(), name)
            for name in os.listdir(_backup_root())
            if name.endswith(".dump")
        ),
        key=os.path.getmtime,
        reverse=True,
    )
    removed = 0
    for old in dumps[max(1, int(keep)) :]:
        try:
            os.remove(old)
            removed += 1
        except OSError:
            pass
    return {
        "ok": True,
        "path": out_path,
        "filename": os.path.basename(out_path),
        "size_bytes": size,
        "kept": min(len(dumps), max(1, int(keep))),
        "removed": removed,
        "message": f"Backup creado: {os.path.basename(out_path)}",
    }


def list_postgres_backups(*, limit: int = 20) -> dict[str, Any]:
    root = _backup_root()
    rows = []
    for name in os.listdir(root):
        if not name.endswith(".dump"):
            continue
        path = os.path.join(root, name)
        try:
            st = os.stat(path)
        except OSError:
            continue
        rows.append(
            {
                "filename": name,
                "path": path,
                "size_bytes": st.st_size,
                "mtime": st.st_mtime,
            }
        )
    rows.sort(key=lambda r: r["mtime"], reverse=True)
    return {"backups_dir": root, "backups": rows[: max(1, min(int(limit), 100))]}

