import os
import shutil
import re
import pandas as pd
import logging
import sys
import argparse
from datetime import datetime
import utils
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TimeElapsedColumn, TextColumn
from colorama import init as colorama_init, Fore

# Inicialización
colorama_init(autoreset=True)
console = Console()

# Configuración básica (ajustar en config.py si se desea)
import config
RAIZ = config.RAIZ
ZONA_HORARIA = config.ZONA_HORARIA
MESES_ES = config.MESES_ES


def seleccionar_opcion(lista, mensaje, icono=""):
    # Delegar a utils para mantener una única implementación compartida
    return utils.seleccionar_opcion(lista, mensaje, icono)


def encontrar_columna_categoria(df):
    """Busca una columna que contenga valores 'IP' o 'CFT' (insensible a mayúsculas).
    Si no encuentra, devuelve None."""
    # Preferir columnas explícitas si existen
    preferidas = ['NOMBRE RAZON', 'NOMBRE_RAZON', 'RUT RAZON', 'RUT_RAZON']
    for p in preferidas:
        if p in df.columns:
            return p

    # Si no existen, buscar cualquier columna que contenga directamente 'IP' o 'CFT'
    for col in df.columns:
        try:
            vals = df[col].astype(str).str.strip().str.upper()
            if vals.isin(["IP", "CFT"]).any():
                return col
        except Exception:
            continue
    return None


def clasificar_por_nombre(nombre):
    """Clasifica una cadena de nombre de razón social en 'IP' o 'CFT' o None."""
    if not isinstance(nombre, str):
        return None
    s = nombre.strip().upper()
    if 'INSTITUTO PROFESIONAL' in s or '\tINSTITUTO' in s or ' INSTITUTO' in s or ' IP ' in s or s.endswith(' IP') or s.startswith('IP '):
        return 'IP'
    if 'FORMACIÓN TÉCNICA' in s or 'FORMACION TECNICA' in s or 'CENTRO DE FORMACIÓN TÉCNICA' in s or 'CFT' in s:
        return 'CFT'
    # otras heurísticas
    if 'INSTITUTO' in s and 'PROFESIONAL' in s:
        return 'IP'
    if 'FORMACION' in s and 'TECNICA' in s:
        return 'CFT'
    return None


def hallar_fila_por_nombre(df, nombre_archivo):
    """Intenta encontrar la fila que referencia el archivo por coincidencia exacta
    o por columnas típicas como 'archivo_xml' o 'Archivo_XML_Usado'. Devuelve índice o None."""
    nombre_norm = nombre_archivo.strip()

    # Columnas preferidas
    candidatos = ['archivo_xml', 'Archivo_XML_Usado', 'Archivo PDF', 'archivo_pdf', 'Archivo']
    for c in candidatos:
        if c in df.columns:
            try:
                match = df.index[df[c].astype(str).str.strip().eq(nombre_norm)]
                if len(match) > 0:
                    return match[0]
            except Exception:
                pass

    # Búsqueda general en todo el DataFrame (string exact match)
    for col in df.columns:
        try:
            match = df.index[df[col].astype(str).str.strip().eq(nombre_norm)]
            if len(match) > 0:
                return match[0]
        except Exception:
            continue

    # Intentar coincidencia por base (sin extensión)
    base = os.path.splitext(nombre_norm)[0]
    for col in df.columns:
        try:
            vals = df[col].astype(str).str.strip().str.replace(r"\..*$", "", regex=True)
            match = df.index[vals.eq(base)]
            if len(match) > 0:
                return match[0]
        except Exception:
            continue

    return None


def procesar_carpeta_fuente(ruta_fuente, ruta_destino_mes, df, columna_categoria, mover=False, dry_run=False):
    """Procesa archivos .pdf y .xml en ruta_fuente y los guarda en subcarpetas por categoria (IP/CFT).
    Archivos sin coincidencia van a 'SinClasificar'."""
    os.makedirs(ruta_destino_mes, exist_ok=True)
    rutas = [f for f in os.listdir(ruta_fuente) if f.lower().startswith('bhe_') and f.lower().endswith(('.pdf', '.xml'))]

    if not rutas:
        console.print(Panel.fit("[yellow]⚠️ No se encontraron archivos 'bhe_' PDF/XML en la carpeta seleccionada.[/yellow]", style="yellow"))
        return 0

    total = len(rutas)
    procesados = 0

    with Progress(
        TextColumn("[bold blue]Procesando[/bold blue] {task.fields[file]}"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("sep", total=total, file="")
        for nombre in rutas:
            progress.update(task, file=nombre)
            idx = hallar_fila_por_nombre(df, nombre)
            categoria = None
            if idx is not None and columna_categoria is not None:
                try:
                    categoria = str(df.at[idx, columna_categoria]).strip()
                except Exception:
                    categoria = None

            if categoria:
                # Si la columna seleccionada es un nombre de razón social, clasificar por texto
                carpeta_cat = None
                try:
                    # Si la columna apunta al RUT, intentar usar 'NOMBRE RAZON' si existe
                    col_upper = (columna_categoria or '').upper()
                    if 'RUT' in col_upper and 'NOMBRE RAZON' in df.columns:
                        nombre_rs = str(df.at[idx, 'NOMBRE RAZON'])
                        carpeta_cat = clasificar_por_nombre(nombre_rs)
                    else:
                        carpeta_cat = clasificar_por_nombre(str(categoria))
                except Exception:
                    carpeta_cat = None

                if carpeta_cat is None:
                    upper = str(categoria).upper()
                    if 'IP' in upper:
                        carpeta_cat = 'IP'
                    elif 'CFT' in upper:
                        carpeta_cat = 'CFT'
                    else:
                        carpeta_cat = 'Otros'
            else:
                carpeta_cat = 'SinClasificar'

            carpeta_dest = os.path.join(ruta_destino_mes, carpeta_cat)
            os.makedirs(carpeta_dest, exist_ok=True)

            src = os.path.join(ruta_fuente, nombre)
            dst = os.path.join(carpeta_dest, nombre)

            if dry_run:
                logging.info(f"[DRY-RUN] {('Mover' if mover else 'Copiar')} {src} -> {dst}")
            else:
                try:
                    if mover:
                        shutil.move(src, dst)
                        logging.info(f"Movido: {src} -> {dst}")
                    else:
                        shutil.copy2(src, dst)
                        logging.info(f"Copiado: {src} -> {dst}")
                except Exception as e:
                    logging.error(f"Error al copiar/mover {src} -> {dst}: {e}")

            procesados += 1
            progress.advance(task)

    console.print(Panel.fit(f"✅ Proceso finalizado. Archivos procesados: {procesados}", style="bold green"))
    return procesados


def procesar_por_filas(df, ruta_fuente, ruta_destino_mes, col_rut_razon, col_rut_sin_dv, mover=False, dry_run=False, mapping=None, no_interactive=False):
    """Para cada fila del DataFrame: toma el RUT_SIN_DV, busca archivos cuyo nombre empiece por
    'bhe_{rut_sin_dv}-' y mueve/copia los .pdf y .xml correspondientes a la carpeta según RUT_RAZON (IP/CFT)."""
    archivos_procesados = 0
    movimientos = []
    # cache para decisiones manuales por RUT (evita preguntar varias veces)
    decision_por_rut = {}

    total = len(df)
    with Progress(
        TextColumn("[bold blue]Procesando fila[/bold blue] {task.fields[row]}"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("proc_rows", total=total, row="")
        for idx, fila in df.iterrows():
            progress.update(task, row=str(idx+1))
            try:
                rut_sin_dv = str(fila.get(col_rut_sin_dv, '')).strip()
                rut_razon = fila.get(col_rut_razon, '') if col_rut_razon in df.columns else ''
                if not rut_sin_dv:
                    logging.info(f"Fila {idx+1}: RUT_SIN_DV vacío, se omite")
                    progress.advance(task)
                    continue

                # Normalizar RUT: quitar todo lo que no sea dígito (por si trae guión y DV)
                rut_digits = utils.normalizar_rut_digits(rut_sin_dv)
                if not rut_digits:
                    logging.info(f"Fila {idx+1}: RUT_SIN_DV vacío o no numérico ('{rut_sin_dv}'), se omite")
                    progress.advance(task)
                    continue

                # determinar categoria
                categoria = clasificar_por_nombre(str(rut_razon)) if rut_razon else None
                if categoria is None:
                    # fallback: intentar detectar literal en la columna RUT_RAZON (si es texto)
                    if isinstance(rut_razon, str):
                        upper = rut_razon.upper()
                        if 'IP' in upper:
                            categoria = 'IP'
                        elif 'CFT' in upper:
                            categoria = 'CFT'
                if categoria is None:
                    # intentar obtener nombre razon desde la fila si col_rut_razon apunta a RUT
                    nombre_rs = None
                    try:
                        if col_rut_razon and 'RUT' in col_rut_razon.upper() and 'NOMBRE RAZON' in df.columns:
                            nombre_rs = str(df.at[idx, 'NOMBRE RAZON'])
                        elif col_rut_razon and col_rut_razon in df.columns:
                            nombre_rs = str(fila.get(col_rut_razon, ''))
                    except Exception:
                        nombre_rs = None

                    if nombre_rs:
                        categoria = clasificar_por_nombre(nombre_rs)

                # Si aún no hay categoria, intentar mapping o preguntar al usuario (una vez por RUT)
                if categoria is None:
                    clave_rut = str(fila.get(col_rut_sin_dv, '')).strip() or str(fila.get(col_rut_razon, '')).strip()
                    # primero, usar mapping si se entregó
                    if mapping and clave_rut in mapping:
                        categoria = mapping[clave_rut]
                    elif clave_rut in decision_por_rut:
                        categoria = decision_por_rut[clave_rut]
                    else:
                        if no_interactive:
                            # en modo no interactivo y sin mapping, no asignamos y saltamos
                            logging.warning(f"No-interactive: no hay clasificación para RUT {clave_rut}, se omite")
                            progress.advance(task)
                            continue
                        # preguntar al usuario
                        while True:
                            resp = console.input(f"[yellow]No se pudo clasificar automáticamente la fila {idx+1} (RUT: {clave_rut}). Es IP o CFT? [I/C]: [/]").strip().upper()
                            if resp in ('I', 'IP'):
                                categoria = 'IP'
                                break
                            if resp in ('C', 'CFT'):
                                categoria = 'CFT'
                                break
                            console.print("[red]Respuesta inválida. Escribe I (IP) o C (CFT).[/red]")
                        decision_por_rut[clave_rut] = categoria

                carpeta_cat = categoria if categoria else 'CFT'

                # encontrar archivos que coincidan con el patrón
                patron_prefijo = f"bhe_{rut_digits}-"
                archivos_en_fuente = os.listdir(ruta_fuente)
                encontrados = [f for f in archivos_en_fuente if f.lower().startswith(patron_prefijo.lower()) and f.lower().endswith(('.pdf', '.xml'))]

                if not encontrados:
                    # Intentar búsqueda más laxa: contener rut_digits en el nombre (solo dígitos del nombre)
                    encontrados = [f for f in archivos_en_fuente if rut_digits in re.sub(r"\D", "", f) and f.lower().endswith(('.pdf', '.xml'))]

                if not encontrados:
                    logging.info(f"Fila {idx+1} ({rut_sin_dv}): no se encontraron archivos para patrón {patron_prefijo}")
                    console.print(Fore.YELLOW + f"[⚠️] Fila {idx+1}: no se encontraron archivos para RUT {rut_sin_dv} ({patron_prefijo})")
                    progress.advance(task)
                    continue

                carpeta_dest = os.path.join(ruta_destino_mes, carpeta_cat)
                os.makedirs(carpeta_dest, exist_ok=True)

                # Mostrar cuántos archivos encontrados para esta fila
                console.print(f"Fila {idx+1}: encontrados {len(encontrados)} archivo(s) para RUT {rut_sin_dv}: {encontrados}")
                for nombre in encontrados:
                    src = os.path.join(ruta_fuente, nombre)
                    dst = os.path.join(carpeta_dest, nombre)
                    if dry_run:
                        logging.info(f"[DRY-RUN] {('Mover' if mover else 'Copiar')} {src} -> {dst}")
                        console.print(Fore.MAGENTA + f"[DRY-RUN] {('Mover' if mover else 'Copiar')} {src} -> {dst}")
                    else:
                        try:
                            if mover:
                                shutil.move(src, dst)
                                logging.info(f"Movido: {src} -> {dst}")
                                console.print(Fore.GREEN + f"[MOVIDO] {src} -> {dst}")
                            else:
                                # si existe dst, renombrar con sufijo para evitar pérdida
                                if os.path.exists(dst):
                                    base, ext = os.path.splitext(dst)
                                    i = 1
                                    nuevo = f"{base}_{i}{ext}"
                                    while os.path.exists(nuevo):
                                        i += 1
                                        nuevo = f"{base}_{i}{ext}"
                                    dst = nuevo
                                shutil.copy2(src, dst)
                                logging.info(f"Copiado: {src} -> {dst}")
                                console.print(Fore.GREEN + f"[COPIADO] {src} -> {dst}")
                        except Exception as e:
                            logging.error(f"Error al copiar/mover {src} -> {dst}: {e}")
                            console.print(Fore.RED + f"[ERROR] {src} -> {dst}: {e}")
                    movimientos.append((idx+1, rut_sin_dv, nombre, carpeta_cat))
                    archivos_procesados += 1

            except Exception as e:
                logging.error(f"Error procesando fila {idx+1}: {e}")
            progress.advance(task)

    console.print(Panel.fit(f"✅ Proceso por filas finalizado. Archivos procesados: {archivos_procesados}", style="bold green"))
    return archivos_procesados, movimientos


def main():
    console.print(Panel.fit("[bold cyan]📁 Separador de BH por IP / CFT[/bold cyan]", style="bold green"))

    # Parsear flags opcionales para ejecución no interactiva
    parser = argparse.ArgumentParser(description="Separar BH por IP/CFT según Solicitud.xlsx")
    parser.add_argument('--dry-run', action='store_true', help='Simula las acciones sin copiar/mover archivos')
    parser.add_argument('--mover', action='store_true', help='Mover archivos en vez de copiar')
    parser.add_argument('--no-interactive', action='store_true', help='No preguntar; usar --map para suministrar clasificaciones')
    parser.add_argument('--map', type=str, help='CSV con mapeo RUT_SIN_DV,IP/CFT para clasificación no interactiva')
    args = parser.parse_args()

    mapping = None
    if args.map:
        # cargar CSV simple: RUT,CAT
        try:
            import csv
            mapping = {}
            with open(args.map, newline='', encoding='utf-8') as fh:
                r = csv.reader(fh)
                for row in r:
                    if not row: continue
                    rut = str(row[0]).strip()
                    cat = str(row[1]).strip().upper() if len(row) > 1 else ''
                    if cat in ('IP','CFT'):
                        mapping[rut] = cat
        except (OSError, csv.Error) as e:
            console.print(Panel.fit(f"[red]No se pudo leer mapping CSV: {e}[/red]", style="bold red"))
            return

    # Selección año/mes
    años = [d for d in os.listdir(RAIZ) if os.path.isdir(os.path.join(RAIZ, d))]
    if not años:
        console.print(Panel.fit("[red]⚠️ No hay carpetas de año en la ruta configurada.[/red]", style="bold red"))
        return
    año = seleccionar_opcion(sorted(años), "Seleccione el año:", "🗓️")
    ruta_año = os.path.join(RAIZ, año)

    meses = [d for d in os.listdir(ruta_año) if os.path.isdir(os.path.join(ruta_año, d))]
    if not meses:
        console.print(Panel.fit(f"[red]⚠️ No hay carpetas de mes en {ruta_año}[/red]", style="bold red"))
        return
    mes = seleccionar_opcion(sorted(meses), "Seleccione el mes:", "🗓️")
    ruta_mes = os.path.join(ruta_año, mes)

    # Buscar Solicitud.xlsx
    ruta_excel = os.path.join(ruta_mes, "Solicitud.xlsx")
    if not os.path.isfile(ruta_excel):
        console.print(Panel.fit(f"[red]❌ No se encontró archivo Solicitud.xlsx en {ruta_mes}[/red]", style="bold red"))
        return

    # Ruta origen: permite al usuario elegir carpeta que contenga los archivos a procesar
    console.print(Panel.fit("📂 Seleccione la carpeta donde están los archivos a separar (puede ser la misma carpeta del mes o una carpeta externa).", style="cyan"))
    console.print("1. Usar la carpeta del mes: " + ruta_mes)
    console.print("2. Ingresar ruta personalizada")
    opcion = console.input("[green]➡️ Opción (1/2): [/]").strip()
    if opcion == '2':
        ruta_fuente = console.input("[green]📁 Ingresa la ruta completa de la carpeta fuente: [/]").strip()
        if not os.path.isdir(ruta_fuente):
            console.print(Panel.fit(f"[red]❌ La ruta no existe: {ruta_fuente}[/red]", style="bold red"))
            return
    else:
        ruta_fuente = ruta_mes

    # Parámetros: mover o copiar, dry-run (flags opcionales sobrescriben prompts)
    if args.mover:
        mover = True
    else:
        mover = console.input("[green]¿Deseas mover los archivos en lugar de copiarlos? (s/N): [/] ").strip().lower() == 's'

    if args.dry_run:
        dry_run = True
    else:
        dry_run = console.input("[green]¿Dry-run? (solo mostrar acciones) (s/N): [/] ").strip().lower() == 's'

    # Cargar Excel y seleccionar hoja
    try:
        xls = pd.ExcelFile(ruta_excel, engine='openpyxl')
        hojas = xls.sheet_names
    except (OSError, ValueError, KeyError) as e:
        console.print(Panel.fit(f"[red]❌ Error leyendo el archivo Excel: {e}[/red]", style="bold red"))
        return

    hoja = seleccionar_opcion(hojas, "Seleccione la hoja del Excel para usar:", "📄")
    try:
        df = pd.read_excel(ruta_excel, sheet_name=hoja, engine='openpyxl')
    except (OSError, ValueError, KeyError) as e:
        console.print(Panel.fit(f"[red]❌ Error leyendo la hoja '{hoja}': {e}[/red]", style="bold red"))
        return

    # Detectar columna de categoria (IP / CFT)
    col_cat = encontrar_columna_categoria(df)
    if col_cat is None:
        console.print(Panel.fit("[yellow]⚠️ No se detectó automáticamente una columna con valores 'IP'/'CFT'.[/yellow]", style="yellow"))
        console.print("Columnas disponibles:")
        for c in df.columns:
            console.print(f" - {c}")
        col_cat = console.input("[green]👉 Ingresa el nombre de la columna que contiene IP/CFT (o deja vacío para no usar): [/] ").strip()
        if col_cat == '':
            col_cat = None
        elif col_cat not in df.columns:
            console.print(Panel.fit(f"[red]❌ Columna '{col_cat}' no encontrada en el Excel.[/red]", style="bold red"))
            return

    # Preparar logging simple
    carpeta_logs = os.path.join(ruta_mes, 'logs_separa')
    os.makedirs(carpeta_logs, exist_ok=True)
    log_file = os.path.join(carpeta_logs, f"separa_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Modo de procesamiento: por filas (recomendado) o por detección de archivos
    console.print("\n[cyan]Modo de procesamiento:[/]\n  1. Por filas del Excel (buscar por RUT_SIN_DV en cada fila)\n  2. Por archivos detectados en la carpeta (modo previo)")
    modo = console.input("[green]➡️ Elige modo (1/2, default 1): [/] ").strip()
    if modo == '' or modo == '1':
        # seleccionar columnas necesarias
        # detectar columna RUT_SIN_DV (frecuente 'RUT_SIN_DV' o 'RUT_SIN_D V' o 'RUT SIN DV')
        posibles_rut = ['RUT_SIN_DV', 'RUT SIN DV', 'RUT_SIN_D V', 'RUT_SIN_D', 'RUT']
        col_rut_sin = None
        for p in posibles_rut:
            if p in df.columns:
                col_rut_sin = p
                break
        if col_rut_sin is None:
            console.print("Columnas disponibles para seleccionar RUT_SIN_DV:")
            for c in df.columns:
                console.print(f" - {c}")
            col_rut_sin = console.input("[green]👉 Ingresa el nombre de la columna que contiene RUT_SIN_DV (ej: 'RUT_SIN_DV' o 'RUT'): [/] ").strip()
            if col_rut_sin == '':
                console.print(Panel.fit("[red]❌ No se indicó columna de RUT_SIN_DV. Abortando.[/red]", style="bold red"))
                return

        # columna de RUT RAZON (para clasificar IP/CFT)
        col_rut_razon = None
        for opt in ['RUT RAZON', 'RUT_RAZON', 'NOMBRE RAZON', 'NOMBRE_RAZON']:
            if opt in df.columns:
                col_rut_razon = opt
                break
        if col_rut_razon is None:
            console.print("Columnas disponibles (elije la que contiene Nombre/Razón o RUT RAZON):")
            for c in df.columns:
                console.print(f" - {c}")
            col_rut_razon = console.input("[green]👉 Ingresa el nombre de la columna que contiene 'RUT RAZON' o 'NOMBRE RAZON' (o deja vacío para no usar): [/] ").strip()
            if col_rut_razon == '':
                col_rut_razon = None

        # si se solicitó modo no interactivo sin mapping, abortar
        if args.no_interactive and not mapping:
            console.print(Panel.fit("[red]Modo no-interactive activado pero no se entregó --map. Abortando.[/red]", style="bold red"))
            return

        procesados, movimientos = procesar_por_filas(
            df, ruta_fuente, ruta_mes, col_rut_razon, col_rut_sin,
            mover=mover, dry_run=dry_run, mapping=mapping, no_interactive=args.no_interactive
        )
        # opcional: guardar resumen en CSV
        if procesados > 0:
            resumen_csv = os.path.join(ruta_mes, 'logs_separa', f'resumen_separa_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
            try:
                import csv
                with open(resumen_csv, 'w', newline='', encoding='utf-8') as fh:
                    w = csv.writer(fh)
                    w.writerow(['Fila', 'RUT_SIN_DV', 'Archivo', 'Categoria'])
                    for r in movimientos:
                        w.writerow(r)
                console.print(Panel.fit(f"📄 Resumen guardado en: {resumen_csv}", style="bold green"))
            except Exception as e:
                logging.error(f"No se pudo escribir resumen CSV: {e}")

    else:
        procesados = procesar_carpeta_fuente(ruta_fuente, ruta_mes, df, col_cat, mover=mover, dry_run=dry_run)

    console.print(Panel.fit(f"📌 Registro guardado en: {log_file}", style="bold blue"))


if __name__ == '__main__':
    main()
