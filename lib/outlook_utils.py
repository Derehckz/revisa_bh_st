"""Conexión COM a Outlook (Windows)."""
from __future__ import annotations

import logging
import os
import subprocess
import time
from datetime import datetime
from typing import Callable

import utils

utils.asegurar_utf8_salida()

CancelCheck = Callable[[], bool]


def _outlook_process_running() -> bool:
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq OUTLOOK.EXE", "/NH"],
            text=True,
            errors="ignore",
            creationflags=flags,
        )
        return "OUTLOOK.EXE" in out.upper()
    except Exception:
        return False


def _outlook_exe_candidates() -> list[str]:
    roots = [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("LOCALAPPDATA", ""),
    ]
    rels = [
        r"Microsoft Office\root\Office16\OUTLOOK.EXE",
        r"Microsoft Office\Office16\OUTLOOK.EXE",
        r"Microsoft Office\root\Office15\OUTLOOK.EXE",
        r"Microsoft Office\Office15\OUTLOOK.EXE",
        r"Microsoft\WindowsApps\Microsoft.OutlookForWindows_8wekyb3d8bbwe\outlook.exe",
    ]
    paths: list[str] = []
    for root in roots:
        if not root:
            continue
        for rel in rels:
            paths.append(os.path.join(root, rel))
    return paths


def asegurar_outlook_abierto(*, log: Callable[[str], None] | None = None) -> None:
    """Si Outlook no está en ejecución, lo inicia."""
    _log = log or (lambda m: logging.info(m))
    if _outlook_process_running():
        return

    _log("Outlook estaba cerrado; abriéndolo…")
    launched = False
    for path in _outlook_exe_candidates():
        if os.path.isfile(path):
            try:
                subprocess.Popen([path], close_fds=True)
                launched = True
                break
            except OSError as e:
                logging.warning("No se pudo lanzar %s: %s", path, e)

    if not launched:
        try:
            # Fallback: protocolo / PATH
            os.startfile("outlook")  # type: ignore[attr-defined]
            launched = True
        except OSError:
            try:
                subprocess.Popen(
                    ["cmd", "/c", "start", "", "outlook.exe"],
                    shell=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                launched = True
            except OSError as e:
                raise RuntimeError(
                    "No se pudo abrir Outlook automáticamente. Ábrelo manualmente e inténtalo de nuevo."
                ) from e

    if launched:
        _log("Esperando a que Outlook termine de iniciar…")


def check_outlook_health(*, probe_com: bool = True) -> dict:
    """
    Preflight de Outlook para etapas 1/2/5/7.

    No lanza Outlook; solo reporta estado. `ready` es True si el proceso corre
    (y, si probe_com, si COM responde).
    """
    process_running = _outlook_process_running()
    exe_found = any(os.path.isfile(p) for p in _outlook_exe_candidates())
    com_ok: bool | None = None
    com_error: str | None = None

    if probe_com and process_running:
        try:
            import win32com.client

            app = win32com.client.Dispatch("Outlook.Application")
            _ = app.GetNamespace("MAPI")
            com_ok = True
        except Exception as e:
            com_ok = False
            com_error = str(e)

    if process_running and com_ok is not False:
        ready = True
        message = "Outlook está listo."
    elif process_running and com_ok is False:
        ready = False
        message = (
            "Outlook está abierto pero no responde (COM). "
            "Ciérralo y vuelve a abrirlo, o reinicia Outlook."
        )
    elif exe_found:
        ready = False
        message = (
            "Outlook está cerrado. Ábrelo o inicia el paso: el sistema intentará abrirlo solo."
        )
    else:
        ready = False
        message = (
            "No se encontró Outlook en este equipo. Instala Outlook de escritorio "
            "o ábrelo manualmente antes de enviar/bajar correos."
        )

    return {
        "ready": ready,
        "process_running": process_running,
        "exe_found": exe_found,
        "com_ok": com_ok,
        "com_error": com_error,
        "can_auto_launch": exe_found and not process_running,
        "message": message,
        "required_for_stages": [1, 2, 5, 7],
    }


def conectar_outlook_app(
    *,
    ensure_running: bool = True,
    wait_s: float = 60,
    cancel_check: CancelCheck | None = None,
    progress_log: Callable[[str], None] | None = None,
):
    """
    Conecta a Outlook y devuelve la aplicación.
    Si ensure_running=True y Outlook está cerrado, lo abre y reintenta.
    """
    import win32com.client

    _log = progress_log or (lambda m: logging.info(m))
    _log("Conectando a Outlook…")

    if ensure_running:
        asegurar_outlook_abierto(log=_log)

    deadline = time.time() + max(5.0, wait_s)
    last_err: Exception | None = None
    attempt = 0

    while time.time() < deadline:
        if cancel_check and cancel_check():
            from interaction.exceptions import SessionCancelled

            raise SessionCancelled()
        attempt += 1
        try:
            outlook_app = win32com.client.Dispatch("Outlook.Application")
            # Fuerza carga de perfil MAPI
            _ = outlook_app.GetNamespace("MAPI")
            usuario = outlook_app.Session.CurrentUser.Name
            _log(f"Conectado a Outlook: {usuario}")
            logging.info("Conectado a la cuenta: %s", usuario)
            return outlook_app
        except Exception as e:
            last_err = e
            logging.warning("Intento Outlook %s falló: %s", attempt, e)
            if attempt == 1 or attempt % 3 == 0:
                _log(f"Outlook aún no responde (intento {attempt}). Esperando…")
            # Si el proceso no apareció, reintentar apertura
            if ensure_running and not _outlook_process_running():
                try:
                    asegurar_outlook_abierto(log=_log)
                except Exception as launch_err:
                    last_err = launch_err
            time.sleep(2.0)

    msg = (
        "No fue posible conectar a Outlook. Ábrelo en este equipo, inicia sesión si pide "
        f"credenciales, y vuelve a intentar. Detalle: {last_err}"
    )
    logging.error(msg)
    raise RuntimeError(msg) from last_err


def conectar_outlook_ns(
    *,
    ensure_running: bool = True,
    wait_s: float = 60,
    cancel_check: CancelCheck | None = None,
    progress_log: Callable[[str], None] | None = None,
):
    """Conecta a Outlook y devuelve el namespace MAPI."""
    outlook_app = conectar_outlook_app(
        ensure_running=ensure_running,
        wait_s=wait_s,
        cancel_check=cancel_check,
        progress_log=progress_log,
    )
    return outlook_app.GetNamespace("MAPI")


def filtrar_correos_por_fecha(folder, fecha_inicio: datetime, fecha_fin: datetime):
    """Filtra correos en la carpeta dada por rango de fechas."""
    filtro = (
        f"[ReceivedTime] >= '{fecha_inicio.strftime('%m/%d/%Y %I:%M %p')}' AND "
        f"[ReceivedTime] <= '{fecha_fin.strftime('%m/%d/%Y %I:%M %p')}'"
    )
    logging.info("Aplicando filtro: %s", filtro)
    items = folder.Items
    items.Sort("[ReceivedTime]", True)
    try:
        filtrados = items.Restrict(filtro)
        mensajes = [msg for msg in filtrados if getattr(msg, "Class", None) == 43]
        logging.info("Correos encontrados en rango: %s", len(mensajes))
        utils.print_success(f"Correos encontrados en rango: {len(mensajes)}")
        return mensajes
    except Exception as e:
        logging.error("Error al filtrar correos: %s", e)
        utils.print_error(f"Error al filtrar correos: {e}")
        return []
