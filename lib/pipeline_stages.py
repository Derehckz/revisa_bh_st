"""Definición declarativa de etapas del pipeline (usada por `main.py`).

Mantener una sola fuente de verdad para número de paso, archivo y contrato CLI.
"""
from __future__ import annotations

SCRIPTS: list[dict] = [
    {
        "num": 0,
        "file": "etapas/0.-generar_solicitud.py",
        "desc": "Generación/actualización de Solicitud.xlsx",
        "accepts": "mes_ano",
        "optional_in_full_run": True,
    },
    {
        "num": 1,
        "file": "etapas/1.-envia_correo_mensual_bh.py",
        "desc": "Envío de correos iniciales",
        "accepts": "year_month",
        "optional_in_full_run": False,
    },
    {
        "num": 2,
        "file": "etapas/2.-extrae_xml_correo.py",
        "desc": "Extracción de adjuntos XML/PDF",
        "accepts": "none",
        "optional_in_full_run": False,
    },
    {
        "num": 3,
        "file": "etapas/3.-revisa_solicitud_VS_recibidas.py",
        "desc": "Validación solicitud vs recibidas",
        "accepts": "year_month",
        "optional_in_full_run": False,
    },
    {
        "num": 4,
        "file": "etapas/4.-extrae_datos_xml_al_excel.py",
        "desc": "Extracción datos XML al Excel",
        "accepts": "year_month",
        "optional_in_full_run": False,
    },
    {
        "num": 5,
        "file": "etapas/5.-Enviar_Correo_Recepcion.py",
        "desc": "Envío de correos de recepción",
        "accepts": "year_month",
        "optional_in_full_run": False,
    },
    {
        "num": 6,
        "file": "etapas/6.-Informe_final_boletas.py",
        "desc": "Generación de informe final",
        "accepts": "year_month",
        "optional_in_full_run": False,
    },
    {
        "num": 7,
        "file": "etapas/7.-Envia_mail_pagos.py",
        "desc": "Envío de mails de pagos",
        "accepts": "year_month",
        "optional_in_full_run": False,
    },
    {
        "num": 8,
        "file": "etapas/8.-separa_bh_ip_cft.py",
        "desc": "Separación BH IP/CFT",
        "accepts": "year_month",
        "optional_in_full_run": False,
    },
    {
        "num": 9,
        "file": "etapas/9.-agrupa_por_docente.py",
        "desc": "Agrupación por docente",
        "accepts": "year_month",
        "optional_in_full_run": False,
    },
    {
        "num": 10,
        "file": "etapas/10.-revisa_carpetas_ip_cft.py",
        "desc": "Revisión de carpetas IP/CFT",
        "accepts": "year_month",
        "optional_in_full_run": False,
    },
]

MIN_STEP = min(s["num"] for s in SCRIPTS)
MAX_STEP = max(s["num"] for s in SCRIPTS)
