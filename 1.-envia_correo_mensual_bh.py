import os
import pandas as pd
import win32com.client as win32
import time
import logging
from tqdm import tqdm
from colorama import Fore, init as colorama_init
import tempfile
import shutil

import config
import utils

# Inicializar colorama
colorama_init(autoreset=True)


def listar_carpetas(ruta):
    try:
        return [d for d in os.listdir(ruta) if os.path.isdir(os.path.join(ruta, d))]
    except OSError as e:
        logging.error(f"Error accediendo a {ruta}: {e}")
        print(Fore.RED + f"❌ Error accediendo a {ruta}: {e}")
        return []

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
    outlook = win32.Dispatch('Outlook.Application')
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
                    <p><b>Estimado(a) Sr(a). {nombre_completo}:</b></p>

                    <p>Junto con saludar cordialmente, Le informamos que se ha iniciado el proceso de emisión de boletas de honorarios correspondientes al mes de <b>{mes.capitalize()}</b>. Las boletas serán recepcionadas <b>hasta el día {config.ULT_FECHA_RECEPCION}, a las {config.HORARIO_RECEPCION}</b> (plazo impostergable).</p>

                    <hr>
                    <h3>📌 Instrucciones</h3>
                    <ol>
                        <li>Emitir la boleta desde el portal del SII al correo: <b>{config.EMAIL_CONTABILIDAD}</b></li>
                        <li>Enviar copia de la boleta generada (en formato XML y PDF) a:<br>
                            <b>{config.EMAIL_XML_1}</b><br>
                            <b>{config.EMAIL_XML_2}</b></li>
                        <li>Respetar exactamente el <b>RUT</b>, <b>dirección</b>, <b>glosa</b> y <b>monto</b> indicados más abajo.</li>
                        <li>No modificar el nombre de los archivos adjuntos. Ejemplo: <code>bhe_11111111-1.pdf</code> o <code>.xml</code></li>
                    </ol>

                    <hr>
                    <h3>⚠️ Importante</h3>
                    <p>Si no se envía la copia XML de la boleta tanto a <b>{config.EMAIL_CONTABILIDAD}</b> como a <b>{config.EMAIL_XML_1}</b>, <b>el documento no será considerado para pago</b> en los plazos establecidos.</p>

                    <hr>
                    <h3>📄 Detalle del Docente</h3>
                    <ul>
                        <li><b>RUT:</b> {rut_docente}</li>
                        <li><b>Nombre:</b> {nombre_completo}</li>
                    </ul>

                    <h3>💼 Datos para la emisión de la boleta</h3>
                    <ul>
                        <li><b>RUT:</b> {rut_razon}</li>
                        <li><b>Razón Social:</b> {razon_social}</li>
                        <li><b>Dirección:</b> {direccion_razon}</li>
                        <li><b>Glosa:</b> {glosa}</li>
                        <li><b>Monto:</b> ${monto:,.0f}.-</li>
                    </ul>

                    <p>La boleta debe ser emitida únicamente con los datos indicados. Cualquier diferencia podría generar el rechazo del documento.</p>

                    <p>Ante dudas sobre el detalle de su pago, puede contactar a su director(a) de programa al correo: <b>{email_dp}</b></p>

                    <p>Quedamos atentos a su envío.</p>

                    <p>Saludos cordiales,</p>
                    """
            else:  # recordatorio
                asunto = f"Recordatorio: Solicitud Boleta Honorarios {mes} {año} - {rut_docente}-{nombre_completo}"
                cuerpo_html = f"""
                    <p><b>Estimado(a) Sr(a). {nombre_completo}:</b></p>

                    <p>Hasta la fecha no hemos recibido la Boleta de Honorarios en formato XML y PDF correspondiente al mes de <b>{mes.capitalize()}</b>.</p>
                    <p>Le solicitamos enviar la boleta antes del <b>{config.ULT_FECHA_RECEPCION}</b>, a las <b>{config.HORARIO_RECEPCION}</b>. De no hacerlo, lamentablemente no podrá ser procesado su pago en los plazos establecidos.</p>

                    <hr>
                    <h3>📌 Instrucciones</h3>
                    <ol>
                        <li>Emitir la boleta desde el portal del SII al correo: <b>{config.EMAIL_CONTABILIDAD}</b></li>
                        <li>Enviar copia de la boleta generada (en formato XML y PDF) a:<br>
                            <b>{config.EMAIL_XML_1}</b><br>
                            <b>{config.EMAIL_XML_2}</b></li>
                        <li>Respetar exactamente el <b>RUT</b>, <b>dirección</b>, <b>glosa</b> y <b>monto</b> indicados más abajo.</li>
                        <li>No modificar el nombre de los archivos adjuntos. Ejemplo: <code>bhe_11111111-1.pdf</code> o <code>.xml</code></li>
                    </ol>

                    <hr>
                    <h3>⚠️ Importante</h3>
                    <p>Si no se envía la copia XML de la boleta tanto a <b>{config.EMAIL_CONTABILIDAD}</b> como a <b>{config.EMAIL_XML_1}</b>, <b>el documento no será considerado para pago</b> en los plazos establecidos.</p>

                    <hr>
                    <h3>📄 Detalle del Docente</h3>
                    <ul>
                        <li><b>RUT:</b> {rut_docente}</li>
                        <li><b>Nombre:</b> {nombre_completo}</li>
                    </ul>

                    <h3>💼 Datos para la emisión de la boleta</h3>
                    <ul>
                        <li><b>RUT:</b> {rut_razon}</li>
                        <li><b>Razón Social:</b> {razon_social}</li>
                        <li><b>Dirección:</b> {direccion_razon}</li>
                        <li><b>Glosa:</b> {glosa}</li>
                        <li><b>Monto:</b> ${monto:,.0f}.-</li>
                    </ul>

                    <p>Ante dudas sobre el detalle de su pago, puede contactar a su director(a) de programa al correo: <b>{email_dp}</b></p>

                    <p>Quedamos atentos a su envío.</p>

                    <p>Saludos cordiales,</p>
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

def main():
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    import utils

    console = Console()

    console.print(Panel.fit("🚀 [bold cyan]INICIO DE PROCESO DE ENVÍO DE CORREOS[/bold cyan]\nBoletas de Honorarios", style="bold green", padding=(1, 2)))

    if not os.path.isfile(config.ARCHIVO_ADJUNTO):
        console.print(f"[red]❌ Archivo adjunto no encontrado: {config.ARCHIVO_ADJUNTO}[/red]")
        return

    carpetas_ano = listar_carpetas(config.RAIZ)
    if not carpetas_ano:
        console.print(f"[red]❌ No se encontraron carpetas en {config.RAIZ}[/red]")
        return
    ano_seleccionado = utils.seleccionar_opcion(carpetas_ano, "Seleccione el AÑO")

    ruta_ano = os.path.join(config.RAIZ, ano_seleccionado)
    carpetas_mes = listar_carpetas(ruta_ano)
    if not carpetas_mes:
        console.print(f"[red]❌ No se encontraron carpetas de mes en {ruta_ano}[/red]")
        return
    mes_seleccionado = utils.seleccionar_opcion(carpetas_mes, "Seleccione el MES")

    ruta_mes = os.path.join(ruta_ano, mes_seleccionado)
    archivos = [f for f in os.listdir(ruta_mes) if f.lower().endswith('.xlsx')]
    if not archivos:
        console.print(f"[red]❌ No se encontró archivo Excel en {ruta_mes}[/red]")
        return
    archivo_excel = archivos[0] if len(archivos) == 1 else utils.seleccionar_opcion(archivos, "Seleccione el archivo Excel")

    ruta_archivo_excel = os.path.join(ruta_mes, archivo_excel)
    ruta_logs = os.path.join(ruta_mes, "logs_envios")
    os.makedirs(ruta_logs, exist_ok=True)
    ruta_log_file = os.path.join(ruta_logs, "envio_boletas.log")

    logging.basicConfig(filename=ruta_log_file, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    if input("➡️ Respuesta: ").strip().lower() == 's':
        if len(indices_sin_envio) > 0:
            enviar_correos(df, indices_sin_envio, tipo="original")
        else:
            console.print("[yellow]⚠️ No hay correos pendientes para envío original.[/yellow]")
    else:
        console.print("[yellow]🚫 Envío cancelado por el usuario.[/yellow]")

    # Confirmación envío recordatorio
    if len(indices_recordatorio) > 0:
        console.print("\n🤖 ¿Desea enviar/re-enviar recordatorios a los que aún no han enviado la boleta? ([green]s[/green]/[red]n[/red])")
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
    main()
