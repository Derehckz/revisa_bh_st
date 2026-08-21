#!/usr/bin/env python3
import _sys_path  # noqa: E402
import os
import shutil
import re
import pandas as pd
import logging
import sys
import argparse
from datetime import datetime
import utils
from rich.progress import Progress, BarColumn, TimeElapsedColumn, TextColumn

# Configuración básica (ajustar en config.py si se desea)
import config
RAIZ = config.RAIZ
ZONA_HORARIA = config.ZONA_HORARIA
MESES_ES = config.MESES_ES

console = utils.console


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
        utils.print_warning("No se encontraron archivos 'bhe_' PDF/XML en la carpeta seleccionada.")
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

    utils.print_success(f"Proceso finalizado. Archivos procesados: {procesados}")
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
                            resp = utils.prompt_required(
                                f"No se pudo clasificar automáticamente la fila {idx+1} (RUT: {clave_rut}). Es IP o CFT? [I/C]"
                            ).strip().upper()
                            if resp in ('I', 'IP'):
                                categoria = 'IP'
                                break
                            if resp in ('C', 'CFT'):
                                categoria = 'CFT'
                                break
                            utils.print_error("Respuesta inválida. Escribe I (IP) o C (CFT).")
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
                    utils.print_warning(f"Fila {idx+1}: no se encontraron archivos para RUT {rut_sin_dv} ({patron_prefijo})")
                    progress.advance(task)
                    continue

                carpeta_dest = os.path.join(ruta_destino_mes, carpeta_cat)
                os.makedirs(carpeta_dest, exist_ok=True)

                # Mostrar cuántos archivos encontrados para esta fila
                utils.print_info(f"Fila {idx+1}: encontrados {len(encontrados)} archivo(s) para RUT {rut_sin_dv}: {encontrados}")
                for nombre in encontrados:
                    src = os.path.join(ruta_fuente, nombre)
                    dst = os.path.join(carpeta_dest, nombre)
                    if dry_run:
                        logging.info(f"[DRY-RUN] {('Mover' if mover else 'Copiar')} {src} -> {dst}")
                        utils.print_info(f"[DRY-RUN] {('Mover' if mover else 'Copiar')} {src} -> {dst}")
                    else:
                        try:
                            if mover:
                                shutil.move(src, dst)
                                logging.info(f"Movido: {src} -> {dst}")
                                utils.print_success(f"MOVIDO: {src} -> {dst}")
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
                                utils.print_success(f"COPIADO: {src} -> {dst}")
                        except Exception as e:
                            logging.error(f"Error al copiar/mover {src} -> {dst}: {e}")
                            utils.print_error(f"Error al copiar/mover {src} -> {dst}: {e}")
                    movimientos.append((idx+1, rut_sin_dv, nombre, carpeta_cat))
                    archivos_procesados += 1

            except Exception as e:
                logging.error(f"Error procesando fila {idx+1}: {e}")
            progress.advance(task)

    utils.print_success(f"Proceso por filas finalizado. Archivos procesados: {archivos_procesados}")
    return archivos_procesados, movimientos


def main():
    utils.print_header("📁 Separador de BH por IP / CFT", "Clasificación automática de boletas")

    # Parsear flags opcionales para ejecución no interactiva
    parser = argparse.ArgumentParser(description="Separar BH por IP/CFT según Solicitud.xlsx")
    parser.add_argument('--dry-run', action='store_true', help='Simula las acciones sin copiar/mover archivos')
    parser.add_argument('--mover', action='store_true', help='Mover archivos en vez de copiar')
    parser.add_argument('--no-interactive', action='store_true', help='No preguntar; usar --map para suministrar clasificaciones')
    parser.add_argument('--map', type=str, help='CSV con mapeo RUT_SIN_DV,IP/CFT para clasificación no interactiva')
    parser.add_argument('--sheet', type=str, default=None, help='Hoja del Excel (ej. Solicitud).')
    utils.register_non_interactive_cli(parser)
    utils.register_period_args(parser)
    args = parser.parse_args()
    utils.apply_non_interactive_from_args(args)
    if args.no_interactive:
        utils.force_non_interactive()

    mapping = None
    if args.map:
        # cargar CSV simple: RUT,CAT (UTF-8 / cp1252 / etc.)
        try:
            from map_ip_cft import load_map_ip_cft

            mapping = load_map_ip_cft(args.map)
            if not mapping:
                utils.print_error(
                    "El CSV de mapeo no tiene filas IP/CFT válidas "
                    "(¿elegiste Contabilidad_pagos en vez de map_ip_cft.csv?)."
                )
                return
        except (OSError, ValueError, ImportError) as e:
            utils.print_error(f"No se pudo leer mapping CSV: {e}")
            return

    # Selección año/mes
    try:
        año, mes = utils.resolve_año_mes(RAIZ, getattr(args, "year", None), getattr(args, "month", None))
    except ValueError as e:
        utils.print_error(str(e))
        return
    ruta_mes = os.path.join(RAIZ, año, mes)

    # Buscar Solicitud.xlsx
    ruta_excel = os.path.join(ruta_mes, "Solicitud.xlsx")
    if not os.path.isfile(ruta_excel):
        utils.print_error(f"No se encontró archivo Solicitud.xlsx en {ruta_mes}")
        return

    # Ruta origen: permite al usuario elegir carpeta que contenga los archivos a procesar
    if utils.is_non_interactive() or args.no_interactive:
        ruta_fuente = ruta_mes
        utils.print_info(f"Modo no interactivo: carpeta fuente = {ruta_fuente}")
    else:
        utils.print_info("Seleccione la carpeta donde están los archivos a separar (puede ser la misma carpeta del mes o una carpeta externa).")
        utils.print_list("Opciones", [f"1. Usar la carpeta del mes: {ruta_mes}", "2. Ingresar ruta personalizada"])
        opcion = utils.prompt_required("Opción (1/2)")
        if opcion == '2':
            ruta_fuente = utils.prompt_required("Ingresa la ruta completa de la carpeta fuente")
            if not os.path.isdir(ruta_fuente):
                utils.print_error(f"La ruta no existe: {ruta_fuente}")
                return
        else:
            ruta_fuente = ruta_mes

    continuar = utils.mostrar_contexto_ejecucion(
        "🗂️ Contexto de ejecución",
        [
            ("Raíz", RAIZ),
            ("Período", f"{mes} {año}"),
            ("Carpeta mes", ruta_mes),
            ("Carpeta fuente", ruta_fuente),
            ("Excel", ruta_excel),
        ],
        preview_items=["Se separarán archivos por IP/CFT según la hoja seleccionada."],
        confirm_message="¿Continuar con la separación de archivos? (s/n)",
    )
    if not continuar:
        utils.print_warning("Proceso cancelado por el usuario.")
        return

    # Parámetros: mover o copiar, dry-run (flags opcionales sobrescriben prompts)
    if args.mover:
        mover = True
    else:
        mover = utils.print_confirm("¿Deseas mover los archivos en lugar de copiarlos?")

    if args.dry_run:
        dry_run = True
    else:
        dry_run = utils.print_confirm("¿Dry-run? (solo mostrar acciones)")

    # Cargar Excel y seleccionar hoja
    try:
        xls = pd.ExcelFile(ruta_excel, engine='openpyxl')
        hojas = xls.sheet_names
    except (OSError, ValueError, KeyError) as e:
        utils.print_error(f"Error leyendo el archivo Excel: {e}")
        return

    hoja = utils.choose_excel_sheet(
        hojas,
        sheet=getattr(args, "sheet", None),
        prompt_message="Seleccione la hoja del Excel para usar:",
    )
    try:
        df = pd.read_excel(ruta_excel, sheet_name=hoja, engine='openpyxl')
    except (OSError, ValueError, KeyError) as e:
        utils.print_error(f"Error leyendo la hoja '{hoja}': {e}")
        return

    # Detectar columna de categoria (IP / CFT)
    col_cat = encontrar_columna_categoria(df)
    if col_cat is None:
        utils.print_warning("No se detectó automáticamente una columna con valores 'IP'/'CFT'.")
        utils.print_info("Columnas disponibles:")
        for c in df.columns:
            utils.console.print(f" - {c}")
        col_cat = utils.prompt_optional("Ingresa el nombre de la columna que contiene IP/CFT (o deja vacío para no usar)")
        if col_cat == '':
            col_cat = None
        elif col_cat not in df.columns:
            utils.print_error(f"Columna '{col_cat}' no encontrada en el Excel.")
            return

    # Preparar logging simple
    carpeta_logs = os.path.join(ruta_mes, 'logs_separa')
    os.makedirs(carpeta_logs, exist_ok=True)
    log_file = os.path.join(carpeta_logs, f"separa_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    utils.configurar_logging(log_file)

    # Modo de procesamiento: por filas (recomendado) o por detección de archivos
    utils.print_info("Modo de procesamiento:")
    utils.print_list(
        "Modos",
        [
            "1. Por filas del Excel (buscar por RUT_SIN_DV en cada fila)",
            "2. Por archivos detectados en la carpeta (modo previo)",
        ],
    )
    modo = utils.prompt_optional("Elige modo (1/2, default 1)")
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
            utils.print_info("Columnas disponibles para seleccionar RUT_SIN_DV:")
            for c in df.columns:
                utils.console.print(f" - {c}")
            col_rut_sin = utils.prompt_required("Ingresa el nombre de la columna que contiene RUT_SIN_DV (ej: 'RUT_SIN_DV' o 'RUT')")
            if col_rut_sin == '':
                utils.print_error("No se indicó columna de RUT_SIN_DV. Abortando.")
                return

        # columna de RUT RAZON (para clasificar IP/CFT)
        col_rut_razon = None
        for opt in ['RUT RAZON', 'RUT_RAZON', 'NOMBRE RAZON', 'NOMBRE_RAZON']:
            if opt in df.columns:
                col_rut_razon = opt
                break
        if col_rut_razon is None:
            utils.print_info("Columnas disponibles (elige la que contiene Nombre/Razón o RUT RAZON):")
            for c in df.columns:
                utils.console.print(f" - {c}")
            col_rut_razon = utils.prompt_optional("Ingresa el nombre de la columna que contiene 'RUT RAZON' o 'NOMBRE RAZON' (o deja vacío para no usar)")
            if col_rut_razon == '':
                col_rut_razon = None

        # si se solicitó modo no interactivo sin mapping, abortar
        if args.no_interactive and not mapping:
            utils.print_error("Modo no-interactive activado pero no se entregó --map. Abortando.")
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
                utils.print_success(f"Resumen guardado en: {resumen_csv}")
            except Exception as e:
                logging.error(f"No se pudo escribir resumen CSV: {e}")

    else:
        procesados = procesar_carpeta_fuente(ruta_fuente, ruta_mes, df, col_cat, mover=mover, dry_run=dry_run)

    utils.print_info(f"Registro guardado en: {log_file}")


if __name__ == '__main__':
    main()
