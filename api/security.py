"""Controles de seguridad y configuracion HTTP para API."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from settings import get_setting


def get_cors_origins() -> list[str]:
    raw = get_setting("BH_API_CORS_ORIGINS", "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def install_cors(app) -> None:
    origins = get_cors_origins()
    if not origins:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    valid_keys = get_api_keys()
    if not valid_keys:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SECURITY_NOT_CONFIGURED",
                "message": "API key no configurada en servidor",
                "details": {"required_env": "BH_API_KEY o BH_API_KEYS"},
            },
        )
    if not x_api_key or x_api_key not in valid_keys:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "UNAUTHORIZED",
                "message": "x-api-key invalida o ausente",
                "details": {},
            },
        )


def get_operator_name(x_operator_name: str | None = Header(default=None)) -> str | None:
    """Nombre del operador enviado por la UI (auditoría suave)."""
    name = (x_operator_name or "").strip()
    return name[:128] if name else None


def get_api_keys() -> set[str]:
    keys: set[str] = set()
    primary = get_setting("BH_API_KEY", "").strip()
    if primary:
        keys.add(primary)

    previous = get_setting("BH_API_KEY_PREVIOUS", "").strip()
    if previous:
        keys.add(previous)

    multi = get_setting("BH_API_KEYS", "").strip()
    if multi:
        keys.update(item.strip() for item in multi.split(",") if item.strip())

    return keys


_RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_RATE_LOCK = threading.Lock()


def _get_rate_config() -> tuple[int, int]:
    try:
        max_requests = int(get_setting("BH_API_RATE_LIMIT_MAX_REQUESTS", "120"))
    except ValueError:
        max_requests = 120
    try:
        window_seconds = int(get_setting("BH_API_RATE_LIMIT_WINDOW_SECONDS", "60"))
    except ValueError:
        window_seconds = 60
    return max(1, max_requests), max(1, window_seconds)


def _is_rate_limit_enabled() -> bool:
    raw = get_setting("BH_API_RATE_LIMIT_ENABLED", "1").strip().lower()
    return raw in {"1", "true", "yes", "y", "si", "s"}


def check_rate_limit(client_ip: str, api_key: str | None) -> dict:
    if not _is_rate_limit_enabled():
        return {"limited": False}

    max_requests, window_seconds = _get_rate_config()
    safe_key = api_key.strip() if api_key else "no-key"
    bucket_key = f"{client_ip}|{safe_key}"
    now = time.monotonic()
    window_start = now - window_seconds

    with _RATE_LOCK:
        bucket = _RATE_BUCKETS[bucket_key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= max_requests:
            retry_after = max(1, int(window_seconds - (now - bucket[0])))
            return {
                "limited": True,
                "retry_after": retry_after,
                "limit": max_requests,
                "window_seconds": window_seconds,
            }
        bucket.append(now)

    return {"limited": False, "limit": max_requests, "window_seconds": window_seconds}
