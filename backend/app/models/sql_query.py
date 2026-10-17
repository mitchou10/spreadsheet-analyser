import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, pg_enum


class SqlQueryStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SqlQuery(Base):
    """A SQL query the agent asked to run over the files of a run, executed by the analysis worker.

    The backend decides what the query may read (the files of the run's scope, analysed, readable by the person
    who asked), the worker runs it sandboxed on the Parquet copies of those files and reports a bounded result."""

    __tablename__ = "sql_queries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    sql: Mapped[str] = mapped_column(Text)
    # The files it may read, each under the name (the schema) the SQL uses:
    # [{"ref": "f1", "file_id": ..., "file_name": ..., "result_key": ".../analyse.json"}]
    tables: Mapped[list[dict]] = mapped_column(JSONB)
    status: Mapped[SqlQueryStatus] = mapped_column(
        pg_enum(SqlQueryStatus, "sql_query_status"), default=SqlQueryStatus.QUEUED, index=True
    )
    # {"columns": [{"name", "type"}], "rows": [[...]], "truncated": bool} once COMPLETED.
    result: Mapped[dict | None] = mapped_column(JSONB, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    # On failure: what could have been queried, as the SQL must name it, so that the author can correct itself.
    available_tables: Mapped[list[dict] | None] = mapped_column(JSONB, default=None)
    task_id: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
