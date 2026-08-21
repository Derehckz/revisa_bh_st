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
import bh_errors
import terminal_ui

# Inicialización mínima para funciones utilitarias
colorama_init(autoreset=True)
console = terminal_ui.console


def _apply_non_interactive_env() -> None:
    v = os.environ.get("BH_NON_INTERACTIVE", "").strip().lower()
    if v in ("1", "true", "yes"):
        terminal_ui.set_non_interactive(True)


_apply_non_interactive_env()


def register_non_interactive_cli(parser, *, with_send: bool = False) -> None:
    """Flags estándar para scripts del pipeline (parse_args antes de main)."""
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Sin confirmaciones interactivas en consola.",
    )
    if with_send:
        parser.add_argument(
            "--send",
            action="store_true",
            help="Junto con --yes: permite envío real de correos (sin esto no se despachan).",
        )


def apply_non_interactive_from_args(args: Any) -> None:
    if getattr(args, "yes", False):
        terminal_ui.set_non_interactive(True)


def force_non_interactive() -> None:
    """Activa modo no interactivo (p. ej. flags legacy como --no-interactive en script 8)."""
    terminal_ui.set_non_interactive(True)


def register_period_args(parser: Any) -> None:
    """Añade --year / --month para carpeta de período (alternativa a BH_YEAR/BH_MONTH)."""
    parser.add_argument(
        "--year",
        type=str,
        default=None,
        metavar="Y",
        help="Carpeta año del período (ej. 2026). Con --month evita prompts y variables de entorno.",
    )
    parser.add_argument(
        "--month",
        type=str,
        default=None,
        metavar="MES",
        help="Carpeta mes del período (nombre, ej. Abril).",
    )


def is_non_interactive() -> bool:
    return terminal_ui.is_non_interactive()


def pick_excel_sheet(hojas: list[str], canonical: str = "Solicitud") -> str:
    """Elige hoja por nombre canónico o la primera del libro (modo batch)."""
    import schema_validator

    found = schema_validator.find_sheet(hojas, canonical)
    return found or (hojas[0] if hojas else "")


def seleccionar_opcion(lista: list[Any], mensaje: str, icono: str = "") -> Any:
    """Menú numerado en consola (delegado a terminal_ui)."""
    return terminal_ui.seleccionar_opcion(lista, mensaje, icono)


def choose_excel_sheet(
    hojas: list[str],
    *,
    sheet: str | None = None,
    canonical: str = "Solicitud",
    prompt_message: str = "Seleccione la hoja del Excel:",
    icon: str = "📄",
) -> str:
    """Elige hoja: --sheet explícito > canónica > batch/primer prompt."""
    import schema_validator

    if not hojas:
        raise ValueError("El archivo Excel no tiene hojas.")

    wanted = (sheet or "").strip()
    if wanted:
        if wanted not in hojas:
            raise ValueError(
                f"Hoja '{wanted}' no existe. Hojas disponibles: {', '.join(hojas)}"
            )
        print_info(f"Usando hoja indicada: '{wanted}'")
        return wanted

    found = schema_validator.find_sheet(hojas, canonical)
    if found and found in hojas:
        print_info(f"Usando hoja canónica detectada: '{found}'")
        return found

    if is_non_interactive():
        return pick_excel_sheet(hojas, canonical)

    return seleccionar_opcion(hojas, prompt_message, icon)


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


def mostrar_contexto_ejecucion(
    titulo: str,
    rutas: list[tuple[str, str]],
    preview_items: Optional[list[str]] = None,
    confirm_message: str = "¿Desea continuar con la ejecución? (s/n)",
    confirmar: bool = True,
) -> bool:
    """Muestra rutas clave + vista previa y confirma antes de ejecutar."""
    print_section(titulo)
    print_table("Carpetas y rutas utilizadas", [(str(k), str(v)) for k, v in rutas])
    if preview_items:
        print_list("Vista previa", [str(item) for item in preview_items])
    if not confirmar:
        return True
    if terminal_ui.is_non_interactive():
        print_info("Modo no interactivo: se continúa sin confirmación de contexto.")
        return True
    return prompt_yes_no_s(confirm_message, default="n")


def seleccionar_opcion(lista: List[Any], mensaje: str, icono: str = "") -> Any:
    """Selector de opciones en consola (retorna el elemento seleccionado)."""
    return terminal_ui.seleccionar_opcion(lista, mensaje, icono)


def email_from_cell(value: Any) -> str:
    """Normaliza una celda de correo (NaN/None/'nan' → vacío)."""
    if value is None:
        return ""
    if isinstance(value, float) and value != value:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "nat", "<na>"}:
        return ""
    return text


def validar_email(email: Optional[str]) -> bool:
    """Valida formato básico de correo electrónico."""
    text = email_from_cell(email)
    if not text:
        return False
    patron = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(patron, text))


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


def _commit_temp_to_target(tmp_path: str, target_path: str) -> None:
    """Publica un .xlsx temporal sobre el destino (reintentos + fallback en Windows)."""
    import shutil
    import stat
    import time

    tmp_path = os.path.abspath(tmp_path)
    target_path = os.path.abspath(target_path)
    target_dir = os.path.dirname(target_path) or "."
    os.makedirs(target_dir, exist_ok=True)

    def _clear_readonly(path: str) -> None:
        try:
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            pass

    delays = (0.0, 0.35, 0.7, 1.2, 2.0)
    last_err: OSError | None = None

    for delay in delays:
        if delay:
            time.sleep(delay)
        try:
            os.replace(tmp_path, target_path)
            return
        except OSError as e:
            last_err = e
            if getattr(e, "winerror", None) not in (5, 32) and e.errno not in (13, 16, 1):
                break

    for delay in delays:
        if delay:
            time.sleep(delay)
        try:
            if os.path.exists(target_path):
                _clear_readonly(target_path)
                os.remove(target_path)
            shutil.move(tmp_path, target_path)
            return
        except OSError as e:
            last_err = e

    try:
        if os.path.exists(target_path):
            _clear_readonly(target_path)
        shutil.copy2(tmp_path, target_path)
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return
    except OSError as e:
        last_err = e

    raise PermissionError(
        f"No se pudo guardar {target_path}. Cierre Excel, la vista previa del Explorador "
        f"o sincronización en esa carpeta. Detalle: {last_err}"
    ) from last_err


def atomic_excel_write(target_path: str, write_callable) -> str:
    """Escribe un Excel de forma atómica: backup + tmp + publicación al destino.

    `write_callable(tmp_path)` debe escribir todo el contenido al `tmp_path`.

    - Crea backup ZIP del archivo destino si existe.
    - Escribe a un archivo temporal en la misma carpeta (misma unidad que el destino).
    - Publica con reintentos y fallback si Windows bloquea `os.replace`.

    Devuelve la ruta del backup (o cadena vacía si no había archivo previo).
    """
    import gc
    import tempfile

    target_path = os.path.abspath(target_path)
    target_dir = os.path.dirname(target_path) or "."
    os.makedirs(target_dir, exist_ok=True)

    backup_path = ""
    if os.path.exists(target_path):
        try:
            backup_path = backup_file(target_path) or ""
        except OSError:
            backup_path = ""

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".xlsx", dir=target_dir)
    os.close(tmp_fd)

    try:
        write_callable(tmp_path)
        gc.collect()
        _commit_temp_to_target(tmp_path, target_path)
        return backup_path
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


def write_run_summary(run_id: str, payload: dict) -> str:
    """Escribe un resumen JSON consolidado de la corrida en `<RAIZ>/.state/runs/`.

    Devuelve la ruta del archivo escrito.
    """
    import config as _config

    runs_dir = os.path.join(_config.RAIZ, ".state", "runs")
    os.makedirs(runs_dir, exist_ok=True)
    summary_path = os.path.join(runs_dir, f"{run_id}.json")

    base = {
        "run_id": run_id,
        "written_at": datetime.utcnow().isoformat() + "Z",
    }
    base.update(payload or {})
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(base, fh, ensure_ascii=False, indent=2)
    return summary_path


def listar_carpetas(ruta):
    try:
        # Filtra solo carpetas relevantes: excluye .git, __pycache__, .gitignore, etc.
        carpetas = [
            d for d in os.listdir(ruta)
            if os.path.isdir(os.path.join(ruta, d))
            and not d.startswith('.')
            and not d.startswith('__')
        ]

        # Si en el nivel actual existen carpetas de año (ej: 2024, 2025, 2026),
        # priorizarlas para evitar mostrar carpetas técnicas (api, db, frontend, etc.).
        años = [d for d in carpetas if re.fullmatch(r"(19|20)\d{2}", str(d))]
        if años:
            return años

        return carpetas
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


def resolve_año_mes(
    raiz: str,
    year: Optional[str] = None,
    month: Optional[str] = None,
) -> tuple[str, str]:
    """Resuelve carpeta año/mes: --year/--month explícitos > env en batch > prompts."""
    y_in = (year or "").strip() or None
    m_in = (month or "").strip() or None
    if (y_in and not m_in) or (m_in and not y_in):
        raise ValueError(
            bh_errors.format_bh(
                "PERIOD_INCOMPLETE",
                "Indique ambos --year y --month o ninguno (para selección interactiva).",
            )
        )
    if y_in and m_in:
        ruta = os.path.join(raiz, y_in, m_in)
        if not os.path.isdir(ruta):
            raise ValueError(
                bh_errors.format_bh(
                    "PERIOD_NOT_FOUND",
                    f"No existe la carpeta del período: {ruta}",
                )
            )
        return y_in, m_in
    if terminal_ui.is_non_interactive():
        y = os.environ.get("BH_YEAR", "").strip()
        m = os.environ.get("BH_MONTH", "").strip()
        if y and m:
            ruta = os.path.join(raiz, y, m)
            if not os.path.isdir(ruta):
                raise ValueError(
                    bh_errors.format_bh(
                        "PERIOD_NOT_FOUND",
                        f"No existe la carpeta de período {y}/{m} bajo {raiz}",
                    )
                )
            return y, m
        raise ValueError(
            bh_errors.format_bh(
                "PERIOD_ENV_MISSING",
                "Modo no interactivo: use --year/--month o defina BH_YEAR y BH_MONTH.",
            )
        )
    años = listar_carpetas(raiz)
    if not años:
        raise ValueError(bh_errors.format_bh("NO_YEAR_FOLDERS", "No hay carpetas de año en la ruta configurada."))
    año = seleccionar_opcion(sorted(años), "Seleccione el año:", "🗓️")
    ruta_año = os.path.join(raiz, año)

    meses = listar_carpetas(ruta_año)
    if not meses:
        raise ValueError(bh_errors.format_bh("NO_MONTH_FOLDERS", f"No hay carpetas de mes en {ruta_año}"))
    mes = seleccionar_opcion(sorted(meses), "Seleccione el mes:", "🗓️")

    return año, mes


def seleccionar_año_mes(raiz: str) -> tuple[str, str]:
    """Selecciona año y mes de las carpetas disponibles (sin CLI; ver `resolve_año_mes`)."""
    return resolve_año_mes(raiz, None, None)
