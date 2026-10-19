"""reuse analyses by file hash

Revision ID: f2a6b1c9d7e4
Revises: c9e5a2f81d3b
Create Date: 2026-10-20 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a6b1c9d7e4"
down_revision: str | None = "c9e5a2f81d3b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(op.f("ix_files_file_hash"), "files", ["file_hash"], unique=False)
    op.add_column("analyses", sa.Column("analyzer_version", sa.String(length=32), nullable=True))
    op.add_column("analyses", sa.Column("source_analysis_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_analyses_source_analysis_id", "analyses", "analyses", ["source_analysis_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_analyses_source_analysis_id", "analyses", type_="foreignkey")
    op.drop_column("analyses", "source_analysis_id")
    op.drop_column("analyses", "analyzer_version")
    op.drop_index(op.f("ix_files_file_hash"), table_name="files")
