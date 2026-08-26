"""Reinicio del servidor BH desde la API (misma máquina Windows)."""
from __future__ import annotations

import os
import subprocess
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def restart_server(*, port: int = 8000) -> dict[str, str]:
    """Lanza start-bh.ps1 -Restart en proceso separado."""
    if os.name != "nt":
        raise RuntimeError("El reinicio automático solo está disponible en Windows.")

    script = os.path.join(_REPO_ROOT, "scripts", "start-bh.ps1")
    if not os.path.isfile(script):
        # Compatibilidad si alguien deja el script en la raíz
        legacy = os.path.join(_REPO_ROOT, "start-bh.ps1")
        script = legacy if os.path.isfile(legacy) else script
    if not os.path.isfile(script):
        raise FileNotFoundError(f"No se encontró scripts/start-bh.ps1 en {_REPO_ROOT}")

    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        script,
        "-Restart",
        "-Port",
        str(port),
    ]
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    subprocess.Popen(
        cmd,
        cwd=_REPO_ROOT,
        creationflags=creationflags,
        close_fds=True,
    )
    return {
        "ok": True,
        "message": "Reiniciando servidor. La página se reconectará en unos segundos.",
    }
