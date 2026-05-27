#!/usr/bin/env python3
import _sys_path  # noqa: E402
import os
import argparse
import pandas as pd
import config
import utils
import schema_validator

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

    canonical_errors, canonical_warnings = schema_validator.validate_for_stage(
        df_hoja, "stage6_informe_final"
    )
    for w in canonical_warnings:
        utils.print_warning(f"[schema] {w}")
    for e in canonical_errors:
        utils.print_error(f"[schema] {e}")

    # Tolerante a tildes y casing: acepta "Datos extraídos OK" / "DATOS EXTRAIDOS OK"
    obs_norm = (
        df_hoja['Observaciones_XML']
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace('Á', 'A', regex=False)
        .str.replace('É', 'E', regex=False)
        .str.replace('Í', 'I', regex=False)
        .str.replace('Ó', 'O', regex=False)
        .str.replace('Ú', 'U', regex=False)
    )
    df_filtrado = df_hoja[obs_norm == "DATOS EXTRAIDOS OK"].copy()

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
