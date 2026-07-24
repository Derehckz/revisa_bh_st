"""Reintento COM leyendo filas `pending` del outbox (sin re-ejecutar el script completo).

Enruta por `stage` hacia la misma lógica de envío que 1 / 5 / 7, reutilizando el `id` de outbox existente.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd

import config
import bh_excel_workbook
import email_outbox
import utils

ROOT = Path(__file__).resolve().parent.parent


def _load_module(mod_name: str, file_name: str):
    path = ROOT / file_name
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar {path}")
    mod = importlib.util.module_from_spec(spec)
    # nombre único para evitar colisiones al recargar
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _parse_script1_parts(item_key: str) -> tuple[str, str, str, str, str | None, bool]:
    """Devuelve (año, mes, rut_docente, email, rut_razon|None, provisionado)."""
    parts = item_key.split("|")
    if len(parts) >= 2 and parts[-1].startswith("r") and parts[-1][1:].isdigit():
        parts = parts[:-1]
    provisionado = False
    if parts and parts[-1] == "prov":
        provisionado = True
        parts = parts[:-1]
    # Actual: año|mes|rut|rut_razon|email  (5)
    # Legacy: año|mes|rut|email  (4)
    if len(parts) == 5:
        return str(parts[0]), str(parts[1]), str(parts[2]), str(parts[4]), str(parts[3]), provisionado
    if len(parts) == 4:
        return str(parts[0]), str(parts[1]), str(parts[2]), str(parts[3]), None, provisionado
    raise ValueError(f"item_key script1 inválido ({len(parts)} partes): {item_key!r}")


def _parse_script5_parts(item_key: str) -> tuple[str, str, str, str]:
    parts = item_key.split("|")
    if len(parts) != 4:
        raise ValueError(f"item_key script5 inválido: {item_key!r}")
    return str(parts[0]), str(parts[1]), str(parts[2]), str(parts[3])


def _script1_tipo_from_stage(stage: str) -> str:
    if stage.endswith(".recordatorio"):
        return "recordatorio"
    return "original"


def _script1_find_idx(
    df: pd.DataFrame,
    año: str,
    mes: str,
    rut: str,
    email: str,
    *,
    rut_razon: str | None = None,
    provisionado: bool = False,
):
    from stages.stage1.mail import es_glosa_provisionado

    mes_u = mes.upper()
    email_l = email.strip().lower()
    rr_norm = utils.normalizar_rut_con_dv(rut_razon) if rut_razon else None
    for idx in df.index:
        try:
            y = str(int(float(df.at[idx, "YEAR"])))
        except (TypeError, ValueError, KeyError):
            y = str(df.at[idx, "YEAR"])
        m = str(df.at[idx, "MONTH"]).strip().upper()
        em = str(df.at[idx, "EMPLID"]).strip()
        eml = str(df.at[idx, "Email_Docente"]).strip().lower()
        if not (y == str(año) and m == mes_u and em == str(rut).strip() and eml == email_l):
            continue
        glosa = df.at[idx, "GLOSA"] if "GLOSA" in df.columns else ""
        if es_glosa_provisionado(glosa) != provisionado:
            continue
        if rr_norm is not None and "RUT RAZON" in df.columns:
            row_rr = utils.normalizar_rut_con_dv(df.at[idx, "RUT RAZON"])
            if row_rr != rr_norm:
                continue
        return idx
    return None


def _script1_save(ruta_excel: str, hoja: str, df: pd.DataFrame) -> None:
    if not bh_excel_workbook.replace_sheet_atomically(ruta_excel, hoja, df):
        raise OSError("No se pudo guardar Excel (reemplazo atómico de hoja) en dispatch script1")


def _dispatch_script1(*, ob_id: int, stage: str, item_key: str, dry_run: bool) -> str:
    año, mes, rut, email, rut_razon, provisionado = _parse_script1_parts(item_key)
    tipo = _script1_tipo_from_stage(stage)
    ruta_mes = os.path.join(config.RAIZ, año, mes)
    if not os.path.isdir(ruta_mes):
        email_outbox.mark_failed(ob_id, f"Carpeta período inexistente: {ruta_mes}")
        return "failed"
    xlsx = [f for f in os.listdir(ruta_mes) if f.lower().endswith(".xlsx")]
    if not xlsx:
        email_outbox.mark_failed(ob_id, f"Sin Excel en {ruta_mes}")
        return "failed"
    archivo = "Solicitud.xlsx" if "Solicitud.xlsx" in xlsx else xlsx[0]
    ruta_excel = os.path.join(ruta_mes, archivo)
    xls = pd.ExcelFile(ruta_excel, engine="openpyxl")
    hoja = utils.pick_excel_sheet(xls.sheet_names)
    df = pd.read_excel(ruta_excel, sheet_name=hoja, engine="openpyxl")
    idx = _script1_find_idx(
        df, año, mes, rut, email, rut_razon=rut_razon, provisionado=provisionado
    )
    if idx is None:
        email_outbox.mark_failed(ob_id, "Fila no encontrada en Excel para item_key")
        return "failed"
    if dry_run:
        logging.info("[dry-run] script1 ob_id=%s idx=%s tipo=%s", ob_id, idx, tipo)
        return "skipped"
    mod1 = _load_module("bh_envio_mensual_dispatch", "etapas/1.-envia_correo_mensual_bh.py")
    mod1.enviar_correos(
        df,
        [idx],
        tipo=tipo,
        force_resend=True,
        outbox_ids_by_index={idx: ob_id},
    )
    _script1_save(ruta_excel, hoja, df)
    st = email_outbox.get_row_status(ob_id)
    return "sent" if st == "sent" else "failed"


def _script5_find_idx(df: pd.DataFrame, boleta: str, correo: str, mod5) -> object | None:
    correo_l = correo.strip().lower()
    b_target = mod5.format_entero(boleta)
    for idx in df.index:
        b = mod5.format_entero(df.at[idx, "numeroBoleta_XML"])
        c = str(df.at[idx, "Email_Docente"]).strip().lower()
        if b == b_target and c == correo_l:
            return idx
    return None


def _dispatch_script5(*, ob_id: int, item_key: str, dry_run: bool) -> str:
    año, mes, boleta, correo = _parse_script5_parts(item_key)
    if dry_run:
        logging.info("[dry-run] script5 ob_id=%s boleta=%s", ob_id, boleta)
        return "skipped"
    mod5 = _load_module("bh_envio_recepcion_dispatch", "etapas/5.-Enviar_Correo_Recepcion.py")
    ruta_excel = os.path.join(config.RAIZ, año, mes, "Solicitud.xlsx")
    if not os.path.isfile(ruta_excel):
        email_outbox.mark_failed(ob_id, f"No existe {ruta_excel}")
        return "failed"
    df = pd.read_excel(ruta_excel, sheet_name=0, engine="openpyxl")
    idx = _script5_find_idx(df, boleta, correo, mod5)
    if idx is None:
        email_outbox.mark_failed(ob_id, "Fila recepción no encontrada (boleta/correo)")
        return "failed"
    try:
        idx_int = int(idx)
    except (TypeError, ValueError):
        idx_int = idx
    args = argparse.Namespace(
        force_resend=True,
        yes=True,
        year=año,
        month=mes,
    )
    utils.apply_non_interactive_from_args(args)
    mod5.main(args, dispatch_outbox={idx_int: ob_id}, dispatch_only_indices={idx_int})
    st = email_outbox.get_row_status(ob_id)
    return "sent" if st == "sent" else "failed"


def _build_script7_item_key(fila, mes: str, año: str, mod7) -> str:
    correo = str(fila.get("MAIL", "")).strip()
    rut = fila.get("ID", "")
    codigo_origen = str(
        fila.get("LOCATION", fila.get("CODIGO", fila.get("INS", "")))
    ).strip()
    n_boleta = fila.get("Boleta", "")
    tipo_cuenta = fila.get("FORMA PAGO", "")
    nro_cuenta = mod7.normalizar_nro_cuenta(fila.get("NªCUENTA", ""))
    monto = mod7.normalizar_monto_liquido(fila.get("LÍQUIDO", 0))
    mes_año_pago = f"{mes} {año}"
    return (
        f"{mes_año_pago}|{rut}|{correo}|{codigo_origen}|{n_boleta}|{tipo_cuenta}|{nro_cuenta}|{monto}"
    ).lower()


def _dispatch_script7(*, ob_id: int, item_key: str, payload: dict, dry_run: bool) -> str:
    if dry_run:
        logging.info("[dry-run] script7 ob_id=%s", ob_id)
        return "skipped"
    fecha_pago = (payload.get("fecha_pago") or "").strip()
    if not fecha_pago:
        email_outbox.mark_failed(ob_id, "payload sin fecha_pago; reenvíe con 7 --fecha-pago o borre la fila")
        return "failed"
    parts = item_key.split("|")
    if len(parts) != 8:
        email_outbox.mark_failed(ob_id, f"item_key script7 inesperado ({len(parts)} partes)")
        return "failed"
    mes_año = parts[0].strip()
    tok = mes_año.rsplit(" ", 1)
    if len(tok) != 2:
        email_outbox.mark_failed(ob_id, f"mes_año_pago inválido: {mes_año!r}")
        return "failed"
    mes, año = tok[0], tok[1]
    ruta_excel = os.path.join(config.RAIZ, año, mes, "Solicitud.xlsx")
    if not os.path.isfile(ruta_excel):
        email_outbox.mark_failed(ob_id, f"No existe {ruta_excel}")
        return "failed"
    df = pd.read_excel(ruta_excel, sheet_name="Pagos", engine="openpyxl")
    want = item_key.strip().lower()
    idx_hit = None
    mod7 = _load_module("bh_envio_pagos_dispatch", "etapas/7.-Envia_mail_pagos.py")
    for idx, fila in df.iterrows():
        if _build_script7_item_key(fila, mes, año, mod7) == want:
            idx_hit = idx
            break
    if idx_hit is None:
        email_outbox.mark_failed(ob_id, "Fila Pagos no encontrada para item_key")
        return "failed"
    try:
        idx_int = int(idx_hit)
    except (TypeError, ValueError):
        idx_int = idx_hit
    args = argparse.Namespace(
        force_resend=True,
        yes=True,
        send=True,
        fecha_pago=fecha_pago,
        year=año,
        month=mes,
        dispatch_outbox={idx_int: ob_id},
        dispatch_only_indices={idx_int},
    )
    utils.apply_non_interactive_from_args(args)
    mod7.main(args)
    st = email_outbox.get_row_status(ob_id)
    return "sent" if st == "sent" else "failed"


def dispatch_pending_com(*, limit: int = 30, dry_run: bool = False) -> tuple[int, int, int]:
    """Procesa filas `pending` FIFO. Retorna (enviados_ok, fallidos, omitidos_dry)."""
    rows = email_outbox.fetch_pending_rows(limit=limit)
    ok = fail = skip = 0
    for row in rows:
        ob_id = int(row["id"])
        stage = str(row["stage"])
        item_key = str(row["item_key"])
        payload: dict = {}
        raw = row.get("payload")
        if raw:
            try:
                payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
            except json.JSONDecodeError:
                payload = {}
        try:
            if stage.startswith("script1.mail_send."):
                r = _dispatch_script1(ob_id=ob_id, stage=stage, item_key=item_key, dry_run=dry_run)
            elif stage == "script5.recepcion_send":
                r = _dispatch_script5(ob_id=ob_id, item_key=item_key, dry_run=dry_run)
            elif stage == "script7.pago_send":
                r = _dispatch_script7(ob_id=ob_id, item_key=item_key, payload=payload, dry_run=dry_run)
            else:
                email_outbox.mark_failed(ob_id, f"stage no soportado para dispatch: {stage}")
                r = "failed"
        except Exception as e:
            logging.exception("dispatch ob_id=%s", ob_id)
            email_outbox.mark_failed(ob_id, str(e)[:1900])
            r = "failed"
        if r == "sent":
            ok += 1
        elif r == "failed":
            fail += 1
        else:
            skip += 1
    return ok, fail, skip


def main_cli() -> int:
    import argparse as ap

    p = ap.ArgumentParser(description="Reintento COM desde outbox (pending)")
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    o, f, s = dispatch_pending_com(limit=a.limit, dry_run=a.dry_run)
    print(f"dispatch-com: ok={o} failed={f} dry_skipped={s}")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main_cli())
