"""Deduplicación de boletas por período priorizando filas con mejor estado."""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import UTC, datetime

if __package__ is None or __package__ == "":
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    _lib = os.path.join(_root, "lib")
    for _p in (_lib, _root):
        if _p not in sys.path:
            sys.path.insert(0, _p)

from sqlalchemy import select

from db.models import Archivo, Boleta, BoletaXmlData, EnvioEmail, Periodo
from db.session import SessionLocal
import utils


def _norm(value: object) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s.lower() == "nan" else s


def _signature(row: Boleta) -> str:
    xml_name = _norm(row.descripcion)
    if xml_name:
        # Priorizar archivo XML/PDF asociado porque representa la misma boleta real
        # incluso si cambia boleta_key entre NB/XML.
        return f"XMLFILE|{xml_name.lower()}"
    key = _norm(row.boleta_key)
    if key:
        key_norm = re.sub(r"\|IDX\|\d+$", "", key, flags=re.IGNORECASE)
        if "|NB|" in key_norm or "|XML|" in key_norm:
            return f"KEY|{key_norm}"
    # Fallback seguro para duplicados por reimportación de snapshot corto:
    # solo se usa en combinación con reglas conservadoras más abajo.
    trio = f"{_norm(row.emplid)}|{_norm(row.rut_razon)}|{_norm(row.monto_bruto)}|{_norm(row.estado_recepcion)}"
    if _norm(row.emplid) and _norm(row.rut_razon) and _norm(row.monto_bruto):
        return f"TRIO|{trio}"
    return ""


def _score(row: Boleta, has_xml: bool) -> tuple[int, int, datetime]:
    estado = _norm(row.estado_recepcion).upper()
    estado_score = 0
    if estado == "RECIBIDO":
        estado_score = 3
    elif estado == "RECIBIDO CON ERROR":
        estado_score = 2
    elif estado == "NO RECIBIDO":
        estado_score = 1
    xml_score = 1 if has_xml else 0
    updated = row.updated_at or datetime.min.replace(tzinfo=UTC)
    return (estado_score, xml_score, updated)


def run(year: int, month: str) -> dict:
    month_norm = month.strip().capitalize()
    stats = {"period_id": None, "total_before": 0, "deleted": 0, "groups_merged": 0}

    with SessionLocal() as session:
        periodo = session.execute(
            select(Periodo).where(Periodo.anio == year, Periodo.mes_nombre == month_norm)
        ).scalar_one_or_none()
        if not periodo:
            raise RuntimeError(f"No existe período {year}-{month_norm}")
        stats["period_id"] = periodo.id

        rows = session.execute(
            select(Boleta).where(Boleta.periodo_id == periodo.id).order_by(Boleta.id.asc())
        ).scalars().all()
        stats["total_before"] = len(rows)
        if not rows:
            return stats

        xml_by_boleta = {
            x.boleta_id: x
            for x in session.execute(
                select(BoletaXmlData).join(Boleta, Boleta.id == BoletaXmlData.boleta_id).where(Boleta.periodo_id == periodo.id)
            ).scalars().all()
        }

        grouped: dict[str, list[Boleta]] = {}
        for row in rows:
            sig = _signature(row)
            if sig:
                grouped.setdefault(sig, []).append(row)

        for _, group_rows in grouped.items():
            if len(group_rows) <= 1:
                continue

            informed = [r for r in group_rows if _norm(r.estado_recepcion)]
            empty_state = [r for r in group_rows if not _norm(r.estado_recepcion)]
            duplicates: list[Boleta] = []
            if informed and empty_state:
                # Caso clásico: conservar fila informada y borrar las vacías.
                keeper = max(informed, key=lambda b: _score(b, b.id in xml_by_boleta))
                duplicates = empty_state
            else:
                # Caso de duplicados informados (misma BH replicada): conservar la mejor.
                sig = _signature(group_rows[0])
                if not sig:
                    continue
                if sig.startswith("TRIO|"):
                    # En fallback TRIO solo deduplicar si hay mezcla clara
                    # "con XML/archivo" vs "sin XML/archivo", para evitar borrar BH legítimas.
                    with_file = [r for r in informed if _norm(r.descripcion)]
                    without_file = [r for r in informed if not _norm(r.descripcion)]
                    if not with_file or not without_file:
                        # Excepción controlada: duplicados NO RECIBIDO exactos por reimport.
                        # Si todas son NO RECIBIDO y sin archivo, colapsar a una.
                        if not all(_norm(r.estado_recepcion).upper() == "NO RECIBIDO" for r in informed):
                            continue
                estados = {_norm(r.estado_recepcion).upper() for r in informed}
                if not informed or len(estados) != 1:
                    continue
                keeper = max(informed, key=lambda b: _score(b, b.id in xml_by_boleta))
                duplicates = [r for r in informed if r.id != keeper.id]

            if not duplicates:
                continue

            stats["groups_merged"] += 1

            keeper_xml = xml_by_boleta.get(keeper.id)
            for dup in duplicates:
                dup_xml = xml_by_boleta.get(dup.id)
                if dup_xml is not None:
                    if keeper_xml is None:
                        dup_xml.boleta_id = keeper.id
                        keeper_xml = dup_xml
                    else:
                        session.delete(dup_xml)

                for email in session.execute(select(EnvioEmail).where(EnvioEmail.boleta_id == dup.id)).scalars():
                    email.boleta_id = keeper.id
                for archivo in session.execute(select(Archivo).where(Archivo.boleta_id == dup.id)).scalars():
                    archivo.boleta_id = keeper.id

                session.delete(dup)
                stats["deleted"] += 1

        session.commit()
    return stats


def main() -> int:
    utils.asegurar_utf8_salida()
    parser = argparse.ArgumentParser(description="Deduplicar boletas de un período en DB")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=str, required=True)
    args = parser.parse_args()

    result = run(args.year, args.month)
    utils.print_table(
        "Resultado deduplicación",
        [
            ("Periodo ID", result["period_id"]),
            ("Total antes", result["total_before"]),
            ("Grupos fusionados", result["groups_merged"]),
            ("Filas eliminadas", result["deleted"]),
            ("Total después", result["total_before"] - result["deleted"]),
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

