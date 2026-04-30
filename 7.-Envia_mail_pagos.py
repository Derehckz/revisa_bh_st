import os
import pandas as pd
from outlook_utils import conectar_outlook_app
import time
import logging
import config
import utils
import email_templates as templates
import schema_validator
import idempotency_store

RAIZ = config.RAIZ
LOG_FOLDER_NAME = "logs_envios_pagos"

# =========================
# Configuración de correo
# =========================
EMAIL_COPIA = ""  # puedes agregar CC si quieres

# =========================
# Funciones auxiliares
# =========================

def enviar_correo(outlook, email_destino, cc, asunto, cuerpo_html):
    mail = outlook.CreateItem(0)
    mail.To = email_destino
    mail.CC = cc
    mail.Subject = asunto
    mail.HTMLBody = cuerpo_html
    mail.Send()

# =========================
# Función principal
# =========================

def main():
    utils.print_header("📂 Selección de Excel y envío de correos de pagos", "Cargando configuración de envíos")
    utils.print_step(1, 4, "Preparando contexto de ejecución")

    # Selección año/mes
    try:
        año, mes = utils.seleccionar_año_mes(RAIZ)
    except ValueError as e:
        utils.print_error(str(e))
        return
    ruta_mes = os.path.join(RAIZ, año, mes)
    mes_año_pago = f"{mes} {año}"

    # Archivo Excel
    ruta_excel = os.path.join(ruta_mes, "Solicitud.xlsx")
    if not os.path.isfile(ruta_excel):
        utils.print_error(f"No se encontró archivo Excel en {ruta_excel}")
        return

    # Carpeta de logs
    ruta_logs = os.path.join(ruta_mes, LOG_FOLDER_NAME)
    os.makedirs(ruta_logs, exist_ok=True)
    ruta_log_file = os.path.join(ruta_logs, "envio_pagos.log")
    utils.configurar_logging(ruta_log_file)
    logging.info(f"🧭 run_id={utils.get_run_id()} correlation_id={utils.get_correlation_id()}")

    # Fecha de pago
    fecha_pago = utils.prompt_required("📅 Ingrese la fecha de pago (ej: 05/09/2025)")

    # Leer hoja "Pagos"
    utils.print_step(2, 4, "Cargando hoja de pagos")
    try:
        df = pd.read_excel(ruta_excel, sheet_name="Pagos", engine='openpyxl')
    except (OSError, ValueError, KeyError) as e:
        utils.print_error(f"Error leyendo hoja 'Pagos': {e}")
        return

    if "MAIL" not in df.columns:
        utils.print_error("No se encontró la columna 'MAIL' en la hoja 'Pagos'.")
        return

    schema_issues = []
    schema_issues.extend(
        schema_validator.validate_required_columns(
            df.columns,
            ["MAIL", "Nombre", "ID", "BANCO", "FORMA PAGO", "NªCUENTA", "Boleta", "LÍQUIDO"],
        )
    )
    for warning_line in schema_validator.format_issues(schema_issues, "script7"):
        logging.warning(warning_line)
        utils.print_warning(warning_line)

    # Agregar columna de control de envío
    if 'Correo Enviado' not in df.columns:
        df['Correo Enviado'] = ""

    outlook = conectar_outlook_app()

    utils.print_step(3, 4, "Enviando correos")
    for idx, fila in df.iterrows():
        correo = str(fila.get("MAIL", "")).strip()
        nombre = fila.get("Nombre", "")
        rut = fila.get("ID", "")
        banco = fila.get("BANCO", "")
        tipo_cuenta = fila.get("FORMA PAGO", "")
        nro_cuenta = fila.get("NªCUENTA", "")
        if pd.notna(nro_cuenta):
            nro_cuenta = str(int(nro_cuenta))
        else:
            nro_cuenta = ""
        n_boleta = fila.get("Boleta","")
        monto = fila.get("LÍQUIDO", 0)

        if not utils.validar_email(correo):
            df.at[idx, 'Correo Enviado'] = "❌ Correo inválido"
            logging.warning(f"Correo inválido: {correo} fila {idx+1}")
            utils.print_warning(f"Correo inválido en fila {idx+1}: {correo}")
            continue

        asunto = templates.generar_asunto_pago(nombre, mes_año_pago)
        cuerpo_html = templates.generar_cuerpo_pago(
            nombre=nombre,
            mes_año_pago=mes_año_pago,
            fecha_pago=fecha_pago,
            banco=banco,
            tipo_cuenta=tipo_cuenta,
            nro_cuenta=nro_cuenta,
            monto=monto,
        )

        try:
            item_key = f"{mes_año_pago}|{rut}|{correo}".lower()
            if idempotency_store.report_duplicate("script7.mail_attempt", item_key):
                logging.warning(f"Duplicado detectado (solo reporte): {item_key}")
            enviar_correo(outlook, correo, EMAIL_COPIA, asunto, cuerpo_html)
            df.at[idx, 'Correo Enviado'] = "✅ Enviado"
            logging.info(f"Correo enviado a {correo} fila {idx+1}")
            utils.print_success(f"Correo enviado a {correo}")
            time.sleep(1)  # breve pausa para no saturar Outlook
        except Exception as e:
            df.at[idx, 'Correo Enviado'] = f"❌ Error: {e}"
            logging.error(f"No se pudo enviar correo a {correo} fila {idx+1}: {e}")
            utils.print_error(f"Error enviando correo a {correo}: {e}")

    # Guardar cambios en Excel
    utils.print_step(4, 4, "Guardando resultados en Excel")
    try:
        # Backup previo del Excel antes de sobrescribir
        try:
            utils.backup_file(ruta_excel)
        except OSError:
            pass
        with pd.ExcelWriter(ruta_excel, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df.to_excel(writer, index=False, sheet_name="Pagos")
        utils.print_success(f"Hoja 'Pagos' sobrescrita correctamente en {ruta_excel}")
        logging.info(f"Excel actualizado correctamente en {ruta_excel}")
    except (OSError, IOError, PermissionError) as e:
        utils.print_error(f"Error guardando Excel: {e}")
        logging.error(f"Error guardando Excel: {e}")

    utils.print_header("🎯 PROCESO FINALIZADO", "Envío de correos completado")

if __name__ == "__main__":
    main()
