# -*- coding: utf-8 -*-
"""Funciones compartidas del proyecto Boletas de Honorarios."""
from __future__ import annotations

import re
import os
import logging
from datetime import datetime
from typing import Any, List, Optional

from rich.console import Console
from rich.panel import Panel
from colorama import init as colorama_init, Fore

# Inicialización mínima para funciones utilitarias
colorama_init(autoreset=True)
console = Console()


def seleccionar_opcion(lista: List[Any], mensaje: str, icono: str = "") -> Any:
    """Selector de opciones en consola (retorna el elemento seleccionado)."""
    # Ordenar la lista para consistencia
    lista_ordenada = sorted(lista)
    console.print(Panel.fit(f"{icono} {mensaje}", style="cyan bold"))
    for i, opt in enumerate(lista_ordenada, 1):
        console.print(f"[yellow]{i}.[/] {opt}")
    while True:
        try:
            sel = int(console.input("[green]👉 Seleccione número:[/] ").strip())
            if 1 <= sel <= len(lista_ordenada):
                return lista_ordenada[sel - 1]
        except (ValueError, TypeError):
            pass
        console.print("[red]⚠️ Opción inválida, intente de nuevo.[/red]")


def validar_email(email: Optional[str]) -> bool:
    """Valida formato básico de correo electrónico."""
    if email is None or not str(email).strip():
        return False
    patron = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(patron, str(email).strip()))


def find_element_ignore_ns(root: Any, tag_name: str) -> Optional[Any]:
    """Busca un elemento en un árbol XML por nombre de tag, ignorando namespace."""
    for elem in root.iter():
        tag = elem.tag
        if '}' in tag:
            tag = tag.split('}', 1)[1]
        if tag == tag_name:
            return elem
    return None


def normalizar_rut_digits(rut: Optional[str]) -> str:
    """Devuelve solo los dígitos del RUT (quita puntos, guiones, DV y espacios)."""
    if rut is None:
        return ''
    return re.sub(r"\D", "", str(rut))


def normalizar_rut_con_dv(rut: Optional[str]) -> str:
    """Normaliza un RUT dejando DV si existe (quita puntos/espacios/nbsp)."""
    if rut is None:
        return ''
    return re.sub(r'[\.\-\s\u00A0]', '', str(rut)).upper()


def resolver_conflicto(ruta_original: str, politica: Optional[str] = None) -> Optional[str]:
    """Resolver conflicto de archivo existente.
    politica: 'S' sobrescribir, 'A' renombrar con sufijo, 'I' ignorar. Si None, renombra.
    Devuelve ruta destino o None si se debe ignorar.
    """
    if not os.path.exists(ruta_original):
        return ruta_original
    if politica == 'S':
        return ruta_original
    if politica == 'I':
        return None
    # default: renombrar con sufijo
    base, ext = os.path.splitext(ruta_original)
    i = 1
    nueva = f"{base}_{i}{ext}"
    while os.path.exists(nueva):
        i += 1
        nueva = f"{base}_{i}{ext}"
    return nueva


def backup_file(path: Optional[str]) -> Optional[str]:
    """Crear un backup ZIP del archivo indicado (si existe). Devuelve la ruta del zip o None."""
    try:
        if not path or not os.path.exists(path):
            return None
        import zipfile
        base = os.path.splitext(path)[0]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dest = f"{base}_backup_{timestamp}.zip"
        with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(path, arcname=os.path.basename(path))
        return dest
    except (OSError, zipfile.BadZipFile) as e:
        return None


def listar_carpetas(ruta):
    try:
        # Filtra solo carpetas relevantes: excluye .git, __pycache__, .gitignore, etc.
        return [d for d in os.listdir(ruta) 
                if os.path.isdir(os.path.join(ruta, d)) 
                and not d.startswith('.') 
                and not d.startswith('__')]
    except OSError as e:
        logging.error(f"Error accediendo a {ruta}: {e}")
        print(Fore.RED + f"❌ Error accediendo a {ruta}: {e}")
        return []


def configurar_logging(ruta_log_file: str) -> None:
    """Configura logging con RichHandler para consola y archivo."""
    from rich.logging import RichHandler
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(rich_tracebacks=True, markup=True),
            logging.FileHandler(ruta_log_file)
        ]
    )


def seleccionar_año_mes(raiz: str) -> tuple[str, str]:
    """Selecciona año y mes de las carpetas disponibles."""
    años = listar_carpetas(raiz)
    if not años:
        raise ValueError("No hay carpetas de año en la ruta configurada.")
    año = seleccionar_opcion(sorted(años), "Seleccione el año:", "🗓️")
    ruta_año = os.path.join(raiz, año)
    
    meses = listar_carpetas(ruta_año)
    if not meses:
        raise ValueError(f"No hay carpetas de mes en {ruta_año}")
    mes = seleccionar_opcion(sorted(meses), "Seleccione el mes:", "🗓️")
    
    return año, mes
