import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, pg_enum


class ChartStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Chart(Base):
    """A chart of an assistant answer: the agent first runs a SQL query, then asks for a chart of its result.

    The query worker runs the query again (with room for more points than the agent sees), draws the chart and
    writes the PNG to S3 under the conversation and the message that shows it. The image is only ever served by
    the backend, to the person who owns the conversation."""

    __tablename__ = "charts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    # The assistant message that shows the chart. It does not exist yet while the run draws (it is stored when the
    # run completes, under the id the run reserved for it): no foreign key.
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    query_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sql_queries.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(150))
    # What to draw: {"type", "x", "y", "color", "title", ...}, validated when the chart is requested.
    spec: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[ChartStatus] = mapped_column(pg_enum(ChartStatus, "chart_status"), default=ChartStatus.QUEUED)
    # <project>/conversations/<conversation_id>/<message_id>/<chart_id>.png, set when the chart is requested.
    s3_key: Mapped[str] = mapped_column(String(1024))
    width: Mapped[int | None] = mapped_column(Integer, default=None)
    height: Mapped[int | None] = mapped_column(Integer, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    # On failure: the columns the query returns, so that the agent can correct its request.
    available_columns: Mapped[list[dict] | None] = mapped_column(JSONB, default=None)
    task_id: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
