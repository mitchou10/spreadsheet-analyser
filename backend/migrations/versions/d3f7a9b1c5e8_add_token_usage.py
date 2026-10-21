"""add token usage

Revision ID: d3f7a9b1c5e8
Revises: b4d6f8a0c2e5
Create Date: 2026-10-21 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3f7a9b1c5e8"
down_revision: str | None = "b4d6f8a0c2e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "token_usage",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("user_email", sa.String(length=320), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("node", sa.String(length=100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_token_usage_run_id"), "token_usage", ["run_id"], unique=False)
    op.create_index(op.f("ix_token_usage_user_id"), "token_usage", ["user_id"], unique=False)
    op.create_index(op.f("ix_token_usage_node"), "token_usage", ["node"], unique=False)
    op.create_index(op.f("ix_token_usage_created_at"), "token_usage", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_token_usage_created_at"), table_name="token_usage")
    op.drop_index(op.f("ix_token_usage_node"), table_name="token_usage")
    op.drop_index(op.f("ix_token_usage_user_id"), table_name="token_usage")
    op.drop_index(op.f("ix_token_usage_run_id"), table_name="token_usage")
    op.drop_table("token_usage")
