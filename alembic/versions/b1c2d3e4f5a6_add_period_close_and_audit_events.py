"""add period close fields and audit_events

Revision ID: b1c2d3e4f5a6
Revises: a8b7c6d5e4f3
Create Date: 2026-07-28 11:50:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b1c2d3e4f5a6"
down_revision = "a8b7c6d5e4f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("periodos", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("periodos", sa.Column("closed_by", sa.String(length=128), nullable=True))
    op.add_column("periodos", sa.Column("informe_frozen_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("operator", sa.String(length=128), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=True),
        sa.Column("period_month", sa.String(length=32), nullable=True),
        sa.Column("entity", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.String(length=128), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_ts", "audit_events", ["ts"], unique=False)
    op.create_index("ix_audit_events_action", "audit_events", ["action"], unique=False)
    op.create_index(
        "ix_audit_events_period",
        "audit_events",
        ["period_year", "period_month"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_period", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_ts", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_column("periodos", "informe_frozen_at")
    op.drop_column("periodos", "closed_by")
    op.drop_column("periodos", "closed_at")
