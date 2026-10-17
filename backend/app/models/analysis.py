import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, pg_enum

if TYPE_CHECKING:
    from app.models.file import File


class AnalysisStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"
    STOPPED = "stopped"


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (Index("ix_analyses_file_id_file_version", "file_id", "file_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"))
    # File.version this analysis was run against - the analysis of v1 stays valid once v2 is uploaded.
    file_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[AnalysisStatus] = mapped_column(
        pg_enum(AnalysisStatus, "analysis_status"), default=AnalysisStatus.PENDING
    )
    # <collection_id>/<file_id>/versions/<file_version>/analyse.json - only set once the analysis is READY.
    s3_key: Mapped[str | None] = mapped_column(String(1024), default=None)
    error: Mapped[str | None] = mapped_column(String(2048), default=None)
    # clock_timestamp(), not now(): now() is frozen for a whole transaction, and "latest analysis" is
    # decided by created_at, so two analyses queued in one transaction must still be ordered.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    file: Mapped["File"] = relationship(back_populates="analyses")
