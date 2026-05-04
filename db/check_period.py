"""Dashboard CLI por período (año/mes) para métricas operativas."""
from __future__ import annotations

import argparse
import os
import sys

if __package__ is None or __package__ == "":
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    _lib = os.path.join(_root, "lib")
    for _p in (_lib, _root):
        if _p not in sys.path:
            sys.path.insert(0, _p)

from sqlalchemy import func, select

from db.models import Boleta, BoletaXmlData, EnvioEmail, Periodo
from db.session import SessionLocal
import utils


def _normalize_month(name: str) -> str:
    return (name or "").strip().capitalize()


def main() -> int:
    utils.asegurar_utf8_salida()
    parser = argparse.ArgumentParser(description="Métricas de un período en DB")
    parser.add_argument("--year", type=int, required=True, help="Año, ej: 2026")
    parser.add_argument("--month", type=str, required=True, help="Mes, ej: Abril")
    args = parser.parse_args()

    month = _normalize_month(args.month)
    utils.print_header("CHECK PERIOD", f"{args.year}-{month}")

    with SessionLocal() as session:
        periodo = session.execute(
            select(Periodo).where(Periodo.anio == args.year, Periodo.mes_nombre == month)
        ).scalar_one_or_none()
        if periodo is None:
            utils.print_error(f"No existe período {args.year}-{month} en DB.")
            return 1

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

        pct_xml = (total_xml / total_boletas * 100) if total_boletas else 0.0
        pct_emails = (total_emails / total_boletas * 100) if total_boletas else 0.0
        pct_recibidos = (recibidos / total_boletas * 100) if total_boletas else 0.0

        utils.print_table(
            "Resumen período",
            [
                ("Período ID", periodo.id),
                ("Total boletas", total_boletas),
                ("Total XML", total_xml),
                ("Cobertura XML", f"{pct_xml:.2f}%"),
                ("Total emails", total_emails),
                ("Cobertura emails", f"{pct_emails:.2f}%"),
                ("Recibidos (OK + error)", f"{recibidos} ({pct_recibidos:.2f}%)"),
                ("No recibidos", no_recibidos),
                ("Recibidos con error", con_error),
                ("Emails enviados", emails_enviados),
                ("Emails con error", emails_error),
            ],
        )

        top_estados = session.execute(
            select(Boleta.estado_recepcion, func.count(Boleta.id))
            .where(Boleta.periodo_id == periodo.id)
            .group_by(Boleta.estado_recepcion)
            .order_by(func.count(Boleta.id).desc())
        ).all()
        if top_estados:
            utils.print_section("Distribución estado recepción")
            utils.print_list(
                "Estados",
                [f"{estado or '(vacío)'}: {cnt}" for estado, cnt in top_estados],
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
