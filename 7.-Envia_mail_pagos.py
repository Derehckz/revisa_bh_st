import os
import pandas as pd
from outlook_utils import conectar_outlook_app
import time
import logging
from rich.console import Console
from rich.panel import Panel
from colorama import init as colorama_init, Fore
import config
import utils
import email_templates as templates

colorama_init(autoreset=True)
console = Console()

RAIZ = config.RAIZ
LOG_FOLDER_NAME = "logs_envios_pagos"

# =========================
# Configuración de correo
# =========================
EMAIL_COPIA = ""  # puedes agregar CC si quieres

# =========================
# Funciones auxiliares
# =========================

def seleccionar_opcion(lista, mensaje, icono=""):
    return utils.seleccionar_opcion(lista, mensaje, icono)


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
    console.print(Panel.fit("[bold cyan]📂 Selección de Excel y envío de correos de pagos[/bold cyan]", style="bold green"))

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
    mes_año_pago = f"{mes} {año}"

    # Archivo Excel
    ruta_excel = os.path.join(ruta_mes, "Solicitud.xlsx")
    if not os.path.isfile(ruta_excel):
        console.print(Panel.fit(f"[red]⚠️ No se encontró archivo Excel en {ruta_excel}[/red]", style="bold red"))
        return

    # Carpeta de logs
    ruta_logs = os.path.join(ruta_mes, LOG_FOLDER_NAME)
    os.makedirs(ruta_logs, exist_ok=True)
    ruta_log_file = os.path.join(ruta_logs, "envio_pagos.log")
    logging.basicConfig(filename=ruta_log_file, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    for handler in logging.root.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.setLevel(logging.INFO)
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            handler.encoding = 'utf-8'

    # Fecha de pago
    fecha_pago = console.input("[green]📅 Ingrese la fecha de pago (ej: 05/09/2025): [/green]").strip()

    # Leer hoja "Pagos"
    try:
        df = pd.read_excel(ruta_excel, sheet_name="Pagos", engine='openpyxl')
    except (OSError, ValueError, KeyError) as e:
        console.print(Panel.fit(f"[red]❌ Error leyendo hoja 'Pagos': {e}[/red]", style="bold red"))
        return

    if "MAIL" not in df.columns:
        console.print(Panel.fit("[red]❌ No se encontró la columna 'MAIL' en la hoja 'Pagos'.[/red]", style="bold red"))
        return

    # Agregar columna de control de envío
    if 'Correo Enviado' not in df.columns:
        df['Correo Enviado'] = ""

    outlook = conectar_outlook_app()

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
            enviar_correo(outlook, correo, EMAIL_COPIA, asunto, cuerpo_html)
            df.at[idx, 'Correo Enviado'] = "✅ Enviado"
            logging.info(f"Correo enviado a {correo} fila {idx+1}")
            console.print(Fore.GREEN + f"[✅] Correo enviado a {correo}")
            time.sleep(1)  # breve pausa para no saturar Outlook
        except Exception as e:
            df.at[idx, 'Correo Enviado'] = f"❌ Error: {e}"
            logging.error(f"No se pudo enviar correo a {correo} fila {idx+1}: {e}")
            console.print(Fore.RED + f"[❌] Error enviando correo a {correo}: {e}")

    # Guardar cambios en Excel
    try:
        # Backup previo del Excel antes de sobrescribir
        try:
            utils.backup_file(ruta_excel)
        except OSError:
            pass
        with pd.ExcelWriter(ruta_excel, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df.to_excel(writer, index=False, sheet_name="Pagos")
        console.print(Panel.fit(f"[green]✔️ Hoja 'Pagos' sobrescrita correctamente en {ruta_excel}[/green]", style="bold green"))
        logging.info(f"Excel actualizado correctamente en {ruta_excel}")
    except (OSError, IOError, PermissionError) as e:
        console.print(Panel.fit(f"[red]❌ Error guardando Excel: {e}[/red]", style="bold red"))
        logging.error(f"Error guardando Excel: {e}")

    console.print(Panel.fit("[bold cyan]🎯 PROCESO FINALIZADO[/bold cyan]", style="bold blue"))

if __name__ == "__main__":
    main()
