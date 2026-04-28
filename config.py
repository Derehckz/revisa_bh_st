# -*- coding: utf-8 -*-
"""
Configuración central del proyecto Boletas de Honorarios.
Ajusta aquí rutas, correos y textos usados en los scripts.
"""
from __future__ import annotations

import os
from zoneinfo import ZoneInfo
from typing import List

# Ruta raíz del proyecto (carpetas año/mes)
RAIZ: str = os.path.abspath(r"E:\Boletas Honorarios")
CARPETA_BASE: str = RAIZ

# Zona horaria para fechas
ZONA_HORARIA: ZoneInfo = ZoneInfo("America/Santiago")

# Nombres de meses en español (para carpetas y mensajes)
MESES_ES: List[str] = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

# --- Envío de correos (script 1) ---
ULT_FECHA_RECEPCION: str = "28 Abril 2026"
HORARIO_RECEPCION: str = "19:00"  # Corregido: 19:00 (sin AM/PM)
EMAIL_CONTABILIDAD: str = "contabilidad@santotomas.cl"
EMAIL_XML_1: str = "achocano@santotomas.cl"
EMAIL_XML_2: str = ""

# Ruta del PDF de ejemplo adjunto en correos de solicitud
ARCHIVO_ADJUNTO: str = os.path.join(RAIZ, "EjemploEnvioBoleta.pdf")

# Prefijo de archivos de boleta (bhe_)
PREFIJO: str = "bhe_"
