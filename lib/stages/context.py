"""Contexto de ejecución por etapa."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from interaction.types import SupervisionMode


@dataclass
class Stage1Context:
    year: str | None = None
    month: str | None = None
    sheet: str | None = None
    strict: bool = False
    force_resend: bool = False
    allow_send: bool = False
    supervision_mode: SupervisionMode = SupervisionMode.BATCH

    @classmethod
    def from_args(cls, args: Any) -> "Stage1Context":
        import utils

        allow_send = (not utils.is_non_interactive()) or bool(getattr(args, "send", False))
        mode = SupervisionMode.BATCH
        if getattr(args, "supervision_mode", None) == "per_mail":
            mode = SupervisionMode.PER_MAIL
        return cls(
            year=getattr(args, "year", None),
            month=getattr(args, "month", None),
            sheet=getattr(args, "sheet", None),
            strict=bool(getattr(args, "strict", False)),
            force_resend=bool(getattr(args, "force_resend", False)),
            allow_send=allow_send,
            supervision_mode=mode,
        )

    @classmethod
    def from_api_params(cls, params: dict[str, Any]) -> "Stage1Context":
        mode_raw = str(params.get("supervision_mode") or "per_mail")
        mode = (
            SupervisionMode.PER_MAIL
            if mode_raw == "per_mail"
            else SupervisionMode.BATCH
        )
        return cls(
            year=str(params.get("year")) if params.get("year") is not None else None,
            month=str(params.get("month") or ""),
            sheet=(str(params["sheet"]).strip() if params.get("sheet") else None),
            strict=bool(params.get("strict")),
            force_resend=bool(params.get("force_resend")),
            allow_send=bool(params.get("send")),
            supervision_mode=mode,
        )


@dataclass
class Stage2Context:
    fecha_inicio: str | None = None
    fecha_fin: str | None = None
    dry_run: bool = False
    duplicate_policy: str | None = None

    @classmethod
    def from_args(cls, args: Any) -> "Stage2Context":
        return cls(
            fecha_inicio=getattr(args, "fecha_inicio", None),
            fecha_fin=getattr(args, "fecha_fin", None),
            dry_run=bool(getattr(args, "dry_run", False)),
            duplicate_policy=None,
        )

    @classmethod
    def from_api_params(cls, params: dict[str, Any]) -> "Stage2Context":
        dup = params.get("duplicate_policy")
        return cls(
            fecha_inicio=str(params["fecha_inicio"]) if params.get("fecha_inicio") else None,
            fecha_fin=str(params["fecha_fin"]) if params.get("fecha_fin") else None,
            dry_run=bool(params.get("dry_run")),
            duplicate_policy=str(dup).upper()[:1] if dup else None,
        )


@dataclass
class Stage3Context:
    year: str | None = None
    month: str | None = None
    sheet: str | None = None
    strict: bool = False
    supervised: bool = False

    @classmethod
    def from_args(cls, args: Any) -> "Stage3Context":
        return cls(
            year=getattr(args, "year", None),
            month=getattr(args, "month", None),
            sheet=getattr(args, "sheet", None),
            strict=bool(getattr(args, "strict", False)),
            supervised=False,
        )

    @classmethod
    def from_api_params(cls, params: dict[str, Any]) -> "Stage3Context":
        return cls(
            year=str(params.get("year")) if params.get("year") is not None else None,
            month=str(params.get("month") or ""),
            sheet=(str(params["sheet"]).strip() if params.get("sheet") else None),
            strict=bool(params.get("strict")),
            supervised=True,
        )


@dataclass
class Stage4Context:
    year: str | None = None
    month: str | None = None
    sheet: str | None = None
    strict: bool = False
    supervised: bool = False
    overwrite_ok: bool | None = None

    @classmethod
    def from_args(cls, args: Any) -> "Stage4Context":
        return cls(
            year=getattr(args, "year", None),
            month=getattr(args, "month", None),
            sheet=getattr(args, "sheet", None),
            strict=bool(getattr(args, "strict", False)),
            supervised=False,
            overwrite_ok=None,
        )

    @classmethod
    def from_api_params(cls, params: dict[str, Any]) -> "Stage4Context":
        ow = params.get("overwrite_ok")
        return cls(
            year=str(params.get("year")) if params.get("year") is not None else None,
            month=str(params.get("month") or ""),
            sheet=(str(params["sheet"]).strip() if params.get("sheet") else None),
            strict=bool(params.get("strict")),
            supervised=True,
            overwrite_ok=bool(ow) if ow is not None else None,
        )


@dataclass
class Stage5Context:
    year: str | None = None
    month: str | None = None
    force_resend: bool = False
    allow_send: bool = False
    supervised: bool = False
    supervision_mode: SupervisionMode = SupervisionMode.PER_MAIL

    @classmethod
    def from_args(cls, args: Any) -> "Stage5Context":
        import utils

        allow_send = (not utils.is_non_interactive()) or bool(getattr(args, "send", False))
        mode_raw = getattr(args, "supervision_mode", None) or "batch"
        mode = (
            SupervisionMode.PER_MAIL
            if mode_raw == "per_mail"
            else SupervisionMode.BATCH
        )
        return cls(
            year=getattr(args, "year", None),
            month=getattr(args, "month", None),
            force_resend=bool(getattr(args, "force_resend", False)),
            allow_send=allow_send,
            supervision_mode=mode,
        )

    @classmethod
    def from_api_params(cls, params: dict[str, Any]) -> "Stage5Context":
        mode_raw = str(params.get("supervision_mode") or "per_mail")
        mode = (
            SupervisionMode.PER_MAIL
            if mode_raw == "per_mail"
            else SupervisionMode.BATCH
        )
        return cls(
            year=str(params.get("year")) if params.get("year") is not None else None,
            month=str(params.get("month") or ""),
            force_resend=bool(params.get("force_resend")),
            allow_send=bool(params.get("send")),
            supervised=True,
            supervision_mode=mode,
        )


@dataclass
class Stage7Context:
    year: str | None = None
    month: str | None = None
    fecha_pago: str | None = None
    force_resend: bool = False
    allow_send: bool = False
    supervised: bool = False
    supervision_mode: SupervisionMode = SupervisionMode.PER_MAIL

    @classmethod
    def from_args(cls, args: Any) -> "Stage7Context":
        import utils

        allow_send = (not utils.is_non_interactive()) or bool(getattr(args, "send", False))
        mode_raw = getattr(args, "supervision_mode", None) or "batch"
        mode = (
            SupervisionMode.PER_MAIL
            if mode_raw == "per_mail"
            else SupervisionMode.BATCH
        )
        return cls(
            year=getattr(args, "year", None),
            month=getattr(args, "month", None),
            fecha_pago=getattr(args, "fecha_pago", None),
            force_resend=bool(getattr(args, "force_resend", False)),
            allow_send=allow_send,
            supervision_mode=mode,
        )

    @classmethod
    def from_api_params(cls, params: dict[str, Any]) -> "Stage7Context":
        mode_raw = str(params.get("supervision_mode") or "per_mail")
        mode = (
            SupervisionMode.PER_MAIL
            if mode_raw == "per_mail"
            else SupervisionMode.BATCH
        )
        fp = params.get("fecha_pago")
        return cls(
            year=str(params.get("year")) if params.get("year") is not None else None,
            month=str(params.get("month") or ""),
            fecha_pago=str(fp).strip() if fp else None,
            force_resend=bool(params.get("force_resend")),
            allow_send=bool(params.get("send")),
            supervised=True,
            supervision_mode=mode,
        )
