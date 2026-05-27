#!/usr/bin/env python3
import _sys_path  # noqa: E402
import os
import argparse
import pandas as pd
from outlook_utils import conectar_outlook_app
import time
import logging
from rich.panel import Panel
import config
import utils
import bh_excel_workbook
import bh_outlook_mail
import email_templates as templates
import idempotency_store
import email_outbox

console = utils.console

RAIZ = config.RAIZ
LOG_FOLDER_NAME = "logs_envio_recepcion"

# =========================
# Configuración de correo
# =========================
EMAIL_COPIA = ""  # puedes agregar CC si quieres

# =========================
# Funciones auxiliares
# =========================

def seleccionar_opcion(lista, mensaje, icono=""):
    return utils.seleccionar_opcion(lista, mensaje, icono)


def listar_carpetas_validas(ruta):
    return [d for d in os.listdir(ruta)
            if os.path.isdir(os.path.join(ruta, d))
            and not d.startswith('.')
            and not d.startswith('__')]


def format_entero(valor):
    if pd.isna(valor):
        return "N/A"
    try:
        entero = int(float(valor))
        return f"{entero}"
    except (TypeError, ValueError):
        return str(valor)


def guardar_hoja_excel_atomico(ruta_excel, sheet_name, df_actualizado):
    """Actualiza una hoja preservando el resto del libro con escritura atómica."""
    ok = bh_excel_workbook.replace_sheet_atomically(ruta_excel, sheet_name, df_actualizado)
    if not ok:
        logging.error("No se pudo guardar Excel de forma atómica.")
        utils.print_error("No se pudo guardar Excel de forma atómica.")
    return ok


# =========================
# Función principal
# =========================

def main(
    args=None,
    dispatch_outbox: dict[int, int] | None = None,
    dispatch_only_indices: set[int] | None = None,
):
    """dispatch_outbox: índice Excel -> id outbox `pending` (reintento COM).
    dispatch_only_indices: si no es None, solo se procesan esas filas (modo worker)."""
    if args is None:
        args = argparse.Namespace(force_resend=False, yes=False, send=False, year=None, month=None)

    utils.apply_non_interactive_from_args(args)
    utils.print_header("📧 ENVÍO DE CORREOS DE RECEPCIÓN", "Boletas de Honorarios")

    # Modo de prueba / control explícito de envío real.
    # En modo no interactivo solo se envía si viene --send.
    if utils.is_non_interactive():
        modo_prueba = not bool(getattr(args, "send", False))
    else:
        modo_prueba = utils.prompt_yes_no_s(
            "¿Modo de prueba? (s/n) - No envía correos ni modifica Excel", default="n"
        )
    if modo_prueba:
        utils.print_warning("MODO DE PRUEBA ACTIVADO - No se enviarán correos ni se modificará el Excel")

    # Selección año/mes
    try:
        año, mes = utils.resolve_año_mes(RAIZ, getattr(args, "year", None), getattr(args, "month", None))
    except ValueError as e:
        utils.print_error(str(e))
        return
    ruta_mes = os.path.join(RAIZ, año, mes)

    # Archivo Excel (prueba o real)
    excel_filename = "Solicitud_prueba.xlsx" if modo_prueba else "Solicitud.xlsx"
    ruta_excel = os.path.join(ruta_mes, excel_filename)
    if not os.path.isfile(ruta_excel):
        utils.print_error(f"No se encontró archivo {excel_filename} en {ruta_mes}")
        return

    # Carpeta de logs
    ruta_logs = os.path.join(ruta_mes, LOG_FOLDER_NAME)
    os.makedirs(ruta_logs, exist_ok=True)
    ruta_log_file = os.path.join(ruta_logs, "envio_recepcion.log")
    utils.configurar_logging(ruta_log_file)

    continuar = utils.mostrar_contexto_ejecucion(
        "🗂️ Contexto de ejecución",
        [
            ("Raíz", RAIZ),
            ("Período", f"{mes} {año}"),
            ("Carpeta mes", ruta_mes),
            ("Excel", ruta_excel),
            ("Logs", ruta_log_file),
            ("Modo prueba", "Sí" if modo_prueba else "No"),
        ],
        preview_items=["Se filtrarán filas con Estado_Recepcion = RECIBIDO."],
        confirm_message="¿Continuar con la lectura del Excel y vista previa? (s/n)",
    )
    if not continuar:
        utils.print_warning("Proceso cancelado por el usuario.")
        return

    # Leer Excel (hoja principal, asumiendo "Solicitud" o primera)
    try:
        xls = pd.ExcelFile(ruta_excel, engine="openpyxl")
        sheet_name = xls.sheet_names[0]
        df = pd.read_excel(ruta_excel, sheet_name=sheet_name, engine='openpyxl')
    except Exception as e:
        utils.print_error(f"Error leyendo Excel: {e}")
        logging.error(f"Error leyendo Excel: {e}")
        return

    # Verificar columnas necesarias
    required_cols = ['Estado_Recepcion', 'Email_Docente', 'NAME', 'numeroBoleta_XML']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        utils.print_error(f"Columnas faltantes en Excel: {missing_cols}")
        return

    # Agregar columna de control si no existe
    if 'Correo_Recepcion_Enviado' not in df.columns:
        df['Correo_Recepcion_Enviado'] = ""

    # Filtrar filas con Estado_Recepcion == 'RECIBIDO'
    df_filtrado = df[df['Estado_Recepcion'] == 'RECIBIDO']

    if df_filtrado.empty:
        utils.print_warning("No hay registros con estado 'RECIBIDO' para enviar correos.")
        logging.info("No hay registros válidos para envío de correos de recepción.")
        return

    outlook = None if modo_prueba else conectar_outlook_app()

    enviados = 0
    fallidos = 0
    omitidos = 0
    stage_id = "script5.recepcion_send"
    force_resend = bool(getattr(args, "force_resend", False))

    for idx, fila in df_filtrado.iterrows():
        try:
            ix = int(idx)
        except (TypeError, ValueError):
            ix = idx
        if dispatch_only_indices is not None and ix not in dispatch_only_indices:
            continue
        # Verificar si ya fue enviado (marca local en Excel)
        if str(fila.get('Correo_Recepcion_Enviado', '')).strip() == 'Sí':
            utils.print_warning(f"Correo ya enviado previamente para boleta {fila.get('numeroBoleta_XML', 'N/A')}")
            logging.info(f"Correo omitido (ya enviado): boleta {fila.get('numeroBoleta_XML', 'N/A')}")
            omitidos += 1
            continue

        correo = str(fila.get('Email_Docente', '')).strip()
        nombre = fila.get('NAME', 'Estimado')
        numero_boleta = format_entero(fila.get('numeroBoleta_XML', 'N/A'))
        rut = format_entero(fila.get('rutReceptorCompleto_XML', 'N/A'))
        rut_emisor = format_entero(fila.get('rutEmisorCompleto_XML', 'N/A'))
        monto = fila.get('totalHonorarios_XML', 'N/A')

        if not utils.validar_email(correo):
            df.at[idx, 'Correo_Recepcion_Enviado'] = "❌ Correo inválido"
            logging.warning(f"Correo inválido: {correo} para boleta {numero_boleta}")
            utils.print_error(f"Correo inválido: {correo}")
            fallidos += 1
            continue

        # Idempotencia: clave por período + boleta + correo destino.
        item_key = f"{año}|{mes}|{numero_boleta}|{correo}".lower()
        if not modo_prueba and not force_resend and idempotency_store.was_success(stage_id, item_key):
            df.at[idx, 'Correo_Recepcion_Enviado'] = "⏭ Omitido por idempotencia"
            utils.print_warning(f"Omitido (ya enviado, usar --force-resend para reenviar): {correo}")
            logging.info(f"Omitido por idempotencia: {item_key}")
            omitidos += 1
            continue

        asunto = templates.generar_asunto_recepcion(numero_boleta)
        cuerpo_html = templates.generar_cuerpo_recepcion(
            nombre=nombre,
            numero_boleta=numero_boleta,
            rut=rut,
            rut_emisor=rut_emisor,
            monto=monto,
        )

        # Mostrar previsualización en modo prueba
        if modo_prueba:
            utils.print_section("📧 PREVISUALIZACIÓN DEL CORREO")
            utils.print_table(
                "Datos del envío",
                [
                    ("Asunto", asunto),
                    ("Destinatario", correo),
                    ("CC", EMAIL_COPIA if EMAIL_COPIA else "(vacío)"),
                    ("RUT Receptor", rut),
                    ("RUT Emisor", rut_emisor),
                    ("Número de Boleta", numero_boleta),
                    ("Monto Total", monto),
                ],
            )
            utils.print_separator()
            utils.print_info("Contenido completo del correo:")
            utils.console.print(cuerpo_html)
            utils.print_separator()
            enviados += 1
            break

        if dispatch_outbox is not None and ix in dispatch_outbox:
            ob_id = dispatch_outbox[ix]
        else:
            ob_id = email_outbox.record_pending(
                stage_id, item_key, {"boleta": numero_boleta, "to": correo}
            )
        try:
            if not bh_outlook_mail.send_html_mail_with_backoff(
                outlook,
                to=correo,
                cc=EMAIL_COPIA,
                subject=asunto,
                html_body=cuerpo_html,
                max_attempts=3,
                base_delay_s=1.5,
                backoff_factor=1.5,
                log_context=f"script5 boleta={numero_boleta}",
            ):
                raise RuntimeError("No se pudo enviar tras reintentos COM")
            email_outbox.mark_sent(ob_id)
            df.at[idx, 'Correo_Recepcion_Enviado'] = "Sí"
            idempotency_store.mark_success(
                stage_id,
                item_key,
                details=f"boleta={numero_boleta}",
            )
            logging.info(f"Correo enviado exitosamente a {correo} para boleta {numero_boleta}")
            utils.print_success(f"Correo enviado a {correo} (boleta {numero_boleta})")
            enviados += 1
            time.sleep(1)  # Pausa para no saturar Outlook
        except Exception as e:
            email_outbox.mark_failed(ob_id, str(e))
            df.at[idx, 'Correo_Recepcion_Enviado'] = f"❌ Error: {str(e)}"
            logging.error(f"Error enviando correo a {correo} para boleta {numero_boleta}: {e}")
            utils.print_error(f"Error enviando correo a {correo}: {e}")
            fallidos += 1

    # Guardar cambios en Excel (solo en modo real)
    if not modo_prueba:
        if guardar_hoja_excel_atomico(ruta_excel, sheet_name, df):
            utils.print_success("Excel actualizado con estado de envíos.")
            logging.info("Excel actualizado exitosamente.")
    else:
        utils.print_info("[🧪] Modo prueba: No se guardaron cambios en el Excel.")

    # Resumen final
    tipo_resumen = "PREVISUALIZACIÓN" if modo_prueba else "envíos"
    console.print(
        Panel.fit(
            f"[bold green]📊 Resumen de {tipo_resumen}:[/bold green]\n"
            f"✅ Enviados: {enviados}\n"
            f"❌ Fallidos: {fallidos}\n"
            f"⚠️ Omitidos: {omitidos}",
            style="bold blue",
        )
    )
    logging.info(f"Resumen: Enviados {enviados}, Fallidos {fallidos}, Omitidos {omitidos}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Envío de correos de recepción de boletas")
    parser.add_argument(
        '--force-resend',
        action='store_true',
        help='Ignora idempotencia y reenvía aunque el correo ya esté marcado como exitoso.',
    )
    utils.register_non_interactive_cli(parser, with_send=True)
    utils.register_period_args(parser)
    args = parser.parse_args()
    main(args)