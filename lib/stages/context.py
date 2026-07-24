"""Contexto de ejecución por etapa."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from interaction.types import SupervisionMode
from stages.bridged_args import BridgedContext


@dataclass
class Stage1Context:
    year: str | None = None
    month: str | None = None
    month_dir: str | None = None
    excel_file: str | None = None
    sheet: str | None = None
    strict: bool = False
    force_resend: bool = False
    fecha_limite_recepcion: str | None = None
    horario_recepcion: str | None = None
    fecha_limite_recordatorio: str | None = None
    horario_recordatorio: str | None = None
    allow_send: bool = False
    supervision_mode: SupervisionMode = SupervisionMode.BATCH
    supervised: bool = False
    streamlined: bool = False

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
            month_dir=getattr(args, "month_dir", None),
            excel_file=getattr(args, "excel_file", None),
            sheet=getattr(args, "sheet", None),
            strict=bool(getattr(args, "strict", False)),
            force_resend=bool(getattr(args, "force_resend", False)),
            fecha_limite_recepcion=getattr(args, "fecha_limite_recepcion", None),
            horario_recepcion=getattr(args, "horario_recepcion", None),
            fecha_limite_recordatorio=getattr(args, "fecha_limite_recordatorio", None),
            horario_recordatorio=getattr(args, "horario_recordatorio", None),
            allow_send=allow_send,
            supervision_mode=mode,
            streamlined=False,
        )

    @classmethod
    def from_api_params(cls, params: dict[str, Any]) -> "Stage1Context":
        from stages.streamlined import param_streamlined

        mode_raw = str(params.get("supervision_mode") or "batch")
        mode = (
            SupervisionMode.PER_MAIL
            if mode_raw == "per_mail"
            else SupervisionMode.BATCH
        )
        return cls(
            year=str(params.get("year")) if params.get("year") is not None else None,
            month=str(params.get("month") or ""),
            month_dir=(str(params["month_dir"]).strip() if params.get("month_dir") else None),
            excel_file=(str(params["excel_file"]).strip() if params.get("excel_file") else None),
            sheet=(str(params["sheet"]).strip() if params.get("sheet") else None),
            strict=bool(params.get("strict")),
            force_resend=bool(params.get("force_resend")),
            fecha_limite_recepcion=(
                str(params["fecha_limite_recepcion"]).strip()
                if params.get("fecha_limite_recepcion")
                else None
            ),
            horario_recepcion=(
                str(params["horario_recepcion"]).strip()
                if params.get("horario_recepcion")
                else None
            ),
            fecha_limite_recordatorio=(
                str(params["fecha_limite_recordatorio"]).strip()
                if params.get("fecha_limite_recordatorio")
                else None
            ),
            horario_recordatorio=(
                str(params["horario_recordatorio"]).strip()
                if params.get("horario_recordatorio")
                else None
            ),
            allow_send=bool(params.get("send")),
            supervision_mode=mode,
            supervised=True,
            streamlined=param_streamlined(params),
        )


@dataclass
class Stage2Context:
    fecha_inicio: str | None = None
    fecha_fin: str | None = None
    dry_run: bool = False
    duplicate_policy: str | None = None
    streamlined: bool = False

    @classmethod
    def from_args(cls, args: Any) -> "Stage2Context":
        return cls(
            fecha_inicio=getattr(args, "fecha_inicio", None),
            fecha_fin=getattr(args, "fecha_fin", None),
            dry_run=bool(getattr(args, "dry_run", False)),
            duplicate_policy=None,
            streamlined=False,
        )

    @classmethod
    def from_api_params(cls, params: dict[str, Any]) -> "Stage2Context":
        from stages.streamlined import param_streamlined

        dup = params.get("duplicate_policy")
        return cls(
            fecha_inicio=str(params["fecha_inicio"]) if params.get("fecha_inicio") else None,
            fecha_fin=str(params["fecha_fin"]) if params.get("fecha_fin") else None,
            dry_run=bool(params.get("dry_run")),
            duplicate_policy=str(dup).upper()[:1] if dup else None,
            streamlined=param_streamlined(params),
        )


@dataclass
class Stage3Context:
    year: str | None = None
    month: str | None = None
    month_dir: str | None = None
    excel_file: str | None = None
    sheet: str | None = None
    strict: bool = False
    supervised: bool = False
    streamlined: bool = False

    @classmethod
    def from_args(cls, args: Any) -> "Stage3Context":
        return cls(
            year=getattr(args, "year", None),
            month=getattr(args, "month", None),
            month_dir=getattr(args, "month_dir", None),
            excel_file=getattr(args, "excel_file", None),
            sheet=getattr(args, "sheet", None),
            strict=bool(getattr(args, "strict", False)),
            supervised=False,
            streamlined=False,
        )

    @classmethod
    def from_api_params(cls, params: dict[str, Any]) -> "Stage3Context":
        from stages.streamlined import param_streamlined

        return cls(
            year=str(params.get("year")) if params.get("year") is not None else None,
            month=str(params.get("month") or ""),
            month_dir=(str(params["month_dir"]).strip() if params.get("month_dir") else None),
            excel_file=(str(params["excel_file"]).strip() if params.get("excel_file") else None),
            sheet=(str(params["sheet"]).strip() if params.get("sheet") else None),
            strict=bool(params.get("strict")),
            supervised=True,
            streamlined=param_streamlined(params),
        )


@dataclass
class Stage4Context:
    year: str | None = None
    month: str | None = None
    month_dir: str | None = None
    excel_file: str | None = None
    sheet: str | None = None
    strict: bool = False
    supervised: bool = False
    overwrite_ok: bool | None = None
    streamlined: bool = False

    @classmethod
    def from_args(cls, args: Any) -> "Stage4Context":
        return cls(
            year=getattr(args, "year", None),
            month=getattr(args, "month", None),
            month_dir=getattr(args, "month_dir", None),
            excel_file=getattr(args, "excel_file", None),
            sheet=getattr(args, "sheet", None),
            strict=bool(getattr(args, "strict", False)),
            supervised=False,
            overwrite_ok=None,
            streamlined=False,
        )

    @classmethod
    def from_api_params(cls, params: dict[str, Any]) -> "Stage4Context":
        from stages.streamlined import param_streamlined

        ow = params.get("overwrite_ok")
        return cls(
            year=str(params.get("year")) if params.get("year") is not None else None,
            month=str(params.get("month") or ""),
            month_dir=(str(params["month_dir"]).strip() if params.get("month_dir") else None),
            excel_file=(str(params["excel_file"]).strip() if params.get("excel_file") else None),
            sheet=(str(params["sheet"]).strip() if params.get("sheet") else None),
            strict=bool(params.get("strict")),
            supervised=True,
            overwrite_ok=bool(ow) if ow is not None else None,
            streamlined=param_streamlined(params),
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
        mode_raw = str(params.get("supervision_mode") or "batch")
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
        mode_raw = str(params.get("supervision_mode") or "batch")
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


# --- Etapas bridged (0, 6, 8, 9, 10) --------------------------------------
#
# Estas etapas siguen ejecutando el script legacy en `etapas/` vía
# `stages.bridged_runner.run_bridged_stage`, pero exponen un contexto propio
# (subclase de `BridgedContext` con `stage_num` fijo) para que el runner
# interactivo las trate igual que las etapas ya migradas a servicio
# (`StageNContext.from_api_params` + `StageNService().run(ctx, ui)`).


@dataclass
class Stage0Context(BridgedContext):
    @classmethod
    def from_api_params(cls, params: dict[str, Any]) -> "Stage0Context":
        base = BridgedContext.from_api_params(0, params)
        return cls(**vars(base))


@dataclass
class Stage6Context(BridgedContext):
    @classmethod
    def from_api_params(cls, params: dict[str, Any]) -> "Stage6Context":
        base = BridgedContext.from_api_params(6, params)
        return cls(**vars(base))


@dataclass
class Stage8Context(BridgedContext):
    @classmethod
    def from_api_params(cls, params: dict[str, Any]) -> "Stage8Context":
        base = BridgedContext.from_api_params(8, params)
        return cls(**vars(base))


@dataclass
class Stage9Context(BridgedContext):
    @classmethod
    def from_api_params(cls, params: dict[str, Any]) -> "Stage9Context":
        base = BridgedContext.from_api_params(9, params)
        return cls(**vars(base))


@dataclass
class Stage10Context(BridgedContext):
    @classmethod
    def from_api_params(cls, params: dict[str, Any]) -> "Stage10Context":
        base = BridgedContext.from_api_params(10, params)
        return cls(**vars(base))
