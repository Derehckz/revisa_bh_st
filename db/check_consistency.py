"""Chequeos de consistencia de datos en tablas de dominio."""
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


VALID_ESTADOS_RECEPCION = {"RECIBIDO", "RECIBIDO CON ERROR", "NO RECIBIDO", ""}
VALID_ESTADOS_EMAIL = {"ENVIADO", "ERROR", "PENDIENTE"}


def main() -> int:
    utils.asegurar_utf8_salida()
    parser = argparse.ArgumentParser(description="Chequeo de consistencia del dominio")
    parser.add_argument("--limit", type=int, default=10, help="Muestras máximas por hallazgo")
    args = parser.parse_args()

    utils.print_header("CHECK CONSISTENCY", "Integridad de tablas de dominio")

    findings: list[tuple[str, str, int]] = []

    with SessionLocal() as session:
        # 1) Boletas sin XML asociado
        boletas_sin_xml = session.execute(
            select(func.count(Boleta.id)).where(
                ~Boleta.id.in_(select(BoletaXmlData.boleta_id))
            )
        ).scalar_one()
        findings.append(("Boletas sin XML", "warning", boletas_sin_xml))

        # 2) XML huérfanos (boleta inexistente)
        xml_huerfanos = session.execute(
            select(func.count(BoletaXmlData.id)).where(
                ~BoletaXmlData.boleta_id.in_(select(Boleta.id))
            )
        ).scalar_one()
        findings.append(("XML huérfanos", "critical", xml_huerfanos))

        # 3) Estados de recepción no válidos
        estados_invalidos = session.execute(
            select(func.count(Boleta.id)).where(
                ~func.coalesce(Boleta.estado_recepcion, "").in_(VALID_ESTADOS_RECEPCION)
            )
        ).scalar_one()
        findings.append(("Boletas con estado recepción inválido", "warning", estados_invalidos))

        # 4) Estados de email no válidos
        estados_email_invalidos = session.execute(
            select(func.count(EnvioEmail.id)).where(
                ~EnvioEmail.estado.in_(VALID_ESTADOS_EMAIL)
            )
        ).scalar_one()
        findings.append(("Emails con estado inválido", "warning", estados_email_invalidos))

        # 5) Boletas sin período
        boletas_sin_periodo = session.execute(
            select(func.count(Boleta.id)).where(Boleta.periodo_id.is_(None))
        ).scalar_one()
        findings.append(("Boletas sin período", "warning", boletas_sin_periodo))

        # 6) Períodos sin boletas
        periodos_sin_boletas = session.execute(
            select(func.count(Periodo.id)).where(
                ~Periodo.id.in_(select(Boleta.periodo_id))
            )
        ).scalar_one()
        findings.append(("Períodos sin boletas", "info", periodos_sin_boletas))

        # 7) Cobertura de emails por boleta (aprox por período)
        total_boletas = session.execute(select(func.count(Boleta.id))).scalar_one()
        total_emails = session.execute(select(func.count(EnvioEmail.id))).scalar_one()
        cobertura = (total_emails / total_boletas * 100) if total_boletas else 0.0

        utils.print_table(
            "Resumen consistencia",
            [
                ("Total boletas", total_boletas),
                ("Total XML", session.execute(select(func.count(BoletaXmlData.id))).scalar_one()),
                ("Total emails", total_emails),
                ("Cobertura email/boleta (%)", f"{cobertura:.2f}%"),
            ],
        )

        utils.print_section("Hallazgos")
        for name, severity, count in findings:
            icon = {"critical": "❌", "warning": "⚠️", "info": "ℹ️"}.get(severity, "•")
            utils.console.print(f"{icon} {name}: {count}")

        # Muestras para depurar
        if boletas_sin_xml > 0:
            rows = session.execute(
                select(Boleta.id, Boleta.emplid, Boleta.estado_recepcion)
                .where(~Boleta.id.in_(select(BoletaXmlData.boleta_id)))
                .limit(max(1, args.limit))
            ).all()
            utils.print_section("Muestra boletas sin XML")
            utils.print_list(
                "Registros",
                [f"id={r.id} emplid={r.emplid} estado={r.estado_recepcion}" for r in rows],
            )

        if xml_huerfanos > 0:
            rows = session.execute(
                select(BoletaXmlData.id, BoletaXmlData.boleta_id)
                .where(~BoletaXmlData.boleta_id.in_(select(Boleta.id)))
                .limit(max(1, args.limit))
            ).all()
            utils.print_section("Muestra XML huérfanos")
            utils.print_list("Registros", [f"id={r.id} boleta_id={r.boleta_id}" for r in rows])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
