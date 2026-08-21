"""Catálogo de directores de programa (DP) por sede.

Fuente de verdad: PostgreSQL (`directores_programa` + `director_sedes`).
Si la tabla aún no existe, se infiere SEDE → Email_DP desde BD-DOCENTES.xlsx.
"""
from __future__ import annotations

import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

import config
import utils

_EMPTY = {"", "nan", "none", "nat", "<na>"}


def canonical_sede(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in _EMPTY:
        return ""
    return " ".join(text.split()).upper()


def canonical_email(value: Any) -> str:
    return utils.email_from_cell(value).lower()


def _bd_path() -> str:
    return os.path.join(config.RAIZ, "BD-DOCENTES.xlsx")


def mapping_from_pairs(pairs: list[tuple[str, str]]) -> dict[str, str]:
    """SEDE canónica → email (mayoría si hay conflicto)."""
    votes: dict[str, Counter[str]] = defaultdict(Counter)
    for sede_raw, email_raw in pairs:
        sede = canonical_sede(sede_raw)
        email = canonical_email(email_raw)
        if not sede or not utils.validar_email(email):
            continue
        votes[sede][email] += 1
    return {sede: counts.most_common(1)[0][0] for sede, counts in votes.items() if counts}


def mapping_from_excel(path: str | None = None) -> dict[str, str]:
    path = path or _bd_path()
    if not path or not os.path.isfile(path):
        return {}
    try:
        df = pd.read_excel(path, engine="openpyxl")
    except Exception:
        return {}
    pairs: list[tuple[str, str]] = []
    for _, row in df.iterrows():
        pairs.append((str(row.get("SEDE") or ""), str(row.get("Email_DP") or "")))
    return mapping_from_pairs(pairs)


def mapping_from_db(session: Session) -> dict[str, str]:
    from db.models import DirectorPrograma, DirectorSede

    rows = session.execute(
        select(DirectorSede.sede, DirectorPrograma.email)
        .join(DirectorPrograma, DirectorSede.director_id == DirectorPrograma.id)
        .where(DirectorPrograma.activo != "false")
    ).all()
    return mapping_from_pairs([(sede, email) for sede, email in rows])


def sede_email_mapping(session: Session | None = None) -> dict[str, str]:
    if session is not None:
        try:
            found = mapping_from_db(session)
            if found:
                return found
        except Exception:
            pass
    else:
        try:
            from db.session import SessionLocal

            with SessionLocal() as sess:
                found = mapping_from_db(sess)
                if found:
                    return found
        except Exception:
            pass
    return mapping_from_excel()


def email_dp_for_sede(sede: Any, *, session: Session | None = None) -> str:
    mapping = sede_email_mapping(session)
    return mapping.get(canonical_sede(sede), "")


def apply_email_dp_from_sede(
    df: pd.DataFrame,
    *,
    mapping: dict[str, str] | None = None,
    session: Session | None = None,
) -> tuple[pd.DataFrame, int]:
    """Rellena Email_DP (o Correo_Personal merge) según SEDE. Devuelve (df, filas tocadas)."""
    if df is None or df.empty or "SEDE" not in df.columns:
        return df, 0
    col = "Email_DP" if "Email_DP" in df.columns else None
    if col is None:
        return df, 0
    mapping = mapping if mapping is not None else sede_email_mapping(session)
    if not mapping:
        return df, 0
    touched = 0
    for idx, row in df.iterrows():
        email = mapping.get(canonical_sede(row.get("SEDE")))
        if not email:
            continue
        current = canonical_email(row.get(col))
        if current == email:
            continue
        df.at[idx, col] = email
        touched += 1
    return df, touched


def _director_payload(row) -> dict[str, Any]:
    sedes = sorted({canonical_sede(s.sede) for s in (row.sedes or []) if canonical_sede(s.sede)})
    return {
        "id": int(row.id),
        "nombre": (row.nombre or "").strip() or None,
        "email": canonical_email(row.email),
        "activo": row.activo or "true",
        "sedes": sedes,
    }


def list_directores(session: Session) -> list[dict[str, Any]]:
    from sqlalchemy.orm import selectinload

    from db.models import DirectorPrograma

    rows = session.execute(
        select(DirectorPrograma)
        .options(selectinload(DirectorPrograma.sedes))
        .order_by(DirectorPrograma.email)
    ).scalars().all()
    return [_director_payload(r) for r in rows]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_or_create_by_email(session: Session, email: str, nombre: str | None = None):
    from db.models import DirectorPrograma

    email = canonical_email(email)
    row = session.execute(
        select(DirectorPrograma).where(DirectorPrograma.email == email)
    ).scalar_one_or_none()
    if row is None:
        row = DirectorPrograma(
            email=email,
            nombre=(nombre or "").strip() or None,
            activo="true",
        )
        session.add(row)
        session.flush()
    elif nombre and not (row.nombre or "").strip():
        row.nombre = nombre.strip()
        row.updated_at = _now()
    return row


def _assign_sedes(session: Session, director, sedes: list[str]) -> None:
    from db.models import DirectorSede

    wanted = [canonical_sede(s) for s in sedes]
    wanted = [s for s in wanted if s]
    links = session.execute(
        select(DirectorSede).where(DirectorSede.director_id == director.id)
    ).scalars().all()
    existing = {canonical_sede(s.sede): s for s in links}

    for sede, link in list(existing.items()):
        if sede not in wanted:
            session.delete(link)

    for sede in wanted:
        other = session.execute(
            select(DirectorSede).where(DirectorSede.sede == sede)
        ).scalar_one_or_none()
        if other is not None and other.director_id != director.id:
            session.delete(other)
            session.flush()
        if sede not in existing:
            session.add(DirectorSede(director_id=director.id, sede=sede))


def upsert_director(
    session: Session,
    *,
    director_id: int | None = None,
    nombre: str | None,
    email: str,
    sedes: list[str],
    activo: str = "true",
    propagate: bool = True,
) -> dict[str, Any]:
    from db.models import DirectorPrograma

    email = canonical_email(email)
    if not utils.validar_email(email):
        raise ValueError("Email de DP inválido.")
    nombre_clean = (nombre or "").strip() or None

    if director_id:
        row = session.execute(
            select(DirectorPrograma).where(DirectorPrograma.id == director_id)
        ).scalar_one_or_none()
        if row is None:
            raise KeyError(f"DP {director_id} no encontrado")
        conflict = session.execute(
            select(DirectorPrograma).where(
                DirectorPrograma.email == email,
                DirectorPrograma.id != director_id,
            )
        ).scalar_one_or_none()
        if conflict is not None:
            raise ValueError(f"Ya existe un DP con correo {email}")
        row.email = email
        row.nombre = nombre_clean
        row.activo = activo or "true"
        row.updated_at = _now()
    else:
        existing = session.execute(
            select(DirectorPrograma).where(DirectorPrograma.email == email)
        ).scalar_one_or_none()
        if existing is not None:
            raise ValueError(f"Ya existe un DP con correo {email}")
        row = DirectorPrograma(email=email, nombre=nombre_clean, activo=activo or "true")
        session.add(row)
        session.flush()

    _assign_sedes(session, row, sedes)
    session.flush()
    from sqlalchemy.orm import selectinload

    row = session.execute(
        select(DirectorPrograma)
        .options(selectinload(DirectorPrograma.sedes))
        .where(DirectorPrograma.id == row.id)
    ).scalar_one()
    payload = _director_payload(row)
    if propagate:
        propagate_director(session, payload)
    return payload


def delete_director(session: Session, director_id: int) -> None:
    from db.models import DirectorPrograma

    row = session.execute(
        select(DirectorPrograma).where(DirectorPrograma.id == director_id)
    ).scalar_one_or_none()
    if row is None:
        raise KeyError(f"DP {director_id} no encontrado")
    session.delete(row)


def seed_from_excel(session: Session, path: str | None = None) -> dict[str, int]:
    from db.models import DirectorPrograma, DirectorSede

    mapping = mapping_from_excel(path)
    created = 0
    linked = 0
    by_email: dict[str, list[str]] = defaultdict(list)
    for sede, email in mapping.items():
        by_email[email].append(sede)
    for email, sedes in by_email.items():
        existed = session.execute(
            select(DirectorPrograma).where(DirectorPrograma.email == email)
        ).scalar_one_or_none()
        row = _get_or_create_by_email(session, email)
        if existed is None:
            created += 1
        current = {
            canonical_sede(s.sede)
            for s in session.execute(
                select(DirectorSede).where(DirectorSede.director_id == row.id)
            ).scalars()
        }
        merged = sorted(current | set(sedes))
        _assign_sedes(session, row, merged)
        linked += len(sedes)
    session.flush()
    return {"directores": created, "sedes": linked, "mapping": len(mapping)}


def propagate_director(session: Session, payload: dict[str, Any]) -> dict[str, int]:
    """Copia el email del DP a docentes (Postgres + Excel) de sus sedes."""
    from db.models import Docente

    email = canonical_email(payload.get("email"))
    sedes = [canonical_sede(s) for s in (payload.get("sedes") or [])]
    sedes = [s for s in sedes if s]
    updated_db = 0
    if email and sedes:
        rows = session.execute(select(Docente)).scalars().all()
        for docente in rows:
            if canonical_sede(docente.sede) not in sedes:
                continue
            if canonical_email(docente.email_dp) == email:
                continue
            docente.email_dp = email
            updated_db += 1
    updated_xlsx = propagate_email_to_excel(sedes, email) if email and sedes else 0
    return {"docentes_db": updated_db, "docentes_excel": updated_xlsx}


def propagate_email_to_excel(sedes: list[str], email: str, path: str | None = None) -> int:
    path = path or _bd_path()
    if not path or not os.path.isfile(path) or not email:
        return 0
    wanted = {canonical_sede(s) for s in sedes}
    df = pd.read_excel(path, engine="openpyxl")
    if "SEDE" not in df.columns or "Email_DP" not in df.columns:
        return 0
    touched = 0
    for idx, row in df.iterrows():
        if canonical_sede(row.get("SEDE")) not in wanted:
            continue
        if canonical_email(row.get("Email_DP")) == canonical_email(email):
            continue
        df.at[idx, "Email_DP"] = email
        touched += 1
    if touched:
        def _write(tmp: str) -> None:
            df.to_excel(tmp, index=False, engine="openpyxl")

        utils.atomic_excel_write(path, _write)
    return touched


def patch_bd_docentes_row(fields: dict[str, Any], *, path: str | None = None) -> bool:
    """Actualiza una fila de BD-DOCENTES por RUT/EMPLID."""
    path = path or _bd_path()
    if not path or not os.path.isfile(path):
        return False
    rut = str(fields.get("RUT") or fields.get("EMPLID") or "").strip()
    if not rut:
        return False
    df = pd.read_excel(path, engine="openpyxl")
    key_col = "RUT" if "RUT" in df.columns else ("EMPLID" if "EMPLID" in df.columns else None)
    if key_col is None:
        return False
    mask = df[key_col].astype(str).str.strip() == rut
    if not bool(mask.any()):
        return False
    col_map = {
        "Correo_Personal": ("Correo_Personal", "Email_Docente"),
        "Telefono_Personal": ("Telefono_Personal", "Telefono"),
        "Direccion": ("Direccion",),
        "SEDE": ("SEDE",),
        "Email_DP": ("Email_DP",),
        "NOMBRE_COMPLETO": ("NOMBRE_COMPLETO", "NAME"),
        "OBSERVACIONES": ("OBSERVACIONES",),
    }
    for field, aliases in col_map.items():
        if field not in fields and not any(a in fields for a in aliases):
            continue
        value = fields.get(field)
        if value is None:
            for a in aliases:
                if a in fields:
                    value = fields[a]
                    break
        for alias in aliases:
            if alias in df.columns and value is not None:
                df.loc[mask, alias] = value

    def _write(tmp: str) -> None:
        df.to_excel(tmp, index=False, engine="openpyxl")

    utils.atomic_excel_write(path, _write)
    return True


def patch_solicitud_contact(
    path: str,
    emplid: str,
    *,
    email: str | None = None,
    sede: str | None = None,
    email_dp: str | None = None,
) -> bool:
    if not path or not os.path.isfile(path):
        return False
    df = pd.read_excel(path, engine="openpyxl")
    if "EMPLID" not in df.columns:
        return False
    mask = df["EMPLID"].astype(str).str.strip() == emplid.strip()
    if not bool(mask.any()):
        return False
    if email is not None and "Email_Docente" in df.columns:
        df.loc[mask, "Email_Docente"] = email
    if sede is not None and "SEDE" in df.columns:
        df.loc[mask, "SEDE"] = canonical_sede(sede)
    if email_dp is not None and "Email_DP" in df.columns:
        df.loc[mask, "Email_DP"] = canonical_email(email_dp)

    def _write(tmp: str) -> None:
        df.to_excel(tmp, index=False, engine="openpyxl")

    utils.atomic_excel_write(path, _write)
    return True
