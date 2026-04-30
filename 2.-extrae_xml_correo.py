import os
import logging
import argparse
from datetime import datetime
import sys
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, BarColumn, TimeElapsedColumn, TextColumn
from rich.table import Table
import utils
from outlook_utils import conectar_outlook_ns, filtrar_correos_por_fecha

console = utils.console

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
    utils.console.print(panel)


def configurar_logging(fecha_referencia: datetime):
    anio = str(fecha_referencia.year)
    mes_nombre = MESES_ES[fecha_referencia.month - 1]
    carpeta_mes = os.path.join(CARPETA_BASE, anio, mes_nombre)
    os.makedirs(carpeta_mes, exist_ok=True)

    carpeta_logs = os.path.join(carpeta_mes, "logs_extraccion")
    os.makedirs(carpeta_logs, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(carpeta_logs, f"log_{timestamp}.txt")

    utils.configurar_logging(log_file)

    logging.info("🟢 === INICIO DEL PROCESO DE EXTRACCIÓN DE ARCHIVOS ADJUNTOS ===")
    logging.info(f"📁 Log guardado en: {log_file}")
    logging.info(f"🧭 run_id={utils.get_run_id()} correlation_id={utils.get_correlation_id()}")
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

    utils.console.print(tabla)


def solicitar_fecha_interactiva(prompt: str) -> datetime:
    while True:
        fecha_str = utils.prompt_required(f"📅 {prompt}")
        try:
            fecha = datetime.strptime(fecha_str, FORMATO_FECHA_INPUT).replace(tzinfo=ZONA_HORARIA)
            logging.info(f"✔ Fecha ingresada: {fecha_str}")
            return fecha
        except ValueError:
            logging.error("Formato inválido. Por favor ingrese la fecha en formato dd/mm/yyyy.")
            utils.print_error("Formato inválido. Use dd/mm/yyyy.")


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
    utils.console.print(panel)
    utils.print_warning("Archivos duplicados detectados.")
    while True:
        utils.print_info("¿Qué deseas hacer con ellos?")
        utils.print_list("Opciones", [
            "S = Sobrescribir todos",
            "A = Guardar todos con sufijo (_1, _2, ...)",
            "I = Ignorar todos",
            "D = Detallar rutas duplicadas antes de decidir",
        ])
        decision = utils.prompt_required("Ingresa tu opción [S/A/I/D]").strip().upper()

        if decision == "D":
            utils.print_section("Listado de rutas duplicadas")
            for ruta in archivos_repetidos:
                utils.console.print(f" - {ruta}")
            utils.print_blank()
            continue

        if decision in ("S", "A", "I"):
            DECISION_DUPLICADOS = decision
            break
        else:
            utils.print_error("Opción inválida. Intente con S, A, I o D.")


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

    utils.print_progress_status("Escaneando correos para extraer adjuntos 'bhe_' con PDF y XML...")

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

    utils.print_section("📊 Resumen")
    mostrar_resumen(contador_emails, contador_guardados, contador_pdf, contador_xml, archivos_repetidos)

    if dry_run:
        utils.print_warning("[DRY-RUN] No se guardaron archivos.")

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
            utils.print_error("Formato inválido de fechas.")
            return
    elif args.fecha_inicio or args.fecha_fin:
        utils.print_error("Debe especificar ambas fechas o ninguna para modo interactivo.")
        return
    else:
        utils.print_info("Ingrese el rango de fechas:")
        fecha_inicio = solicitar_fecha_interactiva("Fecha inicio (dd/mm/yyyy): ")
        fecha_fin = solicitar_fecha_interactiva("Fecha fin (dd/mm/yyyy): ")
        fecha_fin = fecha_fin.replace(hour=23, minute=59, second=59)

    try:
        validar_rango_fechas(fecha_inicio, fecha_fin)
    except ValueError as ve:
        utils.print_error(str(ve))
        return

    configurar_logging(fecha_inicio)

    outlook_ns = conectar_outlook_ns()

    bandeja = outlook_ns.GetDefaultFolder(6)  # Bandeja de entrada
    mensajes = filtrar_correos_por_fecha(bandeja, fecha_inicio, fecha_fin)
    if not mensajes:
        utils.print_warning("No se encontraron correos para procesar.")
        return

    emails, guardados, pdf, xml, duplicados = guardar_adjuntos(mensajes, dry_run=args.dry_run)

    logging.info(f"📊 Correos procesados: {emails}")
    logging.info(f"📊 Adjuntos guardados: {guardados} (PDF: {pdf}, XML: {xml})")
    if duplicados:
        logging.info(f"🎯 Política aplicada a duplicados: {DECISION_DUPLICADOS}")
    logging.info("✅ Proceso finalizado con éxito.")
    utils.print_success("Proceso finalizado con éxito.")


if __name__ == "__main__":
    main()
