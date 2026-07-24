import config


def _safe_str(value):
    if value is None:
        return ""
    try:
        if isinstance(value, float) and value != value:
            return ""
    except Exception:
        pass
    return str(value)


def _format_monto(valor, simbolo="$"):
    if valor is None:
        return "N/A"
    try:
        # Soporta montos con miles/decimales en formato local.
        if isinstance(valor, str):
            monto = valor.strip().replace("$", "").replace(" ", "")
            if "," in monto and "." in monto:
                # Determina separador decimal por la última aparición.
                if monto.rfind(",") > monto.rfind("."):
                    # 1.234,56 -> 1234.56
                    monto = monto.replace(".", "").replace(",", ".")
                else:
                    # 1,234.56 -> 1234.56
                    monto = monto.replace(",", "")
            elif "," in monto:
                parts = monto.split(",")
                # 206,000 -> miles; 206,5 -> decimal
                if len(parts) > 1 and all(p.isdigit() for p in parts) and all(len(p) == 3 for p in parts[1:]):
                    monto = "".join(parts)
                else:
                    monto = monto.replace(",", ".")
            elif "." in monto:
                parts = monto.split(".")
                # 206.000 -> miles
                if len(parts) > 1 and all(p.isdigit() for p in parts) and all(len(p) == 3 for p in parts[1:]):
                    monto = "".join(parts)
            valor = monto
        return f"{simbolo}{float(valor):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(valor)


def _xml_destinos_html() -> str:
    email_2 = config.EMAIL_XML_2.strip()
    if email_2:
        return f"<strong>{config.EMAIL_XML_1}</strong><br><strong>{email_2}</strong>"
    return f"<strong>{config.EMAIL_XML_1}</strong>"


def generar_asunto_solicitud(tipo: str, mes: str, año: int, rut_docente: str, nombre_completo: str) -> str:
    tipo_texto = "Solicitud Boleta Honorarios" if tipo == "original" else "Recordatorio: Solicitud Boleta Honorarios"
    return f"{tipo_texto} {mes} {año} - {rut_docente}-{nombre_completo}"


def plazo_por_tipo(
    tipo: str,
    *,
    fecha_limite_recepcion: str | None = None,
    horario_recepcion: str | None = None,
    fecha_limite_recordatorio: str | None = None,
    horario_recordatorio: str | None = None,
) -> tuple[str, str]:
    """Plazos explícitos (preferidos) o fallback a config global."""
    if tipo == "original":
        return (
            (fecha_limite_recepcion or config.ULT_FECHA_RECEPCION),
            (horario_recepcion or config.HORARIO_RECEPCION),
        )
    return (
        (fecha_limite_recordatorio or config.ULT_FECHA_RECORDATORIO),
        (horario_recordatorio or config.HORARIO_RECORDATORIO),
    )


def generar_cuerpo_solicitud(
    tipo: str,
    nombre_completo: str,
    rut_docente: str,
    rut_razon: str,
    razon_social: str,
    direccion_razon: str,
    glosa: str,
    monto: float | int | str,
    email_dp: str,
    mes: str,
    año: int,
    *,
    fecha_limite_recepcion: str | None = None,
    horario_recepcion: str | None = None,
    fecha_limite_recordatorio: str | None = None,
    horario_recordatorio: str | None = None,
) -> str:
    fecha_limite, horario_limite = plazo_por_tipo(
        tipo,
        fecha_limite_recepcion=fecha_limite_recepcion,
        horario_recepcion=horario_recepcion,
        fecha_limite_recordatorio=fecha_limite_recordatorio,
        horario_recordatorio=horario_recordatorio,
    )
    titulo = "📄 Solicitud de Boleta de Honorarios"
    titulo_color = "#2E8B57"
    subtitulo = f"Proceso iniciado para {mes.capitalize()} {año}"
    estado_banner = "#e8f5e8"
    estado_banner_title = "📋 Instrucciones"
    motivo_texto = (
        f"Junto con saludar cordialmente, Le informamos que se ha iniciado el proceso de emisión de boletas de honorarios correspondientes al mes de <strong>{mes.capitalize()}</strong>. "
        f"Las boletas serán recepcionadas <strong>hasta el día {fecha_limite}, a las {horario_limite}</strong> (plazo impostergable)."
    )
    if tipo != "original":
        titulo = "⏰ Recordatorio: Boleta de Honorarios"
        titulo_color = "#dc3545"
        subtitulo = f"Pendiente de envío para {mes.capitalize()} {año}"
        motivo_texto = (
            f"Hasta la fecha no hemos recibido la Boleta de Honorarios en formato XML y PDF correspondiente al mes de <strong>{mes.capitalize()}</strong>. "
            f"Le solicitamos enviar la documentación <strong>hasta el día {fecha_limite}, a las {horario_limite}</strong> (plazo impostergable)."
        )

    lista_xml = _xml_destinos_html()
    monto_formateado = _format_monto(monto)
    email_dp = _safe_str(email_dp) or "(sin correo de director(a) registrado)"

    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style="color: {titulo_color}; margin: 0;">{titulo}</h1>
            <p style="color: #666; font-size: 16px; margin: 5px 0;">{subtitulo}</p>
        </div>

        <div style="background-color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="font-size: 18px; color: #333; margin-bottom: 15px;">
                <b>Estimado(a) Sr(a). {nombre_completo}:</b>
            </p>

            <p style="font-size: 16px; line-height: 1.6; color: #555;">
                {motivo_texto}
            </p>

            <div style="background-color: {estado_banner}; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #2E8B57;">
                <h3 style="color: #2E8B57; margin: 0 0 10px 0;">{estado_banner_title}</h3>
                <ol style="margin: 0; padding-left: 20px;">
                    <li>Emitir la boleta desde el portal del SII al correo: <strong>{config.EMAIL_CONTABILIDAD}</strong></li>
                    <li>Enviar copia de la boleta generada (en formato XML y PDF) a:<br>{lista_xml}</li>
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
                    <li style="margin-bottom: 8px;"><strong>💰 Monto:</strong> {monto_formateado}.-</li>
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


def generar_asunto_recepcion(numero_boleta: str) -> str:
    return f"✅ Confirmación de Recepción de Boleta de Honorarios - Boleta n°{numero_boleta}"


def generar_cuerpo_recepcion(
    nombre: str,
    numero_boleta: str,
    rut: str,
    rut_emisor: str,
    monto: float | int | str,
) -> str:
    monto_texto = _format_monto(monto)
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style="color: #2E8B57; margin: 0;">🎉 ¡Boleta Recepcionada Exitosamente!</h1>
            <p style="color: #666; font-size: 16px; margin: 5px 0;">Su documento ha sido procesado correctamente</p>
        </div>

        <div style="background-color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="font-size: 18px; color: #333; margin-bottom: 15px;">
                <b>Estimado(a) {nombre}:</b>
            </p>

            <p style="font-size: 16px; line-height: 1.6; color: #555;">
                Hemos recibido y procesado correctamente su <strong>Boleta de Honorarios</strong>. 
                Su documento está ahora en nuestro sistema y será incluido en el proceso de pagos correspondiente.
            </p>

            <div style="background-color: #e8f5e8; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #2E8B57;">
                <h3 style="color: #2E8B57; margin: 0 0 10px 0;">📋 Detalles de su Boleta</h3>
                <ul style="list-style: none; padding: 0; margin: 0;">
                    <li style="margin-bottom: 8px;"><strong>🆔 RUT Receptor:</strong> {rut}</li>
                    <li style="margin-bottom: 8px;"><strong>📄 Número de Boleta:</strong> {numero_boleta}</li>
                    <li style="margin-bottom: 8px;"><strong>👤 Nombre Receptor:</strong> {nombre}</li>
                    <li style="margin-bottom: 8px;"><strong>🏢 RUT Emisor:</strong> {rut_emisor}</li>
                    <li style="margin-bottom: 8px;"><strong>💰 Monto Total:</strong> {monto_texto}</li>
                </ul>
            </div>

            <div style="background-color: #fff3cd; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #ffc107;">
                <h3 style="color: #856404; margin: 0 0 10px 0;">⚠️ Información Importante</h3>
                <ul style="margin: 0; padding-left: 20px; color: #856404;">
                    <li>Su boleta ha sido validada y está lista para procesamiento de pago.</li>
                    <li>El pago se realizará según el calendario establecido por la institución.</li>
                    <li>Ante cualquier duda, puede contactarnos respondiendo este correo.</li>
                </ul>
            </div>

            <div style="text-align: center; margin-top: 30px;">
                <p style="font-size: 16px; color: #666; margin-bottom: 10px;">
                    💼 <strong>Equipo de Convenio Los Lagos</strong>
                </p>
                <p style="font-size: 14px; color: #999;">
                    Gracias por su colaboración y puntualidad en el envío de documentos 📅
                </p>
            </div>
        </div>

        <div style="text-align: center; font-size: 12px; color: #999; margin-top: 20px;">
            <p>Este es un mensaje automático generado por el sistema de procesamiento de boletas.</p>
            <p>Por favor, no responda directamente a este correo si no es necesario.</p>
        </div>
    </div>
    """


def generar_asunto_pago(nombre: str, mes_año_pago: str) -> str:
    return f"💰 Información de Pago {mes_año_pago} - {nombre}"


def generar_cuerpo_pago(
    nombre: str,
    mes_año_pago: str,
    fecha_pago: str,
    banco: str,
    tipo_cuenta: str,
    nro_cuenta: str,
    monto: float | int | str,
) -> str:
    monto_texto = _format_monto(monto)
    return f"""
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
                    <li style="margin-bottom: 8px;"><strong>💰 Monto a depositar:</strong> {monto_texto}</li>
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
