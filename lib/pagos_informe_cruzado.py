"""Cruzado Informe final (Resumen Boletas) vs hoja Pagos de Contabilidad."""
from __future__ import annotations

import os
import re
from typing import Any

import pandas as pd

import config
from stages.stage7.mail import normalizar_monto_liquido

_SHEET_RESUMEN = ("Resumen Boletas", "Resumen de Boletas", "ResumenBoletas")
_AMOUNT_TOLERANCE = 1  # pesos
_PCT_TOLERANCE = 0.05  # puntos porcentuales

# Tipo Documento Contabilidad → tasas aceptadas (SII BER/BR).
_TIPO_DOC_RATES: dict[str, set[float]] = {
    "BER": {14.5, 15.25},
    "BR": {17.5},
}


def _normalize_rut(value: object) -> str:
    raw = str(value or "").strip().upper().replace(".", "")
    if not raw or raw.lower() == "nan":
        return ""
    raw = raw.replace(" ", "")
    if "-" not in raw and len(raw) >= 2:
        raw = f"{raw[:-1]}-{raw[-1]}"
    if "-" in raw:
        cuerpo, dv = raw.rsplit("-", 1)
        cuerpo = cuerpo.lstrip("0") or "0"
        raw = f"{cuerpo}-{dv}"
    return raw


def _folio_norm(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    texto = str(value).strip()
    if not texto or texto.lower() in {"nan", "none"}:
        return ""
    try:
        return str(int(float(texto)))
    except (TypeError, ValueError):
        return re.sub(r"\D", "", texto) or texto


def _join_key(rut: object, boleta: object) -> str:
    return f"{_normalize_rut(rut)}|{_folio_norm(boleta)}"


def _as_pesos(value: object) -> int | None:
    """Convierte montos Contabilidad (miles) o pesos a enteros.

    En hoja Pagos, Contabilidad usa escala miles: 108.0 / 16.47 / 91.53.
    Un entero < 1000 sin decimales (p. ej. Bruto 108) también es miles.
    Valores >= 1000 se tratan como pesos ya normalizados.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        num = float(value)
        if abs(num) < 1000:
            return int(round(num * 1000))
        return int(round(num))
    # Strings: reutilizar normalizador de envío (maneja 91.53, 1.234, etc.)
    try:
        texto = str(value).strip().replace("$", "").replace(" ", "").replace("\u00a0", "")
        if not texto or texto.lower() in {"nan", "none", "-"}:
            return None
        # Solo dígitos / un punto o coma
        probe = texto.replace(",", ".")
        try:
            num = float(probe)
        except ValueError:
            return int(normalizar_monto_liquido(value))
        if abs(num) < 1000:
            # "108" o "91.53" → miles
            return int(round(num * 1000))
        return int(round(num))
    except Exception:
        return None


def _as_float(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    texto = str(value).strip().replace("%", "").replace(",", ".")
    if not texto or texto.lower() in {"nan", "none"}:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def _pct_from_tipo_doc(tipo: object) -> float | set[float] | None:
    raw = str(tipo or "").strip().upper()
    if not raw or raw in {"NAN", "NONE"}:
        return None
    # "BER( 14,50% )" o "15.25"
    m = re.search(r"(\d+[.,]\d+)", raw)
    if m and "BER" not in raw and "BR" not in raw.replace("BER", ""):
        return _as_float(m.group(1))
    if raw.startswith("BER") or raw == "BER":
        return set(_TIPO_DOC_RATES["BER"])
    if raw.startswith("BR") or raw == "BR":
        return set(_TIPO_DOC_RATES["BR"])
    # Número suelto en Tipo Documento
    num = _as_float(raw)
    return num


def _solicitud_path(year: int | str, month: str) -> str:
    return os.path.join(config.RAIZ, str(year), str(month).strip().capitalize(), "Solicitud.xlsx")


def _find_sheet(xl: pd.ExcelFile, candidates: tuple[str, ...]) -> str | None:
    lower = {s.strip().lower(): s for s in xl.sheet_names}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    return None


def _load_resumen(solicitud_path: str) -> tuple[pd.DataFrame | None, str | None]:
    xl = pd.ExcelFile(solicitud_path, engine="openpyxl")
    sheet = _find_sheet(xl, _SHEET_RESUMEN)
    if not sheet:
        return None, None
    df = pd.read_excel(solicitud_path, sheet_name=sheet, engine="openpyxl")
    return df, sheet


def _load_solicitud_main(solicitud_path: str) -> pd.DataFrame | None:
    xl = pd.ExcelFile(solicitud_path, engine="openpyxl")
    for candidata in ("Sheet1", "Solicitud", *xl.sheet_names):
        if candidata not in xl.sheet_names:
            continue
        probe = pd.read_excel(solicitud_path, sheet_name=candidata, engine="openpyxl", nrows=2)
        cols = {str(c) for c in probe.columns}
        if "EMPLID" in cols or "totalHonorarios_XML" in cols:
            return pd.read_excel(solicitud_path, sheet_name=candidata, engine="openpyxl")
    return None


def _boleta_col(df: pd.DataFrame) -> str | None:
    for c in ("N° Boleta", "Nº Boleta", "N° Boleta", "Numero Boleta", "Número Boleta"):
        if c in df.columns:
            return c
    for c in df.columns:
        if "boleta" in str(c).lower():
            return str(c)
    return None


def _build_xml_index(sol: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """RUT|boleta → campos XML; también índice secundario RUT|RE|LOCATION."""
    by_boleta: dict[str, dict[str, Any]] = {}
    by_re_loc: dict[str, dict[str, Any]] = {}
    for _, row in sol.iterrows():
        rut = _normalize_rut(row.get("EMPLID") or row.get("RUT_SIN_DV"))
        boleta = _folio_norm(row.get("numeroBoleta_XML"))
        meta = {
            "bruto": _as_pesos(row.get("totalHonorarios_XML")),
            "retencion": _as_pesos(row.get("impuestoHonorarios_XML")),
            "liquido": _as_pesos(row.get("liquidoHonorarios_XML")),
            "pct": _as_float(row.get("porcentajeImpuesto_XML")),
            "sede": str(row.get("SEDE") or "").strip(),
            "location": str(row.get("LOCATION") or "").strip(),
            "nombre": str(row.get("NAME") or "").strip(),
            "re": str(row.get("EMPL_RCD") if row.get("EMPL_RCD") is not None else "").strip(),
        }
        if rut and boleta:
            by_boleta[_join_key(rut, boleta)] = meta
        re_key = f"{rut}|{meta['re']}|{meta['location']}"
        if rut and meta["re"] != "":
            by_re_loc[re_key] = meta
    return {"by_boleta": by_boleta, "by_re_loc": by_re_loc}


def _row_presence(rut: str, boleta: str, nombre: str = "") -> dict[str, str]:
    return {"rut": rut, "boleta": boleta, "nombre": nombre}


def _amount_mismatch(
    *,
    rut: str,
    boleta: str,
    field: str,
    expected: int | float | None,
    got: int | float | None,
) -> dict[str, Any]:
    exp_i = int(expected) if expected is not None else None
    got_i = int(got) if got is not None else None
    diff = None
    if exp_i is not None and got_i is not None:
        diff = got_i - exp_i
    return {
        "rut": rut,
        "boleta": boleta,
        "field": field,
        "expected": exp_i,
        "got": got_i,
        "diff": diff,
    }


def compare_informe_vs_pagos(
    *,
    resumen: pd.DataFrame,
    pagos: pd.DataFrame,
    xml_index: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Compara DataFrames ya cargados (útil en tests)."""
    xml_index = xml_index or {"by_boleta": {}, "by_re_loc": {}}
    by_boleta = xml_index.get("by_boleta") or {}
    by_re_loc = xml_index.get("by_re_loc") or {}

    boleta_col = _boleta_col(resumen) or "N° Boleta"
    informe_map: dict[str, dict[str, Any]] = {}
    for _, row in resumen.iterrows():
        rut = _normalize_rut(row.get("RUT") or row.get("ID"))
        boleta = _folio_norm(row.get(boleta_col) if boleta_col in row.index else row.get("N° Boleta"))
        if not rut:
            continue
        key = _join_key(rut, boleta)
        bruto_resumen = _as_pesos(row.get("Monto Bruto"))
        xml = by_boleta.get(key)
        if xml is None:
            re_val = str(row.get("Reg empleo") if row.get("Reg empleo") is not None else "").strip()
            loc = str(row.get("LOCATION") or "").strip()
            xml = by_re_loc.get(f"{rut}|{re_val}|{loc}")
        informe_map[key] = {
            "rut": rut,
            "boleta": boleta,
            "nombre": str(row.get("Nombre Docente") or row.get("Nombre") or "").strip(),
            "bruto": (xml or {}).get("bruto") if (xml or {}).get("bruto") is not None else bruto_resumen,
            "retencion": (xml or {}).get("retencion"),
            "liquido": (xml or {}).get("liquido"),
            "pct": (xml or {}).get("pct"),
            "location": str(row.get("LOCATION") or (xml or {}).get("location") or "").strip(),
            "sede": str((xml or {}).get("sede") or row.get("Nombre Sede") or "").strip(),
            "tipo_pago": str(row.get("Tipo de Pago") or "").strip(),
        }

    pagos_map: dict[str, dict[str, Any]] = {}
    for _, row in pagos.iterrows():
        rut = _normalize_rut(row.get("ID"))
        boleta = _folio_norm(row.get("Número Boleta"))
        if not rut and not boleta:
            continue
        key = _join_key(rut, boleta)
        bruto = _as_pesos(row.get("Bruto $"))
        retencion = _as_pesos(row.get("RETENCIÓN"))
        liquido = _as_pesos(row.get("Liquido Final"))
        if liquido is None:
            liquido = _as_pesos(row.get("LÍQUIDO"))
        pct_derived: float | None = None
        if bruto and retencion is not None and bruto > 0:
            pct_derived = round(100.0 * float(retencion) / float(bruto), 4)
        tipo_pct = _pct_from_tipo_doc(row.get("Tipo Documento"))
        pagos_map[key] = {
            "rut": rut,
            "boleta": boleta,
            "nombre": str(row.get("Nombre") or "").strip(),
            "bruto": bruto,
            "retencion": retencion,
            "liquido": liquido,
            "pct_derived": pct_derived,
            "pct_tipo": tipo_pct,
            "location": str(row.get("Ubicación") or "").strip(),
            "sede": str(row.get("SEDE") or "").strip(),
            "tipo_doc": str(row.get("Tipo Documento") or "").strip(),
        }

    only_in_informe: list[dict[str, str]] = []
    only_in_pagos: list[dict[str, str]] = []
    amount_mismatches: list[dict[str, Any]] = []
    pct_mismatches: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    matched = 0

    informe_keys = set(informe_map)
    pagos_keys = set(pagos_map)

    for key in sorted(informe_keys - pagos_keys):
        row = informe_map[key]
        only_in_informe.append(_row_presence(row["rut"], row["boleta"], row["nombre"]))

    for key in sorted(pagos_keys - informe_keys):
        row = pagos_map[key]
        only_in_pagos.append(_row_presence(row["rut"], row["boleta"], row["nombre"]))

    for key in sorted(informe_keys & pagos_keys):
        matched += 1
        inf = informe_map[key]
        pag = pagos_map[key]
        rut, boleta = inf["rut"], inf["boleta"]

        for field, exp, got in (
            ("bruto", inf.get("bruto"), pag.get("bruto")),
            ("retencion", inf.get("retencion"), pag.get("retencion")),
            ("liquido", inf.get("liquido"), pag.get("liquido")),
        ):
            if exp is None and got is None:
                continue
            if exp is None or got is None:
                amount_mismatches.append(
                    _amount_mismatch(rut=rut, boleta=boleta, field=field, expected=exp, got=got)
                )
                continue
            if abs(int(got) - int(exp)) > _AMOUNT_TOLERANCE:
                amount_mismatches.append(
                    _amount_mismatch(rut=rut, boleta=boleta, field=field, expected=exp, got=got)
                )

        # % retención
        pct_inf = inf.get("pct")
        pct_pag = pag.get("pct_derived")
        pct_tipo = pag.get("pct_tipo")
        if pct_inf is not None and pct_pag is not None:
            if abs(float(pct_pag) - float(pct_inf)) > _PCT_TOLERANCE:
                pct_mismatches.append(
                    {
                        "rut": rut,
                        "boleta": boleta,
                        "field": "porcentaje",
                        "expected": float(pct_inf),
                        "got": float(pct_pag),
                        "diff": round(float(pct_pag) - float(pct_inf), 4),
                        "source": "retencion/bruto",
                    }
                )
        elif pct_inf is not None and isinstance(pct_tipo, set):
            if float(pct_inf) not in pct_tipo and not any(
                abs(float(pct_inf) - r) <= _PCT_TOLERANCE for r in pct_tipo
            ):
                pct_mismatches.append(
                    {
                        "rut": rut,
                        "boleta": boleta,
                        "field": "porcentaje",
                        "expected": float(pct_inf),
                        "got": sorted(pct_tipo),
                        "diff": None,
                        "source": "tipo_documento",
                    }
                )
        elif pct_inf is not None and isinstance(pct_tipo, (int, float)):
            if abs(float(pct_tipo) - float(pct_inf)) > _PCT_TOLERANCE:
                pct_mismatches.append(
                    {
                        "rut": rut,
                        "boleta": boleta,
                        "field": "porcentaje",
                        "expected": float(pct_inf),
                        "got": float(pct_tipo),
                        "diff": round(float(pct_tipo) - float(pct_inf), 4),
                        "source": "tipo_documento",
                    }
                )
        elif pct_inf is not None and pct_pag is None and pct_tipo is None:
            warnings.append(
                {
                    "rut": rut,
                    "boleta": boleta,
                    "field": "porcentaje",
                    "message": "Contabilidad no trae % ni Tipo Documento usable para cruzar retención.",
                }
            )

        # Sede / ubicación — soft
        loc_inf = str(inf.get("location") or "").strip()
        loc_pag = str(pag.get("location") or "").strip()
        if loc_inf and loc_pag:
            try:
                same = int(float(loc_inf)) == int(float(loc_pag))
            except (TypeError, ValueError):
                same = loc_inf.casefold() == loc_pag.casefold()
            if not same:
                warnings.append(
                    {
                        "rut": rut,
                        "boleta": boleta,
                        "field": "ubicacion",
                        "message": f"LOCATION informe={loc_inf} vs Contabilidad={loc_pag}",
                    }
                )

    informe_bruto = sum(int(v["bruto"]) for v in informe_map.values() if v.get("bruto") is not None)
    pagos_bruto = sum(int(v["bruto"]) for v in pagos_map.values() if v.get("bruto") is not None)
    informe_liquido = sum(int(v["liquido"]) for v in informe_map.values() if v.get("liquido") is not None)
    pagos_liquido = sum(int(v["liquido"]) for v in pagos_map.values() if v.get("liquido") is not None)

    errors_count = len(only_in_informe) + len(only_in_pagos) + len(amount_mismatches) + len(pct_mismatches)
    return {
        "ok": errors_count == 0,
        "matched": matched,
        "informe_rows": len(informe_map),
        "pagos_rows": len(pagos_map),
        "only_in_informe": only_in_informe,
        "only_in_pagos": only_in_pagos,
        "amount_mismatches": amount_mismatches,
        "pct_mismatches": pct_mismatches,
        "warnings": warnings,
        "totals": {
            "informe_bruto": informe_bruto,
            "pagos_bruto": pagos_bruto,
            "bruto_diff": pagos_bruto - informe_bruto,
            "informe_liquido": informe_liquido,
            "pagos_liquido": pagos_liquido,
            "liquido_diff": pagos_liquido - informe_liquido,
            "informe_count": len(informe_map),
            "pagos_count": len(pagos_map),
            "count_diff": len(pagos_map) - len(informe_map),
        },
        "errors_count": errors_count,
        "warnings_count": len(warnings),
    }


def cruzar_periodo(
    *,
    year: int | str,
    month: str,
    pagos: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Carga Solicitud del período y cruza Resumen Boletas vs Pagos."""
    month_norm = str(month).strip().capitalize()
    solicitud = _solicitud_path(year, month_norm)
    base: dict[str, Any] = {
        "ok": False,
        "year": int(year),
        "month": month_norm,
        "solicitud": os.path.abspath(solicitud) if os.path.isfile(solicitud) else None,
        "matched": 0,
        "informe_rows": 0,
        "pagos_rows": 0,
        "only_in_informe": [],
        "only_in_pagos": [],
        "amount_mismatches": [],
        "pct_mismatches": [],
        "warnings": [],
        "totals": {},
        "errors_count": 1,
        "warnings_count": 0,
        "message": "",
    }

    if not os.path.isfile(solicitud):
        base["message"] = f"No existe Solicitud del período: {solicitud}"
        return base

    resumen, sheet = _load_resumen(solicitud)
    if resumen is None or sheet is None:
        base["message"] = "No existe la hoja «Resumen Boletas». Generá el informe del paso 6 primero."
        return base

    if pagos is None:
        try:
            pagos = pd.read_excel(solicitud, sheet_name="Pagos", engine="openpyxl")
        except Exception as exc:
            base["message"] = f"No se pudo leer la hoja Pagos: {exc}"
            return base

    if pagos is None or pagos.empty:
        base["message"] = "La hoja Pagos está vacía."
        return base

    sol_main = _load_solicitud_main(solicitud)
    xml_index = _build_xml_index(sol_main) if sol_main is not None else {"by_boleta": {}, "by_re_loc": {}}

    result = compare_informe_vs_pagos(resumen=resumen, pagos=pagos, xml_index=xml_index)
    result["year"] = int(year)
    result["month"] = month_norm
    result["solicitud"] = os.path.abspath(solicitud)
    result["resumen_sheet"] = sheet
    if result["ok"]:
        result["message"] = (
            f"Cruzado OK: {result['matched']} boleta(s) coinciden "
            f"(informe {result['informe_rows']} / Contabilidad {result['pagos_rows']})."
        )
    else:
        result["message"] = (
            f"Cruzado con diferencias: {result['errors_count']} error(es), "
            f"{result['warnings_count']} advertencia(s). "
            f"Solo informe={len(result['only_in_informe'])}, "
            f"solo Contabilidad={len(result['only_in_pagos'])}, "
            f"montos={len(result['amount_mismatches'])}, "
            f"%={len(result['pct_mismatches'])}."
        )
    return result
