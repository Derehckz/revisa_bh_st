import os
import pandas as pd
from outlook_utils import conectar_outlook_app
import time
import logging
from rich.panel import Panel
import config
import utils
import email_templates as templates

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
    utils.print_header("📧 ENVÍO DE CORREOS DE RECEPCIÓN", "Boletas de Honorarios")

    # Modo de prueba
    modo_prueba = utils.prompt_yes_no_s("¿Modo de prueba? (s/n) - No envía correos ni modifica Excel")
    if modo_prueba:
        utils.print_warning("MODO DE PRUEBA ACTIVADO - No se enviarán correos ni se modificará el Excel")

    # Selección año/mes
    años = listar_carpetas_validas(RAIZ)
    if not años:
        utils.print_error("No hay carpetas de año en la ruta configurada.")
        return
    año = seleccionar_opcion(sorted(años), "Seleccione el año:", "🗓️")
    ruta_año = os.path.join(RAIZ, año)

    meses = listar_carpetas_validas(ruta_año)
    if not meses:
        utils.print_error(f"No hay carpetas de mes en {ruta_año}")
        return
    mes = seleccionar_opcion(sorted(meses), "Seleccione el mes:", "🗓️")
    ruta_mes = os.path.join(ruta_año, mes)

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

    # Leer Excel (hoja principal, asumiendo "Solicitud" o primera)
    try:
        df = pd.read_excel(ruta_excel, engine='openpyxl')
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

    for idx, fila in df_filtrado.iterrows():
        # Verificar si ya fue enviado
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
        if pd.notna(monto):
            monto = f"${float(monto):,.0f}"

        if not utils.validar_email(correo):
            df.at[idx, 'Correo_Recepcion_Enviado'] = "❌ Correo inválido"
            logging.warning(f"Correo inválido: {correo} para boleta {numero_boleta}")
            utils.print_error(f"Correo inválido: {correo}")
            fallidos += 1
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

        try:
            enviar_correo(outlook, correo, EMAIL_COPIA, asunto, cuerpo_html)
            df.at[idx, 'Correo_Recepcion_Enviado'] = "Sí"
            logging.info(f"Correo enviado exitosamente a {correo} para boleta {numero_boleta}")
            utils.print_success(f"Correo enviado a {correo} (boleta {numero_boleta})")
            enviados += 1
            time.sleep(1)  # Pausa para no saturar Outlook
        except Exception as e:
            df.at[idx, 'Correo_Recepcion_Enviado'] = f"❌ Error: {str(e)}"
            logging.error(f"Error enviando correo a {correo} para boleta {numero_boleta}: {e}")
            utils.print_error(f"Error enviando correo a {correo}: {e}")
            fallidos += 1

    # Guardar cambios en Excel (solo en modo real)
    if not modo_prueba:
        try:
            with pd.ExcelWriter(ruta_excel, engine='openpyxl', mode='w') as writer:
                df.to_excel(writer, index=False)
            utils.print_success("Excel actualizado con estado de envíos.")
            logging.info("Excel actualizado exitosamente.")
        except Exception as e:
            utils.print_error(f"Error guardando Excel: {e}")
            logging.error(f"Error guardando Excel: {e}")
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
    main()