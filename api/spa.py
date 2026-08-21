"""Sirve el frontend React (frontend/dist) como SPA desde la misma API."""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIST = os.path.join(_REPO, "frontend", "dist")

# Prefijos de API / docs — no deben caer en el fallback SPA.
_API_PREFIXES = (
    "/health",
    "/periods",
    "/period",
    "/runs",
    "/stats",
    "/docentes",
    "/directores",
    "/operations",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/openapi",
)

_NO_CACHE_HTML = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


def frontend_dist_ready() -> bool:
    return os.path.isfile(os.path.join(FRONTEND_DIST, "index.html"))


def is_api_or_docs_path(path: str) -> bool:
    if path == "/":
        return False
    for prefix in _API_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def _html_index() -> FileResponse:
    return FileResponse(
        os.path.join(FRONTEND_DIST, "index.html"),
        media_type="text/html",
        headers=_NO_CACHE_HTML,
    )


class _HashedAssets(StaticFiles):
    """Assets con hash en el nombre: cache agresivo en el navegador."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def mount_frontend_spa(app: FastAPI) -> bool:
    """Monta assets + fallback SPA. Debe llamarse al final del registro de rutas."""
    if not frontend_dist_ready():
        return False

    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", _HashedAssets(directory=assets_dir), name="frontend-assets")

    @app.get("/", include_in_schema=False)
    async def spa_index():
        return _html_index()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        path = "/" + full_path
        if is_api_or_docs_path(path):
            raise HTTPException(status_code=404, detail="Not Found")

        candidate = os.path.normpath(os.path.join(FRONTEND_DIST, full_path))
        if not candidate.startswith(os.path.normpath(FRONTEND_DIST)):
            raise HTTPException(status_code=404, detail="Not Found")
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return _html_index()

    return True
