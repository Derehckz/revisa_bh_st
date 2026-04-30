import os
import pandas as pd
from outlook_utils import conectar_outlook_app
import time
import logging
from tqdm import tqdm
import tempfile
import shutil
import argparse

import config
import utils
import email_templates as templates
import schema_validator
import idempotency_store



def mostrar_previsualizacion(tipo_envio, cantidad_correos, mes, ano, df=None, indices=None):
    """
    Muestra una previsualización de las configuraciones y fecha que se usarán
    antes de enviar los correos.
    """
    from rich.table import Table
    
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
    
    utils.console.print(tabla)
    
    # Mostrar muestra de destinatarios si hay
    if df is not None and indices is not None and len(indices) > 0:
        utils.console.print("\n📋 [bold cyan]MUESTRA DE DESTINATARIOS ([yellow]{}/{} primeros[/yellow])[/bold cyan]".format(
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
        
        utils.console.print(tabla_dest)
        
        if len(indices) > 5:
            utils.console.print(f"[yellow]... y {len(indices) - 5} destinatarios más[/yellow]")


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

            asunto = templates.generar_asunto_solicitud(tipo, mes, año, rut_docente, nombre_completo)
            cuerpo_html = templates.generar_cuerpo_solicitud(
                tipo=tipo,
                nombre_completo=nombre_completo,
                rut_docente=rut_docente,
                rut_razon=rut_razon,
                razon_social=razon_social,
                direccion_razon=direccion_razon,
                glosa=glosa,
                monto=monto,
                email_dp=email_dp,
                mes=mes,
                año=año,
            )

            cc_list = [config.EMAIL_XML_2]
            if isinstance(email_dp, str) and utils.validar_email(email_dp):
                cc_list.append(email_dp)
            cc_combined = "; ".join(cc_list)

            if isinstance(email, str) and utils.validar_email(email):
                item_key = f"{tipo}|{año}|{mes}|{rut_docente}|{email}".lower()
                if idempotency_store.report_duplicate("script1.mail_attempt", item_key):
                    logging.warning(f"Duplicado detectado (solo reporte): {item_key}")
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
                    utils.print_success(f"Correo ({tipo}) enviado a {email} (fila {idx+1})")
                else:
                    df.at[idx, columna_envio] = f"❌ Error envío ({tipo})"
                    logging.error(f"No se pudo enviar el correo ({tipo}) a {email} después de 3 intentos")
                    utils.print_error(f"No se pudo enviar el correo ({tipo}) a {email} (fila {idx+1})")

            else:
                df.at[idx, columna_envio] = f"❌ Correo inválido ({tipo})"
                logging.warning(f"Correo inválido ({tipo}) en fila {idx+1}: {email}")
                utils.print_warning(f"Correo inválido ({tipo}) en fila {idx+1}: {email}")

            time.sleep(1.5)

        except Exception as e:
            df.at[idx, columna_envio] = f"❌ Error: {e} ({tipo})"
            logging.error(f"Error inesperado ({tipo}) en fila {idx+1}: {e}")
            utils.print_error(f"Fila {idx+1}: {e} ({tipo})")

def main(args):
    from rich.table import Table

    utils.print_header("🚀 INICIO DE PROCESO DE ENVÍO DE CORREOS", "Boletas de Honorarios")

    if not os.path.isfile(config.ARCHIVO_ADJUNTO):
        utils.print_error(f"Archivo adjunto no encontrado: {config.ARCHIVO_ADJUNTO}")
        return

    if args.year and args.month:
        ano_seleccionado = args.year
        mes_seleccionado = args.month
        ruta_mes = os.path.join(config.RAIZ, ano_seleccionado, mes_seleccionado)
        if not os.path.exists(ruta_mes):
            utils.print_error(f"Ruta no existe: {ruta_mes}")
            return
    else:
        try:
            ano_seleccionado, mes_seleccionado = utils.seleccionar_año_mes(config.RAIZ)
        except ValueError as e:
            utils.print_error(str(e))
            return
        ruta_mes = os.path.join(config.RAIZ, ano_seleccionado, mes_seleccionado)
    archivos = [f for f in os.listdir(ruta_mes) if f.lower().endswith('.xlsx')]
    if not archivos:
        utils.print_error(f"No se encontró archivo Excel en {ruta_mes}")
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
        utils.print_error(f"Error al leer el Excel: {e}")
        return

    hoja_seleccionada = utils.seleccionar_opcion(hojas, "Seleccione la hoja del Excel para validar")
    df = pd.read_excel(ruta_archivo_excel, sheet_name=hoja_seleccionada, engine='openpyxl')

    schema_issues = []
    schema_issues.extend(
        schema_validator.validate_required_columns(
            df.columns,
            [
                "NAME",
                "EMPLID",
                "RUT RAZON",
                "NOMBRE RAZON",
                "DireccionRazon",
                "GLOSA",
                "CUS_TOT_HON",
                "Email_Docente",
                "MONTH",
                "YEAR",
                "Estado_Recepcion",
            ],
        )
    )
    schema_issues.extend(
        schema_validator.validate_types(
            df,
            {
                "NAME": (str,),
                "Email_Docente": (str,),
                "MONTH": (str, int),
                "YEAR": (int, float, str),
            },
        )
    )
    for warning_line in schema_validator.format_issues(schema_issues, "script1"):
        logging.warning(warning_line)
        utils.print_warning(warning_line)

    columna_envio = 'Correo Enviado'
    columna_estado = 'Estado_Recepcion'

    if columna_envio not in df.columns:
        df[columna_envio] = ""
    df[columna_envio] = df[columna_envio].astype(object)

    if columna_estado not in df.columns:
        utils.print_error(f"No se encontró la columna '{columna_estado}' en el archivo Excel.")
        return

    utils.print_info(f"Iniciando análisis de {len(df)} filas...")

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
        utils.print_warning(f"No se encontraron filas con estado 'no recibido'. Valores únicos más comunes en '{columna_estado}':")
        for val, cnt in unique_vals.items():
            utils.console.print(f"  {cnt}x -> {val}")

    utils.print_info(f"Pendientes de envío original: {len(indices_sin_envio)}")
    utils.print_info(f"Pendientes para recordatorio: {len(indices_recordatorio)}")

    if len(indices_recordatorio) > 0:
        tabla = Table(title="📋 Destinatarios para RECORDATORIO", style="magenta")
        tabla.add_column("N°", justify="center", style="cyan")
        tabla.add_column("Nombre", style="white")
        tabla.add_column("Correo", style="green")
        tabla.add_column("Prev. Recordatorio", style="yellow", justify="center")
        for i, idx in enumerate(indices_recordatorio, 1):
            prev = "Sí" if "recordatorio" in str(df.at[idx, columna_envio]).lower() else "No"
            tabla.add_row(str(i), df.at[idx, "NAME"], df.at[idx, "Email_Docente"], prev)
        utils.console.print(tabla)

    # Confirmación envío original
    utils.print_info("¿Desea continuar con el envío de correos originales? (s/n)")
    if len(indices_sin_envio) > 0:
        utils.print_info("Mostrando previsualización antes de enviar...")
        mostrar_previsualizacion("correo original", len(indices_sin_envio), mes_seleccionado, ano_seleccionado, df, indices_sin_envio)
        utils.print_info(f"¿Desea CONFIRMAR el envío de {len(indices_sin_envio)} correos originales? (s/n)")
        if utils.prompt_yes_no_s("Respuesta (s/n)", default="n"):
            enviar_correos(df, indices_sin_envio, tipo="original")
        else:
            utils.print_warning("Envío cancelado por el usuario.")
    else:
        utils.print_warning("No hay correos pendientes para envío original.")

    # Confirmación envío recordatorio
    if len(indices_recordatorio) > 0:
        utils.print_info("¿Desea enviar/re-enviar recordatorios a los que aún no han enviado la boleta? (s/n)")
        utils.print_info("Mostrando previsualización antes de enviar...")
        mostrar_previsualizacion("recordatorio", len(indices_recordatorio), mes_seleccionado, ano_seleccionado, df, indices_recordatorio)
        utils.print_info(f"¿Desea CONFIRMAR el envío de {len(indices_recordatorio)} recordatorios? (s/n)")
        if utils.prompt_yes_no_s("Respuesta (s/n)", default="n"):
            enviar_correos(df, indices_recordatorio, tipo="recordatorio")
        else:
            utils.print_warning("Envío de recordatorios cancelado por el usuario.")
    else:
        utils.print_warning("No hay destinatarios para recordatorio.")

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
        utils.print_success(f"Archivo guardado correctamente en: {ruta_archivo_excel}")
        logging.info(f"Archivo guardado correctamente en {ruta_archivo_excel}")
    except (OSError, IOError, PermissionError) as e:
        utils.print_error(f"Error al guardar archivo Excel: {e}")
        logging.error(f"Error al guardar archivo Excel: {e}")

    utils.print_header("🎯 PROCESO FINALIZADO EXITOSAMENTE", "Correos enviados correctamente")
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Envío de correos de boletas de honorarios")
    parser.add_argument('--year', type=str, help='Año específico')
    parser.add_argument('--month', type=str, help='Mes específico')
    args = parser.parse_args()
    main(args)
