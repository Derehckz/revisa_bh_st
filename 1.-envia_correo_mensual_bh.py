import os
import pandas as pd
from outlook_utils import conectar_outlook_app
import time
import logging
from tqdm import tqdm
from colorama import Fore, init as colorama_init
import tempfile
import shutil
import argparse

import config
import utils

# Inicializar colorama
colorama_init(autoreset=True)



def mostrar_previsualizacion(tipo_envio, cantidad_correos, mes, ano, df=None, indices=None):
    """
    Muestra una previsualización de las configuraciones y fecha que se usarán
    antes de enviar los correos.
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from datetime import datetime
    
    console = Console()
    
    # Crear tabla con configuraciones
    tabla = Table(title=f"⚙️ PREVISUALIZACIÓN - Envío {tipo_envio.upper()}", style="cyan")
    tabla.add_column("Configuración", style="bold yellow", width=30)
    tabla.add_column("Valor", style="bold white", width=50)
    
    tabla.add_row("📅 Fecha Límite de Recepción", f"[bold cyan]{config.ULT_FECHA_RECEPCION}[/bold cyan]")
    tabla.add_row("⏰ Horario Límite", f"[bold cyan]{config.HORARIO_RECEPCION}[/bold cyan]")
    tabla.add_row("📨 Correos a Enviar", f"[bold green]{cantidad_correos}[/bold green]")
    tabla.add_row("📍 Tipo de Envío", f"[bold magenta]{tipo_envio}[/bold magenta]")
    tabla.add_row("📆 Período", f"[bold cyan]{mes} {ano}[/bold cyan]")
    tabla.add_row("📧 Email Contabilidad", config.EMAIL_CONTABILIDAD)
    tabla.add_row("📧 Email XML Principal", config.EMAIL_XML_1)
    if config.EMAIL_XML_2:
        tabla.add_row("📧 Email XML Secundario", config.EMAIL_XML_2)
    
    console.print(tabla)
    
    # Mostrar muestra de destinatarios si hay
    if df is not None and indices is not None and len(indices) > 0:
        console.print("\n📋 [bold cyan]MUESTRA DE DESTINATARIOS ([yellow]{}/{} primeros[/yellow])[/bold cyan]".format(
            min(5, len(indices)), len(indices)
        ))
        tabla_dest = Table(style="dim white")
        tabla_dest.add_column("Docente", style="blue")
        tabla_dest.add_column("Correo", style="green")
        tabla_dest.add_column("RUT Razon", style="cyan")
        
        for i, idx in enumerate(indices[:5]):
            tabla_dest.add_row(
                df.at[idx, "NAME"],
                df.at[idx, "Email_Docente"],
                str(df.at[idx, "RUT RAZON"])
            )
        
        console.print(tabla_dest)
        
        if len(indices) > 5:
            console.print(f"[yellow]... y {len(indices) - 5} destinatarios más[/yellow]")


def enviar_correo(outlook, email_destino, email_cc, asunto, cuerpo_html, ruta_adjunto=None):
    mail = outlook.CreateItem(0)
    mail.To = email_destino
    mail.CC = email_cc
    mail.Subject = asunto
    mail.HTMLBody = cuerpo_html

    if ruta_adjunto and os.path.isfile(ruta_adjunto):
        mail.Attachments.Add(ruta_adjunto)

    mail.Send()

def enviar_correos(df, indices, tipo="original"):
    """
    Enviar correos segun el tipo: "original" o "recordatorio".
    Solo procesa las filas indicadas en indices.
    """
    outlook = conectar_outlook_app()
    columna_envio = 'Correo Enviado'

    for idx in tqdm(indices, desc=f"Enviando correos ({tipo})", unit="correo"):
        try:
            row = df.loc[idx]

            nombre_completo = row['NAME']
            rut_docente = row['EMPLID']
            rut_razon = row['RUT RAZON']
            razon_social = row['NOMBRE RAZON']
            direccion_razon = row['DireccionRazon']
            glosa = row['GLOSA']
            monto = row['CUS_TOT_HON']
            email = row['Email_Docente']
            email_dp = row.get('Email_DP')
            mes = str(row['MONTH']).upper()
            año = int(row['YEAR'])

            if tipo == "original":
                asunto = f"Solicitud Boleta Honorarios {mes} {año} - {rut_docente}-{nombre_completo}"
                cuerpo_html = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px;">
                    <div style="text-align: center; margin-bottom: 20px;">
                        <h1 style="color: #2E8B57; margin: 0;">📄 Solicitud de Boleta de Honorarios</h1>
                        <p style="color: #666; font-size: 16px; margin: 5px 0;">Proceso iniciado para {mes.capitalize()} {año}</p>
                    </div>

                    <div style="background-color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <p style="font-size: 18px; color: #333; margin-bottom: 15px;">
                            <b>Estimado(a) Sr(a). {nombre_completo}:</b>
                        </p>

                        <p style="font-size: 16px; line-height: 1.6; color: #555;">
                            Junto con saludar cordialmente, Le informamos que se ha iniciado el proceso de emisión de boletas de honorarios correspondientes al mes de <strong>{mes.capitalize()}</strong>. Las boletas serán recepcionadas <strong>hasta el día {config.ULT_FECHA_RECEPCION}, a las {config.HORARIO_RECEPCION}</strong> (plazo impostergable).
                        </p>

                        <div style="background-color: #e8f5e8; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #2E8B57;">
                            <h3 style="color: #2E8B57; margin: 0 0 10px 0;">📋 Instrucciones</h3>
                            <ol style="margin: 0; padding-left: 20px;">
                                <li>Emitir la boleta desde el portal del SII al correo: <strong>{config.EMAIL_CONTABILIDAD}</strong></li>
                                <li>Enviar copia de la boleta generada (en formato XML y PDF) a:<br>
                                    <strong>{config.EMAIL_XML_1}</strong><br>
                                    <strong>{config.EMAIL_XML_2}</strong></li>
                                <li>Respetar exactamente el <strong>RUT</strong>, <strong>dirección</strong>, <strong>glosa</strong> y <strong>monto</strong> indicados más abajo.</li>
                                <li>No modificar el nombre de los archivos adjuntos. Ejemplo: <code>bhe_11111111-1.pdf</code> o <code>.xml</code></li>
                            </ol>
                        </div>

                        <div style="background-color: #f8d7da; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #dc3545;">
                            <h3 style="color: #721c24; margin: 0 0 10px 0;">⚠️ Importante</h3>
                            <p style="margin: 0; color: #721c24;">
                                Si no se envía la copia XML de la boleta tanto a <strong>{config.EMAIL_CONTABILIDAD}</strong> como a <strong>{config.EMAIL_XML_1}</strong>, <strong>el documento no será considerado para pago</strong> en los plazos establecidos.
                            </p>
                        </div>

                        <div style="background-color: #d1ecf1; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #17a2b8;">
                            <h3 style="color: #0c5460; margin: 0 0 10px 0;">📄 Detalle del Docente</h3>
                            <ul style="list-style: none; padding: 0; margin: 0;">
                                <li style="margin-bottom: 8px;"><strong>🆔 RUT:</strong> {rut_docente}</li>
                                <li style="margin-bottom: 8px;"><strong>👤 Nombre:</strong> {nombre_completo}</li>
                            </ul>
                        </div>

                        <div style="background-color: #d1ecf1; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #17a2b8;">
                            <h3 style="color: #0c5460; margin: 0 0 10px 0;">💼 Datos para la emisión de la boleta</h3>
                            <ul style="list-style: none; padding: 0; margin: 0;">
                                <li style="margin-bottom: 8px;"><strong>🆔 RUT:</strong> {rut_razon}</li>
                                <li style="margin-bottom: 8px;"><strong>🏢 Razón Social:</strong> {razon_social}</li>
                                <li style="margin-bottom: 8px;"><strong>📍 Dirección:</strong> {direccion_razon}</li>
                                <li style="margin-bottom: 8px;"><strong>📝 Glosa:</strong> {glosa}</li>
                                <li style="margin-bottom: 8px;"><strong>💰 Monto:</strong> ${monto:,.0f}.-</li>
                            </ul>
                        </div>

                        <p style="font-size: 16px; line-height: 1.6; color: #555;">
                            La boleta debe ser emitida únicamente con los datos indicados. Cualquier diferencia podría generar el rechazo del documento.
                        </p>

                        <p style="font-size: 16px; line-height: 1.6; color: #555;">
                            Ante dudas sobre el detalle de su pago, puede contactar a su director(a) de programa al correo: <strong>{email_dp}</strong>
                        </p>

                        <div style="text-align: center; margin-top: 30px;">
                            <p style="font-size: 16px; color: #666; margin-bottom: 10px;">
                                💼 <strong>Equipo de Contabilidad</strong>
                            </p>
                            <p style="font-size: 14px; color: #999;">
                                Quedamos atentos a su envío 📤
                            </p>
                        </div>
                    </div>

                    <div style="text-align: center; font-size: 12px; color: #999; margin-top: 20px;">
                        <p>Este es un mensaje automático generado por el sistema de solicitudes.</p>
                        <p>Por favor, no responda directamente a este correo si no es necesario.</p>
                    </div>
                </div>
                """
            else:  # recordatorio
                asunto = f"Recordatorio: Solicitud Boleta Honorarios {mes} {año} - {rut_docente}-{nombre_completo}"
                cuerpo_html = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px;">
                    <div style="text-align: center; margin-bottom: 20px;">
                        <h1 style="color: #dc3545; margin: 0;">⏰ Recordatorio: Boleta de Honorarios</h1>
                        <p style="color: #666; font-size: 16px; margin: 5px 0;">Pendiente de envío para {mes.capitalize()} {año}</p>
                    </div>

                    <div style="background-color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <p style="font-size: 18px; color: #333; margin-bottom: 15px;">
                            <b>Estimado(a) Sr(a). {nombre_completo}:</b>
                        </p>

                        <p style="font-size: 16px; line-height: 1.6; color: #555;">
                            Hasta la fecha no hemos recibido la Boleta de Honorarios en formato XML y PDF correspondiente al mes de <strong>{mes.capitalize()}</strong>.
                        </p>

                        <div style="background-color: #f8d7da; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #dc3545;">
                            <h3 style="color: #721c24; margin: 0 0 10px 0;">⚠️ Urgente</h3>
                            <p style="margin: 0; color: #721c24;">
                                Le solicitamos enviar la boleta antes del <strong>{config.ULT_FECHA_RECEPCION}</strong>, a las <strong>{config.HORARIO_RECEPCION}</strong>. De no hacerlo, lamentablemente no podrá ser procesado su pago en los plazos establecidos.
                            </p>
                        </div>

                        <div style="background-color: #e8f5e8; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #2E8B57;">
                            <h3 style="color: #2E8B57; margin: 0 0 10px 0;">📋 Instrucciones</h3>
                            <ol style="margin: 0; padding-left: 20px;">
                                <li>Emitir la boleta desde el portal del SII al correo: <strong>{config.EMAIL_CONTABILIDAD}</strong></li>
                                <li>Enviar copia de la boleta generada (en formato XML y PDF) a:<br>
                                    <strong>{config.EMAIL_XML_1}</strong><br>
                                    <strong>{config.EMAIL_XML_2}</strong></li>
                                <li>Respetar exactamente el <strong>RUT</strong>, <strong>dirección</strong>, <strong>glosa</strong> y <strong>monto</strong> indicados más abajo.</li>
                                <li>No modificar el nombre de los archivos adjuntos. Ejemplo: <code>bhe_11111111-1.pdf</code> o <code>.xml</code></li>
                            </ol>
                        </div>

                        <div style="background-color: #f8d7da; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #dc3545;">
                            <h3 style="color: #721c24; margin: 0 0 10px 0;">⚠️ Importante</h3>
                            <p style="margin: 0; color: #721c24;">
                                Si no se envía la copia XML de la boleta tanto a <strong>{config.EMAIL_CONTABILIDAD}</strong> como a <strong>{config.EMAIL_XML_1}</strong>, <strong>el documento no será considerado para pago</strong> en los plazos establecidos.
                            </p>
                        </div>

                        <div style="background-color: #d1ecf1; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #17a2b8;">
                            <h3 style="color: #0c5460; margin: 0 0 10px 0;">📄 Detalle del Docente</h3>
                            <ul style="list-style: none; padding: 0; margin: 0;">
                                <li style="margin-bottom: 8px;"><strong>🆔 RUT:</strong> {rut_docente}</li>
                                <li style="margin-bottom: 8px;"><strong>👤 Nombre:</strong> {nombre_completo}</li>
                            </ul>
                        </div>

                        <div style="background-color: #d1ecf1; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #17a2b8;">
                            <h3 style="color: #0c5460; margin: 0 0 10px 0;">💼 Datos para la emisión de la boleta</h3>
                            <ul style="list-style: none; padding: 0; margin: 0;">
                                <li style="margin-bottom: 8px;"><strong>🆔 RUT:</strong> {rut_razon}</li>
                                <li style="margin-bottom: 8px;"><strong>🏢 Razón Social:</strong> {razon_social}</li>
                                <li style="margin-bottom: 8px;"><strong>📍 Dirección:</strong> {direccion_razon}</li>
                                <li style="margin-bottom: 8px;"><strong>📝 Glosa:</strong> {glosa}</li>
                                <li style="margin-bottom: 8px;"><strong>💰 Monto:</strong> ${monto:,.0f}.-</li>
                            </ul>
                        </div>

                        <p style="font-size: 16px; line-height: 1.6; color: #555;">
                            Ante dudas sobre el detalle de su pago, puede contactar a su director(a) de programa al correo: <strong>{email_dp}</strong>
                        </p>

                        <div style="text-align: center; margin-top: 30px;">
                            <p style="font-size: 16px; color: #666; margin-bottom: 10px;">
                                💼 <strong>Equipo de Convenio Los Lagos</strong>
                            </p>
                            <p style="font-size: 14px; color: #999;">
                                Quedamos atentos a su envío 📤
                            </p>
                        </div>
                    </div>

                    <div style="text-align: center; font-size: 12px; color: #999; margin-top: 20px;">
                        <p>Este es un mensaje automático generado por el sistema de recordatorios.</p>
                        <p>Por favor, no responda directamente a este correo si no es necesario.</p>
                    </div>
                </div>
                """

            cc_list = [config.EMAIL_XML_2]
            if isinstance(email_dp, str) and utils.validar_email(email_dp):
                cc_list.append(email_dp)
            cc_combined = "; ".join(cc_list)

            if isinstance(email, str) and utils.validar_email(email):
                enviado = False
                for intento in range(3):
                    try:
                        enviar_correo(outlook, email, cc_combined, asunto, cuerpo_html, ruta_adjunto=config.ARCHIVO_ADJUNTO if tipo=="original" else None)
                        enviado = True
                        break
                    except Exception as e:
                        logging.warning(f"Intento {intento+1} fallido para {email}: {e}")
                        time.sleep(2)

                if enviado:
                    if tipo == "original":
                        df.at[idx, columna_envio] = "✅ Enviado (original)"
                    else:
                        df.at[idx, columna_envio] = "✅ Enviado (recordatorio)"

                    logging.info(f"Correo ({tipo}) enviado a {email} (fila {idx+1})")
                    print(Fore.GREEN + f"[✅] Correo ({tipo}) enviado a {email} (fila {idx+1})")
                else:
                    df.at[idx, columna_envio] = f"❌ Error envío ({tipo})"
                    logging.error(f"No se pudo enviar el correo ({tipo}) a {email} después de 3 intentos")
                    print(Fore.RED + f"[❌] No se pudo enviar el correo ({tipo}) a {email} (fila {idx+1})")

            else:
                df.at[idx, columna_envio] = f"❌ Correo inválido ({tipo})"
                logging.warning(f"Correo inválido ({tipo}) en fila {idx+1}: {email}")
                print(Fore.YELLOW + f"[❌] Correo inválido ({tipo}) en fila {idx+1}: {email}")

            time.sleep(1.5)

        except Exception as e:
            df.at[idx, columna_envio] = f"❌ Error: {e} ({tipo})"
            logging.error(f"Error inesperado ({tipo}) en fila {idx+1}: {e}")
            print(Fore.RED + f"[❌] Fila {idx+1}: {e} ({tipo})")

def main(args):
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    import utils

    console = Console()

    console.print(Panel.fit("🚀 [bold cyan]INICIO DE PROCESO DE ENVÍO DE CORREOS[/bold cyan]\nBoletas de Honorarios", style="bold green", padding=(1, 2)))

    if not os.path.isfile(config.ARCHIVO_ADJUNTO):
        console.print(f"[red]❌ Archivo adjunto no encontrado: {config.ARCHIVO_ADJUNTO}[/red]")
        return

    if args.year and args.month:
        ano_seleccionado = args.year
        mes_seleccionado = args.month
        ruta_mes = os.path.join(config.RAIZ, ano_seleccionado, mes_seleccionado)
        if not os.path.exists(ruta_mes):
            console.print(f"[red]❌ Ruta no existe: {ruta_mes}[/red]")
            return
    else:
        try:
            ano_seleccionado, mes_seleccionado = utils.seleccionar_año_mes(config.RAIZ)
        except ValueError as e:
            console.print(f"[red]❌ {e}[/red]")
            return
        ruta_mes = os.path.join(config.RAIZ, ano_seleccionado, mes_seleccionado)
    archivos = [f for f in os.listdir(ruta_mes) if f.lower().endswith('.xlsx')]
    if not archivos:
        console.print(f"[red]❌ No se encontró archivo Excel en {ruta_mes}[/red]")
        return
    archivo_excel = archivos[0] if len(archivos) == 1 else utils.seleccionar_opcion(archivos, "Seleccione el archivo Excel")

    ruta_archivo_excel = os.path.join(ruta_mes, archivo_excel)
    ruta_logs = os.path.join(ruta_mes, "logs_envios")
    os.makedirs(ruta_logs, exist_ok=True)
    ruta_log_file = os.path.join(ruta_logs, "envio_boletas.log")

    utils.configurar_logging(ruta_log_file)

    try:
        xls = pd.ExcelFile(ruta_archivo_excel, engine='openpyxl')
        hojas = xls.sheet_names
    except (OSError, ValueError, KeyError) as e:
        console.print(f"[red]❌ Error al leer el Excel: {e}[/red]")
        return

    hoja_seleccionada = utils.seleccionar_opcion(hojas, "Seleccione la hoja del Excel para validar")
    df = pd.read_excel(ruta_archivo_excel, sheet_name=hoja_seleccionada, engine='openpyxl')

    columna_envio = 'Correo Enviado'
    columna_estado = 'Estado_Recepcion'

    if columna_envio not in df.columns:
        df[columna_envio] = ""
    df[columna_envio] = df[columna_envio].astype(object)

    if columna_estado not in df.columns:
        console.print(f"[red]❌ No se encontró la columna '{columna_estado}' en el archivo Excel.[/red]")
        return

    console.print(f"\n📨 [bold]Iniciando análisis de {len(df)} filas...[/bold]")

    envio_col = df[columna_envio].astype(str).str.lower().str.strip()
    # Normalizar columna de estado para búsquedas más robustas
    estado_col = df[columna_estado].astype(str).str.lower().str.strip()

    # Pendientes de envío original: no enviado original ni recordatorio y NO están marcados como recibidos
    indices_sin_envio = df[
        ~envio_col.str.contains(r"enviado \(original\)", na=False) &
        ~envio_col.str.contains(r"enviado \(recordatorio\)", na=False) &
        ~estado_col.str.contains(r"\brecibido\b", na=False)
    ].index

    # Selecciona todos los que están en estado "no recibido" (permitiendo reenvíos de recordatorios)
    indices_recordatorio = df[
        estado_col.str.contains(r"no\s*recibido", na=False)
    ].index

    # Ayuda rápida si no se encontró ninguna fila como 'no recibido'
    if len(indices_recordatorio) == 0:
        unique_vals = df[columna_estado].astype(str).str.strip().value_counts().head(10)
        console.print(f"[yellow]⚠️ No se encontraron filas con estado 'no recibido'. Valores únicos más comunes en '{columna_estado}':[/yellow]")
        for val, cnt in unique_vals.items():
            console.print(f"  {cnt}x -> {val}")

    console.print(f"\n📧 [blue]Pendientes de envío original:[/blue] [bold]{len(indices_sin_envio)}[/bold]")
    console.print(f"🔁 [magenta]Pendientes para recordatorio:[/magenta] [bold]{len(indices_recordatorio)}[/bold]")

    if len(indices_recordatorio) > 0:
        tabla = Table(title="📋 Destinatarios para RECORDATORIO", style="magenta")
        tabla.add_column("N°", justify="center", style="cyan")
        tabla.add_column("Nombre", style="white")
        tabla.add_column("Correo", style="green")
        tabla.add_column("Prev. Recordatorio", style="yellow", justify="center")
        for i, idx in enumerate(indices_recordatorio, 1):
            prev = "Sí" if "recordatorio" in str(df.at[idx, columna_envio]).lower() else "No"
            tabla.add_row(str(i), df.at[idx, "NAME"], df.at[idx, "Email_Docente"], prev)
        console.print(tabla)

    # Confirmación envío original
    console.print("\n🤖 ¿Desea continuar con el [bold]envío de correos originales[/bold]? ([green]s[/green]/[red]n[/red])")
    if len(indices_sin_envio) > 0:
        console.print(f"\n[bold cyan]Mostrando previsualización antes de enviar...[/bold cyan]")
        mostrar_previsualizacion("correo original", len(indices_sin_envio), mes_seleccionado, ano_seleccionado, df, indices_sin_envio)
        console.print("\n🤖 ¿Desea [bold cyan]CONFIRMAR[/bold cyan] el envío de [bold green]{} correos originales[/bold green]? ([green]s[/green]/[red]n[/red])".format(len(indices_sin_envio)))
        if input("➡️ Respuesta: ").strip().lower() == 's':
            enviar_correos(df, indices_sin_envio, tipo="original")
        else:
            console.print("[yellow]🚫 Envío cancelado por el usuario.[/yellow]")
    else:
        console.print("[yellow]⚠️ No hay correos pendientes para envío original.[/yellow]")

    # Confirmación envío recordatorio
    if len(indices_recordatorio) > 0:
        console.print("\n🤖 ¿Desea enviar/re-enviar [bold]recordatorios[/bold] a los que aún no han enviado la boleta? ([green]s[/green]/[red]n[/red])")
        console.print(f"\n[bold cyan]Mostrando previsualización antes de enviar...[/bold cyan]")
        mostrar_previsualizacion("recordatorio", len(indices_recordatorio), mes_seleccionado, ano_seleccionado, df, indices_recordatorio)
        console.print("\n🤖 ¿Desea [bold cyan]CONFIRMAR[/bold cyan] el envío de [bold magenta]{} recordatorios[/bold magenta]? ([green]s[/green]/[red]n[/red])".format(len(indices_recordatorio)))
        if input("➡️ Respuesta: ").strip().lower() == 's':
            enviar_correos(df, indices_recordatorio, tipo="recordatorio")
        else:
            console.print("[yellow]🚫 Envío de recordatorios cancelado por el usuario.[/yellow]")
    else:
        console.print("[yellow]⚠️ No hay destinatarios para recordatorio.[/yellow]")

    # Guardar Excel actualizado
    try:
        # Hacer backup del archivo existente antes de sobrescribir
        try:
            utils.backup_file(ruta_archivo_excel)
        except OSError:
            pass

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx").name
        with pd.ExcelWriter(temp_file, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=hoja_seleccionada)
        shutil.move(temp_file, ruta_archivo_excel)
        console.print(Panel.fit(f"✅ Archivo guardado correctamente en:\n[green]{ruta_archivo_excel}[/green]", style="bold green"))
        logging.info(f"Archivo guardado correctamente en {ruta_archivo_excel}")
    except (OSError, IOError, PermissionError) as e:
        console.print(Panel.fit(f"❌ Error al guardar archivo Excel:\n{e}", style="bold red"))
        logging.error(f"Error al guardar archivo Excel: {e}")

    console.print(Panel.fit("🎯 [bold cyan]PROCESO FINALIZADO EXITOSAMENTE[/bold cyan]", style="bold blue", padding=(1, 2)))
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Envío de correos de boletas de honorarios")
    parser.add_argument('--year', type=str, help='Año específico')
    parser.add_argument('--month', type=str, help='Mes específico')
    args = parser.parse_args()
    main(args)
