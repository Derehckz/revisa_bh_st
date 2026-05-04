"""Consulta rápida de tablas de dominio para validar dual-write."""
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


def _last_periodo_label(periodo: Periodo | None) -> str:
    if periodo is None:
        return "-"
    return f"{periodo.anio}-{periodo.mes_nombre}"


def main() -> int:
    utils.asegurar_utf8_salida()

    parser = argparse.ArgumentParser(description="Revisar estado de tablas de dominio")
    parser.add_argument("--limit", type=int, default=5, help="Cantidad de registros de muestra por sección")
    args = parser.parse_args()

    utils.print_header("CHECK DOMAIN TABLES", "Validación dual-write")

    with SessionLocal() as session:
        total_periodos = session.execute(select(func.count(Periodo.id))).scalar_one()
        total_boletas = session.execute(select(func.count(Boleta.id))).scalar_one()
        total_xml = session.execute(select(func.count(BoletaXmlData.id))).scalar_one()
        total_emails = session.execute(select(func.count(EnvioEmail.id))).scalar_one()

        last_periodo = (
            session.execute(select(Periodo).order_by(Periodo.id.desc()).limit(1))
            .scalars()
            .first()
        )

        utils.print_table(
            "Resumen dominio",
            [
                ("Períodos", total_periodos),
                ("Boletas", total_boletas),
                ("Boleta XML Data", total_xml),
                ("Eventos Email", total_emails),
                ("Último período", _last_periodo_label(last_periodo)),
            ],
        )

        boletas = (
            session.execute(
                select(Boleta).order_by(Boleta.id.desc()).limit(max(1, args.limit))
            )
            .scalars()
            .all()
        )
        if boletas:
            utils.print_section("Muestra boletas")
            utils.print_table(
                "Boletas recientes",
                [
                    (
                        f"id={b.id}",
                        f"emplid={b.emplid} | estado={b.estado_recepcion or '-'} | monto={b.monto_bruto or '-'}",
                    )
                    for b in boletas
                ],
            )
        else:
            utils.print_warning("Aún no hay boletas registradas.")

        xml_rows = (
            session.execute(
                select(BoletaXmlData).order_by(BoletaXmlData.id.desc()).limit(max(1, args.limit))
            )
            .scalars()
            .all()
        )
        if xml_rows:
            utils.print_section("Muestra XML")
            utils.print_table(
                "XML recientes",
                [
                    (
                        f"id={x.id} boleta_id={x.boleta_id}",
                        f"numero={x.numero_boleta or '-'} | total={x.total_honorarios or '-'} | obs={x.observaciones_xml or '-'}",
                    )
                    for x in xml_rows
                ],
            )
        else:
            utils.print_warning("Aún no hay datos XML registrados.")

        email_rows = (
            session.execute(
                select(EnvioEmail).order_by(EnvioEmail.id.desc()).limit(max(1, args.limit))
            )
            .scalars()
            .all()
        )
        if email_rows:
            utils.print_section("Muestra emails")
            utils.print_table(
                "Emails recientes",
                [
                    (
                        f"id={e.id} {e.tipo_envio}",
                        f"to={e.to_email} | estado={e.estado} | periodo={e.periodo_label or '-'}",
                    )
                    for e in email_rows
                ],
            )
        else:
            utils.print_warning("Aún no hay eventos de email registrados.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
