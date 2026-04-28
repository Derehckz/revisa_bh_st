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

        asunto = f"[Importante] Información de pago de honorarios - {mes_año_pago}"
        cuerpo_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px;">
            <div style="text-align: center; margin-bottom: 20px;">
                <h1 style="color: #2E8B57; margin: 0;">💰 ¡Información de Pago Disponible!</h1>
                <p style="color: #666; font-size: 16px; margin: 5px 0;">Su depósito será realizado próximamente</p>
            </div>

            <div style="background-color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <p style="font-size: 18px; color: #333; margin-bottom: 15px;">
                    <b>Estimado(a) {nombre}:</b>
                </p>

                <p style="font-size: 16px; line-height: 1.6; color: #555;">
                    Le informamos que su pago de honorarios correspondiente al período <strong>{mes_año_pago}</strong> se realizará el día <strong>{fecha_pago}</strong>.
                </p>

                <div style="background-color: #e8f5e8; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #2E8B57;">
                    <h3 style="color: #2E8B57; margin: 0 0 10px 0;">📌 Detalle de depósito</h3>
                    <ul style="list-style: none; padding: 0; margin: 0;">
                        <li style="margin-bottom: 8px;"><strong>🏦 Banco:</strong> {banco}</li>
                        <li style="margin-bottom: 8px;"><strong>💳 Tipo de cuenta:</strong> {tipo_cuenta}</li>
                        <li style="margin-bottom: 8px;"><strong>🔢 Número de cuenta:</strong> {nro_cuenta}</li>
                        <li style="margin-bottom: 8px;"><strong>💰 Monto a depositar:</strong> ${monto:,.0f}</li>
                    </ul>
                </div>

                <div style="background-color: #fff3cd; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #ffc107;">
                    <h3 style="color: #856404; margin: 0 0 10px 0;">⚠️ Información Importante</h3>
                    <ul style="margin: 0; padding-left: 20px; color: #856404;">
                        <li>Por favor, verifique que los datos de su cuenta sean correctos.</li>
                        <li>Ante cualquier inconsistencia, informar por medio de este correo.</li>
                        <li>Por favor, se solicita no anular BH.</li>
                    </ul>
                </div>

                <div style="text-align: center; margin-top: 30px;">
                    <p style="font-size: 16px; color: #666; margin-bottom: 10px;">
                        💼 <strong>Equipo Convenio Los Lagos</strong>
                    </p>
                    <p style="font-size: 14px; color: #999;">
                        Gracias por su dedicación y profesionalismo 👏
                    </p>
                </div>
            </div>

            <div style="text-align: center; font-size: 12px; color: #999; margin-top: 20px;">
                <p>Este es un mensaje automático generado por el sistema de pagos.</p>
                <p>Por favor, no responda directamente a este correo si no es necesario.</p>
            </div>
        </div>
        """
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
