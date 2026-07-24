"""Validaciones de esquema para Excel/XML del pipeline BH.

Este módulo cumple dos roles complementarios:

1) Helpers genéricos (no bloqueantes) usados por scripts existentes:
   - `validate_required_columns`
   - `validate_types`
   - `format_issues`

2) Esquema canónico versionado (Fase 3 del plan de auditoría):
   - `CANONICAL_SCHEMA`: contrato de columnas requeridas por etapa.
   - `CANONICAL_SHEETS`: nombres canónicos de hojas y aliases conocidos.
   - `CANONICAL_STATES`: enums válidos para estados de recepción.
   - `find_sheet`: localiza una hoja por nombre canónico tolerando alias,
     espacios, capitalización y acentos.
   - `validate_for_stage`: devuelve `errors` / `warnings` para una etapa.

La validación canónica se ofrece como *opt-in* (flag `--strict` por script)
para no romper flujos en producción mientras se rectifican datos.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Iterable, Optional


# ----------------------------------------------------------------------------
# Helpers existentes (compatibilidad hacia atrás)
# ----------------------------------------------------------------------------


@dataclass
class SchemaIssue:
    level: str
    field: str
    message: str


def validate_required_columns(columns: Iterable[str], required: Iterable[str]) -> list[SchemaIssue]:
    cols = {str(c).strip() for c in columns}
    issues: list[SchemaIssue] = []
    for field in required:
        if field not in cols:
            issues.append(SchemaIssue(level="WARN", field=field, message="Columna requerida ausente"))
    return issues


def validate_types(df, expectations: dict[str, tuple[type, ...]]) -> list[SchemaIssue]:
    issues: list[SchemaIssue] = []
    for field, allowed_types in expectations.items():
        if field not in df.columns:
            continue
        series = df[field].dropna()
        if series.empty:
            continue
        sample = series.iloc[0]
        if not isinstance(sample, allowed_types):
            issues.append(
                SchemaIssue(
                    level="WARN",
                    field=field,
                    message=f"Tipo no esperado en muestra: {type(sample).__name__}",
                )
            )
    return issues


def format_issues(issues: list[SchemaIssue], context: str) -> list[str]:
    if not issues:
        return []
    return [f"[{context}] {issue.level} {issue.field}: {issue.message}" for issue in issues]


# ----------------------------------------------------------------------------
# Esquema canónico (Solicitud.xlsx v1)
# ----------------------------------------------------------------------------

SCHEMA_VERSION = "1.0"

# Columnas mínimas que el archivo `Solicitud.xlsx` debe contener al inicio
# del flujo (post script 0 / inicio script 1).
SOLICITUD_BASE_COLUMNS: list[str] = [
    "EMPLID",
    "RUT_SIN_DV",
    "NAME",
    "LOCATION",
    "RUT RAZON",
    "NOMBRE RAZON",
    "DireccionRazon",
    "GLOSA",
    "MONTH",
    "YEAR",
    "CUS_TOT_HON",
    "Email_Docente",
    "Email_DP",
    "SEDE",
    "Correo Enviado",
    "Estado_Recepcion",
]

# Columnas adicionales que aparecen tras la validación de recepción
# (script 3) y que son requeridas por scripts posteriores.
SOLICITUD_RECEPCION_COLUMNS: list[str] = [
    "Observaciones",
    "Observacion_Descartes",
    "archivo_xml",
]

# Columnas que se agregan tras extraer datos del XML (script 4) y que son
# requeridas por scripts de informe y notificaciones.
SOLICITUD_XML_COLUMNS: list[str] = [
    "rutEmisorCompleto_XML",
    "rutReceptorCompleto_XML",
    "nombreReceptor_XML",
    "totalHonorarios_XML",
    "numeroBoleta_XML",
    "fechaBoleta_XML",
    "Observaciones_XML",
]

# Esquema canónico por etapa del pipeline.
CANONICAL_SCHEMA: dict[str, list[str]] = {
    "stage1_envio_inicial": SOLICITUD_BASE_COLUMNS,
    "stage3_validacion_recepcion": SOLICITUD_BASE_COLUMNS,
    "stage4_extraccion_xml": SOLICITUD_BASE_COLUMNS + SOLICITUD_RECEPCION_COLUMNS,
    "stage5_envio_recepcion": SOLICITUD_BASE_COLUMNS + SOLICITUD_RECEPCION_COLUMNS + SOLICITUD_XML_COLUMNS,
    "stage6_informe_final": SOLICITUD_BASE_COLUMNS + SOLICITUD_RECEPCION_COLUMNS + SOLICITUD_XML_COLUMNS,
}

# Tipos esperados (heurística mínima sobre primera muestra no nula).
CANONICAL_TYPES: dict[str, tuple[type, ...]] = {
    "NAME": (str,),
    "Email_Docente": (str,),
    "MONTH": (str, int),
    "YEAR": (int, float, str),
}

# Nombres canónicos de hojas usadas en el flujo y sus aliases conocidos.
CANONICAL_SHEETS: dict[str, list[str]] = {
    "Solicitud": ["Solicitud", "solicitud"],
    "Resumen Boletas": ["Resumen Boletas", "Resumen de Boletas", "ResumenBoletas"],
    "Pagos": ["Pagos", "pagos", "PAGOS"],
}

# Enums válidos para columnas de estado.
CANONICAL_STATES: dict[str, set[str]] = {
    "Estado_Recepcion": {
        "",
        "RECIBIDO",
        "RECIBIDO CON ERROR",
        "NO RECIBIDO",
    },
    # Observaciones_XML es texto libre (paso 4 escribe muchos mensajes distintos).
}


def _sample_matches_types(sample, allowed: tuple[type, ...]) -> bool:
    """Acepta int/float de numpy/pandas además de tipos Python nativos."""
    if isinstance(sample, allowed):
        return True
    try:
        import numpy as np

        if int in allowed and isinstance(sample, np.integer):
            return True
        if float in allowed and isinstance(sample, np.floating):
            return True
    except ImportError:
        pass
    return False


def _normalize_name(value: str) -> str:
    """Quita acentos/espacios/casos para comparar nombres de hoja o campo."""
    if value is None:
        return ""
    s = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return "".join(s.split()).lower()


def find_sheet(hojas: Iterable[str], canonical: str) -> Optional[str]:
    """Devuelve el nombre real de la hoja que corresponde al canónico, o None.

    Tolerante a variaciones de espaciado, capitalización y acentos.
    """
    aliases = CANONICAL_SHEETS.get(canonical, [canonical])
    targets = {_normalize_name(a) for a in aliases}
    for hoja in hojas:
        if _normalize_name(hoja) in targets:
            return hoja
    return None


def validate_for_stage(df, stage_key: str) -> tuple[list[str], list[str]]:
    """Valida el DataFrame contra el contrato canónico de una etapa.

    Devuelve `(errors, warnings)`:
      - errors: lista de problemas que deberían bloquear ejecución en modo strict.
      - warnings: lista de advertencias informativas.
    """
    errors: list[str] = []
    warnings: list[str] = []

    required = CANONICAL_SCHEMA.get(stage_key)
    if not required:
        warnings.append(f"Etapa desconocida en schema canónico: {stage_key}")
        return errors, warnings

    cols = {str(c).strip() for c in df.columns}
    for field in required:
        if field not in cols:
            errors.append(f"Columna requerida ausente: {field}")

    for field, allowed in CANONICAL_TYPES.items():
        if field not in df.columns:
            continue
        series = df[field].dropna()
        if series.empty:
            continue
        sample = series.iloc[0]
        if not _sample_matches_types(sample, allowed):
            warnings.append(
                f"Tipo inesperado en {field}: {type(sample).__name__} (esperado {[t.__name__ for t in allowed]})"
            )

    for field, valid_values in CANONICAL_STATES.items():
        if field not in df.columns:
            continue
        valores = df[field].dropna().astype(str).str.strip().str.upper()
        invalidos = [v for v in valores.unique() if v not in {x.upper() for x in valid_values}]
        if invalidos:
            warnings.append(
                f"Valores fuera de enum en {field}: {invalidos[:5]}{'...' if len(invalidos) > 5 else ''}"
            )

    return errors, warnings
