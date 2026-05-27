import win32com.client
import logging
from datetime import datetime

import utils

utils.asegurar_utf8_salida()

def conectar_outlook_app():
    """
    Conecta a Outlook y devuelve la aplicación.
    """
    logging.info("🔌 Conectando a Outlook...")
    try:
        outlook_app = win32com.client.Dispatch("Outlook.Application")
        usuario_actual = outlook_app.Session.CurrentUser.Name
        logging.info(f"✅ Conectado a la cuenta: {usuario_actual}")
        return outlook_app
    except Exception as e:
        logging.error(f"❌ No fue posible conectar a Outlook: {e}")
        raise


def conectar_outlook_ns():
    """
    Conecta a Outlook y devuelve el namespace MAPI.
    """
    outlook_app = conectar_outlook_app()
    return outlook_app.GetNamespace("MAPI")


def filtrar_correos_por_fecha(folder, fecha_inicio: datetime, fecha_fin: datetime):
    """
    Filtra correos en la carpeta dada por rango de fechas.
    """
    filtro = (
        f"[ReceivedTime] >= '{fecha_inicio.strftime('%m/%d/%Y %I:%M %p')}' AND "
        f"[ReceivedTime] <= '{fecha_fin.strftime('%m/%d/%Y %I:%M %p')}'"
    )
    logging.info(f"🔍 Aplicando filtro: {filtro}")
    items = folder.Items
    items.Sort("[ReceivedTime]", True)
    try:
        filtrados = items.Restrict(filtro)
        mensajes = [msg for msg in filtrados if getattr(msg, "Class", None) == 43]
        logging.info(f"✅ Correos encontrados en rango: {len(mensajes)}")
        utils.print_success(f"Correos encontrados en rango: {len(mensajes)}")
        return mensajes
    except Exception as e:
        logging.error(f"❌ Error al filtrar correos: {e}")
        utils.print_error(f"Error al filtrar correos: {e}")
        return []