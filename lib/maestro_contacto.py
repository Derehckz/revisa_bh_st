"""Ficha de contacto del docente: lo mínimo para no mentir en el envío.

Regla: sin correo válido y sede no hay lote. El DP se resuelve por sede.
Guardar en Docentes actualiza BD-DOCENTES y la Solicitud de meses abiertos
(no hace falta regenerar el paso 0).
"""
from __future__ import annotations

import os
from typing import Any, Iterable

import pandas as pd
from sqlalchemy import select

import config
import director_catalog
import utils

_INVALID_ENVIO = ("correo inválido", "correo invalido")


def ficha_minima_ok(email: Any, sede: Any) -> bool:
    return utils.validar_email(email) and bool(director_catalog.canonical_sede(sede))


def ficha_error(email: Any, sede: Any) -> str | None:
    if not utils.validar_email(email):
        return "correo personal válido es obligatorio"
    if not director_catalog.canonical_sede(sede):
        return "sede es obligatoria (el DP se asigna según la sede)"
    return None


def mask_ficha_incompleta(df: pd.DataFrame) -> pd.Series:
    """True en filas merged (both) sin correo o sin sede."""
    if df is None or df.empty:
        return pd.Series(dtype=bool)
    email_col = "Correo_Personal" if "Correo_Personal" in df.columns else "Email_Docente"
    sede_col = "SEDE" if "SEDE" in df.columns else None
    if email_col not in df.columns or sede_col is None:
        return pd.Series(False, index=df.index)

    def _ok(row) -> bool:
        return ficha_minima_ok(row.get(email_col), row.get(sede_col))

    incompleta = ~df.apply(_ok, axis=1)
    if "merge_status" in df.columns:
        return incompleta & (df["merge_status"].astype(str) == "both")
    return incompleta


def parse_emplid_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        parts = [str(x).strip() for x in raw]
    else:
        parts = [p.strip() for p in str(raw).replace(";", ",").split(",")]
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        key = utils.normalizar_rut_con_dv(part) or part.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(part)
    return out


def filter_indices_by_emplid(df: pd.DataFrame, indices, emplids: Iterable[str]):
    wanted = {utils.normalizar_rut_con_dv(x) or str(x).strip().lower() for x in emplids if str(x).strip()}
    if not wanted:
        return indices
    kept = []
    for idx in indices:
        emplid = str(df.at[idx, "EMPLID"]) if "EMPLID" in df.columns else ""
        key = utils.normalizar_rut_con_dv(emplid) or emplid.strip().lower()
        if key in wanted:
            kept.append(idx)
    if hasattr(indices, "__class__") and indices.__class__.__name__ == "Index":
        return pd.Index(kept)
    return kept


def recipient_payload(df: pd.DataFrame, indices, *, tipo: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if df is None or indices is None:
        return rows
    for idx in indices:
        email = utils.email_from_cell(df.at[idx, "Email_Docente"] if "Email_Docente" in df.columns else "")
        rows.append(
            {
                "index": int(idx),
                "fila": int(idx) + 1,
                "name": str(df.at[idx, "NAME"]) if "NAME" in df.columns else "",
                "emplid": str(df.at[idx, "EMPLID"]) if "EMPLID" in df.columns else "",
                "email": email or "(vacío)",
                "sede": director_catalog.canonical_sede(df.at[idx, "SEDE"] if "SEDE" in df.columns else ""),
                "valid": utils.validar_email(email),
                "tipo": tipo,
            }
        )
    return rows


def _clear_invalid_envio(df: pd.DataFrame, mask) -> None:
    if "Correo Enviado" not in df.columns:
        return
    for idx in df.index[mask]:
        current = str(df.at[idx, "Correo Enviado"] or "").lower()
        if any(tok in current for tok in _INVALID_ENVIO):
            df.at[idx, "Correo Enviado"] = ""


def patch_open_solicitudes_for_docente(
    *,
    rut: str,
    email: str,
    sede: str,
    email_dp: str | None,
) -> dict[str, Any]:
    """Actualiza Solicitud.xlsx de períodos abiertos para este RUT."""
    from db.models import Periodo
    from db.session import SessionLocal
    from period_policy import is_closed_status

    patched: list[str] = []
    skipped: list[str] = []
    rut = str(rut or "").strip()
    if not rut:
        return {"patched": patched, "skipped": skipped}

    try:
        with SessionLocal() as session:
            periodos = session.execute(select(Periodo)).scalars().all()
            open_periods = [
                p for p in periodos if not is_closed_status(getattr(p, "estado", None))
            ]
    except Exception:
        open_periods = []

    if not open_periods:
        # Fallback: mes de config si existe carpeta
        try:
            año, mes = utils.resolve_año_mes(config.RAIZ, None, None)
            open_periods = [type("P", (), {"anio": int(año), "mes_nombre": str(mes)})()]
        except Exception:
            open_periods = []

    for p in open_periods:
        path = os.path.join(config.RAIZ, str(p.anio), str(p.mes_nombre), "Solicitud.xlsx")
        if not os.path.isfile(path):
            continue
        try:
            df = pd.read_excel(path, engine="openpyxl")
        except Exception:
            skipped.append(path)
            continue
        if "EMPLID" not in df.columns:
            continue
        mask = df["EMPLID"].astype(str).str.strip() == rut
        if not bool(mask.any()):
            continue
        if "Email_Docente" in df.columns:
            df.loc[mask, "Email_Docente"] = email or ""
        if "SEDE" in df.columns:
            df.loc[mask, "SEDE"] = director_catalog.canonical_sede(sede) or sede or ""
        if "Email_DP" in df.columns and email_dp:
            df.loc[mask, "Email_DP"] = director_catalog.canonical_email(email_dp)
        _clear_invalid_envio(df, mask)

        def _write(tmp: str, _df=df) -> None:
            _df.to_excel(tmp, index=False, engine="openpyxl")

        try:
            utils.atomic_excel_write(path, _write)
            patched.append(f"{p.anio}/{p.mes_nombre}")
        except Exception:
            skipped.append(path)
            continue

        _patch_boletas_solicitud_row(
            year=int(p.anio),
            month=str(p.mes_nombre),
            rut=rut,
            email=email,
            sede=sede,
            email_dp=email_dp,
        )
    return {"patched": patched, "skipped": skipped}


def _patch_boletas_solicitud_row(
    *,
    year: int,
    month: str,
    rut: str,
    email: str,
    sede: str,
    email_dp: str | None,
) -> None:
    try:
        from db.models import Boleta, Periodo
        from db.session import SessionLocal
    except Exception:
        return
    try:
        with SessionLocal() as session:
            periodo = session.execute(
                select(Periodo).where(Periodo.anio == year, Periodo.mes_nombre == month)
            ).scalar_one_or_none()
            if periodo is None:
                return
            rows = session.execute(
                select(Boleta).where(Boleta.periodo_id == periodo.id, Boleta.emplid == rut)
            ).scalars().all()
            sede_c = director_catalog.canonical_sede(sede) or sede
            dp = director_catalog.canonical_email(email_dp) if email_dp else ""
            for boleta in rows:
                sr = dict(boleta.solicitud_row or {})
                sr["Email_Docente"] = email or ""
                sr["SEDE"] = sede_c
                if dp:
                    sr["Email_DP"] = dp
                envio = str(sr.get("Correo Enviado") or "").lower()
                if any(tok in envio for tok in _INVALID_ENVIO):
                    sr["Correo Enviado"] = ""
                boleta.solicitud_row = sr
            session.commit()
    except Exception:
        return


def count_fichas_incompletas_periodo(session, periodo_id: int) -> int:
    from db.models import Boleta

    rows = session.execute(select(Boleta.solicitud_row).where(Boleta.periodo_id == periodo_id)).all()
    n = 0
    for (sr,) in rows:
        data = sr if isinstance(sr, dict) else {}
        email = data.get("Email_Docente") or data.get("Correo_Personal")
        sede = data.get("SEDE")
        if not ficha_minima_ok(email, sede):
            n += 1
    return n
