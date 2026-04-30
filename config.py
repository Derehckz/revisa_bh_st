# -*- coding: utf-8 -*-
"""
Configuración central del proyecto Boletas de Honorarios.
Ajusta aquí rutas, correos y textos usados en los scripts.
"""
from __future__ import annotations

import os
from zoneinfo import ZoneInfo
from typing import List
import settings

# Ruta raíz del proyecto (carpetas año/mes)
RAIZ: str = os.path.abspath(settings.get_setting("BH_RAIZ", r"E:\Boletas Honorarios"))
CARPETA_BASE: str = RAIZ

# Zona horaria para fechas
ZONA_HORARIA: ZoneInfo = ZoneInfo("America/Santiago")

# Nombres de meses en español (para carpetas y mensajes)
MESES_ES: List[str] = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

# --- Envío de correos (script 1) ---
ULT_FECHA_RECEPCION: str = settings.get_setting("BH_ULT_FECHA_RECEPCION", "28 Abril 2026")
HORARIO_RECEPCION: str = settings.get_setting("BH_HORARIO_RECEPCION", "19:00")
EMAIL_CONTABILIDAD: str = settings.get_setting("BH_EMAIL_CONTABILIDAD", "contabilidad@santotomas.cl")
EMAIL_XML_1: str = settings.get_setting("BH_EMAIL_XML_1", "achocano@santotomas.cl")
EMAIL_XML_2: str = settings.get_setting("BH_EMAIL_XML_2", "")

# Ruta del PDF de ejemplo adjunto en correos de solicitud
ARCHIVO_ADJUNTO: str = os.path.join(RAIZ, "EjemploEnvioBoleta.pdf")

# Prefijo de archivos de boleta (bhe_)
PREFIJO: str = settings.get_setting("BH_PREFIJO", "bhe_")
