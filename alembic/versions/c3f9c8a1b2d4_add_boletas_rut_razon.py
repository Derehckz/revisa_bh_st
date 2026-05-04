"""add boletas rut_razon

Revision ID: c3f9c8a1b2d4
Revises: 8b794a6dd566
Create Date: 2026-04-30 12:22:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c3f9c8a1b2d4"
down_revision = "8b794a6dd566"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("boletas", sa.Column("rut_razon", sa.String(length=16), nullable=True))
    op.create_index(op.f("ix_boletas_rut_razon"), "boletas", ["rut_razon"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_boletas_rut_razon"), table_name="boletas")
    op.drop_column("boletas", "rut_razon")

