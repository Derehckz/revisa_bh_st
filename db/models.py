"""Modelos de trazabilidad y dominio mínimo del proyecto."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class Periodo(Base):
    __tablename__ = "periodos"
    __table_args__ = (
        UniqueConstraint("anio", "mes_num", name="uq_periodos_anio_mes"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anio: Mapped[int] = mapped_column(Integer, nullable=False)
    mes_num: Mapped[int] = mapped_column(Integer, nullable=False)
    mes_nombre: Mapped[str] = mapped_column(String(32), nullable=False)
    estado: Mapped[str] = mapped_column(String(16), nullable=False, default="abierto")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    informe_frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    informe_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    informe_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pagos_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pagos_frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contabilidad_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    contabilidad_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contabilidad_validated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contabilidad_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_ts", "ts"),
        Index("ix_audit_events_action", "action"),
        Index("ix_audit_events_period", "period_year", "period_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    operator: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    period_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period_month: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Docente(Base):
    __tablename__ = "docentes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rut: Mapped[str] = mapped_column(String(16), nullable=False, unique=True, index=True)
    rut_sin_dv: Mapped[str | None] = mapped_column(String(16), nullable=True)
    nombre_completo: Mapped[str] = mapped_column(String(256), nullable=False)
    email_personal: Mapped[str | None] = mapped_column(String(256), nullable=True)
    email_dp: Mapped[str | None] = mapped_column(String(256), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(64), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(256), nullable=True)
    sede: Mapped[str | None] = mapped_column(String(128), nullable=True)
    activo: Mapped[str] = mapped_column(String(8), nullable=False, default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DirectorPrograma(Base):
    """Director(a) de programa: un correo, una o más sedes."""

    __tablename__ = "directores_programa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str | None] = mapped_column(String(256), nullable=True)
    email: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    activo: Mapped[str] = mapped_column(String(8), nullable=False, default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    sedes: Mapped[list["DirectorSede"]] = relationship(
        back_populates="director",
        cascade="all, delete-orphan",
    )


class DirectorSede(Base):
    """Sede con un único DP vigente. Un DP puede cubrir varias sedes."""

    __tablename__ = "director_sedes"
    __table_args__ = (UniqueConstraint("sede", name="uq_director_sedes_sede"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    director_id: Mapped[int] = mapped_column(
        ForeignKey("directores_programa.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sede: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    director: Mapped[DirectorPrograma] = relationship(back_populates="sedes")


class Institucion(Base):
    __tablename__ = "instituciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo_location: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    tipo: Mapped[str] = mapped_column(String(16), nullable=False)
    rut_razon: Mapped[str] = mapped_column(String(16), nullable=False)
    nombre_razon: Mapped[str] = mapped_column(String(256), nullable=False)
    direccion_razon: Mapped[str | None] = mapped_column(String(256), nullable=True)
    glosa_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Boleta(Base):
    __tablename__ = "boletas"
    __table_args__ = (
        UniqueConstraint("periodo_id", "boleta_key", name="uq_boletas_periodo_boleta_key"),
        Index("ix_boletas_periodo_estado_recepcion", "periodo_id", "estado_recepcion"),
        Index("ix_boletas_periodo_id_id", "periodo_id", "id"),
        Index("ix_boletas_periodo_emplid", "periodo_id", "emplid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    periodo_id: Mapped[int | None] = mapped_column(ForeignKey("periodos.id", ondelete="SET NULL"), nullable=True, index=True)
    docente_id: Mapped[int | None] = mapped_column(ForeignKey("docentes.id", ondelete="SET NULL"), nullable=True, index=True)
    institucion_id: Mapped[int | None] = mapped_column(ForeignKey("instituciones.id", ondelete="SET NULL"), nullable=True, index=True)
    boleta_key: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    emplid: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    rut_razon: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    empl_rcd: Mapped[str | None] = mapped_column(String(16), nullable=True)
    monto_bruto: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    glosa: Mapped[str | None] = mapped_column(Text, nullable=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado_recepcion: Mapped[str | None] = mapped_column(String(32), nullable=True)
    observaciones_recepcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    recepcion_status: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    xml_status: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    mail_recepcion_status: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    glosa_match_mode: Mapped[str | None] = mapped_column(String(24), nullable=True)
    effective_status_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    estado_pago: Mapped[str | None] = mapped_column(String(32), nullable=True)
    observaciones_pago: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Snapshot completo de la fila Solicitud.xlsx (maestro + operación + XML).
    solicitud_row: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Archivo(Base):
    __tablename__ = "archivos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    boleta_id: Mapped[int | None] = mapped_column(ForeignKey("boletas.id", ondelete="SET NULL"), nullable=True, index=True)
    periodo_id: Mapped[int | None] = mapped_column(ForeignKey("periodos.id", ondelete="SET NULL"), nullable=True, index=True)
    tipo_archivo: Mapped[str] = mapped_column(String(16), nullable=False)
    nombre_original: Mapped[str] = mapped_column(String(512), nullable=False)
    ruta_relativa: Mapped[str] = mapped_column(String(1024), nullable=False)
    hash_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tamano_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fecha_origen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EnvioEmail(Base):
    __tablename__ = "envios_email"
    __table_args__ = (
        Index("ix_envios_email_periodo_estado_tipo", "periodo_id", "estado", "tipo_envio"),
        Index("ix_envios_email_periodo_id_id", "periodo_id", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    boleta_id: Mapped[int | None] = mapped_column(ForeignKey("boletas.id", ondelete="SET NULL"), nullable=True, index=True)
    docente_id: Mapped[int | None] = mapped_column(ForeignKey("docentes.id", ondelete="SET NULL"), nullable=True, index=True)
    periodo_id: Mapped[int | None] = mapped_column(ForeignKey("periodos.id", ondelete="SET NULL"), nullable=True, index=True)
    periodo_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tipo_envio: Mapped[str] = mapped_column(String(32), nullable=False)
    to_email: Mapped[str] = mapped_column(String(256), nullable=False)
    cc_email: Mapped[str | None] = mapped_column(String(512), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    estado: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDIENTE")
    error_detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class BoletaXmlData(Base):
    __tablename__ = "boleta_xml_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    boleta_id: Mapped[int] = mapped_column(ForeignKey("boletas.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    archivo_id: Mapped[int | None] = mapped_column(ForeignKey("archivos.id", ondelete="SET NULL"), nullable=True, index=True)
    rut_emisor: Mapped[str | None] = mapped_column(String(16), nullable=True)
    rut_receptor: Mapped[str | None] = mapped_column(String(16), nullable=True)
    numero_boleta: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fecha_boleta: Mapped[str | None] = mapped_column(String(32), nullable=True)
    total_honorarios: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    liquido_honorarios: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    impuesto_honorarios: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    porcentaje_impuesto: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    descripcion_linea: Mapped[str | None] = mapped_column(Text, nullable=True)
    observaciones_xml: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    period_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    triggered_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="INTERACTIVO")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RUNNING")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    stages: Mapped[list["PipelineStageRun"]] = relationship(
        back_populates="pipeline_run",
        cascade="all, delete-orphan",
    )


class PipelineStageRun(Base):
    __tablename__ = "pipeline_stage_runs"
    __table_args__ = (
        UniqueConstraint("pipeline_run_id", "stage_num", name="uq_pipeline_stage_per_run"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage_num: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_name: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RUNNING")
    rows_read: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_ok: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_error: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pipeline_run: Mapped[PipelineRun] = relationship(back_populates="stages")
