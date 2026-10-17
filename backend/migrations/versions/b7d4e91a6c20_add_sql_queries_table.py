"""add sql queries table

Revision ID: b7d4e91a6c20
Revises: a3f1c8d52b97
Create Date: 2026-10-17 20:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7d4e91a6c20"
down_revision: str | None = "a3f1c8d52b97"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sql_queries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("sql", sa.Text(), nullable=False),
        sa.Column("tables", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "completed", "failed", name="sql_query_status"),
            nullable=False,
        ),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("available_tables", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("task_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_sql_queries_run_id_runs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sql_queries")),
    )
    op.create_index(op.f("ix_sql_queries_run_id"), "sql_queries", ["run_id"], unique=False)
    op.create_index(op.f("ix_sql_queries_status"), "sql_queries", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sql_queries_status"), table_name="sql_queries")
    op.drop_index(op.f("ix_sql_queries_run_id"), table_name="sql_queries")
    op.drop_table("sql_queries")
    op.execute("DROP TYPE sql_query_status")
