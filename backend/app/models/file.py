import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.analysis import Analysis
    from app.models.collection import Collection


class File(Base):
    __tablename__ = "files"
    # A logical file is identified by its name inside a collection; re-uploading the same name creates a new version.
    __table_args__ = (UniqueConstraint("collection_id", "name", name="uq_files_collection_id_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(255), default=None)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    # sha256 hex digest of the file content, used to detect duplicate uploads.
    file_hash: Mapped[str] = mapped_column(String(64))
    # Bumped each time a new version of the same logical file is uploaded. Older versions stay in S3
    # under their own versions/<n>/ prefix; only the latest one is described by this row.
    version: Mapped[int] = mapped_column(Integer, default=1)
    # <collection_id>/<file_id>/versions/<version>/<raw-file-name> (see app.services.storage).
    s3_key: Mapped[str] = mapped_column(String(1024))
    uploaded_by: Mapped[str] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Joined: a message lists its files with the collection they come from, and lazy loading is not allowed in async.
    collection: Mapped["Collection"] = relationship(back_populates="files", lazy="joined")
    analyses: Mapped[list["Analysis"]] = relationship(back_populates="file", cascade="all, delete-orphan")
