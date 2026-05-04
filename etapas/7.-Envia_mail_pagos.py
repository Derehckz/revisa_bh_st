#!/usr/bin/env python3
import _sys_path  # noqa: E402
import os
import argparse
import pandas as pd
from outlook_utils import conectar_outlook_app
import time
import logging
import re
import config
import utils
import bh_excel_workbook
import bh_outlook_mail
import email_templates as templates
import schema_validator
import idempotency_store
import email_outbox

RAIZ = config.RAIZ
LOG_FOLDER_NAME = "logs_envios_pagos"

# =========================
# Configuración de correo
# =========================
EMAIL_COPIA = ""  # puedes agregar CC si quieres

# =========================
# Funciones auxiliares
# =========================

def normalizar_monto_liquido(valor):
    if pd.isna(valor):
        return 0

    if isinstance(valor, int):
        return valor

    if isinstance(valor, float):
        # Regla de negocio CLP: monto de honorarios se envía sin decimales.
        # Excel a veces convierte "91.530" en 91.53 (pierde el 0 final al leer).
        # Para valores "chicos" con 2-3 decimales, interpretamos que el punto era separador de miles.
        if abs(valor) < 1000:
            texto_float = f"{valor:.12f}".rstrip("0").rstrip(".")
            if "." in texto_float:
                decimales = texto_float.split(".")[1]
                if len(decimales) in (2, 3):
                    return int(round(valor * 1000))
        # Caso frecuente en esta planilla: "159.669" (miles) llega como float 159.669.
        # Si tiene exactamente 3 decimales y es menor a 10.000, se interpreta como miles.
        texto_float = f"{valor:.12f}".rstrip("0").rstrip(".")
        if "." in texto_float:
            decimales = texto_float.split(".")[1]
            if len(decimales) == 3 and abs(valor) < 10000:
                return int(round(valor * 1000))
        return int(round(float(valor)))

    texto = str(valor).strip()
    if not texto:
        return 0

    texto = texto.replace("$", "").replace(" ", "")
    texto = re.sub(r"[^\d,.\-]", "", texto)

    # Casos típicos locales:
    # - 159.669  -> miles con punto
    # - 159,669  -> miles con coma
    # - 159669,00 / 159669.00 -> decimal
    if "." in texto and "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "." in texto:
        partes = texto.split(".")
        if len(partes) > 1 and all(p.isdigit() for p in partes) and all(len(p) == 3 for p in partes[1:]):
            texto = "".join(partes)
        else:
            try:
                # Regla CLP para textos como "91.53" o "91.530" cuando el origen usa punto de miles.
                valor_num = float(texto)
                decimales = len(partes[-1]) if len(partes) > 1 else 0
                if abs(valor_num) < 1000 and decimales in (2, 3):
                    return int(round(valor_num * 1000))
            except (TypeError, ValueError):
                pass
    elif "," in texto:
        partes = texto.split(",")
        if len(partes) > 1 and all(p.isdigit() for p in partes) and all(len(p) == 3 for p in partes[1:]):
            texto = "".join(partes)
        else:
            texto = texto.replace(",", ".")

    try:
        return int(round(float(texto)))
    except (TypeError, ValueError):
        return valor


def normalizar_nro_cuenta(valor):
    if pd.isna(valor):
        return ""

    texto = str(valor).strip()
    if not texto:
        return ""

    if texto.isdigit():
        return texto

    # Si viene como número decimal por Excel (ej: 12345.0), dejar entero.
    texto_sin_espacios = texto.replace(" ", "")
    try:
        numero = float(texto_sin_espacios.replace(",", "."))
        if numero.is_integer():
            return str(int(numero))
    except (TypeError, ValueError):
        pass

    return texto


def guardar_hoja_excel_atomico(ruta_excel, sheet_name, df_actualizado):
    """Actualiza una hoja preservando el resto del libro con escritura atómica."""
    ok = bh_excel_workbook.replace_sheet_atomically(ruta_excel, sheet_name, df_actualizado)
    if not ok:
        logging.error("No se pudo guardar Excel de forma atómica.")
        utils.print_warning("No se pudo guardar Excel de forma atómica.")
    return ok


def guardar_estado_envio_excel(ruta_excel, df):
    if not guardar_hoja_excel_atomico(ruta_excel, "Pagos", df):
        logging.error("No se pudo persistir estado parcial en Excel.")

# =========================
# Función principal
# =========================

def main(args=None):
    if args is None:
        args = argparse.Namespace(
            force_resend=False, yes=False, send=False, fecha_pago=None, year=None, month=None
        )

    utils.apply_non_interactive_from_args(args)
    utils.print_header("📂 Selección de Excel y envío de correos de pagos", "Cargando configuración de envíos")
    utils.print_step(1, 4, "Preparando contexto de ejecución")

    # Selección año/mes
    try:
        año, mes = utils.resolve_año_mes(RAIZ, getattr(args, "year", None), getattr(args, "month", None))
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

    continuar = utils.mostrar_contexto_ejecucion(
        "🗂️ Contexto de ejecución",
        [
            ("Raíz", RAIZ),
            ("Período", f"{mes} {año}"),
            ("Carpeta mes", ruta_mes),
            ("Excel", ruta_excel),
            ("Logs", ruta_log_file),
        ],
        preview_items=["Se leerá hoja 'Pagos' y se validará columna MAIL."],
        confirm_message="¿Continuar a la vista previa de montos? (s/n)",
    )
    if not continuar:
        utils.print_warning("Proceso cancelado por el usuario.")
        return

    # Fecha de pago
    fp = (getattr(args, "fecha_pago", None) or "").strip()
    if fp:
        fecha_pago = fp
    elif utils.is_non_interactive():
        utils.print_error("Modo no interactivo: use --fecha-pago DD/MM/AAAA.")
        return
    else:
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

    # Vista previa antes de enviar: permite validar formato de montos
    utils.print_section("🧪 Vista previa de montos (LÍQUIDO -> correo)")
    preview_rows = []
    for idx, fila in df.iterrows():
        correo = str(fila.get("MAIL", "")).strip()
        if not utils.validar_email(correo):
            continue
        estado_envio = str(fila.get("Correo Enviado", "")).strip().lower()
        if "enviado" in estado_envio:
            continue
        monto_original = fila.get("LÍQUIDO", 0)
        monto_normalizado = normalizar_monto_liquido(monto_original)
        monto_correo = f"${monto_normalizado:,.0f}".replace(",", ".")
        preview_rows.append((idx + 1, correo, monto_original, monto_correo))
        if len(preview_rows) >= 8:
            break

    if preview_rows:
        for fila_preview in preview_rows:
            n_fila, correo_preview, original_preview, monto_preview = fila_preview
            utils.print_info(
                f"Fila {n_fila} | {correo_preview} | LÍQUIDO='{original_preview}' -> {monto_preview}"
            )
    else:
        utils.print_warning("No hay filas válidas para previsualizar.")

    allow_send = (not utils.is_non_interactive()) or getattr(args, "send", False)
    if not allow_send:
        utils.print_warning(
            "Modo no interactivo sin --send: no se envían correos de pago (vista previa mostrada)."
        )
        return

    if utils.is_non_interactive():
        confirmar_envio = True
    else:
        confirmar_envio = utils.prompt_yes_no_s("¿Enviar correos con estos montos? (s/n)", "n")
    if not confirmar_envio:
        utils.print_warning("Envío cancelado por el usuario luego de la vista previa.")
        return

    outlook = conectar_outlook_app()
    stage_id = "script7.pago_send"
    force_resend = bool(getattr(args, "force_resend", False))

    dispatch_only = getattr(args, "dispatch_only_indices", None)

    utils.print_step(3, 4, "Enviando correos")
    for idx, fila in df.iterrows():
        try:
            ix = int(idx)
        except (TypeError, ValueError):
            ix = idx
        if dispatch_only is not None and ix not in dispatch_only:
            continue
        correo = str(fila.get("MAIL", "")).strip()
        nombre = fila.get("Nombre", "")
        rut = fila.get("ID", "")
        banco = fila.get("BANCO", "")
        tipo_cuenta = fila.get("FORMA PAGO", "")
        nro_cuenta = normalizar_nro_cuenta(fila.get("NªCUENTA", ""))
        n_boleta = fila.get("Boleta","")
        codigo_origen = str(
            fila.get("LOCATION", fila.get("CODIGO", fila.get("INS", "")))
        ).strip()
        monto = normalizar_monto_liquido(fila.get("LÍQUIDO", 0))
        estado_envio = str(fila.get("Correo Enviado", "")).strip().lower()

        if "enviado" in estado_envio:
            logging.info(f"Fila {idx+1} omitida: ya marcada como enviada.")
            continue

        if not utils.validar_email(correo):
            df.at[idx, 'Correo Enviado'] = "❌ Correo inválido"
            logging.warning(f"Correo inválido: {correo} fila {idx+1}")
            utils.print_warning(f"Correo inválido en fila {idx+1}: {correo}")
            guardar_estado_envio_excel(ruta_excel, df)
            continue

        item_key = (
            f"{mes_año_pago}|{rut}|{correo}|{codigo_origen}|{n_boleta}|{tipo_cuenta}|{nro_cuenta}|{monto}"
        ).lower()

        # Idempotencia: si ya se notificó este pago exacto, omitir salvo override.
        if not force_resend and idempotency_store.was_success(stage_id, item_key):
            df.at[idx, 'Correo Enviado'] = "⏭ Omitido por idempotencia"
            logging.info(f"Omitido por idempotencia: {item_key}")
            utils.print_warning(f"Omitido (ya enviado, usar --force-resend para reenviar): {correo}")
            guardar_estado_envio_excel(ruta_excel, df)
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

        dob = getattr(args, "dispatch_outbox", None)
        if dob is not None and ix in dob:
            ob_id = dob[ix]
        else:
            ob_id = email_outbox.record_pending(
                stage_id,
                item_key,
                {
                    "to": correo,
                    "boleta": str(n_boleta),
                    "monto": monto,
                    "fecha_pago": fecha_pago,
                },
            )
        try:
            if idempotency_store.report_duplicate("script7.mail_attempt", item_key):
                logging.warning(f"Reintento detectado (solo reporte): {item_key}")
            if not bh_outlook_mail.send_html_mail_with_backoff(
                outlook,
                to=correo,
                cc=EMAIL_COPIA,
                subject=asunto,
                html_body=cuerpo_html,
                max_attempts=3,
                base_delay_s=1.5,
                backoff_factor=1.5,
                log_context=f"script7 fila={idx + 1}",
            ):
                raise RuntimeError("No se pudo enviar tras reintentos COM")
            email_outbox.mark_sent(ob_id)
            df.at[idx, 'Correo Enviado'] = "✅ Enviado"
            idempotency_store.mark_success(
                stage_id,
                item_key,
                details=f"boleta={n_boleta}|monto={monto}",
            )
            logging.info(f"Correo enviado a {correo} fila {idx+1}")
            utils.print_success(f"Correo enviado a {correo}")
            guardar_estado_envio_excel(ruta_excel, df)
            time.sleep(1)  # breve pausa para no saturar Outlook
        except Exception as e:
            email_outbox.mark_failed(ob_id, str(e))
            df.at[idx, 'Correo Enviado'] = f"❌ Error: {e}"
            logging.error(f"No se pudo enviar correo a {correo} fila {idx+1}: {e}")
            utils.print_error(f"Error enviando correo a {correo}: {e}")
            guardar_estado_envio_excel(ruta_excel, df)

    # Guardar cambios en Excel
    utils.print_step(4, 4, "Guardando resultados en Excel")
    try:
        if guardar_hoja_excel_atomico(ruta_excel, "Pagos", df):
            utils.print_success(f"Hoja 'Pagos' sobrescrita correctamente en {ruta_excel}")
            logging.info(f"Excel actualizado correctamente en {ruta_excel}")
        else:
            utils.print_error("Error guardando Excel en modo atómico.")
            logging.error("Error guardando Excel en modo atómico.")
    except Exception as e:
        utils.print_error(f"Error guardando Excel: {e}")
        logging.error(f"Error guardando Excel: {e}")

    utils.print_header("🎯 PROCESO FINALIZADO", "Envío de correos completado")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Envío de correos de pago de boletas de honorarios")
    parser.add_argument(
        '--force-resend',
        action='store_true',
        help='Ignora idempotencia y reenvía aunque el correo ya esté marcado como exitoso.',
    )
    parser.add_argument(
        "--fecha-pago",
        dest="fecha_pago",
        type=str,
        default=None,
        help="Fecha de pago mostrada en el correo (ej: 05/09/2025). Obligatoria con --yes.",
    )
    utils.register_non_interactive_cli(parser, with_send=True)
    utils.register_period_args(parser)
    args = parser.parse_args()
    main(args)
