"""add period informe and pagos snapshots

Revision ID: e4f5a6b7c8d9
Revises: c7d8e9f0a1b2
Create Date: 2026-07-30
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("periodos", sa.Column("informe_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("periodos", sa.Column("informe_sha256", sa.String(length=64), nullable=True))
    op.add_column("periodos", sa.Column("pagos_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("periodos", sa.Column("pagos_frozen_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("periodos", "pagos_frozen_at")
    op.drop_column("periodos", "pagos_snapshot")
    op.drop_column("periodos", "informe_sha256")
    op.drop_column("periodos", "informe_snapshot")
