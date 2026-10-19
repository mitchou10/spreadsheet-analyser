"""add ephemeral analyses

Revision ID: b4d6f8a0c2e5
Revises: a8c3d5e7f901
Create Date: 2026-10-20 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4d6f8a0c2e5"
down_revision: str | None = "a8c3d5e7f901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("collections", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("collections", sa.Column("ttl_hours", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_collections_expires_at"), "collections", ["expires_at"], unique=False)
    op.add_column("conversations", sa.Column("ephemeral_collection_id", sa.UUID(), nullable=True))
    op.create_index(
        op.f("ix_conversations_ephemeral_collection_id"), "conversations", ["ephemeral_collection_id"], unique=False
    )
    op.create_foreign_key(
        "fk_conversations_ephemeral_collection_id",
        "conversations",
        "collections",
        ["ephemeral_collection_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_conversations_ephemeral_collection_id", "conversations", type_="foreignkey")
    op.drop_index(op.f("ix_conversations_ephemeral_collection_id"), table_name="conversations")
    op.drop_column("conversations", "ephemeral_collection_id")
    op.drop_index(op.f("ix_collections_expires_at"), table_name="collections")
    op.drop_column("collections", "ttl_hours")
    op.drop_column("collections", "expires_at")
