import os
import re
import pandas as pd
import logging
from datetime import datetime
from rich.progress import Progress, BarColumn, TimeElapsedColumn, TextColumn
import utils

# Configuración básica
import config
RAIZ = config.RAIZ
ZONA_HORARIA = config.ZONA_HORARIA
MESES_ES = config.MESES_ES
PREFIJO = config.PREFIJO

console = utils.console


def obtener_institucion(location):
    """Mapea LOCATION a IP o CFT."""
    loc = str(location).strip()
    if loc == "508":
        return "IP"
    elif loc == "114":
        return "CFT"
    else:
        return None


def normalizar_nombre_carpeta(nombre):
    """Normaliza el nombre para usarlo como nombre de carpeta."""
    if not nombre:
        return "SinNombre"
    # Quitar caracteres especiales, mantener espacios y guiones
    nombre = str(nombre).strip()
    nombre = re.sub(r'[<>:"/\\|?*]', '', nombre)
    nombre = re.sub(r'\s+', ' ', nombre)
    return nombre[:100]  # limitar longitud


def procesar_docentes(df, ruta_mes):
    """
    Procesa cada fila del Excel y crea carpetas por docente.
    Devuelve número de docentes procesados y lista de carpetas creadas.
    """
    docentes_procesados = 0
    docentes_info = []
    
    total = len(df)
    
    with Progress(
        TextColumn("[bold blue]Procesando docente[/bold blue] {task.fields[docente]}"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("proc_docentes", total=total, docente="")
        
        for idx, fila in df.iterrows():
            try:
                # Leer campos
                emplid = str(fila.get('EMPLID', '')).strip()
                name = str(fila.get('NAME', '')).strip()
                rut_sin_dv = str(fila.get('RUT_SIN_DV', '')).strip()
                location = str(fila.get('LOCATION', '')).strip()
                
                if not emplid or not name or not rut_sin_dv:
                    logging.warning(f"Fila {idx+1}: campos vacíos (EMPLID={emplid}, NAME={name}, RUT={rut_sin_dv})")
                    progress.update(task, docente=f"Fila {idx+1}: incompleta")
                    progress.advance(task)
                    continue
                
                # Determinar institución
                institucion = obtener_institucion(location)
                if not institucion:
                    logging.warning(f"Fila {idx+1}: LOCATION inválida ({location})")
                    progress.update(task, docente=f"{emplid}: LOCATION inválida")
                    progress.advance(task)
                    continue
                
                # Crear nombre de carpeta docente (usar guion bajo entre EMPLID y nombre)
                emplid_name = f"{emplid}_{normalizar_nombre_carpeta(name)}"
                carpeta_docente = os.path.join(ruta_mes, institucion, emplid_name)
                
                # Crear carpeta del docente si no existe
                os.makedirs(carpeta_docente, exist_ok=True)
                
                # Mostrar en consola
                progress.update(task, docente=f"{emplid_name}")
                utils.print_info(f"Docente: {emplid_name} ({institucion})")
                logging.info(f"Carpeta creada/verificada: {carpeta_docente}")
                
                docentes_info.append((idx+1, emplid, name, rut_sin_dv, institucion, emplid_name))
                docentes_procesados += 1
                
            except Exception as e:
                logging.error(f"Error procesando fila {idx+1}: {e}")
                utils.print_error(f"Fila {idx+1}: {e}")
            
            progress.advance(task)
    
    utils.print_success(
        f"Proceso finalizado\n"
        f"Docentes procesados: {docentes_procesados}"
    )
    
    return docentes_procesados, docentes_info


def main():
    utils.print_header("📁 Agrupa docentes por Institución (IP/CFT)", "Creación de estructura de carpetas")
    
    # Selección año/mes
    try:
        año, mes = utils.seleccionar_año_mes(RAIZ)
    except ValueError as e:
        utils.print_error(str(e))
        return
    ruta_mes = os.path.join(RAIZ, año, mes)
    
    # Buscar Solicitud.xlsx
    ruta_excel = os.path.join(ruta_mes, "Solicitud.xlsx")
    if not os.path.isfile(ruta_excel):
        utils.print_error(f"No se encontró archivo Solicitud.xlsx en {ruta_mes}")
        return
    
    # Cargar Excel (preferir hoja 'Resumen de Boletas' si existe)
    try:
        xls = pd.ExcelFile(ruta_excel, engine='openpyxl')
        hojas = xls.sheet_names
    except (OSError, ValueError, KeyError) as e:
        utils.print_error(f"Error leyendo Excel: {e}")
        return

    if 'Resumen de Boletas' in hojas:
        hoja = 'Resumen de Boletas'
        utils.print_info("Usando hoja 'Resumen de Boletas' (aprobadas para pago)")
    else:
        hoja = utils.seleccionar_opcion(hojas, "Seleccione la hoja del Excel:", "📄")

    try:
        df = pd.read_excel(ruta_excel, sheet_name=hoja, engine='openpyxl')
    except (OSError, ValueError, KeyError) as e:
        utils.print_error(f"Error leyendo hoja '{hoja}': {e}")
        return

    # Normalizar nombres de columnas y crear columnas canónicas
    df = df.copy()
    # Columnas de entrada posibles
    col_rut_candidates = ['RUT', 'RUT_SIN_DV', 'Rut', 'rut']
    col_name_candidates = ['Nombre Docente', 'NAME', 'Name', 'NOMBRE', 'Nombre']
    col_loc_candidates = ['LOCATION', 'Location', 'location']

    # Seleccionar columna existente
    col_rut = next((c for c in col_rut_candidates if c in df.columns), None)
    col_name = next((c for c in col_name_candidates if c in df.columns), None)
    col_loc = next((c for c in col_loc_candidates if c in df.columns), None)

    if col_rut is None or col_name is None or col_loc is None:
        utils.print_error(f"No se encontraron columnas necesarias. Buscando columnas: RUT, Nombre Docente, LOCATION. Columnas encontradas: {list(df.columns)}")
        return

    # Crear columnas canónicas para procesar
    df['RUT_CAN'] = df[col_rut].astype(str).str.replace(r'[^0-9]', '', regex=True).str.strip()
    df['NAME_CAN'] = df[col_name].astype(str).str.strip()
    df['LOCATION_CAN'] = df[col_loc].astype(str).str.strip()

    # Detectar y guardar duplicados (por RUT_CAN + NAME_CAN + LOCATION_CAN)
    df['_dup_key'] = df['RUT_CAN'].fillna('') + '||' + df['NAME_CAN'].fillna('') + '||' + df['LOCATION_CAN'].fillna('')
    duplicated_mask = df.duplicated(subset=['_dup_key'], keep='first')
    df_duplicates = df[duplicated_mask]
    df_clean = df[~duplicated_mask].copy()

    # Configurar logging
    carpeta_logs = os.path.join(ruta_mes, 'logs_agrupa')
    os.makedirs(carpeta_logs, exist_ok=True)
    log_file = os.path.join(carpeta_logs, f"agrupa_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    utils.configurar_logging(log_file)

    logging.info(f"Iniciando agrupación de docentes para {año}/{mes}, hoja: {hoja}")

    # Guardar CSV de duplicados si existen
    if not df_duplicates.empty:
        dup_csv = os.path.join(carpeta_logs, f'duplicados_agrupa_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        try:
            df_duplicates.to_csv(dup_csv, index=False, encoding='utf-8')
            utils.print_warning(f"Se detectaron duplicados. Archivo con duplicados: {dup_csv}")
            logging.info(f"Duplicados guardados en: {dup_csv}")
        except OSError as e:
            logging.error(f"Error guardando CSV de duplicados: {e}")
    
    # Preparar DataFrame para `procesar_docentes`: mapear a columnas esperadas
    df_proc = df_clean.copy()
    # Crear columnas que espera procesar_docentes: EMPLID, NAME, RUT_SIN_DV, LOCATION
    if 'EMPLID' not in df_proc.columns:
        # Usamos RUT_CAN como identificador cuando no hay EMPLID
        df_proc['EMPLID'] = df_proc['RUT_CAN']
    if 'NAME' not in df_proc.columns:
        df_proc['NAME'] = df_proc['NAME_CAN']
    if 'RUT_SIN_DV' not in df_proc.columns:
        df_proc['RUT_SIN_DV'] = df_proc['RUT_CAN']
    if 'LOCATION' not in df_proc.columns:
        df_proc['LOCATION'] = df_proc['LOCATION_CAN']

    # Procesar docentes y crear carpetas (con DataFrame limpio)
    docentes, docentes_info = procesar_docentes(df_proc, ruta_mes)
    
    # Guardar resumen en CSV
    if docentes_info:
        resumen_csv = os.path.join(carpeta_logs, f'resumen_agrupa_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        try:
            import csv
            with open(resumen_csv, 'w', newline='', encoding='utf-8') as fh:
                w = csv.writer(fh)
                w.writerow(['Fila', 'EMPLID', 'Nombre', 'RUT_SIN_DV', 'Institucion', 'Carpeta_Creada'])
                for info in docentes_info:
                    w.writerow(info)
            utils.print_success(f"Resumen guardado en: {resumen_csv}")
            logging.info(f"Resumen guardado en: {resumen_csv}")
        except OSError as e:
            logging.error(f"Error guardando resumen CSV: {e}")
    
    utils.print_info(f"Log guardado en: {log_file}")
    logging.info("Proceso completado.")


if __name__ == '__main__':
    main()
