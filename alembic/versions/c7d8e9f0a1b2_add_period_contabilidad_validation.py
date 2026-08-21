"""add period contabilidad validation fields

Revision ID: c7d8e9f0a1b2
Revises: b1c2d3e4f5a6
Create Date: 2026-07-28
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("periodos", sa.Column("contabilidad_status", sa.String(length=24), nullable=True))
    op.add_column("periodos", sa.Column("contabilidad_validated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("periodos", sa.Column("contabilidad_validated_by", sa.String(length=128), nullable=True))
    op.add_column("periodos", sa.Column("contabilidad_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("periodos", "contabilidad_notes")
    op.drop_column("periodos", "contabilidad_validated_by")
    op.drop_column("periodos", "contabilidad_validated_at")
    op.drop_column("periodos", "contabilidad_status")
