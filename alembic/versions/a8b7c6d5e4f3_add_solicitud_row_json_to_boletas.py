"""add solicitud_row json to boletas

Revision ID: a8b7c6d5e4f3
Revises: 1f2e3d4c5b6a
Create Date: 2026-07-28 11:35:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a8b7c6d5e4f3"
down_revision = "1f2e3d4c5b6a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "boletas",
        sa.Column(
            "solicitud_row",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("boletas", "solicitud_row")
