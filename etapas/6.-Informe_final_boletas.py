#!/usr/bin/env python3
import _sys_path  # noqa: E402
import os
import argparse
import pandas as pd
import config
import utils
import schema_validator
from sqlalchemy import select
from db.models import Boleta, BoletaXmlData, Periodo
from db.session import SessionLocal
from db.period_projector import project_dataframe

RAIZ = config.RAIZ

def obtener_ins(location):
    if str(location) == "508":
        return "IPS"
    elif str(location) == "114":
        return "CFT"
    else:
        return ""

def obtener_nombre_sede(location):
    if str(location) in ["508", "114"]:
        return "Matriz LL"
    else:
        return ""

def formatear_fecha(fecha):
    try:
        if pd.isna(fecha) or str(fecha).strip() == "":
            return ""
        fecha_str = str(int(fecha)).strip()
        if len(fecha_str) == 8:
            anio = fecha_str[0:4]
            mes = fecha_str[4:6]
            dia = fecha_str[6:8]
            return f"{dia}/{mes}/{anio}"
        else:
            return ""
    except (ValueError, TypeError):
        return ""

def determinar_tipo_pago(observacion):
    obs = str(observacion).strip().upper()
    if "OK; OJO ES PROVISIONADO" in obs:
        return "Boleta Pago Provisionado"
    elif "OK" in obs:
        return "Boleta Pago Normal"
    else:
        return ""


def _normalizar_obs_xml(valor) -> str:
    s = str(valor or "").strip().upper()
    for a, b in (("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U")):
        s = s.replace(a, b)
    return s


def fila_incluible_en_informe_final(fila, ruta_mes: str | None = None) -> tuple[bool, str]:
    """
    Solo boletas válidas para pago/informe:
    - extracción XML OK
    - Estado_Recepcion = RECIBIDO (no error / no pendiente)
    - glosa del XML coincide con la solicitada (tolerancias de formato)
    """
    from stages.stage3.revision_core import glosa_recibida_es_valida

    if _normalizar_obs_xml(fila.get("Observaciones_XML", "")) != "DATOS EXTRAIDOS OK":
        return False, "extraccion_xml"

    estado = str(fila.get("Estado_Recepcion", "") or "").strip().upper()
    if estado != "RECIBIDO":
        if estado == "RECIBIDO CON ERROR":
            return False, "recibido_con_error"
        if estado == "NO RECIBIDO":
            return False, "no_recibido"
        if not estado:
            return False, "sin_estado"
        return False, "estado_no_valido"

    if not glosa_recibida_es_valida(fila, ruta_mes):
        return False, "glosa_incorrecta"

    return True, "ok"


def filtrar_filas_informe_final(df_hoja: pd.DataFrame, ruta_mes: str | None = None):
    """Devuelve (df_incluido, conteo_exclusiones)."""
    if df_hoja is None or df_hoja.empty:
        return df_hoja.copy() if df_hoja is not None else pd.DataFrame(), {}

    mask = []
    exclusiones: dict[str, int] = {}
    for _, fila in df_hoja.iterrows():
        ok, reason = fila_incluible_en_informe_final(fila, ruta_mes)
        mask.append(ok)
        if not ok:
            exclusiones[reason] = exclusiones.get(reason, 0) + 1
    return df_hoja[pd.Series(mask, index=df_hoja.index)].copy(), exclusiones


def _digits_only(value) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _folio_norm(value) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        return str(int(float(raw)))
    except (TypeError, ValueError):
        return _digits_only(raw)


def _periodo_id_db(anio: int, mes: str) -> int | None:
    with SessionLocal() as session:
        row = session.execute(
            select(Periodo.id).where(
                Periodo.anio == int(anio),
                Periodo.mes_nombre == str(mes),
            )
        ).first()
        return int(row[0]) if row else None


def filtrar_filas_informe_final_db(df_hoja: pd.DataFrame, *, anio: int, mes: str):
    """
    Filtro canónico desde DB (fuente de verdad):
    - recepcion_status = RECIBIDO_OK
    - xml_status = OK
    - glosa_match_mode != distinta
    """
    periodo_id = _periodo_id_db(anio, mes)
    if periodo_id is None:
        return pd.DataFrame(), {"sin_periodo_db": len(df_hoja)}

    with SessionLocal() as session:
        rows = session.execute(
            select(
                Boleta.emplid,
                BoletaXmlData.numero_boleta,
            )
            .join(BoletaXmlData, BoletaXmlData.boleta_id == Boleta.id)
            .where(
                Boleta.periodo_id == periodo_id,
                Boleta.recepcion_status == "RECIBIDO_OK",
                Boleta.xml_status == "OK",
                (Boleta.glosa_match_mode.is_(None) | (Boleta.glosa_match_mode != "distinta")),
            )
        ).all()
    include_keys = {
        (_digits_only(emplid), _folio_norm(numero))
        for emplid, numero in rows
        if _digits_only(emplid) and _folio_norm(numero)
    }

    if not include_keys:
        return df_hoja.iloc[0:0].copy(), {"db_sin_boletas_validas": len(df_hoja)}

    keep_mask = []
    exclusiones: dict[str, int] = {}
    for _, fila in df_hoja.iterrows():
        key = (_digits_only(fila.get("EMPLID", "")), _folio_norm(fila.get("numeroBoleta_XML", "")))
        ok = key in include_keys
        keep_mask.append(ok)
        if not ok:
            exclusiones["excluida_por_estado_db"] = exclusiones.get("excluida_por_estado_db", 0) + 1

    return df_hoja[pd.Series(keep_mask, index=df_hoja.index)].copy(), exclusiones


def formatear_tipo_doc(valor):
    try:
        v = float(valor)
        if v == 14.5:
            return "BER( 14,50% )"
        elif v == 17.5:
            return "BR( 17,50% )"
        else:
            return str(valor)
    except (ValueError, TypeError):
        return str(valor)
    
def formatear_rut(rut):
    rut_str = str(rut).strip()
    if len(rut_str) == 9:
        rut_str = "0" + rut_str
    if rut_str[-1:].lower() == 'k':
        rut_str = rut_str[:-1] + 'K'
    return rut_str

def main(args=None):
    if args is None:
        args = argparse.Namespace(yes=False, year=None, month=None)
    utils.apply_non_interactive_from_args(args)
    utils.print_header("📂 Selección de Excel y creación hoja resumen", "Generando hoja resumen de boletas")
    utils.print_step(1, 4, "Selección de período")

    try:
        año, mes = utils.resolve_año_mes(RAIZ, getattr(args, "year", None), getattr(args, "month", None))
    except ValueError as e:
        utils.print_error(str(e))
        return
    ruta_mes = os.path.join(RAIZ, año, mes)

    ruta_excel = os.path.join(ruta_mes, "Solicitud.xlsx")
    if not os.path.isfile(ruta_excel):
        utils.print_error(f"No se encontró archivo Excel en {ruta_excel}")
        return

    continuar = utils.mostrar_contexto_ejecucion(
        "🗂️ Contexto de ejecución",
        [
            ("Raíz", RAIZ),
            ("Período", f"{mes} {año}"),
            ("Carpeta mes", ruta_mes),
            ("Excel", ruta_excel),
        ],
        preview_items=["Se leerán hojas y se regenerará 'Resumen Boletas'."],
        confirm_message="¿Continuar con la generación del informe final? (s/n)",
    )
    if not continuar:
        utils.print_warning("Proceso cancelado por el usuario.")
        return

    utils.print_step(2, 4, "Lectura y filtrado de datos")
    df = pd.read_excel(ruta_excel, sheet_name=None, engine='openpyxl')
    hojas = list(df.keys())
    hoja = utils.choose_excel_sheet(
        hojas,
        sheet=getattr(args, "sheet", None),
        prompt_message="Seleccione la hoja del Excel a procesar:",
    )
    df_hoja = df[hoja]
    mes_num = config.MESES_ES.index(mes) + 1 if mes in config.MESES_ES else 0
    if mes_num > 0:
        proj = project_dataframe(
            year=int(año),
            month_num=mes_num,
            month_name=mes,
            df=df_hoja,
        )
        utils.print_info(
            f"DB projector etapa 6: {proj.get('projected', 0)} sincronizadas, "
            f"{proj.get('failed', 0)} fallidas."
        )

    canonical_errors, canonical_warnings = schema_validator.validate_for_stage(
        df_hoja, "stage6_informe_final"
    )
    for w in canonical_warnings:
        utils.print_warning(f"[schema] {w}")
    for e in canonical_errors:
        utils.print_error(f"[schema] {e}")

    # Fuente de verdad preferente: DB canónica.
    # Fallback: reglas locales sobre Excel (solo si DB no tiene período/boletas aún).
    try:
        df_filtrado, exclusiones = filtrar_filas_informe_final_db(
            df_hoja,
            anio=int(año),
            mes=mes,
        )
        if df_filtrado.empty and exclusiones and ("sin_periodo_db" in exclusiones or "db_sin_boletas_validas" in exclusiones):
            utils.print_warning("DB aún sin datos canónicos para el período; se usa filtro local de respaldo.")
            df_filtrado, exclusiones = filtrar_filas_informe_final(df_hoja, ruta_mes)
    except Exception as e:
        utils.print_warning(f"No se pudo usar filtro canónico DB ({e}); se usa filtro local.")
        df_filtrado, exclusiones = filtrar_filas_informe_final(df_hoja, ruta_mes)
    n_excl = sum(exclusiones.values())
    if n_excl:
        detalle = ", ".join(f"{k}={v}" for k, v in sorted(exclusiones.items()))
        utils.print_warning(
            f"Se excluyeron {n_excl} fila(s) del informe final ({detalle})."
        )
    utils.print_info(
        f"Incluidas en Resumen Boletas: {len(df_filtrado)} de {len(df_hoja)} fila(s)."
    )

    datos_resumen = []
    for _, fila in df_filtrado.iterrows():
        fecha_formateada = formatear_fecha(fila.get("fechaBoleta_XML", ""))
        tipo_pago = determinar_tipo_pago(fila.get("Observaciones", ""))
        ins = obtener_ins(fila.get("LOCATION", ""))
        nombre_sede = obtener_nombre_sede(fila.get("LOCATION", ""))
        tipo_doc_formateado = formatear_tipo_doc(fila.get("porcentajeImpuesto_XML", ""))

        nueva_fila = {
            "RUT": formatear_rut(fila.get("EMPLID", "")),
            "Nombre Docente": fila.get("NAME", ""),
            "Reg empleo": fila.get("EMPL_RCD", ""),
            "LOCATION": fila.get("LOCATION", ""),
            "INS": ins,
            "Nombre Sede": nombre_sede,
            "N° Boleta": fila.get("numeroBoleta_XML", ""),
            "Tipo Doc": tipo_doc_formateado,
            "Tipo de Pago": tipo_pago,
            "Fecha emisión": fecha_formateada,
            "Monto Bruto": fila.get("totalHonorarios_XML", "")
        }
        datos_resumen.append(nueva_fila)

    df_resumen = pd.DataFrame(datos_resumen)

    columnas_final = [
        "RUT", "Nombre Docente", "Reg empleo", "LOCATION", "INS", "Nombre Sede",
        "N° Boleta", "Tipo Doc", "Tipo de Pago", "Fecha emisión", "Monto Bruto"
    ]
    df_resumen = df_resumen[columnas_final]

    utils.print_step(3, 4, "Guardando hoja resumen")
    try:
        hojas = pd.read_excel(ruta_excel, sheet_name=None, engine='openpyxl')
        hojas["Resumen Boletas"] = df_resumen

        def _writer(tmp_path):
            with pd.ExcelWriter(tmp_path, engine='openpyxl', mode='w') as writer:
                for nombre_hoja, df_hoja in hojas.items():
                    df_hoja.to_excel(writer, index=False, sheet_name=nombre_hoja)

        utils.atomic_excel_write(ruta_excel, _writer)
        utils.print_success(f"Hoja 'Resumen Boletas' sobrescrita correctamente en {ruta_excel}")
    except (OSError, IOError, PermissionError) as e:
        utils.print_error(f"Error guardando Excel: {e}")
        return

    utils.print_step(4, 4, "Proceso completado")
    utils.print_success("Informe final de boletas generado correctamente.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Informe final de boletas (hoja Resumen)")
    parser.add_argument(
        "--sheet",
        type=str,
        default=None,
        help="Hoja de origen en Solicitud.xlsx (por defecto Solicitud).",
    )
    utils.register_non_interactive_cli(parser)
    utils.register_period_args(parser)
    args = parser.parse_args()
    main(args)
