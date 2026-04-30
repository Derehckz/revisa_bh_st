import os
import pandas as pd
import argparse
import logging
from datetime import datetime
from typing import Tuple, List

import config
import utils


# ============================================================================
# MAPPING DE INSTITUCIONES (ESTÁTICO)
# ============================================================================

MAPPING_INSTITUCIONES = {
    114: {
        "RUT RAZON": "65175242-6",
        "NOMBRE RAZON": "Corporación Centro de Formación Técnica Santo Tomás",
        "DireccionRazon": "Andres Bello #2711, Las condes, RM",
        "LOCATION.1": 114,
        "GLOSA_BASE": "CFTST Convenio los Lagos Código FDI CST2588-{MES}"
    },
    508: {
        "RUT RAZON": "65175239-6",
        "NOMBRE RAZON": "Corporación Instituto Profesional Santo Tomás",
        "DireccionRazon": "Andres Bello #2711, Las condes, RM",
        "LOCATION.1": 508,
        "GLOSA_BASE": "IPST Convenio los lagos Código FDI IST2588-{MES}"
    }
    # Agregar más LOCATIONs según necesites
}

def limpiar_emplid(emplid):
    """
    Limpia EMPLID: Quita el 0 antepuesto
    Ejemplo: 06717063-6 → 6717063-6
    """
    if pd.isna(emplid):
        return ""
    
    emplid = str(emplid).strip()
    
    # Si comienza con 0 y tiene DV (formato RUT con guión)
    if emplid.startswith("0") and "-" in emplid:
        emplid = emplid[1:]  # Quitar primer 0
    
    return emplid


def normalizar_rut(rut):
    """Normaliza RUT a formato consistente"""
    if pd.isna(rut):
        return ""
    return str(rut).strip()


def completar_datos_institucion(df_abril: pd.DataFrame, mes: str) -> pd.DataFrame:
    """
    Completa las columnas de institución basadas en LOCATION
    """
    utils.print_info("Agregando datos de instituciones...")
    
    # Crear nuevas columnas
    df_abril["RUT RAZON"] = ""
    df_abril["NOMBRE RAZON"] = ""
    df_abril["DireccionRazon"] = ""
    df_abril["LOCATION.1"] = df_abril["LOCATION"]
    df_abril["GLOSA"] = ""
    
    # Completar por cada fila
    for idx, row in df_abril.iterrows():
        location = row["LOCATION"]
        
        if location in MAPPING_INSTITUCIONES:
            institucion = MAPPING_INSTITUCIONES[location]
            df_abril.at[idx, "RUT RAZON"] = institucion["RUT RAZON"]
            df_abril.at[idx, "NOMBRE RAZON"] = institucion["NOMBRE RAZON"]
            df_abril.at[idx, "DireccionRazon"] = institucion["DireccionRazon"]
            df_abril.at[idx, "LOCATION.1"] = institucion["LOCATION.1"]
            df_abril.at[idx, "GLOSA"] = institucion["GLOSA_BASE"].format(MES=mes.upper())
        else:
            utils.print_warning(f"LOCATION {location} no encontrado en mapping")
    
    utils.print_success("Datos de instituciones completados")
    return df_abril

def cargar_archivo(ruta: str, nombre: str) -> pd.DataFrame:
    """
    Carga archivo Excel con manejo de errores
    """
    try:
        with utils.console.status(f"Cargando [bold]{nombre}[/bold]...", spinner="dots"):
            df = pd.read_excel(ruta, engine='openpyxl')
        utils.print_success(f"{nombre} cargado ({len(df)} filas)")
        return df
    except FileNotFoundError:
        utils.print_error(f"No se encontró: {ruta}")
        raise
    except Exception as e:
        utils.print_error(f"Error cargando {nombre}: {e}")
        raise


def validar_columnas(df: pd.DataFrame, columnas_requeridas: List[str], nombre_archivo: str) -> bool:
    """
    Valida que existan las columnas requeridas
    """
    faltantes = [col for col in columnas_requeridas if col not in df.columns]
    
    if faltantes:
        utils.print_warning(f"{nombre_archivo} falta columnas:")
        for col in faltantes:
            utils.console.print(f"   • {col}")
        return False
    
    return True


def listar_archivos_xlsx(ruta: str) -> List[str]:
    return [f for f in os.listdir(ruta)
            if os.path.isfile(os.path.join(ruta, f))
            and f.lower().endswith('.xlsx')]


def seleccionar_archivo_excel_en_carpeta(ruta: str, mensaje: str) -> str:
    archivos = listar_archivos_xlsx(ruta)
    if not archivos:
        raise FileNotFoundError(f"No se encontró ningún archivo .xlsx en {ruta}")
    if len(archivos) == 1:
        utils.print_info(f"Archivo encontrado: [bold]{archivos[0]}[/bold]")
        return archivos[0]
    return utils.seleccionar_opcion(sorted(archivos), mensaje, "📄")


def obtener_ruta_maestro(args) -> str:
    if args.ruta_maestro:
        return args.ruta_maestro

    if args.mes and args.año:
        ruta_mes = os.path.join(config.RAIZ, str(args.año), args.mes)
        if not os.path.isdir(ruta_mes):
            utils.print_warning(f"La carpeta {ruta_mes} no existe. Se solicitará año/mes interactivo.")
            args.mes = None
            args.año = None
        else:
            utils.print_info(f"Procesando carpeta: [bold]{ruta_mes}[/bold]")
    
    if not args.mes or not args.año:
        año_seleccionado, mes_seleccionado = utils.seleccionar_año_mes(config.RAIZ)
        args.año = int(año_seleccionado)
        args.mes = mes_seleccionado
        ruta_mes = os.path.join(config.RAIZ, año_seleccionado, mes_seleccionado)

    if args.archivo_maestro:
        ruta_maestro = os.path.join(ruta_mes, args.archivo_maestro)
        if os.path.exists(ruta_maestro):
            utils.print_info(f"Archivo maestro directo: [bold]{ruta_maestro}[/bold]")
            return ruta_maestro
        utils.print_warning(f"No se encontró {ruta_maestro}. Se seleccionará interactivo entre los archivos existentes.")

    archivo_maestro = seleccionar_archivo_excel_en_carpeta(
        ruta_mes,
        "Seleccione el archivo maestro dentro de la carpeta del mes:"
    )
    ruta_maestro = os.path.join(ruta_mes, archivo_maestro)
    utils.print_success(f"Archivo maestro seleccionado: {ruta_maestro}")
    return ruta_maestro


def obtener_ruta_bd_docentes(args) -> str:
    if args.ruta_bd:
        return args.ruta_bd

    archivos_root = listar_archivos_xlsx(config.RAIZ)
    candidatos = [f for f in archivos_root if "bd" in f.lower() or "docentes" in f.lower()]
    if not candidatos:
        raise FileNotFoundError(f"No se encontró un archivo BD-DOCENTES.xlsx en {config.RAIZ}")
    if len(candidatos) == 1:
        ruta_bd = os.path.join(config.RAIZ, candidatos[0])
        utils.print_info(f"BD seleccionada: [bold]{ruta_bd}[/bold]")
        return ruta_bd

    archivo_bd = utils.seleccionar_opcion(
        sorted(candidatos),
        "Seleccione el archivo BD-DOCENTES:",
        "📄"
    )
    ruta_bd = os.path.join(config.RAIZ, archivo_bd)
    utils.print_success(f"BD-DOCENTES seleccionado: {ruta_bd}")
    return ruta_bd


def validar_preservacion_datos_maestro(
    df_original: pd.DataFrame,
    df_resultado: pd.DataFrame,
    columnas: List[str]
) -> List[str]:
    """Valida que los valores de las columnas originales del maestro se preserven fila a fila."""
    errores = []
    for col in columnas:
        if col not in df_resultado.columns:
            errores.append(f"Columna {col} no encontrada en resultado")
            continue

        original = df_original[col].fillna("").astype(str).reset_index(drop=True)
        resultado = df_resultado[col].fillna("").astype(str).reset_index(drop=True)

        if not original.equals(resultado):
            diferencias = (original != resultado)
            indices = [str(i + 1) for i, diff in enumerate(diferencias) if diff][:5]
            errores.append(
                f"Diferencias en columna {col} en filas {', '.join(indices)}"
            )
    return errores


def validar_mapping_institucion(df: pd.DataFrame) -> List[str]:
    """Valida que todas las filas tengan mapping de institución completo."""
    errores = []
    filas_faltantes = df[
        df["RUT RAZON"].isna() | (df["RUT RAZON"] == "") |
        df["NOMBRE RAZON"].isna() | (df["NOMBRE RAZON"] == "") |
        df["GLOSA"].isna() | (df["GLOSA"] == "")
    ]

    if len(filas_faltantes) > 0:
        errores.append(
            f"{len(filas_faltantes)} filas sin mapping de institución completo"
        )
        for idx, row in filas_faltantes.head(5).iterrows():
            errores.append(
                f"Fila {idx + 1}: LOCATION={row['LOCATION']} sin información de institución"
            )
    return errores


def generar_solicitud(
    ruta_maestro: str,
    ruta_bd_docentes: str,
    ruta_salida: str = None,
    mes: str = "Abril",
    año: int = 2026
) -> Tuple[pd.DataFrame, dict]:
    """
    Genera Solicitud.xlsx combinando el archivo maestro + BD-DOCENTES.xlsx

    Parámetros:
        ruta_maestro: Path al archivo maestro
        ruta_bd_docentes: Path a BD-DOCENTES.xlsx
        ruta_salida: Dónde guardar Solicitud.xlsx (opcional)
        mes: Nombre mes (Abril, Mayo, etc.)
        año: Año (2026)
    
    Retorna:
        (DataFrame de resultado, dict con estadísticas)
    """
    
    stats = {
        "filas_abril": 0,
        "filas_bd": 0,
        "filas_resultado": 0,
        "docentes_encontrados": 0,
        "docentes_no_encontrados": 0,
        "nuevos_en_bd": 0,
        "errores": []
    }
    
    utils.print_header("PASO 0: Generador de Solicitud", "Combina el archivo maestro de boletas + BD-DOCENTES → Solicitud.xlsx")

    utils.print_step(1, 8, "Cargando archivos")
    try:
        df_abril = cargar_archivo(ruta_maestro, "archivo maestro")
        df_bd = cargar_archivo(ruta_bd_docentes, "BD-DOCENTES.xlsx")
    except Exception as e:
        stats["errores"].append(str(e))
        utils.print_error(f"Error fatal: {e}")
        return None, stats
    
    stats["filas_abril"] = len(df_abril)
    stats["filas_bd"] = len(df_bd)
    
    utils.print_step(2, 8, "Validando columnas")
    
    columnas_abril_requeridas = [
        "EMPLID", "NAME", "LOCATION", "EMPL_RCD", "HR_STATUS",
        "DESCR", "MONTH", "YEAR",
        "CUS_INCIDENCIA", "CUS_MTO_CTA", "CUS_MTO_BONO", "CUS_MTO_DAPTO", "CUS_TOT_HON"
    ]
    
    columnas_bd_requeridas = [
        "RUT", "NOMBRE_COMPLETO", "Correo_Personal", "Email_DP", "SEDE"
    ]
    
    if not validar_columnas(df_abril, columnas_abril_requeridas, "archivo maestro"):
        stats["errores"].append("Columnas faltantes en el archivo maestro")
        return None, stats
    
    if not validar_columnas(df_bd, columnas_bd_requeridas, "BD-DOCENTES.xlsx"):
        stats["errores"].append("Columnas faltantes en BD-DOCENTES.xlsx")
        return None, stats
    
    utils.print_success("Todas las columnas validadas")
    
    utils.print_step(3, 8, "Limpiando EMPLIDs y RUTs")
    utils.print_info("Eliminando ceros antepuestos en EMPLIDs...")
    df_abril["EMPLID"] = df_abril["EMPLID"].apply(limpiar_emplid)
    utils.print_success("EMPLIDs normalizados")
    
    utils.print_info("Normalizando RUTs en BD...")
    df_bd["RUT"] = df_bd["RUT"].apply(normalizar_rut)
    utils.print_success("RUTs normalizados")
    
    utils.print_info("Eliminando duplicados en BD-DOCENTES...")
    filas_antes = len(df_bd)
    df_bd = df_bd.drop_duplicates(subset=["RUT"], keep="first")
    filas_despues = len(df_bd)
    eliminados = filas_antes - filas_despues
    if eliminados > 0:
        utils.print_warning(f"{eliminados} duplicados eliminados")
    else:
        utils.print_success("No se encontraron duplicados en BD-DOCENTES")
    
    utils.print_step(4, 8, "Completando datos de instituciones")
    df_abril = completar_datos_institucion(df_abril, mes)

    errores_mapping = validar_mapping_institucion(df_abril)
    if errores_mapping:
        utils.print_error("Hay filas sin mapping de institución completo.")
        utils.print_list("Detalles:", errores_mapping)
        stats["errores"].extend(errores_mapping)
        return None, stats

    utils.print_step(5, 8, "Realizando merge (EMPLID = RUT)")
    df_resultado = df_abril.merge(
        df_bd[["RUT", "Correo_Personal", "Email_DP", "SEDE"]],
        left_on="EMPLID",
        right_on="RUT",
        how="left",
        indicator="merge_status"
    )

    if len(df_resultado) != len(df_abril):
        stats["errores"].append(
            f"Número de filas incorrecto después del merge: maestro={len(df_abril)}, Resultado={len(df_resultado)}"
        )
        utils.print_error("ERROR CRÍTICO: Número de filas no coincide después del merge")
        utils.print_list("Detalles:", [
            f"Maestro: {len(df_abril)} filas",
            f"Resultado: {len(df_resultado)} filas"
        ])
        return None, stats

    no_encontrados = df_resultado[df_resultado["merge_status"] == "left_only"].copy()
    docentes_unicos_abril = df_resultado["EMPLID"].nunique()
    docentes_encontrados = df_resultado[df_resultado["merge_status"] == "both"]["EMPLID"].nunique()
    docentes_no_encontrados = docentes_unicos_abril - docentes_encontrados

    stats["docentes_encontrados"] = docentes_encontrados
    stats["docentes_no_encontrados"] = docentes_no_encontrados

    if len(no_encontrados) > 0:
        utils.print_warning(f"{len(no_encontrados)} filas con docentes NO encontrados en BD")
        utils.print_info("Se solicitarán datos por terminal para completarlos.")

        nuevas_filas = []
        for rut_docente in no_encontrados["EMPLID"].unique():
            fila_ejemplo = no_encontrados[no_encontrados["EMPLID"] == rut_docente].iloc[0]
            nombre = fila_ejemplo["NAME"]

            utils.print_header("DATOS PARA NUEVO DOCENTE", f"RUT: {rut_docente} - Nombre: {nombre}")
            correo_personal = utils.prompt_required("📧 Correo personal")
            sede = utils.prompt_required("🏫 SEDE")
            email_dp = utils.prompt_required("📧 Email coordinador (DP)")
            telefono = utils.prompt_optional("📞 Teléfono [Enter para vacío]")
            direccion = utils.prompt_optional("📍 Dirección [Enter para vacío]")

            nueva_fila = {
                "RUT": rut_docente,
                "RUT_SIN_DV": rut_docente.split("-")[0] if "-" in rut_docente else rut_docente,
                "NOMBRE_COMPLETO": nombre,
                "Correo_Personal": correo_personal,
                "Telefono_Personal": telefono,
                "Direccion": direccion,
                "SEDE": sede,
                "Email_DP": email_dp,
                "PS": "",
                "BANNER": "",
                "TI": "",
                "ST": "",
                "OBSERVACIONES": f"[AUTO] Agregado {datetime.now().strftime('%Y-%m-%d')}"
            }
            nuevas_filas.append(nueva_fila)
            utils.print_success("Docente agregado a BD")

        df_bd_nuevas = pd.DataFrame(nuevas_filas)
        df_bd = pd.concat([df_bd, df_bd_nuevas], ignore_index=True)
        stats["nuevos_en_bd"] = len(nuevas_filas)

        mapping_docentes = df_bd.set_index("RUT")[["Correo_Personal", "Email_DP", "SEDE"]].to_dict("index")
        for idx, row in df_resultado.iterrows():
            if row["merge_status"] == "left_only":
                rut_docente = row["EMPLID"]
                if rut_docente in mapping_docentes:
                    df_resultado.at[idx, "Correo_Personal"] = mapping_docentes[rut_docente]["Correo_Personal"]
                    df_resultado.at[idx, "Email_DP"] = mapping_docentes[rut_docente]["Email_DP"]
                    df_resultado.at[idx, "SEDE"] = mapping_docentes[rut_docente]["SEDE"]
                    df_resultado.at[idx, "RUT"] = rut_docente
                    df_resultado.at[idx, "merge_status"] = "both"

        utils.print_success("BD-DOCENTES actualizada con datos completos")
    else:
        utils.print_success("Todos los docentes encontrados en BD")

    utils.print_step(6, 8, "Validando preservación de los datos del maestro")
    errores_preservacion = validar_preservacion_datos_maestro(
        df_abril,
        df_resultado,
        columnas_abril_requeridas
    )
    if errores_preservacion:
        utils.print_error("Se encontraron diferencias entre el maestro y el resultado.")
        utils.print_list("Diferencias detectadas:", errores_preservacion)
        stats["errores"].extend(errores_preservacion)
        return None, stats

    utils.print_step(7, 8, "Preparando columnas finales")

    df_resultado["Correo Enviado"] = ""
    df_resultado["Estado_Recepcion"] = ""
    df_resultado["RUT_SIN_DV"] = df_resultado["EMPLID"].apply(
        lambda x: x.split("-")[0] if "-" in str(x) else str(x)
    )

    df_resultado = df_resultado.rename(columns={
        "Correo_Personal": "Email_Docente"
    })

    columnas_finales = [
        "EMPLID", "RUT_SIN_DV", "NAME", "EMPL_RCD", "HR_STATUS", "LOCATION",
        "RUT RAZON", "NOMBRE RAZON", "DireccionRazon",
        "LOCATION.1", "GLOSA", "DESCR", "MONTH", "YEAR",
        "CUS_INCIDENCIA", "CUS_MTO_CTA", "CUS_MTO_BONO",
        "CUS_MTO_DAPTO", "CUS_TOT_HON",
        "Email_Docente", "SEDE", "Email_DP",
        "Correo Enviado", "Estado_Recepcion"
    ]

    columnas_faltantes = [col for col in columnas_finales if col not in df_resultado.columns]
    if columnas_faltantes:
        utils.print_warning("Columnas no encontradas en resultado:")
        utils.print_list("Columnas faltantes:", columnas_faltantes)
        columnas_finales = [col for col in columnas_finales if col in df_resultado.columns]
        utils.print_info(f"Usando {len(columnas_finales)} columnas disponibles")

    df_resultado = df_resultado[columnas_finales]
    stats["filas_resultado"] = len(df_resultado)

    utils.print_success(f"{len(columnas_finales)} columnas preparadas")

    utils.print_step(8, 8, "Guardando archivos")

    try:
        if ruta_salida is None:
            ruta_salida = os.path.join(os.path.dirname(ruta_maestro), "Solicitud.xlsx")

        with utils.console.status("Guardando Solicitud.xlsx...", spinner="dots"):
            df_resultado.to_excel(ruta_salida, index=False, engine='openpyxl')
        utils.print_success(f"Solicitud.xlsx guardado en {ruta_salida}")

        with utils.console.status("Guardando BD-DOCENTES.xlsx...", spinner="dots"):
            df_bd.to_excel(ruta_bd_docentes, index=False, engine='openpyxl')
        utils.print_success(f"BD-DOCENTES.xlsx guardado en {ruta_bd_docentes}")

    except Exception as e:
        stats["errores"].append(f"Error al guardar: {e}")
        utils.print_error(f"Error al guardar: {e}")
        return df_resultado, stats

    utils.print_header("GENERACIÓN COMPLETADA", "Solicitud.xlsx y BD-DOCENTES.xlsx han sido actualizados")
    utils.print_table("ESTADÍSTICAS", [
        ("Filas en maestro", stats['filas_abril']),
        ("Docentes en BD", stats['filas_bd']),
        ("Docentes encontrados", stats['docentes_encontrados']),
        ("Docentes NO encontrados", stats['docentes_no_encontrados']),
        ("Nuevos agregados a BD", stats['nuevos_en_bd']),
        ("Filas en Solicitud.xlsx", stats['filas_resultado']),
    ])
    utils.print_list("ARCHIVOS GENERADOS:", [ruta_salida, ruta_bd_docentes])

    return df_resultado, stats


# ============================================================================
# MAIN - CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="PASO 0: Generador de Solicitud de Boletas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Modo 1: Especificar mes y año (busca en carpeta de config)
  python "0.-generar_solicitud.py" --mes Abril --año 2026
  
  # Modo 2: Especificar rutas exactas
  python "0.-generar_solicitud.py" \\
    --ruta-maestro "e:\\Boletas Honorarios\\2026\\Abril\\MAESTRO_BH.xlsx" \\
    --ruta-bd "e:\\Boletas Honorarios\\BD-DOCENTES.xlsx" \\
    --ruta-salida "e:\\Boletas Honorarios\\2026\\Abril\\Solicitud.xlsx"
        """
    )
    
    parser.add_argument(
        "--mes",
        type=str,
        default=None,
        help="Mes a procesar (por defecto se selecciona interactivo)"
    )
    parser.add_argument(
        "--año",
        type=int,
        default=None,
        help="Año a procesar (por defecto se selecciona interactivo)"
    )
    parser.add_argument(
        "--ruta-abril",
        "--ruta-maestro",
        dest="ruta_maestro",
        type=str,
        help="Ruta completa al archivo maestro (sobreescribe --mes --año y --archivo-maestro)"
    )
    parser.add_argument(
        "--archivo-maestro",
        type=str,
        help="Nombre del archivo maestro dentro de la carpeta del mes (por ejemplo: MAESTRO_BH.xlsx)."
    )
    parser.add_argument(
        "--ruta-bd",
        type=str,
        help="Ruta a BD-DOCENTES.xlsx"
    )
    parser.add_argument(
        "--ruta-salida",
        type=str,
        help="Ruta donde guardar Solicitud.xlsx (opcional)"
    )
    
    args = parser.parse_args()
    
    # Determinar rutas de entrada
    try:
        ruta_maestro = obtener_ruta_maestro(args)
    except Exception as e:
        utils.print_error(str(e))
        return 1

    try:
        ruta_bd = obtener_ruta_bd_docentes(args)
    except Exception as e:
        utils.print_error(str(e))
        return 1

    ruta_salida = args.ruta_salida
    
    # Validar rutas
    if not os.path.exists(ruta_maestro):
        utils.print_error(f"No se encontró: {ruta_maestro}")
        return 1
    
    if not os.path.exists(ruta_bd):
        utils.print_error(f"No se encontró: {ruta_bd}")
        return 1
    
    # Ejecutar
    try:
        df_resultado, stats = generar_solicitud(
            ruta_maestro=ruta_maestro,
            ruta_bd_docentes=ruta_bd,
            ruta_salida=ruta_salida,
            mes=args.mes,
            año=args.año
        )
        
        if stats["errores"]:
            utils.print_warning("Errores durante el proceso:")
            utils.print_list("Detalle de errores:", stats["errores"])
            return 1
        
        utils.print_success("Proceso completado sin errores.")
        return 0
        
    except Exception as e:
        utils.print_error(f"Error fatal: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
