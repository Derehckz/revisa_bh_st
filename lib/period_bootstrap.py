"""Crear mes, subir archivos de arranque y estado de preparación del período."""
from __future__ import annotations

import os
import re
from typing import Any

import config
from db.file_repository import get_or_create_periodo
from db.period_sync import MESES_ES, discover_period_folders

_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_SAFE_NAME_RE = re.compile(r"^[^<>:\"/\\|?*\x00-\x1f]+$")


class PeriodBootstrapError(ValueError):
    """Error de validación / conflicto al preparar un período."""

    def __init__(self, message: str, *, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def _canonical_month(month_name: str) -> tuple[int, str]:
    key = str(month_name or "").strip().casefold()
    for idx, name in enumerate(MESES_ES):
        if name.casefold() == key:
            return idx + 1, name
    raise PeriodBootstrapError(
        f"Mes inválido: {month_name!r}. Usa uno de: {', '.join(MESES_ES)}."
    )


def _month_dir(year: int, month_name: str) -> str:
    return os.path.join(config.RAIZ, str(year), month_name)


def _safe_under_raiz(path: str) -> bool:
    try:
        root = os.path.abspath(config.RAIZ)
        target = os.path.abspath(path)
        return os.path.commonpath([root, target]) == root
    except ValueError:
        return False


def _sanitize_filename(name: str) -> str:
    base = os.path.basename(str(name or "").strip())
    if not base or base in (".", "..") or not _SAFE_NAME_RE.match(base):
        raise PeriodBootstrapError("Nombre de archivo inválido.")
    if ".." in base:
        raise PeriodBootstrapError("Nombre de archivo inválido.")
    return base


def list_missing_months(year: int) -> dict[str, Any]:
    if year < 2000 or year > 2100:
        raise PeriodBootstrapError("Año fuera de rango (2000–2100).")
    folders = discover_period_folders(config.RAIZ)
    present = {mes_num for anio, mes_num, _ in folders if anio == year}
    missing = [
        {"month_num": idx + 1, "month_name": name}
        for idx, name in enumerate(MESES_ES)
        if (idx + 1) not in present
    ]
    return {"year": year, "missing": missing, "existing_count": len(present)}


def create_period(year: int, month_name: str) -> dict[str, Any]:
    if year < 2000 or year > 2100:
        raise PeriodBootstrapError("Año fuera de rango (2000–2100).")
    mes_num, mes_nombre = _canonical_month(month_name)
    month_path = _month_dir(year, mes_nombre)
    if os.path.isdir(month_path):
        raise PeriodBootstrapError(
            f"Ya existe la carpeta del período {mes_nombre} {year}.",
            status_code=409,
        )

    os.makedirs(month_path, exist_ok=False)
    periodo_id = get_or_create_periodo(year, mes_num, mes_nombre)
    if periodo_id is None:
        # Carpeta creada; reintentar sync vía ensure no crítico
        raise PeriodBootstrapError(
            "Carpeta creada pero no se pudo registrar el período en la base de datos.",
            status_code=503,
        )

    return {
        "ok": True,
        "created": True,
        "period": {
            "id": periodo_id,
            "year": year,
            "month_num": mes_num,
            "month_name": mes_nombre,
            "status": "abierto",
        },
        "month_dir": os.path.abspath(month_path),
        "message": f"Período {mes_nombre} {year} creado.",
    }


def _is_excluded_maestro_name(filename: str) -> bool:
    """Archivos del mes que no son el Excel maestro de Base a Pago."""
    low = filename.casefold()
    if not low.endswith(".xlsx"):
        return True
    if low.startswith("~$"):
        return True
    if low == "solicitud.xlsx":
        return True
    # Derivados / artefactos del pipeline
    prefixes = (
        "solicitud_",
        "contabilidad",
        "revision_",
        "tmp",
        "map_",
        "backup_",
        "informe_",
    )
    return any(low.startswith(p) for p in prefixes)


def _maestro_files(month_path: str) -> list[str]:
    if not os.path.isdir(month_path):
        return []
    out: list[str] = []
    for f in os.listdir(month_path):
        if _is_excluded_maestro_name(f):
            continue
        path = os.path.join(month_path, f)
        if os.path.isfile(path):
            out.append(f)
    return sorted(out)


def _pick_maestro_validation(month_path: str, maestros: list[str]) -> tuple[bool, str, list[str]]:
    """Valida candidatos a maestro; usa el primero OK o el mejor mensaje de error."""
    if not maestros:
        return True, "", []

    import maestro_validation

    first_error_msg = ""
    validated_name = ""
    for name in maestros:
        path = os.path.join(month_path, name)
        v = maestro_validation.validate_maestro_path(path)
        if v.get("ok"):
            msg = ""
            if v.get("warnings"):
                msg = "; ".join(v.get("warnings")[:2])
            return True, msg, [name]
        if not first_error_msg:
            errs = v.get("errors") or ["Columnas inválidas"]
            first_error_msg = f"{name}: " + "; ".join(errs)
            validated_name = name
    return False, first_error_msg or "Ningún Excel del mes es un maestro válido.", [validated_name or maestros[0]]


def _bd_files() -> list[str]:
    if not os.path.isdir(config.RAIZ):
        return []
    out: list[str] = []
    for f in os.listdir(config.RAIZ):
        if not f.lower().endswith(".xlsx"):
            continue
        if "bd" in f.lower() or "docentes" in f.lower():
            path = os.path.join(config.RAIZ, f)
            if os.path.isfile(path):
                out.append(f)
    return out


def period_setup(year: int, month_name: str) -> dict[str, Any]:
    mes_num, mes_nombre = _canonical_month(month_name)
    month_path = _month_dir(year, mes_nombre)
    month_exists = os.path.isdir(month_path)
    maestros = _maestro_files(month_path) if month_exists else []
    bds = _bd_files()
    adjunto_path = os.path.abspath(config.ARCHIVO_ADJUNTO)
    adjunto_ok = os.path.isfile(adjunto_path)
    solicitud_path = os.path.join(month_path, "Solicitud.xlsx")
    solicitud_exists = os.path.isfile(solicitud_path)

    maestro_validation_ok = True
    maestro_validation_msg = ""
    maestros_ok_files = maestros

    # Si ya existe Solicitud.xlsx, el mes ya pasó el paso 0: no exigir ni validar maestro.
    if solicitud_exists:
        maestro_validation_ok = True
        maestro_validation_msg = ""
        maestros_ok_files = []
        # Intentar listar un maestro real solo para mostrar el nombre; sin fallar el ítem.
        if maestros:
            ok_pick, _msg, picked = _pick_maestro_validation(month_path, maestros)
            if ok_pick:
                maestros_ok_files = picked
        maestro_item_ok = True
    elif maestros:
        maestro_validation_ok, maestro_validation_msg, maestros_ok_files = _pick_maestro_validation(
            month_path, maestros
        )
        maestro_item_ok = maestro_validation_ok
    else:
        maestro_item_ok = False
        maestro_validation_msg = "Sube el maestro de pagos (.xlsx) del mes."

    outlook: dict[str, Any]
    try:
        from outlook_utils import check_outlook_health

        outlook = check_outlook_health(probe_com=False)
    except Exception as exc:  # pragma: no cover - defensivo
        outlook = {"ok": False, "status": "error", "message": str(exc)}

    items = [
        {
            "id": "period_folder",
            "label": "Carpeta del período",
            "ok": month_exists,
            "blocking": True,
            "message": "" if month_exists else f"Crea el mes {mes_nombre} {year} desde Operación.",
            "kind": None,
        },
        {
            "id": "maestro",
            "label": "Excel maestro en la carpeta del mes",
            "ok": maestro_item_ok,
            "blocking": not solicitud_exists,
            "message": (
                "Listo: Solicitud.xlsx ya generada (el maestro solo se usa en el paso 0)."
                if solicitud_exists
                else (
                    ""
                    if maestro_item_ok and not maestro_validation_msg
                    else (maestro_validation_msg or "Sube el maestro de pagos (.xlsx) del mes.")
                )
            ),
            "kind": None if solicitud_exists else "maestro",
            "files": maestros_ok_files if maestros_ok_files else ([] if solicitud_exists else maestros),
        },
        {
            "id": "bd_docentes",
            "label": "BD-DOCENTES (o similar) en la raíz",
            "ok": len(bds) > 0,
            "blocking": not solicitud_exists,
            "message": "" if bds else "Sube BD-DOCENTES.xlsx (base de docentes).",
            "kind": None if solicitud_exists else "bd",
            "files": bds,
        },
        {
            "id": "adjunto_ejemplo",
            "label": "PDF de ejemplo para correos",
            "ok": adjunto_ok,
            "blocking": False,
            "message": "" if adjunto_ok else f"Falta {os.path.basename(adjunto_path)} (necesario para paso 1).",
            "kind": "adjunto",
            "path": adjunto_path,
        },
        {
            "id": "outlook",
            "label": "Outlook en este equipo",
            "ok": bool(outlook.get("ok")),
            "blocking": False,
            "message": str(outlook.get("message") or ""),
            "kind": None,
            "outlook": outlook,
        },
        {
            "id": "solicitud",
            "label": "Solicitud.xlsx generada",
            "ok": solicitud_exists,
            "blocking": False,
            "message": "" if solicitud_exists else "Se crea con el paso 0.",
            "kind": None,
        },
    ]

    ready_for_step0 = month_exists and (
        (len(maestros) > 0 and maestro_validation_ok and len(bds) > 0) or solicitud_exists
    )
    # BD sigue siendo útil, pero no bloquea el panel si ya hay Solicitud.
    if solicitud_exists:
        ready_for_step0 = month_exists
    setup_complete = bool(solicitud_exists) and month_exists

    return {
        "year": year,
        "month": mes_nombre,
        "month_num": mes_num,
        "month_dir": os.path.abspath(month_path) if month_exists else month_path,
        "items": items,
        "ready_for_step0": ready_for_step0,
        "setup_complete": setup_complete,
        "solicitud_exists": solicitud_exists,
        # Solo mostrar panel de arranque si aún no hay Solicitud.
        "needs_setup_panel": month_exists and not solicitud_exists,
    }


def upload_period_file(
    year: int,
    month_name: str,
    kind: str,
    *,
    filename: str,
    data: bytes,
) -> dict[str, Any]:
    kind_norm = str(kind or "").strip().lower()
    if kind_norm not in ("maestro", "bd", "adjunto", "pagos"):
        raise PeriodBootstrapError("kind debe ser maestro, bd, adjunto o pagos.")

    if not data:
        raise PeriodBootstrapError("Archivo vacío.")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise PeriodBootstrapError(
            f"Archivo demasiado grande (máx. {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )

    safe_name = _sanitize_filename(filename)
    _, mes_nombre = _canonical_month(month_name)
    month_path = _month_dir(year, mes_nombre)

    if kind_norm == "maestro":
        if not safe_name.lower().endswith(".xlsx"):
            raise PeriodBootstrapError("El maestro debe ser un archivo .xlsx.")
        if safe_name.casefold() == "solicitud.xlsx":
            raise PeriodBootstrapError(
                "No subas Solicitud.xlsx como maestro; usa el Excel de Base a Pago del mes."
            )
        if not os.path.isdir(month_path):
            raise PeriodBootstrapError(
                f"No existe la carpeta del mes {mes_nombre} {year}. Créala primero.",
                status_code=404,
            )
        dest = os.path.join(month_path, safe_name)
    elif kind_norm == "bd":
        if not safe_name.lower().endswith(".xlsx"):
            raise PeriodBootstrapError("La base de docentes debe ser un archivo .xlsx.")
        # Preferir nombre canónico si el archivo no parece BD/docentes
        if "bd" not in safe_name.lower() and "docentes" not in safe_name.lower():
            safe_name = "BD-DOCENTES.xlsx"
        dest = os.path.join(config.RAIZ, safe_name)
    elif kind_norm == "pagos":
        if not (
            safe_name.lower().endswith(".xlsx")
            or safe_name.lower().endswith(".xlsm")
            or safe_name.lower().endswith(".csv")
            or safe_name.lower().endswith(".eml")
            or safe_name.lower().endswith(".html")
            or safe_name.lower().endswith(".htm")
        ):
            raise PeriodBootstrapError(
                "Los pagos de Contabilidad deben ser .eml, .csv o .xlsx "
                "(o pégalos en el paso 7 desde el correo)."
            )
        if not os.path.isdir(month_path):
            raise PeriodBootstrapError(
                f"No existe la carpeta del mes {mes_nombre} {year}. Créala primero.",
                status_code=404,
            )
        # Evitar sobrescribir Solicitud
        if safe_name.casefold() == "solicitud.xlsx":
            safe_name = "Contabilidad_Pagos.xlsx"
        if not safe_name.lower().startswith("contabilidad"):
            base, ext = os.path.splitext(safe_name)
            safe_name = f"Contabilidad_{base}{ext}"
        dest = os.path.join(month_path, safe_name)
    else:  # adjunto
        if not safe_name.lower().endswith(".pdf"):
            raise PeriodBootstrapError("El adjunto de ejemplo debe ser un PDF.")
        dest = os.path.abspath(config.ARCHIVO_ADJUNTO)

    if not _safe_under_raiz(dest):
        raise PeriodBootstrapError("Ruta de destino fuera del proyecto.")

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data)

    validation = None
    import_result = None
    if kind_norm == "maestro":
        import maestro_validation

        validation = maestro_validation.validate_maestro_path(dest)
        if not validation.get("ok"):
            try:
                os.remove(dest)
            except OSError:
                pass
            detail = "; ".join(validation.get("errors") or ["Maestro inválido"])
            raise PeriodBootstrapError(f"Maestro rechazado: {detail}")
    elif kind_norm == "pagos":
        import pagos_import

        try:
            import_result = pagos_import.import_pagos_into_period(
                year=year,
                month=mes_nombre,
                source_path=dest,
                write=True,
            )
        except Exception as exc:
            raise PeriodBootstrapError(f"No se pudo importar Pagos: {exc}") from exc

    out = {
        "ok": True,
        "kind": kind_norm,
        "path": os.path.abspath(dest),
        "filename": os.path.basename(dest),
        "size_bytes": len(data),
        "message": f"Archivo guardado: {os.path.basename(dest)}",
        "setup": period_setup(year, mes_nombre),
    }
    if validation is not None:
        out["validation"] = validation
        if validation.get("warnings"):
            out["message"] += " · " + "; ".join(validation["warnings"][:2])
    if import_result is not None:
        out["pagos_import"] = import_result
        out["message"] = import_result.get("message") or out["message"]
    return out

