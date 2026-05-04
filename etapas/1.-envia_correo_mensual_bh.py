#!/usr/bin/env python3
import _sys_path  # noqa: E402
import os
import pandas as pd
from outlook_utils import conectar_outlook_app
import time
import logging
from tqdm import tqdm
import argparse

import config
import utils
import bh_excel_workbook
import bh_outlook_mail
import email_templates as templates
import schema_validator
import idempotency_store
import email_outbox
import reminder_policy
from db import email_repository

_parse_recordatorio_count = reminder_policy.parse_recordatorio_count
MAX_RECORDATORIOS_POR_PERIODO = reminder_policy.MAX_RECORDATORIOS_POR_PERIODO


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


def enviar_correos(
    df,
    indices,
    tipo="original",
    force_resend=False,
    outbox_ids_by_index: dict[int, int] | None = None,
):
    """
    Enviar correos segun el tipo: "original" o "recordatorio".
    Solo procesa las filas indicadas en indices.

    Si `force_resend` es False, omite envíos que ya fueron marcados como
    exitosos en el store de idempotencia (evita duplicados en reejecución).
    """
    outlook = conectar_outlook_app()
    columna_envio = 'Correo Enviado'
    tipo_envio_db = "SOLICITUD" if tipo == "original" else "RECORDATORIO"
    stage_id = f"script1.mail_send.{tipo}"

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

            cc_list = [config.EMAIL_XML_2] if config.EMAIL_XML_2 else []
            if isinstance(email_dp, str) and utils.validar_email(email_dp):
                cc_list.append(email_dp)
            cc_combined = "; ".join(cc_list)

            if isinstance(email, str) and utils.validar_email(email):
                if tipo == "recordatorio":
                    recordatorio_num = _parse_recordatorio_count(
                        df.at[idx, "Recordatorios Enviados"]
                    ) + 1
                    item_key = f"{año}|{mes}|{rut_docente}|{email}|r{recordatorio_num}".lower()
                else:
                    item_key = f"{año}|{mes}|{rut_docente}|{email}".lower()

                # Idempotencia: evitar reenvíos accidentales salvo override.
                if not force_resend and idempotency_store.was_success(stage_id, item_key):
                    df.at[idx, columna_envio] = f"⏭ Omitido por idempotencia ({tipo})"
                    logging.info(f"Omitido por idempotencia ({tipo}): {item_key}")
                    utils.print_warning(f"Omitido (ya enviado, usar --force-resend para reenviar): {email}")
                    continue

                # Registro de observabilidad (no bloqueante)
                if idempotency_store.report_duplicate("script1.mail_attempt", item_key):
                    logging.warning(f"Reintento detectado (solo reporte): {item_key}")

                if outbox_ids_by_index is not None and idx in outbox_ids_by_index:
                    ob_id = outbox_ids_by_index[idx]
                else:
                    ob_id = email_outbox.record_pending(
                        stage_id, item_key, {"tipo": tipo, "to": email, "asunto": asunto}
                    )
                enviado = bh_outlook_mail.send_html_mail_with_backoff(
                    outlook,
                    to=email,
                    cc=cc_combined,
                    subject=asunto,
                    html_body=cuerpo_html,
                    attachment_path=config.ARCHIVO_ADJUNTO if tipo == "original" else None,
                    max_attempts=3,
                    base_delay_s=2.0,
                    backoff_factor=1.5,
                    log_context=f"script1 {tipo} {item_key}",
                )

                if enviado:
                    email_outbox.mark_sent(ob_id)
                    if tipo == "original":
                        df.at[idx, columna_envio] = "✅ Enviado (original)"
                    else:
                        prev_count = _parse_recordatorio_count(df.at[idx, "Recordatorios Enviados"])
                        new_count = prev_count + 1
                        df.at[idx, "Recordatorios Enviados"] = new_count
                        df.at[idx, columna_envio] = f"✅ Enviado (recordatorio #{new_count})"

                    idempotency_store.mark_success(
                        stage_id,
                        item_key,
                        details=f"asunto={asunto}",
                    )
                    logging.info(f"Correo ({tipo}) enviado a {email} (fila {idx+1})")
                    utils.print_success(f"Correo ({tipo}) enviado a {email} (fila {idx+1})")
                    email_repository.save_email_event(
                        tipo_envio=tipo_envio_db,
                        to_email=email,
                        cc_email=cc_combined,
                        subject=asunto,
                        estado="ENVIADO",
                        periodo_label=f"{año}-{mes}",
                    )
                else:
                    email_outbox.mark_failed(ob_id, "No se pudo enviar después de 3 intentos")
                    df.at[idx, columna_envio] = f"❌ Error envío ({tipo})"
                    logging.error(f"No se pudo enviar el correo ({tipo}) a {email} después de 3 intentos")
                    utils.print_error(f"No se pudo enviar el correo ({tipo}) a {email} (fila {idx+1})")
                    email_repository.save_email_event(
                        tipo_envio=tipo_envio_db,
                        to_email=email,
                        cc_email=cc_combined,
                        subject=asunto,
                        estado="ERROR",
                        error_detalle="No se pudo enviar después de 3 intentos",
                        periodo_label=f"{año}-{mes}",
                    )

            else:
                df.at[idx, columna_envio] = f"❌ Correo inválido ({tipo})"
                logging.warning(f"Correo inválido ({tipo}) en fila {idx+1}: {email}")
                utils.print_warning(f"Correo inválido ({tipo}) en fila {idx+1}: {email}")
                email_repository.save_email_event(
                    tipo_envio=tipo_envio_db,
                    to_email=str(email),
                    cc_email=cc_combined,
                    subject=asunto,
                    estado="ERROR",
                    error_detalle="Correo inválido",
                    periodo_label=f"{año}-{mes}",
                )

            time.sleep(1.5)

        except Exception as e:
            df.at[idx, columna_envio] = f"❌ Error: {e} ({tipo})"
            logging.error(f"Error inesperado ({tipo}) en fila {idx+1}: {e}")
            utils.print_error(f"Fila {idx+1}: {e} ({tipo})")
            email_repository.save_email_event(
                tipo_envio=tipo_envio_db,
                to_email=str(df.loc[idx].get("Email_Docente", "")),
                cc_email=str(df.loc[idx].get("Email_DP", "")),
                subject=None,
                estado="ERROR",
                error_detalle=str(e),
                periodo_label=f"{df.loc[idx].get('YEAR', '')}-{df.loc[idx].get('MONTH', '')}",
            )

def main(args):
    from rich.table import Table

    utils.apply_non_interactive_from_args(args)
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
            ano_seleccionado, mes_seleccionado = utils.resolve_año_mes(
                config.RAIZ, getattr(args, "year", None), getattr(args, "month", None)
            )
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
    continuar = utils.mostrar_contexto_ejecucion(
        "🗂️ Contexto de ejecución",
        [
            ("Raíz", config.RAIZ),
            ("Período", f"{mes_seleccionado} {ano_seleccionado}"),
            ("Carpeta mes", ruta_mes),
            ("Excel", ruta_archivo_excel),
            ("Adjunto", config.ARCHIVO_ADJUNTO),
            ("Logs", ruta_log_file),
        ],
        preview_items=["Se leerá hoja seleccionada y se mostrará previsualización antes de cada envío."],
        confirm_message="¿Continuar con el proceso de análisis y previsualización? (s/n)",
    )
    if not continuar:
        utils.print_warning("Proceso cancelado por el usuario.")
        return

    try:
        xls = pd.ExcelFile(ruta_archivo_excel, engine='openpyxl')
        hojas = xls.sheet_names
    except (OSError, ValueError, KeyError) as e:
        utils.print_error(f"Error al leer el Excel: {e}")
        return

    hoja_seleccionada = (
        utils.pick_excel_sheet(hojas)
        if utils.is_non_interactive()
        else utils.seleccionar_opcion(hojas, "Seleccione la hoja del Excel para validar")
    )
    df = pd.read_excel(ruta_archivo_excel, sheet_name=hoja_seleccionada, engine='openpyxl')

    # Validación canónica del esquema (Fase 3): warnings por defecto;
    # con --strict se aborta si hay errores estructurales.
    canonical_errors, canonical_warnings = schema_validator.validate_for_stage(
        df, "stage1_envio_inicial"
    )
    for w in canonical_warnings:
        logging.warning(f"[script1] WARN {w}")
        utils.print_warning(f"[schema] {w}")
    for e in canonical_errors:
        logging.error(f"[script1] ERROR {e}")
        utils.print_error(f"[schema] {e}")
    if canonical_errors and getattr(args, "strict", False):
        utils.print_error("Validación estricta activada y se detectaron errores de esquema. Abortando.")
        return

    columna_envio = 'Correo Enviado'
    columna_estado = 'Estado_Recepcion'
    columna_recordatorios = 'Recordatorios Enviados'

    if columna_envio not in df.columns:
        df[columna_envio] = ""
    df[columna_envio] = df[columna_envio].astype(object)
    if columna_recordatorios not in df.columns:
        df[columna_recordatorios] = 0
    df[columna_recordatorios] = df[columna_recordatorios].apply(_parse_recordatorio_count)

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
    recordatorios_actuales = df[columna_recordatorios].apply(_parse_recordatorio_count)
    indices_recordatorio = reminder_policy.indices_recordatorio(
        df,
        columna_estado,
        columna_recordatorios,
        force_resend=args.force_resend,
    )

    # Ayuda rápida si no se encontró ninguna fila como 'no recibido'
    if len(indices_recordatorio) == 0:
        unique_vals = df[columna_estado].astype(str).str.strip().value_counts().head(10)
        utils.print_warning(f"No se encontraron filas con estado 'no recibido'. Valores únicos más comunes en '{columna_estado}':")
        for val, cnt in unique_vals.items():
            utils.console.print(f"  {cnt}x -> {val}")

    utils.print_info(f"Pendientes de envío original: {len(indices_sin_envio)}")
    utils.print_info(f"Pendientes para recordatorio: {len(indices_recordatorio)}")
    rec_count = recordatorios_actuales.apply(_parse_recordatorio_count)
    resumen_rec = reminder_policy.resumen_recordatorios(df, columna_estado, columna_recordatorios)
    cand_recordatorio_1 = resumen_rec["cand_1"]
    cand_recordatorio_2 = resumen_rec["cand_2"]
    bloqueados_tope = resumen_rec["bloqueados"]

    utils.print_table(
        "Resumen operativo de recordatorios",
        [
            ("Candidatos a recordatorio #1", str(cand_recordatorio_1)),
            ("Candidatos a recordatorio #2", str(cand_recordatorio_2)),
            (f"Bloqueados por tope ({MAX_RECORDATORIOS_POR_PERIODO})", str(bloqueados_tope)),
            ("Modo force-resend", "Sí" if args.force_resend else "No"),
        ],
    )

    if len(indices_recordatorio) > 0:
        tabla = Table(title="📋 Destinatarios para RECORDATORIO", style="magenta")
        tabla.add_column("N°", justify="center", style="cyan")
        tabla.add_column("Nombre", style="white")
        tabla.add_column("Correo", style="green")
        tabla.add_column("Recordatorios enviados", style="yellow", justify="center")
        for i, idx in enumerate(indices_recordatorio, 1):
            count = _parse_recordatorio_count(df.at[idx, columna_recordatorios])
            tabla.add_row(str(i), df.at[idx, "NAME"], df.at[idx, "Email_Docente"], str(count))
        utils.console.print(tabla)

    if not args.force_resend:
        bloqueados_max = int(
            (
                estado_col.str.contains(r"no\s*recibido", na=False) &
                (recordatorios_actuales >= MAX_RECORDATORIOS_POR_PERIODO)
            ).sum()
        )
        if bloqueados_max > 0:
            utils.print_warning(
                f"{bloqueados_max} docentes NO RECIBIDO ya alcanzaron el máximo de "
                f"{MAX_RECORDATORIOS_POR_PERIODO} recordatorios."
            )

    allow_send = (not utils.is_non_interactive()) or getattr(args, "send", False)

    # Confirmación envío original
    utils.print_info("¿Desea continuar con el envío de correos originales? (s/n)")
    if len(indices_sin_envio) > 0:
        if not allow_send:
            utils.print_warning(
                "Modo no interactivo sin --send: no se envían correos originales "
                "(se omite el envío; el Excel se guardará con el estado actual)."
            )
        else:
            utils.print_info("Mostrando previsualización antes de enviar...")
            mostrar_previsualizacion(
                "correo original",
                len(indices_sin_envio),
                mes_seleccionado,
                ano_seleccionado,
                df,
                indices_sin_envio,
            )
            if utils.is_non_interactive():
                enviar_correos(df, indices_sin_envio, tipo="original", force_resend=args.force_resend)
            else:
                utils.print_info(f"¿Desea CONFIRMAR el envío de {len(indices_sin_envio)} correos originales? (s/n)")
                if utils.prompt_yes_no_s("Respuesta (s/n)", default="n"):
                    enviar_correos(df, indices_sin_envio, tipo="original", force_resend=args.force_resend)
                else:
                    utils.print_warning("Envío cancelado por el usuario.")
    else:
        utils.print_warning("No hay correos pendientes para envío original.")

    # Confirmación envío recordatorio
    if len(indices_recordatorio) > 0:
        if not allow_send:
            utils.print_warning(
                "Modo no interactivo sin --send: no se envían recordatorios "
                "(se omite el envío; el Excel se guardará con el estado actual)."
            )
        else:
            utils.print_info("¿Desea enviar/re-enviar recordatorios a los que aún no han enviado la boleta? (s/n)")
            utils.print_info("Mostrando previsualización antes de enviar...")
            mostrar_previsualizacion(
                "recordatorio",
                len(indices_recordatorio),
                mes_seleccionado,
                ano_seleccionado,
                df,
                indices_recordatorio,
            )
            if utils.is_non_interactive():
                enviar_correos(df, indices_recordatorio, tipo="recordatorio", force_resend=args.force_resend)
            else:
                utils.print_info(f"¿Desea CONFIRMAR el envío de {len(indices_recordatorio)} recordatorios? (s/n)")
                if utils.prompt_yes_no_s("Respuesta (s/n)", default="n"):
                    enviar_correos(df, indices_recordatorio, tipo="recordatorio", force_resend=args.force_resend)
                else:
                    utils.print_warning("Envío de recordatorios cancelado por el usuario.")
    else:
        utils.print_warning("No hay destinatarios para recordatorio.")

    if bh_excel_workbook.replace_sheet_atomically(ruta_archivo_excel, hoja_seleccionada, df):
        utils.print_success(f"Archivo guardado correctamente en: {ruta_archivo_excel}")
        logging.info(f"Archivo guardado correctamente en {ruta_archivo_excel}")
    else:
        utils.print_error("Error al guardar archivo Excel (reemplazo atómico de hoja).")
        logging.error("Error al guardar archivo Excel (reemplazo atómico de hoja).")

    utils.print_header("🎯 PROCESO FINALIZADO EXITOSAMENTE", "Correos enviados correctamente")
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Envío de correos de boletas de honorarios")
    parser.add_argument('--year', type=str, help='Año específico')
    parser.add_argument('--month', type=str, help='Mes específico')
    parser.add_argument(
        '--force-resend',
        action='store_true',
        help='Ignora idempotencia y reenvía aunque el correo ya esté marcado como exitoso.',
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Aborta si la Solicitud.xlsx no cumple el esquema canónico.',
    )
    utils.register_non_interactive_cli(parser, with_send=True)
    args = parser.parse_args()
    main(args)
