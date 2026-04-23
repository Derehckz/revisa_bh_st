import os
import re
import pandas as pd
import logging
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TimeElapsedColumn, TextColumn
from colorama import init as colorama_init, Fore
import utils

# Inicialización
colorama_init(autoreset=True)
console = Console()

# Configuración básica
import config
RAIZ = config.RAIZ
ZONA_HORARIA = config.ZONA_HORARIA
MESES_ES = config.MESES_ES
PREFIJO = config.PREFIJO


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
                console.print(f"[cyan]Docente:[/] {emplid_name} ({institucion})")
                logging.info(f"Carpeta creada/verificada: {carpeta_docente}")
                
                docentes_info.append((idx+1, emplid, name, rut_sin_dv, institucion, emplid_name))
                docentes_procesados += 1
                
            except Exception as e:
                logging.error(f"Error procesando fila {idx+1}: {e}")
                console.print(Fore.RED + f"[ERROR] Fila {idx+1}: {e}")
            
            progress.advance(task)
    
    console.print(Panel.fit(
        f"✅ Proceso finalizado\n"
        f"Docentes procesados: {docentes_procesados}",
        style="bold green"
    ))
    
    return docentes_procesados, docentes_info


def main():
    console.print(Panel.fit("[bold cyan]📁 Agrupa docentes por Institución (IP/CFT)[/bold cyan]", style="bold green"))
    
    # Selección año/mes
    años = utils.listar_carpetas(RAIZ)
    if not años:
        console.print(Panel.fit("[red]⚠️ No hay carpetas de año en la ruta configurada.[/red]", style="bold red"))
        return
    
    año = utils.seleccionar_opcion(sorted(años), "Seleccione el año:", "🗓️")
    ruta_año = os.path.join(RAIZ, año)
    
    meses = utils.listar_carpetas(ruta_año)
    if not meses:
        console.print(Panel.fit(f"[red]⚠️ No hay carpetas de mes en {ruta_año}[/red]", style="bold red"))
        return
    
    mes = utils.seleccionar_opcion(sorted(meses), "Seleccione el mes:", "🗓️")
    ruta_mes = os.path.join(ruta_año, mes)
    
    # Buscar Solicitud.xlsx
    ruta_excel = os.path.join(ruta_mes, "Solicitud.xlsx")
    if not os.path.isfile(ruta_excel):
        console.print(Panel.fit(f"[red]❌ No se encontró archivo Solicitud.xlsx en {ruta_mes}[/red]", style="bold red"))
        return
    
    # Cargar Excel (preferir hoja 'Resumen de Boletas' si existe)
    try:
        xls = pd.ExcelFile(ruta_excel, engine='openpyxl')
        hojas = xls.sheet_names
    except (OSError, ValueError, KeyError) as e:
        console.print(Panel.fit(f"[red]❌ Error leyendo Excel: {e}[/red]", style="bold red"))
        return

    if 'Resumen de Boletas' in hojas:
        hoja = 'Resumen de Boletas'
        console.print(Panel.fit("Usando hoja 'Resumen de Boletas' (aprobadas para pago)", style="cyan"))
    else:
        hoja = utils.seleccionar_opcion(hojas, "Seleccione la hoja del Excel:", "📄")

    try:
        df = pd.read_excel(ruta_excel, sheet_name=hoja, engine='openpyxl')
    except (OSError, ValueError, KeyError) as e:
        console.print(Panel.fit(f"[red]❌ Error leyendo hoja '{hoja}': {e}[/red]", style="bold red"))
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
        console.print(Panel.fit(f"[red]❌ No se encontraron columnas necesarias. Buscando columnas: RUT, Nombre Docente, LOCATION. Columnas encontradas: {list(df.columns)}[/red]", style="bold red"))
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
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    logging.info(f"Iniciando agrupación de docentes para {año}/{mes}, hoja: {hoja}")

    # Guardar CSV de duplicados si existen
    if not df_duplicates.empty:
        dup_csv = os.path.join(carpeta_logs, f'duplicados_agrupa_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        try:
            df_duplicates.to_csv(dup_csv, index=False, encoding='utf-8')
            console.print(Panel.fit(f"📄 Se detectaron duplicados. Archivo con duplicados: {dup_csv}", style="yellow"))
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
            console.print(Panel.fit(f"📄 Resumen guardado en: {resumen_csv}", style="bold green"))
            logging.info(f"Resumen guardado en: {resumen_csv}")
        except OSError as e:
            logging.error(f"Error guardando resumen CSV: {e}")
    
    console.print(Panel.fit(f"📌 Log guardado en: {log_file}", style="bold blue"))
    logging.info("Proceso completado.")


if __name__ == '__main__':
    main()
