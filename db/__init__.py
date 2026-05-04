"""Paquete de base de datos del proyecto."""

from db import pipeline_repository

from db import email_repository
from db import file_repository
from db import boleta_repository
from db import docente_repository
from db import xml_repository

__all__ = [
    "pipeline_repository",
    "email_repository",
    "file_repository",
    "boleta_repository",
    "docente_repository",
    "xml_repository",
]
