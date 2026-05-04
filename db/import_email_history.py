"""Carga histórica de envíos de correo desde Solicitud.xlsx (hojas operativas)."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime

if __package__ is None or __package__ == "":
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    _lib = os.path.join(_root, "lib")
    for _p in (_lib, _root):
        if _p not in sys.path:
            sys.path.insert(0, _p)

import pandas as pd
from sqlalchemy import select

from db.import_excel_snapshot import REQUIRED_SOLICITUD_COLUMNS, detect_solicitud_sheet
from db.models import EnvioEmail, Periodo
from db.session import SessionLocal
from db.file_repository import get_or_create_periodo
import utils


def _clean(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def _infer_estado(correo_enviado: str) -> str:
    t = correo_enviado.lower()
    if "✅" in t or "enviado" in t:
        return "ENVIADO"
    if "❌" in t or "error" in t or "inválido" in t or "invalido" in t:
        return "ERROR"
    return "PENDIENTE"


def _infer_tipo(correo_enviado: str) -> str:
    t = correo_enviado.lower()
    if "recordatorio" in t:
        return "RECORDATORIO"
    return "SOLICITUD"


def import_month(file_path: str, year: int, month_name: str) -> dict:
    sheet = detect_solicitud_sheet(file_path)
    df0 = pd.read_excel(file_path, sheet_name=sheet, engine="openpyxl", nrows=0)
    cols = set(map(str, df0.columns))
    if not REQUIRED_SOLICITUD_COLUMNS.issubset(cols):
        raise ValueError(f"Hoja {sheet} no cumple esquema operativo requerido.")

    df = pd.read_excel(file_path, sheet_name=sheet, engine="openpyxl")
    meses = [m.lower() for m in ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]]
    mes_num = meses.index(month_name.lower()) + 1
    periodo_id = get_or_create_periodo(year, mes_num, month_name)
    if periodo_id is None:
        raise RuntimeError("No fue posible crear/obtener período.")

    stats = {"rows": len(df), "inserted": 0, "updated": 0, "skipped": 0, "errors": 0, "sheet": sheet}

    with SessionLocal() as session:
        for _, row in df.iterrows():
            try:
                to_email = _clean(row.get("Email_Docente"))
                if not to_email:
                    stats["skipped"] += 1
                    continue

                correo_enviado = _clean(row.get("Correo Enviado"))
                estado = _infer_estado(correo_enviado)
                tipo = _infer_tipo(correo_enviado)
                subject = f"{tipo} {month_name} {year}"
                cc_email = _clean(row.get("Email_DP")) or None
                error_detalle = correo_enviado if estado == "ERROR" else None
                periodo_label = f"{year}-{month_name}"

                existing = session.execute(
                    select(EnvioEmail).where(
                        EnvioEmail.periodo_id == periodo_id,
                        EnvioEmail.to_email == to_email,
                        EnvioEmail.tipo_envio == tipo,
                    )
                ).scalar_one_or_none()

                if existing is None:
                    row_db = EnvioEmail(
                        periodo_id=periodo_id,
                        periodo_label=periodo_label,
                        tipo_envio=tipo,
                        to_email=to_email,
                        cc_email=cc_email,
                        subject=subject,
                        estado=estado,
                        error_detalle=error_detalle,
                        sent_at=datetime.now(UTC) if estado == "ENVIADO" else None,
                    )
                    session.add(row_db)
                    stats["inserted"] += 1
                else:
                    existing.cc_email = cc_email
                    existing.subject = subject
                    existing.estado = estado
                    existing.error_detalle = error_detalle
                    existing.periodo_label = periodo_label
                    if estado == "ENVIADO" and existing.sent_at is None:
                        existing.sent_at = datetime.now(UTC)
                    stats["updated"] += 1
            except Exception:
                stats["errors"] += 1

        session.commit()

    return stats


def main() -> int:
    utils.asegurar_utf8_salida()
    parser = argparse.ArgumentParser(description="Importar histórico de envíos de correo desde 2026/*/Solicitud.xlsx")
    parser.add_argument("--root-2026", required=True, help="Ruta raíz del año 2026")
    args = parser.parse_args()

    utils.print_header("IMPORT EMAIL HISTORY", "Solicitud.xlsx -> envios_email")
    root = args.root_2026
    months = [m for m in sorted(os.listdir(root)) if os.path.isdir(os.path.join(root, m))]
    totals = {"rows": 0, "inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

    for month in months:
        xlsx = os.path.join(root, month, "Solicitud.xlsx")
        if not os.path.isfile(xlsx):
            continue
        stats = import_month(xlsx, 2026, month)
        totals["rows"] += stats["rows"]
        totals["inserted"] += stats["inserted"]
        totals["updated"] += stats["updated"]
        totals["skipped"] += stats["skipped"]
        totals["errors"] += stats["errors"]
        utils.print_table(
            f"Mes {month}",
            [
                ("Hoja usada", stats["sheet"]),
                ("Filas", stats["rows"]),
                ("Insertados", stats["inserted"]),
                ("Actualizados", stats["updated"]),
                ("Omitidos (sin email)", stats["skipped"]),
                ("Errores", stats["errors"]),
            ],
        )

    utils.print_section("Resumen total")
    utils.print_table(
        "Total histórico emails 2026",
        [
            ("Filas", totals["rows"]),
            ("Insertados", totals["inserted"]),
            ("Actualizados", totals["updated"]),
            ("Omitidos", totals["skipped"]),
            ("Errores", totals["errors"]),
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
