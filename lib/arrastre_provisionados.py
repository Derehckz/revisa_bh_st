"""Arrastre de boletas NO RECIBIDO hacia filas PROVISIONADO del mes siguiente.

Regla de lookback:
- Siempre incluye el mes inmediatamente anterior, aunque esté cerrado
  (si no, al cerrar julio se varan las deudas y agosto sale sin provisión).
- Después sigue hacia atrás mientras los meses estén abiertos y se detiene
  en el siguiente período cerrado.
"""
from __future__ import annotations

import os
from typing import Any, Callable, List, Optional, Tuple

import pandas as pd

import config
import utils

ClosedFn = Callable[[int, str], bool]

MAPPING_GLOSA = {
    114: "CFTST Convenio los Lagos Código FDI CST2588-{MES}",
    508: "IPST Convenio los lagos Código FDI IST2588-{MES}",
}


def resolver_mes_anio_anterior(mes: str, año: int) -> Optional[Tuple[str, int]]:
    try:
        month_idx = config.MESES_ES.index(str(mes).strip().capitalize())
    except ValueError:
        return None
    if month_idx == 0:
        return config.MESES_ES[-1], año - 1
    return config.MESES_ES[month_idx - 1], año


def _period_is_closed(year: int, month: str) -> bool:
    """True solo si la BD marca el período cerrado; si no hay fila/BD, no corta el lookback."""
    try:
        import period_policy

        estado = period_policy.get_period_status(year, month)
        if estado is None:
            return False
        return period_policy.is_closed_status(estado)
    except Exception:
        return False


def _normalizar_estado_recepcion(value: object) -> str:
    return str(value or "").strip().upper()


def _person_arrastre_key(row: pd.Series) -> Tuple[str, str]:
    emplid = str(row.get("EMPLID", "") or "").strip()
    rut_razon = str(row.get("RUT RAZON", "") or "").strip()
    return emplid, rut_razon


def _monto_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _es_glosa_provisionado(glosa: object) -> bool:
    return "provisionado" in str(glosa or "").lower()


def _append_provisionado(glosa: object) -> str:
    current = str(glosa or "").strip()
    if "provisionado" in current.lower():
        return current
    if current:
        return f"{current} - PROVISIONADO"
    return "PROVISIONADO"


def _institucion_corta(location: object, rut_razon: object = "") -> str:
    try:
        loc = int(float(str(location).strip()))
    except (TypeError, ValueError):
        loc = None
    if loc == 114:
        return "CFT"
    if loc == 508:
        return "IP"
    rr = str(rut_razon or "")
    if "65175242" in rr.replace(".", "").replace("-", ""):
        return "CFT"
    if "65175239" in rr.replace(".", "").replace("-", ""):
        return "IP"
    return ""


def _glosa_para_mes_actual(template_row: pd.Series, mes: str) -> str:
    location = template_row.get("LOCATION")
    try:
        loc_key = int(location) if location is not None and str(location).strip() != "" else None
    except (TypeError, ValueError):
        loc_key = None
    if loc_key in MAPPING_GLOSA:
        return _append_provisionado(MAPPING_GLOSA[loc_key].format(MES=str(mes).upper()))
    return _append_provisionado(template_row.get("GLOSA"))


def _fila_provisionado_desde_template(
    template_row: pd.Series,
    *,
    mes: str,
    año: int,
    monto: float,
) -> pd.Series:
    new_row = template_row.copy()
    if "MONTH" in new_row.index:
        new_row["MONTH"] = str(mes).upper()
    if "YEAR" in new_row.index:
        new_row["YEAR"] = año
    if "GLOSA" in new_row.index:
        new_row["GLOSA"] = _glosa_para_mes_actual(template_row, mes)
    new_row["CUS_TOT_HON"] = monto
    if "Estado_Recepcion" in new_row.index:
        new_row["Estado_Recepcion"] = ""
    if "Correo Enviado" in new_row.index:
        new_row["Correo Enviado"] = ""
    if "Recordatorios Enviados" in new_row.index:
        new_row["Recordatorios Enviados"] = ""
    return new_row


def lookback_months(
    mes: str,
    año: int,
    *,
    max_months: int = 12,
    period_is_closed: ClosedFn | None = None,
) -> List[Tuple[str, int, bool]]:
    """Meses previos para arrastre: (mes, año, cerrado).

    El primero (mes anterior) entra aunque esté cerrado.
    """
    is_closed = period_is_closed or _period_is_closed
    out: List[Tuple[str, int, bool]] = []
    cur = resolver_mes_anio_anterior(mes, año)
    first = True
    while cur and len(out) < max_months:
        prev_mes, prev_anio = cur
        closed = bool(is_closed(prev_anio, prev_mes))
        if closed and not first:
            break
        out.append((prev_mes, prev_anio, closed))
        first = False
        cur = resolver_mes_anio_anterior(prev_mes, prev_anio)
    return out


def _open_lookback_months(
    mes: str,
    año: int,
    *,
    max_months: int = 12,
    period_is_closed: ClosedFn | None = None,
) -> List[Tuple[str, int]]:
    return [
        (m, y)
        for m, y, _closed in lookback_months(
            mes, año, max_months=max_months, period_is_closed=period_is_closed
        )
    ]


def aplicar_arrastre_provisionados(
    df_resultado: pd.DataFrame,
    mes: str,
    año: int,
    *,
    quiet: bool = False,
    period_is_closed: ClosedFn | None = None,
) -> Tuple[pd.DataFrame, int]:
    """
    Arrastra NO RECIBIDO de meses previos hacia el mes actual.

    - Las filas del maestro del mes actual no se modifican (monto/glosa quedan normales).
    - El arrastre crea filas aparte con GLOSA PROVISIONADO y el monto pendiente neto.
    - Match/acumulación por EMPLID + RUT RAZON (IP/CFT), independiente del monto.
    - Solo suman al saldo las filas NO RECIBIDO *sin* glosa PROVISIONADO (deuda nueva del mes).
    - Una fila PROVISIONADO aún NO RECIBIDO no se vuelve a sumar (ya representa deuda previa);
      solo se usa como saldo de apertura si aún no hay deuda acumulada en el lookback
      (p. ej. origen en un mes ya cerrado fuera de la ventana).
    - Si un mes posterior recibió una fila PROVISIONADO, esa deuda se descuenta.
    """
    lookback = _open_lookback_months(mes, año, period_is_closed=period_is_closed)
    if not lookback:
        if not quiet:
            utils.print_warning("No hay meses previos para arrastre de provisionados.")
        return df_resultado, 0

    required_cols = {"EMPLID", "RUT RAZON", "CUS_TOT_HON", "Estado_Recepcion"}
    deudas: dict[Tuple[str, str], dict] = {}
    meses_tocados: List[str] = []

    for prev_mes, prev_anio in reversed(lookback):
        prev_solicitud_path = os_join_solicitud(prev_anio, prev_mes)
        if not _isfile(prev_solicitud_path):
            if not quiet:
                utils.print_info(f"No existe Solicitud.xlsx en {prev_mes} {prev_anio}; se omite del arrastre.")
            continue
        try:
            df_prev = pd.read_excel(prev_solicitud_path, engine="openpyxl")
        except Exception as exc:
            if not quiet:
                utils.print_warning(f"No se pudo leer Solicitud {prev_mes} {prev_anio}: {exc}")
            continue
        if not required_cols.issubset(set(df_prev.columns)):
            if not quiet:
                utils.print_warning(
                    f"Solicitud {prev_mes} {prev_anio} incompleta para arrastre "
                    f"(faltan: {sorted(required_cols - set(df_prev.columns))})."
                )
            continue

        mes_label = f"{prev_mes} {prev_anio}"
        month_new: dict[Tuple[str, str], float] = {}
        month_prov_recibido: dict[Tuple[str, str], float] = {}
        month_prov_pendiente: dict[Tuple[str, str], float] = {}
        month_template: dict[Tuple[str, str], pd.Series] = {}

        for _, row in df_prev.iterrows():
            person_key = _person_arrastre_key(row)
            if not person_key[0] or not person_key[1]:
                continue
            estado = _normalizar_estado_recepcion(row.get("Estado_Recepcion"))
            monto = _monto_float(row.get("CUS_TOT_HON"))
            if monto <= 0:
                continue
            es_prov = _es_glosa_provisionado(row.get("GLOSA"))

            if estado == "NO RECIBIDO" and not es_prov:
                month_new[person_key] = month_new.get(person_key, 0.0) + monto
                month_template[person_key] = row
            elif estado == "RECIBIDO" and es_prov:
                month_prov_recibido[person_key] = month_prov_recibido.get(person_key, 0.0) + monto
                month_template[person_key] = row
            elif estado == "NO RECIBIDO" and es_prov:
                month_prov_pendiente[person_key] = month_prov_pendiente.get(person_key, 0.0) + monto
                month_template[person_key] = row

        touched_keys = set(month_new) | set(month_prov_recibido) | set(month_prov_pendiente)
        if not touched_keys:
            continue

        meses_tocados.append(mes_label)
        for person_key in touched_keys:
            entry = deudas.get(person_key)
            if entry is None:
                entry = {"monto": 0.0, "template": month_template[person_key]}
                deudas[person_key] = entry

            entry["monto"] += float(month_new.get(person_key, 0.0))
            cobrado = float(month_prov_recibido.get(person_key, 0.0))
            if cobrado:
                entry["monto"] = max(0.0, float(entry["monto"]) - cobrado)

            pendiente_prov = float(month_prov_pendiente.get(person_key, 0.0))
            if pendiente_prov > 0.009 and float(entry["monto"]) <= 0.009:
                entry["monto"] = pendiente_prov

            if person_key in month_template:
                entry["template"] = month_template[person_key]

    deudas = {k: v for k, v in deudas.items() if float(v["monto"]) > 0.009}
    if not deudas:
        if not quiet:
            utils.print_info(
                "Sin saldo provisionado pendiente en meses previos; no se agregan filas."
            )
        return df_resultado, 0

    if df_resultado is None or df_resultado.empty:
        df_work = pd.DataFrame()
    else:
        df_work = df_resultado

    nuevas: List[pd.Series] = []
    for person_key, entry in deudas.items():
        debt = float(entry["monto"])
        match_rows = [
            row
            for _, row in df_work.iterrows()
            if _person_arrastre_key(row) == person_key
        ]
        template = match_rows[0] if match_rows else entry["template"]
        nuevas.append(
            _fila_provisionado_desde_template(template, mes=mes, año=año, monto=debt)
        )

    if not nuevas:
        return df_resultado, 0

    df_out = pd.concat(
        [df_work, pd.DataFrame(nuevas)],
        ignore_index=True,
    )
    origen = ", ".join(meses_tocados) if meses_tocados else "meses previos"
    if not quiet:
        utils.print_info(
            f"Arrastre provisionado desde [{origen}]: {len(nuevas)} filas PROVISIONADO aparte "
            f"(maestro intacto; no duplica PROVISIONADO pendiente; descuenta PROVISIONADO RECIBIDO)."
        )
    return df_out, len(nuevas)


def preview_arrastre_provisionados(
    mes: str,
    año: int,
    *,
    period_is_closed: ClosedFn | None = None,
) -> dict[str, Any]:
    """Vista previa serializable (sin escribir Excel) de lo que el paso 0 agregará."""
    mes_n = str(mes or "").strip().capitalize()
    año_n = int(año)
    lb = lookback_months(mes_n, año_n, period_is_closed=period_is_closed)
    lookback_payload = []
    for prev_mes, prev_anio, closed in lb:
        path = os_join_solicitud(prev_anio, prev_mes)
        lookback_payload.append(
            {
                "month": prev_mes,
                "year": prev_anio,
                "closed": closed,
                "has_solicitud": _isfile(path),
            }
        )

    empty = pd.DataFrame()
    out, count = aplicar_arrastre_provisionados(
        empty,
        mes_n,
        año_n,
        quiet=True,
        period_is_closed=period_is_closed,
    )
    rows: list[dict[str, Any]] = []
    total = 0.0
    if count and out is not None and not out.empty:
        for _, row in out.iterrows():
            monto = _monto_float(row.get("CUS_TOT_HON"))
            total += monto
            email = str(row.get("Email_Docente") or row.get("Correo_Personal") or "").strip()
            rows.append(
                {
                    "emplid": str(row.get("EMPLID") or "").strip(),
                    "name": str(row.get("NAME") or "").strip(),
                    "institucion": _institucion_corta(row.get("LOCATION"), row.get("RUT RAZON")),
                    "location": row.get("LOCATION"),
                    "rut_razon": str(row.get("RUT RAZON") or "").strip(),
                    "monto": monto,
                    "glosa": str(row.get("GLOSA") or "").strip(),
                    "email": email,
                }
            )
        rows.sort(key=lambda r: (str(r.get("name") or "").lower(), str(r.get("institucion") or "")))

    previous_closed = bool(lb and lb[0][2])
    if not lb:
        message = "No hay meses previos para arrastrar. El maestro del mes se genera sin filas PROVISIONADO."
    elif count:
        origen = ", ".join(f"{m} {y}" for m, y, _c in lb)
        extra = (
            f" El mes anterior ({lb[0][0]}) está cerrado; igual se arrastra su NO RECIBIDO."
            if previous_closed
            else ""
        )
        message = (
            f"Al generar se agregarán {count} fila(s) PROVISIONADO "
            f"(revisado: {origen}).{extra} Cada una tendrá su propio correo en el paso 1."
        )
    else:
        message = (
            "No hay saldo provisionado pendiente en los meses revisados. "
            "La Solicitud saldrá solo con el maestro del mes."
        )

    return {
        "year": año_n,
        "month": mes_n,
        "lookback": lookback_payload,
        "previous_closed": previous_closed,
        "count": int(count or 0),
        "total_monto": float(total),
        "rows": rows,
        "message": message,
    }


def os_join_solicitud(year: int, month: str) -> str:
    return os.path.join(config.RAIZ, str(year), str(month).strip(), "Solicitud.xlsx")


def _isfile(path: str) -> bool:
    return os.path.isfile(path)
