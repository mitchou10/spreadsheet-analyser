"""add charts table

Revision ID: c9e5a2f81d3b
Revises: b7d4e91a6c20
Create Date: 2026-10-18 09:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c9e5a2f81d3b"
down_revision: str | None = "b7d4e91a6c20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("answer_message_id", sa.UUID(), nullable=True))
    op.create_table(
        "charts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("query_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Enum("queued", "running", "completed", "failed", name="chart_status"), nullable=False),
        sa.Column("s3_key", sa.String(length=1024), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("available_columns", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("task_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_charts_run_id_runs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_charts_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["query_id"], ["sql_queries.id"], name=op.f("fk_charts_query_id_sql_queries"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_charts")),
    )
    op.create_index(op.f("ix_charts_run_id"), "charts", ["run_id"], unique=False)
    op.create_index(op.f("ix_charts_conversation_id"), "charts", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_charts_message_id"), "charts", ["message_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_charts_message_id"), table_name="charts")
    op.drop_index(op.f("ix_charts_conversation_id"), table_name="charts")
    op.drop_index(op.f("ix_charts_run_id"), table_name="charts")
    op.drop_table("charts")
    op.execute("DROP TYPE chart_status")
    op.drop_column("runs", "answer_message_id")
