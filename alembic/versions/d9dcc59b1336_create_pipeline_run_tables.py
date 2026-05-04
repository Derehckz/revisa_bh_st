"""create pipeline run tables

Revision ID: d9dcc59b1336
Revises: 
Create Date: 2026-04-30 00:42:26.237891

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9dcc59b1336'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("period_label", sa.String(length=32), nullable=True),
        sa.Column("triggered_by", sa.String(length=128), nullable=True),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pipeline_runs_run_id", "pipeline_runs", ["run_id"], unique=True)

    op.create_table(
        "pipeline_stage_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pipeline_run_id", sa.Integer(), nullable=False),
        sa.Column("stage_num", sa.Integer(), nullable=False),
        sa.Column("stage_name", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("rows_read", sa.Integer(), nullable=True),
        sa.Column("rows_ok", sa.Integer(), nullable=True),
        sa.Column("rows_error", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pipeline_run_id", "stage_num", name="uq_pipeline_stage_per_run"),
    )
    op.create_index("ix_pipeline_stage_runs_pipeline_run_id", "pipeline_stage_runs", ["pipeline_run_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_pipeline_stage_runs_pipeline_run_id", table_name="pipeline_stage_runs")
    op.drop_table("pipeline_stage_runs")
    op.drop_index("ix_pipeline_runs_run_id", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
