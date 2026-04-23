import os
import logging
import argparse
from datetime import datetime
import sys
from colorama import Fore, Style, init as colorama_init
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, BarColumn, TimeElapsedColumn, TextColumn
from rich.table import Table
import utils
from outlook_utils import conectar_outlook, filtrar_correos_por_fecha

# Inicialización
colorama_init(autoreset=True)
console = Console()

# --- Configuración básica ---
import config as cfg
CARPETA_BASE = cfg.CARPETA_BASE
ZONA_HORARIA = cfg.ZONA_HORARIA
FORMATO_FECHA_INPUT = "%d/%m/%Y"
MESES_ES = cfg.MESES_ES

DECISION_DUPLICADOS = None


def imprimir_encabezado():
    texto = Text("\n📥 EXTRACCIÓN DE ADJUNTOS DE OUTLOOK", style="bold white on blue", justify="center")
    panel = Panel(texto, expand=True, border_style="blue")
    console.print(panel)


def configurar_logging(fecha_referencia: datetime):
    anio = str(fecha_referencia.year)
    mes_nombre = MESES_ES[fecha_referencia.month - 1]
    carpeta_mes = os.path.join(CARPETA_BASE, anio, mes_nombre)
    os.makedirs(carpeta_mes, exist_ok=True)

    carpeta_logs = os.path.join(carpeta_mes, "logs_extraccion")
    os.makedirs(carpeta_logs, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(carpeta_logs, f"log_{timestamp}.txt")

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()

    file_fmt = logging.Formatter(fmt="📅 %(asctime)s | [%(levelname)s] 👉 %(message)s", datefmt="%d/%m/%Y %H:%M:%S")
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_fmt)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(file_fmt)
    logger.addHandler(console_handler)

    logging.info("🟢 === INICIO DEL PROCESO DE EXTRACCIÓN DE ARCHIVOS ADJUNTOS ===")
    logging.info(f"📁 Log guardado en: {log_file}")
    logging.info(f"📆 Rango inicial de fecha: {fecha_referencia.strftime('%d/%m/%Y')}")


def mostrar_resumen(contador_emails, contador_guardados, contador_pdf, contador_xml, duplicados):
    tabla = Table(title="📊 Resumen del proceso", show_lines=True)
    tabla.add_column("Ítem", style="cyan", justify="left")
    tabla.add_column("Cantidad", style="magenta", justify="right")

    tabla.add_row("Correos procesados", str(contador_emails))
    tabla.add_row("Adjuntos guardados", str(contador_guardados))
    tabla.add_row(" - Archivos PDF", str(contador_pdf))
    tabla.add_row(" - Archivos XML", str(contador_xml))

    if duplicados:
        tabla.add_row("Duplicados detectados", str(len(duplicados)))
        tabla.add_row("Acción aplicada", DECISION_DUPLICADOS)

    console.print(tabla)


def solicitar_fecha_interactiva(prompt: str) -> datetime:
    while True:
        fecha_str = input(f"{Fore.CYAN}📅 {prompt}{Style.RESET_ALL} ")
        try:
            fecha = datetime.strptime(fecha_str, FORMATO_FECHA_INPUT).replace(tzinfo=ZONA_HORARIA)
            logging.info(f"✔ Fecha ingresada: {fecha_str}")
            return fecha
        except ValueError:
            logging.error("❌ Formato inválido. Por favor ingrese la fecha en formato dd/mm/yyyy.")


def parsear_args():
    parser = argparse.ArgumentParser(description="🗂️  Extraer adjuntos (XML y PDF) de correos de Outlook")
    parser.add_argument("--fecha-inicio", type=str, help="Fecha inicio en formato dd/mm/yyyy")
    parser.add_argument("--fecha-fin", type=str, help="Fecha fin en formato dd/mm/yyyy")
    parser.add_argument("--dry-run", action="store_true", help="Simula la ejecución sin guardar archivos")
    return parser.parse_args()


def decidir_guardado_archivos_repetidos(archivos_repetidos):
    global DECISION_DUPLICADOS
    if not archivos_repetidos:
        DECISION_DUPLICADOS = None
        return

    panel = Panel.fit(f"⚠️ Se detectaron {len(archivos_repetidos)} archivos duplicados.", title="Archivos duplicados", border_style="yellow")
    console.print(panel)

    print(f"\n{Fore.YELLOW}⚠️  Archivos duplicados detectados.{Style.RESET_ALL}")
    while True:
        print(f"{Fore.CYAN}¿Qué deseas hacer con ellos?{Style.RESET_ALL}")
        print("  S = Sobrescribir todos")
        print("  A = Guardar todos con sufijo (_1, _2, ...)")
        print("  I = Ignorar todos")
        print("  D = Detallar rutas duplicadas antes de decidir")
        decision = input(f"{Fore.CYAN}Ingresa tu opción [S/A/I/D]: {Style.RESET_ALL}").strip().upper()

        if decision == "D":
            print(f"\n{Fore.MAGENTA}Listado de rutas duplicadas:{Style.RESET_ALL}")
            for ruta in archivos_repetidos:
                print(f" - {ruta}")
            print("")
            continue

        if decision in ("S", "A", "I"):
            DECISION_DUPLICADOS = decision
            break
        else:
            print(f"{Fore.RED}Opción inválida. Intente con S, A, I o D.{Style.RESET_ALL}")


def resolver_conflicto(ruta_original):
    # Delegar a utils.resolver_conflicto para mantener política centralizada.
    return utils.resolver_conflicto(ruta_original, politica=DECISION_DUPLICADOS)


def guardar_adjuntos(mensajes, dry_run=False):
    global DECISION_DUPLICADOS
    DECISION_DUPLICADOS = None

    contador_emails = 0
    contador_guardados = 0
    contador_pdf = 0
    contador_xml = 0
    archivos_repetidos = []
    rutas_a_guardar = []

    console.print(f"\n[blue]📥 Escaneando correos para extraer adjuntos 'bhe_' con PDF y XML...[/blue]")

    for msg in mensajes:
        try:
            adjuntos = [att for att in msg.Attachments if "bhe_" in att.FileName.lower()]
            if not adjuntos:
                continue

            tiene_pdf = any(att.FileName.lower().endswith(".pdf") for att in adjuntos)
            tiene_xml = any(att.FileName.lower().endswith(".xml") for att in adjuntos)
            if not (tiene_pdf and tiene_xml):
                continue

            fecha_msg = msg.ReceivedTime
            try:
                fecha_msg = fecha_msg.replace(tzinfo=ZONA_HORARIA)
            except (TypeError, AttributeError):
                pass

            logging.info(f"📩 Procesando correo recibido el {fecha_msg.strftime('%d/%m/%Y %H:%M')} con {len(adjuntos)} adjuntos.")
            contador_emails += 1

            anio = str(fecha_msg.year)
            mes_nombre = MESES_ES[fecha_msg.month - 1]
            carpeta_mes = os.path.join(CARPETA_BASE, anio, mes_nombre)

            for att in adjuntos:
                ruta_final = os.path.join(carpeta_mes, att.FileName)
                rutas_a_guardar.append((att, ruta_final, msg))
                if os.path.exists(ruta_final):
                    archivos_repetidos.append(ruta_final)

        except Exception as e:
            logging.error(f"❌ Error en correo: {e}")

    decidir_guardado_archivos_repetidos(archivos_repetidos)

    with Progress(
        TextColumn("[bold blue]Guardando[/bold blue]"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        TimeElapsedColumn(),
        console=console
    ) as progress:
        tarea = progress.add_task("Procesando adjuntos...", total=len(rutas_a_guardar))

        for att, ruta_final, msg in rutas_a_guardar:
            try:
                fecha_msg = msg.ReceivedTime
                try:
                    fecha_msg = fecha_msg.replace(tzinfo=ZONA_HORARIA)
                except Exception:
                    pass
                anio = str(fecha_msg.year)
                mes_nombre = MESES_ES[fecha_msg.month - 1]
                carpeta_mes = os.path.join(CARPETA_BASE, anio, mes_nombre)
                os.makedirs(carpeta_mes, exist_ok=True)

                ruta_decidida = resolver_conflicto(ruta_final)
                if ruta_decidida is None:
                    logging.info(f"⏭ Ignorado archivo: {att.FileName}")
                    progress.advance(tarea)
                    continue

                if dry_run:
                    logging.info(f"[DRY-RUN] Se simula guardado de: {ruta_decidida}")
                else:
                    att.SaveAsFile(ruta_decidida)
                    logging.info(f"💾 Guardado archivo: {ruta_decidida}")

                if not dry_run:
                    contador_guardados += 1
                    ext = os.path.splitext(ruta_decidida)[1].lower()
                    if ext == ".xml":
                        contador_xml += 1
                    elif ext == ".pdf":
                        contador_pdf += 1

            except OSError as e:
                logging.error(f"❌ Error guardando '{att.FileName}': {e}")

            progress.advance(tarea)

    console.print("\n[blue]📊 === Resumen ===[/blue]")
    mostrar_resumen(contador_emails, contador_guardados, contador_pdf, contador_xml, archivos_repetidos)

    if dry_run:
        console.print("[magenta][DRY-RUN] No se guardaron archivos.[/magenta]")

    return contador_emails, contador_guardados, contador_pdf, contador_xml, archivos_repetidos


def validar_rango_fechas(fecha_inicio, fecha_fin):
    if fecha_inicio > fecha_fin:
        raise ValueError("La fecha de inicio no puede ser posterior a la fecha fin.")


def main():
    imprimir_encabezado()
    args = parsear_args()

    if args.fecha_inicio and args.fecha_fin:
        try:
            fecha_inicio = datetime.strptime(args.fecha_inicio, FORMATO_FECHA_INPUT).replace(tzinfo=ZONA_HORARIA)
            fecha_fin = datetime.strptime(args.fecha_fin, FORMATO_FECHA_INPUT).replace(tzinfo=ZONA_HORARIA)
            fecha_fin = fecha_fin.replace(hour=23, minute=59, second=59)
        except ValueError:
            console.print("[bold red]❌ Formato inválido de fechas.[/bold red]")
            return
    elif args.fecha_inicio or args.fecha_fin:
        console.print("[bold red]❌ Debe especificar ambas fechas o ninguna para modo interactivo.[/bold red]")
        return
    else:
        console.print("[cyan]📅 Ingrese el rango de fechas:[/cyan]")
        fecha_inicio = solicitar_fecha_interactiva("Fecha inicio (dd/mm/yyyy): ")
        fecha_fin = solicitar_fecha_interactiva("Fecha fin (dd/mm/yyyy): ")
        fecha_fin = fecha_fin.replace(hour=23, minute=59, second=59)

    try:
        validar_rango_fechas(fecha_inicio, fecha_fin)
    except ValueError as ve:
        console.print(f"[bold red]❌ {ve}[/bold red]")
        return

    configurar_logging(fecha_inicio)

    outlook_ns = conectar_outlook()

    bandeja = outlook_ns.GetDefaultFolder(6)  # Bandeja de entrada
    mensajes = filtrar_correos_por_fecha(bandeja, fecha_inicio, fecha_fin)
    if not mensajes:
        console.print("[yellow]⚠️ No se encontraron correos para procesar.[/yellow]")
        return

    emails, guardados, pdf, xml, duplicados = guardar_adjuntos(mensajes, dry_run=args.dry_run)

    logging.info(f"📊 Correos procesados: {emails}")
    logging.info(f"📊 Adjuntos guardados: {guardados} (PDF: {pdf}, XML: {xml})")
    if duplicados:
        logging.info(f"🎯 Política aplicada a duplicados: {DECISION_DUPLICADOS}")
    logging.info("✅ Proceso finalizado con éxito.")
    console.print("\n[bold green]🎉 Proceso finalizado con éxito.[/bold green]")


if __name__ == "__main__":
    main()
