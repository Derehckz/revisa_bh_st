"""Importa pagos de Contabilidad hacia la hoja Pagos del período.

Contabilidad suele enviar solo una tabla en el cuerpo del correo (HTML),
sin Excel. Pegar esa tabla en Excel corrompe montos y Nº de cuenta.
Este módulo acepta:
  - pegado HTML / TSV / CSV (vía API paso 7)
  - archivo .xlsx / .csv si existe
y completa MAIL + SEDE desde la Solicitud del mes.
"""
from __future__ import annotations

import os
import re
from io import StringIO
from typing import Any

import pandas as pd

import bh_excel_workbook
import config

# Columnas canónicas de la hoja Pagos (Abril 2026 como referencia).
PAGOS_COLUMNS = [
    "Descripción",
    "Empr",
    "ID",
    "RE",
    "Nombre",
    "Ubicación",
    "SEDE",
    "Número Boleta",
    "Tipo Documento",
    "Estado Boleta",
    "Fecha Emisión",
    "Mes",
    "Año",
    "Bruto $",
    "RETENCIÓN",
    "LÍQUIDO",
    "Liquido Final",
    "FORMA PAGO",
    "COD BANC",
    "BANCO",
    "NªCUENTA",
    "MAIL",
    "Correo Enviado",
]

_ALIASES: dict[str, tuple[str, ...]] = {
    "Descripción": ("descripcion", "descripción", "descripcion empr", "descripción empr"),
    "Empr": ("empr", "empresa"),
    "ID": ("id", "rut", "emplid", "rut docente"),
    "RE": ("re", "empl_rcd", "regempleo"),
    "Nombre": ("nombre", "name", "nombre docente"),
    "Ubicación": ("ubicacion", "ubicación", "location", "codsede"),
    "SEDE": ("sede", "nombresede", "nombre sede"),
    "Número Boleta": ("numero boleta", "número boleta", "n° boleta", "nº boleta", "boleta", "folio"),
    "Tipo Documento": ("tipo documento", "tipdoc", "tipo doc"),
    "Estado Boleta": ("estado boleta", "estado"),
    "Fecha Emisión": ("fecha emision", "fecha emisión", "fechaemis"),
    "Mes": ("mes", "month"),
    "Año": ("año", "ano", "year"),
    "Bruto $": ("bruto $", "bruto", "montobruto", "monto bruto"),
    "RETENCIÓN": ("retencion", "retención", "%retencion", "retencion $"),
    "LÍQUIDO": ("liquido", "líquido", "liquido $"),
    "Liquido Final": ("liquido final", "líquido final", "liquido fina"),
    "FORMA PAGO": ("forma pago", "tipodepago", "tipo de pago", "forma de pago"),
    "COD BANC": ("cod banc", "cod banco", "codigo banco", "cód banco"),
    "BANCO": ("banco",),
    "NªCUENTA": ("nªcuenta", "nºcuenta", "n°cuenta", "ncuenta", "cuenta", "nº cuenta", "no cuenta"),
    "MAIL": ("mail", "email", "email_docente", "correo"),
    "Correo Enviado": ("correo enviado",),
}


def _norm_header(value: object) -> str:
    s = str(value or "").strip().lower()
    s = s.replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s)
    return s


def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename: dict[str, str] = {}
    used_targets: set[str] = set()
    for col in df.columns:
        key = _norm_header(col)
        for target, aliases in _ALIASES.items():
            if target in used_targets:
                continue
            if key == _norm_header(target) or key in aliases:
                rename[col] = target
                used_targets.add(target)
                break
    out = df.rename(columns=rename)
    return out


def _parse_amount_miles(value: object) -> float | None:
    """Conserva el formato Contabilidad (miles: 91.53 → 91.53), no pesos enteros."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    texto = str(value).strip()
    if not texto or texto.lower() in {"nan", "none", "-"}:
        return None
    texto = texto.replace("$", "").replace(" ", "").replace("\u00a0", "")
    # Miles CL con punto miles y coma decimal: 1.234,56
    if "." in texto and "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto and "." not in texto:
        # Solo coma → decimal CL
        texto = texto.replace(",", ".")
    # Solo puntos: si parece miles chilenos 1.234.567 sin decimales
    elif texto.count(".") > 1:
        partes = texto.split(".")
        if all(p.isdigit() for p in partes) and all(len(p) == 3 for p in partes[1:]):
            texto = "".join(partes)
    try:
        return float(texto)
    except ValueError:
        return None


def _parse_cuenta(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # Evita 5.51E+10 en string; si perdió precisión ya no hay remedio.
        if value.is_integer() or abs(value - round(value)) < 1e-6:
            return str(int(round(value)))
        # Notación científica leída como float
        return f"{value:.0f}"
    texto = str(value).strip()
    if not texto or texto.lower() in {"nan", "none"}:
        return ""
    if re.fullmatch(r"\d+(\.0+)?", texto):
        return texto.split(".")[0]
    if re.search(r"[eE][+\-]?\d+", texto):
        try:
            return str(int(float(texto.replace(",", "."))))
        except ValueError:
            return texto
    return re.sub(r"\D", "", texto) or texto


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


def _solicitud_path(year: int | str, month: str) -> str:
    return os.path.join(config.RAIZ, str(year), str(month).strip().capitalize(), "Solicitud.xlsx")


def _load_solicitud_sheet(solicitud_path: str) -> pd.DataFrame | None:
    if not os.path.isfile(solicitud_path):
        return None
    xl = pd.ExcelFile(solicitud_path, engine="openpyxl")
    hoja = None
    for candidata in ("Sheet1", "Solicitud", *xl.sheet_names):
        if candidata not in xl.sheet_names:
            continue
        probe = pd.read_excel(solicitud_path, sheet_name=candidata, engine="openpyxl", nrows=2)
        cols = {str(c) for c in probe.columns}
        if "Email_Docente" in cols or "EMPLID" in cols:
            hoja = candidata
            break
    if not hoja:
        return None
    return pd.read_excel(solicitud_path, sheet_name=hoja, engine="openpyxl")


def _solicitud_enrichment(solicitud_path: str) -> dict[str, dict[str, str]]:
    """ID (RUT) → {mail, sede} desde hoja Solicitud."""
    sol = _load_solicitud_sheet(solicitud_path)
    if sol is None:
        return {}
    out: dict[str, dict[str, str]] = {}
    for _, row in sol.iterrows():
        rid = _normalize_rut(row.get("EMPLID") or row.get("RUT_SIN_DV"))
        if not rid:
            continue
        mail = str(row.get("Email_Docente") or "").strip()
        if mail.lower() in {"nan", "none"}:
            mail = ""
        sede = str(row.get("SEDE") or "").strip()
        if sede.lower() in {"nan", "none"}:
            sede = ""
        prev = out.get(rid) or {"mail": "", "sede": ""}
        if mail and "@" in mail and not prev["mail"]:
            prev["mail"] = mail
        if sede and not prev["sede"]:
            prev["sede"] = sede
        out[rid] = prev
    return out


def _mail_index_from_solicitud(solicitud_path: str) -> dict[str, str]:
    return {rid: meta["mail"] for rid, meta in _solicitud_enrichment(solicitud_path).items() if meta["mail"]}


def dataframe_from_paste(text: str) -> pd.DataFrame:
    """Parsea tabla pegada desde correo Contabilidad (HTML, TSV o CSV)."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Pegá la tabla del correo de Contabilidad (vacío).")

    df: pd.DataFrame | None = None
    # HTML table (pegar desde "ver origen" o mensaje HTML)
    if "<table" in raw.lower() or "<tr" in raw.lower():
        try:
            tables = pd.read_html(StringIO(raw))
            if tables:
                df = tables[0]
        except (ValueError, ImportError):
            df = None

    if df is None:
        # TSV típico al copiar celdas desde Outlook
        try:
            probe = pd.read_csv(StringIO(raw), sep="\t", dtype=str, engine="python")
            if probe.shape[1] >= 2:
                df = probe
        except Exception:
            df = None

    if df is None:
        try:
            df = pd.read_csv(StringIO(raw), sep=None, engine="python", dtype=str)
        except Exception as exc:
            raise ValueError(
                "No se pudo leer la tabla pegada. Copiá la tabla del correo "
                "(HTML o celdas) o subí un .csv/.xlsx."
            ) from exc

    if df is None or df.empty:
        raise ValueError("La tabla pegada no tiene filas.")
    # Limpia columnas Unnamed vacías
    df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed")]]
    return _map_columns(df)


def _read_csv_robust(path: str) -> pd.DataFrame:
    """CSV Contabilidad suele venir en MacRoman/cp1252 (no UTF-8), con `;`."""
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "mac_roman", "cp1252", "latin-1"):
        try:
            return pd.read_csv(path, sep=None, engine="python", encoding=enc)
        except UnicodeDecodeError as exc:
            last_err = exc
            continue
    # Último recurso: reemplazar bytes inválidos
    try:
        return pd.read_csv(path, sep=None, engine="python", encoding="latin-1")
    except Exception as exc:
        raise ValueError(
            f"No se pudo leer el CSV (encoding). Probá guardarlo como UTF-8 o .xlsx. Detalle: {last_err or exc}"
        ) from exc


def _sniff_is_zip_xlsx(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"PK"
    except OSError:
        return False


def _dataframe_from_eml(path: str) -> pd.DataFrame:
    """Extrae la tabla de pagos del correo .eml de Contabilidad (HTML)."""
    import email
    import re
    from email import policy
    from io import StringIO

    with open(path, "rb") as f:
        msg = email.message_from_bytes(f.read(), policy=policy.default)

    html = None
    plain = None
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype == "text/html" and html is None:
            try:
                html = part.get_content()
            except Exception:
                payload = part.get_payload(decode=True) or b""
                html = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        elif ctype == "text/plain" and plain is None:
            try:
                plain = part.get_content()
            except Exception:
                payload = part.get_payload(decode=True) or b""
                plain = payload.decode(part.get_content_charset() or "utf-8", errors="replace")

    if isinstance(html, str) and html.strip():
        tables = list(re.finditer(r"<table\b[^>]*>[\s\S]*?</table>", html, flags=re.IGNORECASE))
        best: pd.DataFrame | None = None
        for match in tables:
            chunk = match.group(0)
            marker = chunk.upper()
            if not any(k in marker for k in ("LQUIDO", "LÍQUIDO", "BRUTO", "BOLETA", ">ID<")):
                continue
            try:
                dfs = pd.read_html(StringIO(chunk))
            except ValueError:
                continue
            for df in dfs:
                if df.shape[1] < 6 or df.shape[0] < 2:
                    continue
                if best is None or df.shape[0] * df.shape[1] > best.shape[0] * best.shape[1]:
                    best = df
        if best is not None:
            df = best.copy()
            # Si la primera fila es el encabezado (columnas 0..n)
            if all(str(c).isdigit() or isinstance(c, (int, float)) for c in df.columns):
                header = [str(x).strip() for x in list(df.iloc[0])]
                body = df.iloc[1:].copy()
                body.columns = header
                df = body.reset_index(drop=True)
            return df

    if isinstance(plain, str) and plain.strip():
        return dataframe_from_paste(plain)

    raise ValueError(
        "No se encontró la tabla de pagos en el .eml. "
        "Abrí el correo en Outlook y exportá/guardá la tabla como CSV, o pegala en el paso 7."
    )


def load_contabilidad_dataframe(path: str) -> pd.DataFrame:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"No existe archivo: {path}")
    ext = os.path.splitext(path)[1].lower()
    is_zip = _sniff_is_zip_xlsx(path)

    if ext == ".eml":
        df = _dataframe_from_eml(path)
    elif ext in {".xlsx", ".xlsm"} or (ext == ".xls" and is_zip):
        if not is_zip:
            # Excel vacío / CSV renombrado a .xlsx
            try:
                df = _read_csv_robust(path)
            except Exception as exc:
                raise ValueError(
                    "El archivo .xlsx no es un Excel válido (parece texto/CSV). "
                    "Subí el .csv original, el .eml del correo, o guardá de nuevo como Libro de Excel."
                ) from exc
        else:
            df = pd.read_excel(path, engine="openpyxl")
            if df.empty or len(df.columns) == 0:
                raise ValueError(
                    "El Excel de pagos no tiene filas ni columnas. "
                    "Usá el .csv o el .eml del correo de Contabilidad (no un .xlsx vacío)."
                )
    elif ext == ".xls":
        df = pd.read_excel(path)
    elif ext == ".csv" or (ext in {"", ".txt"} and not is_zip):
        df = _read_csv_robust(path)
    elif ext in {".html", ".htm"}:
        tables = pd.read_html(path)
        if not tables:
            raise ValueError("El HTML no contiene tablas.")
        df = tables[0]
    else:
        # Extensión rara: intentar por contenido
        if is_zip:
            df = pd.read_excel(path, engine="openpyxl")
        elif ext == ".eml" or path.lower().endswith(".eml"):
            df = _dataframe_from_eml(path)
        else:
            df = _read_csv_robust(path)
    if df.empty:
        raise ValueError("El archivo de Contabilidad no tiene filas.")
    return _map_columns(df)


def build_pagos_dataframe(
    source: pd.DataFrame,
    *,
    mail_by_rut: dict[str, str] | None = None,
    sede_by_rut: dict[str, str] | None = None,
) -> pd.DataFrame:
    mail_by_rut = mail_by_rut or {}
    sede_by_rut = sede_by_rut or {}
    rows: list[dict[str, Any]] = []
    for _, raw in source.iterrows():
        item = {c: "" for c in PAGOS_COLUMNS}
        for col in PAGOS_COLUMNS:
            if col in source.columns and col not in (
                "MAIL",
                "Correo Enviado",
                "Bruto $",
                "RETENCIÓN",
                "LÍQUIDO",
                "Liquido Final",
                "NªCUENTA",
                "ID",
                "SEDE",
            ):
                val = raw.get(col)
                item[col] = "" if pd.isna(val) else val

        rid = _normalize_rut(raw.get("ID") if "ID" in source.columns else "")
        item["ID"] = rid
        item["NªCUENTA"] = _parse_cuenta(raw.get("NªCUENTA") if "NªCUENTA" in source.columns else "")

        for money_col in ("Bruto $", "RETENCIÓN", "LÍQUIDO", "Liquido Final"):
            if money_col in source.columns:
                parsed = _parse_amount_miles(raw.get(money_col))
                item[money_col] = parsed if parsed is not None else ""

        # Liquido Final = LÍQUIDO si viene vacío
        if item["Liquido Final"] in ("", None) and item["LÍQUIDO"] not in ("", None):
            item["Liquido Final"] = item["LÍQUIDO"]

        sede = ""
        if "SEDE" in source.columns:
            sede = str(raw.get("SEDE") or "").strip()
            if sede.lower() in {"nan", "none"}:
                sede = ""
        if not sede and rid:
            sede = sede_by_rut.get(rid, "")
        item["SEDE"] = sede

        mail = ""
        if "MAIL" in source.columns:
            mail = str(raw.get("MAIL") or "").strip()
            if mail.lower() in {"nan", "none"}:
                mail = ""
        if not mail and rid:
            mail = mail_by_rut.get(rid, "")
        item["MAIL"] = mail
        item["Correo Enviado"] = ""
        if not rid and not item.get("Nombre"):
            continue
        rows.append(item)

    if not rows:
        raise ValueError("No se pudo mapear ninguna fila de pagos.")
    return pd.DataFrame(rows, columns=PAGOS_COLUMNS)


def _summary_from_pagos(pagos: pd.DataFrame, *, year: int, month: str, source_label: str) -> dict[str, Any]:
    missing_mail = int((pagos["MAIL"].astype(str).str.strip() == "").sum())
    missing_sede = int((pagos["SEDE"].astype(str).str.strip() == "").sum())
    missing_liquido = int(
        pagos["LÍQUIDO"].isna().sum() + (pagos["LÍQUIDO"].astype(str).str.strip() == "").sum()
    )
    sample = []
    for _, row in pagos.head(8).iterrows():
        sample.append(
            {
                "id": str(row.get("ID") or ""),
                "nombre": str(row.get("Nombre") or ""),
                "sede": str(row.get("SEDE") or ""),
                "mail": str(row.get("MAIL") or ""),
                "liquido": row.get("LÍQUIDO"),
                "cuenta": str(row.get("NªCUENTA") or ""),
            }
        )
    return {
        "ok": True,
        "year": int(year),
        "month": month,
        "source": source_label,
        "rows": int(len(pagos)),
        "missing_mail": missing_mail,
        "missing_sede": missing_sede,
        "missing_liquido": missing_liquido,
        "sample": sample,
        "written": False,
    }


def import_pagos_dataframe_into_period(
    *,
    year: int | str,
    month: str,
    source: pd.DataFrame,
    source_label: str = "paste",
    write: bool = True,
) -> dict[str, Any]:
    month_norm = str(month).strip().capitalize()
    solicitud = _solicitud_path(year, month_norm)
    if not os.path.isfile(solicitud):
        raise FileNotFoundError(f"No existe Solicitud del período: {solicitud}")

    enrich = _solicitud_enrichment(solicitud)
    mails = {rid: meta["mail"] for rid, meta in enrich.items() if meta["mail"]}
    sedes = {rid: meta["sede"] for rid, meta in enrich.items() if meta["sede"]}
    mapped = source if "ID" in source.columns else _map_columns(source)
    if "ID" not in mapped.columns:
        mapped = _map_columns(source)
    pagos = build_pagos_dataframe(mapped, mail_by_rut=mails, sede_by_rut=sedes)

    result = _summary_from_pagos(pagos, year=int(year), month=month_norm, source_label=source_label)
    result["solicitud"] = os.path.abspath(solicitud)
    if write:
        ok = bh_excel_workbook.replace_sheet_atomically(solicitud, "Pagos", pagos)
        if not ok:
            raise RuntimeError("No se pudo escribir la hoja Pagos en Solicitud.xlsx")
        result["written"] = True
        result["message"] = (
            f"Hoja Pagos actualizada: {len(pagos)} fila(s). "
            f"Sin MAIL: {result['missing_mail']}. "
            f"Sin SEDE: {result['missing_sede']}. "
            f"Sin LÍQUIDO: {result['missing_liquido']}."
        )

    import pagos_informe_cruzado

    cruzado = pagos_informe_cruzado.cruzar_periodo(
        year=year,
        month=month_norm,
        pagos=pagos,
    )
    result["cruzado"] = cruzado
    if cruzado.get("message"):
        result["message"] = (result.get("message") or "") + " · " + str(cruzado["message"])

    if write:
        try:
            import period_snapshots
            from stages.stage7.payment_projection import project_pagos_dataframe

            payload = period_snapshots.build_pagos_payload_from_df(
                year, month_norm, pagos, source=source_label
            )
            period_snapshots.save_pagos_snapshot(year, month_norm, payload, mark_frozen=False)
            result["pagos_snapshot"] = {"total_rows": payload.get("total_rows")}
            result["payment_projection"] = project_pagos_dataframe(
                year=year, month=month_norm, df=pagos
            )
        except Exception as exc:
            result["pagos_snapshot_error"] = str(exc)

    return result


def import_pagos_from_paste(
    *,
    year: int | str,
    month: str,
    paste: str,
    write: bool = True,
) -> dict[str, Any]:
    source = dataframe_from_paste(paste)
    return import_pagos_dataframe_into_period(
        year=year,
        month=month,
        source=source,
        source_label="paste",
        write=write,
    )


def import_pagos_into_period(
    *,
    year: int | str,
    month: str,
    source_path: str,
    write: bool = True,
) -> dict[str, Any]:
    source = load_contabilidad_dataframe(source_path)
    return import_pagos_dataframe_into_period(
        year=year,
        month=month,
        source=source,
        source_label=os.path.abspath(source_path),
        write=write,
    )


def preview_pagos_emails(
    *,
    year: int | str,
    month: str,
    fecha_pago: str,
    force_resend: bool = False,
) -> dict[str, Any]:
    """Arma la lista de correos que enviaría el paso 7 desde la hoja Pagos."""
    import email_templates as templates
    import mail_ledger
    import utils
    from stages.stage7 import mail as mail_ops

    month_norm = str(month).strip().capitalize()
    solicitud = _solicitud_path(year, month_norm)
    if not os.path.isfile(solicitud):
        raise FileNotFoundError(f"No existe Solicitud del período: {solicitud}")

    fecha = (fecha_pago or "").strip()
    if not fecha:
        raise ValueError("Indica la fecha de pago (dd/mm/aaaa).")

    try:
        df = pd.read_excel(solicitud, sheet_name="Pagos", engine="openpyxl")
    except Exception as exc:
        raise ValueError(f"No se pudo leer la hoja Pagos: {exc}") from exc

    if df.empty:
        raise ValueError("La hoja Pagos está vacía. Importá primero la tabla de Contabilidad.")
    if "MAIL" not in df.columns:
        raise ValueError("Falta columna MAIL en Pagos.")

    if "Correo Enviado" not in df.columns:
        df["Correo Enviado"] = ""

    mes_año_pago = f"{month_norm} {year}"
    candidates: list[dict[str, Any]] = []
    skipped_no_mail = 0
    skipped_already = 0

    for idx, fila in df.iterrows():
        correo = str(fila.get("MAIL", "")).strip()
        nombre = str(fila.get("Nombre", "") or "")
        estado = str(fila.get("Correo Enviado", "") or "").strip().lower()
        if not utils.validar_email(correo):
            skipped_no_mail += 1
            continue
        if "enviado" in estado and not force_resend:
            skipped_already += 1
            continue

        rut = fila.get("ID", "")
        banco = fila.get("BANCO", "")
        tipo_cuenta = fila.get("FORMA PAGO", "")
        nro_cuenta = mail_ops.normalizar_nro_cuenta(fila.get("NªCUENTA", ""))
        n_boleta = fila.get("Boleta", fila.get("Número Boleta", ""))
        codigo_origen = str(
            fila.get(
                "LOCATION",
                fila.get("CODIGO", fila.get("INS", fila.get("Ubicación", ""))),
            )
        ).strip()
        monto = mail_ops.normalizar_monto_liquido(fila.get("LÍQUIDO", 0))
        monto_bruto = mail_ops.normalizar_monto_liquido(fila.get("Bruto $", 0))
        monto_retencion = mail_ops.normalizar_monto_liquido(fila.get("RETENCIÓN", 0))
        monto_correo = f"${monto:,.0f}".replace(",", ".")
        pct = None
        if monto_bruto:
            try:
                pct = round(100.0 * float(monto_retencion) / float(monto_bruto), 2)
            except Exception:
                pct = None
        item_key = mail_ops.build_item_key(
            mes_año_pago, rut, correo, codigo_origen, n_boleta, tipo_cuenta, nro_cuenta, monto
        )
        already_ledger = (not force_resend) and mail_ledger.was_sent(mail_ops.STAGE_ID, item_key)
        if already_ledger:
            skipped_already += 1
            continue

        asunto = templates.generar_asunto_pago(nombre, mes_año_pago)
        cuerpo = templates.generar_cuerpo_pago(
            nombre=nombre,
            mes_año_pago=mes_año_pago,
            fecha_pago=fecha,
            banco=banco,
            tipo_cuenta=tipo_cuenta,
            nro_cuenta=nro_cuenta,
            monto=monto,
        )
        try:
            ix = int(idx)
        except (TypeError, ValueError):
            ix = idx
        candidates.append(
            {
                "index": ix,
                "nombre": nombre,
                "mail": correo,
                "sede": str(fila.get("SEDE") or ""),
                "ubicacion": codigo_origen,
                "id": str(rut or ""),
                "boleta": str(n_boleta or ""),
                "descripcion": str(fila.get("Descripción") or ""),
                "bruto": monto_bruto,
                "bruto_txt": f"${monto_bruto:,.0f}".replace(",", "."),
                "retencion": monto_retencion,
                "retencion_txt": f"${monto_retencion:,.0f}".replace(",", "."),
                "pct_retencion": pct,
                "monto": monto,
                "monto_txt": monto_correo,
                "banco": str(banco or ""),
                "cuenta": nro_cuenta,
                "forma_pago": str(tipo_cuenta or ""),
                "tipo_documento": str(fila.get("Tipo Documento") or ""),
                "fecha_pago": fecha,
                "subject": asunto,
                "html_body": cuerpo,
                "idempotency_key": item_key,
            }
        )

    return {
        "ok": True,
        "year": int(year),
        "month": month_norm,
        "fecha_pago": fecha,
        "total_rows": int(len(df)),
        "ready": len(candidates),
        "skipped_no_mail": skipped_no_mail,
        "skipped_already": skipped_already,
        "candidates": candidates,
    }
