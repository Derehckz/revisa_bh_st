"""Lock por período (año/mes) para evitar ejecuciones concurrentes.

Diseño minimalista compatible con Windows:

- El lock es un archivo en `<RAIZ>/.state/locks/<year>_<month>.lock`.
- Contenido: JSON con `pid`, `hostname`, `started_at`, `script`.
- Si el archivo existe pero el PID ya no está vivo (lock huérfano), se puede
  liberar automáticamente con `force=True`.
- Uso preferido: `with PeriodLock(year, month, script="main.py"): ...`

Esta capa no es transaccional (no hay garantía absoluta entre máquinas), pero
cubre el caso operativo más frecuente: dos ventanas en el mismo equipo
ejecutando el mismo período en paralelo.
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
from datetime import datetime
from typing import Optional

import config


class PeriodLockError(RuntimeError):
    """Error genérico del lock por período."""


# Guarda en memoria del proceso (además del archivo). El archivo por sí solo no
# detecta conflictos entre dos `PeriodLock` distintos creados por el MISMO
# proceso (mismo pid) — caso típico del servidor API, donde una sesión
# interactiva y un job pueden competir por el mismo período dentro del mismo
# proceso uvicorn. Esta guarda cierra ese hueco sin afectar el comportamiento
# entre procesos (main.py, scripts de consola), que sigue dependiendo del
# archivo + pid.
_ACTIVE_LOCKS: dict[tuple[str, str], "PeriodLock"] = {}
_ACTIVE_LOCKS_GUARD = threading.Lock()


class PeriodLock:
    def __init__(self, year: Optional[str], month: Optional[str], script: str = "unknown"):
        self.year = str(year) if year else "NA"
        self.month = str(month) if month else "NA"
        self.script = script
        self._acquired = False

    @property
    def lock_dir(self) -> str:
        path = os.path.join(config.RAIZ, ".state", "locks")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def lock_path(self) -> str:
        return os.path.join(self.lock_dir, f"{self.year}_{self.month}.lock")

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            if os.name == "nt":
                # tasklist con CSV/NH devuelve líneas solo si encontró el PID;
                # si el PID no existe, stdout queda vacío o con "INFO:".
                import subprocess
                out = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                stdout = (out.stdout or "").strip()
                if not stdout:
                    return False
                # Mensajes informativos de "no encontrado" en distintos idiomas
                lowered = stdout.lower()
                if lowered.startswith("info:") or "no tasks" in lowered or "ninguna tarea" in lowered:
                    return False
                # Si llegamos aquí y aparece la columna con el PID, está vivo
                return f'"{pid}"' in stdout or f",{pid}," in stdout
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def read(self) -> Optional[dict]:
        if not os.path.isfile(self.lock_path):
            return None
        try:
            with open(self.lock_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None

    @property
    def _key(self) -> tuple[str, str]:
        return (self.year, self.month)

    def acquire(self, force: bool = False) -> None:
        with _ACTIVE_LOCKS_GUARD:
            holder = _ACTIVE_LOCKS.get(self._key)
            if holder is not None and holder is not self and not force:
                raise PeriodLockError(
                    f"Lock activo para período {self.year}/{self.month} en este mismo "
                    f"proceso (script={holder.script}). Espere a que termine."
                )

            existing = self.read()
            if existing:
                pid = int(existing.get("pid", 0) or 0)
                if pid != os.getpid() and self._pid_alive(pid) and not force:
                    raise PeriodLockError(
                        f"Lock activo para período {self.year}/{self.month} "
                        f"(pid={pid}, host={existing.get('hostname')}, "
                        f"script={existing.get('script')}). "
                        "Espere o use force=True / --force-lock."
                    )

            payload = {
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "started_at": datetime.utcnow().isoformat(),
                "script": self.script,
                "year": self.year,
                "month": self.month,
            }
            with open(self.lock_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            self._acquired = True
            _ACTIVE_LOCKS[self._key] = self

    def release(self) -> None:
        if not self._acquired:
            return
        try:
            existing = self.read()
            if existing and int(existing.get("pid", 0) or 0) == os.getpid():
                os.remove(self.lock_path)
        except OSError:
            pass
        self._acquired = False
        with _ACTIVE_LOCKS_GUARD:
            if _ACTIVE_LOCKS.get(self._key) is self:
                del _ACTIVE_LOCKS[self._key]

    def __enter__(self) -> "PeriodLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


def break_stale(year: str, month: str) -> bool:
    """Libera un lock si su PID ya no está vivo. Devuelve True si se liberó."""
    lock = PeriodLock(year, month)
    existing = lock.read()
    if not existing:
        return False
    pid = int(existing.get("pid", 0) or 0)
    if PeriodLock._pid_alive(pid):
        return False
    try:
        os.remove(lock.lock_path)
        return True
    except OSError:
        return False
