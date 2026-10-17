import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, pg_enum


class RunStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIVE_RUN_STATUSES = (RunStatus.QUEUED, RunStatus.RUNNING)


class Run(Base):
    """One asynchronous execution of the AI agent, triggered by a user message and executed by the worker.

    The API answers the user message immediately with the queued run; the worker moves it
    queued -> running -> completed/failed and stores the assistant reply as a new message."""

    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    # The user message this run answers (and whose collection/file scope it works on).
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"))
    status: Mapped[RunStatus] = mapped_column(pg_enum(RunStatus, "run_status"), default=RunStatus.QUEUED, index=True)
    # Email of whoever sent the message (as in their token): collections shared with them are matched by
    # email, and the worker's agent must see exactly what that person may see.
    requester_email: Mapped[str | None] = mapped_column(String(320), default=None)
    # LLM the worker must use for this run (resolved when the message is sent: the user's pick or the default).
    model: Mapped[str | None] = mapped_column(String(255), default=None)
    # Celery task id, kept so a cancel can revoke the task if it has not started yet.
    task_id: Mapped[str | None] = mapped_column(String(255), default=None)
    # The assistant message produced by a COMPLETED run.
    result_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), default=None
    )
    error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
