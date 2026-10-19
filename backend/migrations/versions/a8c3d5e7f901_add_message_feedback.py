"""add message feedback

Revision ID: a8c3d5e7f901
Revises: f2a6b1c9d7e4
Create Date: 2026-10-20 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a8c3d5e7f901"
down_revision: str | None = "f2a6b1c9d7e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RATING = postgresql.ENUM("up", "down", name="feedback_rating", create_type=False)
REASON = postgresql.ENUM(
    "wrong_result", "wrong_files", "incomplete", "unclear", "other", name="feedback_reason", create_type=False
)


def upgrade() -> None:
    RATING.create(op.get_bind(), checkfirst=True)
    REASON.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "message_feedback",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("rating", RATING, nullable=False),
        sa.Column("reason", REASON, nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", "user_id", name="uq_message_feedback_message_user"),
    )
    op.create_index(op.f("ix_message_feedback_message_id"), "message_feedback", ["message_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_message_feedback_message_id"), table_name="message_feedback")
    op.drop_table("message_feedback")
    REASON.drop(op.get_bind(), checkfirst=True)
    RATING.drop(op.get_bind(), checkfirst=True)
