"""Versión de capacidades de la API (cambiar al alterar reglas visibles para la UI)."""
from __future__ import annotations

# Incrementar cuando cambien reglas de negocio que la UI asume (glosa, recepción, etc.).
CAPABILITIES_VERSION = 2

CAPABILITIES = {
    "glosa_estricta": True,
    "recepcion_estado_sync": True,
    "display_format_cl": True,
    "db_migrate_web": True,
    "period_verify_web": True,
    "server_restart_web": True,
}
