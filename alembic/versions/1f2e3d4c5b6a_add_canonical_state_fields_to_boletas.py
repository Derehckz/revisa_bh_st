"""add canonical state fields to boletas

Revision ID: 1f2e3d4c5b6a
Revises: c3f9c8a1b2d4
Create Date: 2026-07-28 10:08:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1f2e3d4c5b6a"
down_revision = "c3f9c8a1b2d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("boletas", sa.Column("recepcion_status", sa.String(length=24), nullable=True))
    op.add_column("boletas", sa.Column("xml_status", sa.String(length=16), nullable=True))
    op.add_column("boletas", sa.Column("mail_recepcion_status", sa.String(length=24), nullable=True))
    op.add_column("boletas", sa.Column("glosa_match_mode", sa.String(length=24), nullable=True))
    op.add_column("boletas", sa.Column("effective_status_reason", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_boletas_recepcion_status"), "boletas", ["recepcion_status"], unique=False)
    op.create_index(op.f("ix_boletas_xml_status"), "boletas", ["xml_status"], unique=False)
    op.create_index(
        op.f("ix_boletas_mail_recepcion_status"),
        "boletas",
        ["mail_recepcion_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_boletas_mail_recepcion_status"), table_name="boletas")
    op.drop_index(op.f("ix_boletas_xml_status"), table_name="boletas")
    op.drop_index(op.f("ix_boletas_recepcion_status"), table_name="boletas")
    op.drop_column("boletas", "effective_status_reason")
    op.drop_column("boletas", "glosa_match_mode")
    op.drop_column("boletas", "mail_recepcion_status")
    op.drop_column("boletas", "xml_status")
    op.drop_column("boletas", "recepcion_status")
