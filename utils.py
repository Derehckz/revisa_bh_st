# -*- coding: utf-8 -*-
"""Funciones compartidas del proyecto Boletas de Honorarios."""
from __future__ import annotations

import re
import os
import json
import uuid
import logging
from datetime import datetime
import contextvars
from typing import Any, List, Optional

from colorama import init as colorama_init
import terminal_ui

# Inicialización mínima para funciones utilitarias
colorama_init(autoreset=True)
console = terminal_ui.console
_RUN_ID: str = os.getenv("BH_RUN_ID", uuid.uuid4().hex[:12])
_CORRELATION_ID: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default=_RUN_ID)


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = _RUN_ID
        record.correlation_id = _CORRELATION_ID.get()
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "run_id": getattr(record, "run_id", _RUN_ID),
            "correlation_id": getattr(record, "correlation_id", _CORRELATION_ID.get()),
        }
        return json.dumps(payload, ensure_ascii=False)


def print_header(title: str, subtitle: str | None = None) -> None:
    terminal_ui.print_header(title, subtitle)


def print_step(step: int, total: int, message: str) -> None:
    terminal_ui.print_step(step, total, message)


def print_info(message: str) -> None:
    terminal_ui.print_info(message)


def print_success(message: str) -> None:
    terminal_ui.print_success(message)


def print_warning(message: str) -> None:
    terminal_ui.print_warning(message)


def print_error(message: str) -> None:
    terminal_ui.print_error(message)


def print_section(title: str) -> None:
    terminal_ui.print_section(title)


def get_run_id() -> str:
    return _RUN_ID


def set_correlation_id(value: str) -> None:
    _CORRELATION_ID.set(value or _RUN_ID)


def get_correlation_id() -> str:
    return _CORRELATION_ID.get()


def prompt_required(prompt_text: str, default: str = "") -> str:
    return terminal_ui.prompt_required(prompt_text, default)


def print_confirm(message: str, default: bool = False) -> bool:
    return terminal_ui.print_confirm(message, default)


def prompt_yes_no_s(message: str, default: str = "n") -> bool:
    """Prompt SI/NO conservando semántica histórica ('s' como afirmativo)."""
    return terminal_ui.prompt_yes_no_s(message, default)


def prompt_optional(prompt_text: str, default: str = "") -> str:
    """Solicita un valor opcional (puede estar vacío)."""
    return terminal_ui.prompt_optional(prompt_text, default)


def print_progress_status(message: str) -> None:
    """Muestra un mensaje de estado/progreso."""
    terminal_ui.print_progress_status(message)


def print_separator(char: str = "─", width: int = 80) -> None:
    """Dibuja una línea separadora."""
    terminal_ui.print_separator(char, width)


def print_blank() -> None:
    """Imprime una línea vacía."""
    terminal_ui.print_blank()


def print_table(title: str, rows: list[tuple[str, str]]) -> None:
    terminal_ui.print_table(title, rows)


def print_list(title: str, items: list[str]) -> None:
    terminal_ui.print_list(title, items)


def seleccionar_opcion(lista: List[Any], mensaje: str, icono: str = "") -> Any:
    """Selector de opciones en consola (retorna el elemento seleccionado)."""
    return terminal_ui.seleccionar_opcion(lista, mensaje, icono)


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
        print_error(f"Error accediendo a {ruta}: {e}")
        return []


def asegurar_utf8_salida() -> None:
    """Asegura que stdout y stderr usen UTF-8 para que los emojis se impriman correctamente."""
    import sys

    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def configurar_logging(ruta_log_file: str) -> None:
    """Configura logging compatible + JSON paralelo con run_id/correlation_id."""
    from rich.logging import RichHandler

    asegurar_utf8_salida()
    os.makedirs(os.path.dirname(ruta_log_file), exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    context_filter = _ContextFilter()

    rich_handler = RichHandler(rich_tracebacks=True, markup=True)
    rich_handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))
    rich_handler.addFilter(context_filter)
    logger.addHandler(rich_handler)

    text_file_handler = logging.FileHandler(ruta_log_file, encoding="utf-8")
    text_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    text_file_handler.addFilter(context_filter)
    logger.addHandler(text_file_handler)

    json_log_path = os.path.splitext(ruta_log_file)[0] + ".jsonl"
    json_file_handler = logging.FileHandler(json_log_path, encoding="utf-8")
    json_file_handler.setFormatter(_JsonFormatter())
    json_file_handler.addFilter(context_filter)
    logger.addHandler(json_file_handler)


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
