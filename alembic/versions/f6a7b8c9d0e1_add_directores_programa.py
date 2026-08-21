"""add directores de programa and sede assignments

Revision ID: f6a7b8c9d0e1
Revises: e4f5a6b7c8d9
Create Date: 2026-08-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "directores_programa",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nombre", sa.String(length=256), nullable=True),
        sa.Column("email", sa.String(length=256), nullable=False),
        sa.Column("activo", sa.String(length=8), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_directores_programa_email", "directores_programa", ["email"], unique=True)

    op.create_table(
        "director_sedes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("director_id", sa.Integer(), nullable=False),
        sa.Column("sede", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["director_id"], ["directores_programa.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sede", name="uq_director_sedes_sede"),
    )
    op.create_index("ix_director_sedes_director_id", "director_sedes", ["director_id"], unique=False)
    op.create_index("ix_director_sedes_sede", "director_sedes", ["sede"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_director_sedes_sede", table_name="director_sedes")
    op.drop_index("ix_director_sedes_director_id", table_name="director_sedes")
    op.drop_table("director_sedes")
    op.drop_index("ix_directores_programa_email", table_name="directores_programa")
    op.drop_table("directores_programa")
