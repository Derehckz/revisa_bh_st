"""Validaciones no bloqueantes de esquema para Excel/XML."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


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
