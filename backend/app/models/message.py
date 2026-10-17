import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, pg_enum

if TYPE_CHECKING:
    from app.models.collection import Collection
    from app.models.conversation import Conversation
    from app.models.file import File


class MessageRole(enum.StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


# Link rows are removed with either side, so deleting a collection/file just narrows old messages' scope
# and never blocks the delete or loses chat history.
message_collections = Table(
    "message_collections",
    Base.metadata,
    Column("message_id", UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True),
    Column("collection_id", UUID(as_uuid=True), ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
)

message_files = Table(
    "message_files",
    Base.metadata,
    Column("message_id", UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True),
    Column("file_id", UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True),
)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(pg_enum(MessageRole, "message_role"))
    content: Mapped[str | None] = mapped_column(Text, default=None)
    # Tool calls requested by the assistant, e.g. [{"id": ..., "name": ..., "arguments": {...}}].
    tool_calls: Mapped[list[dict] | None] = mapped_column(JSONB, default=None)
    # How an assistant answer was produced: {"plan", "files", "steps": [{"tool", "arguments", "output"}]}.
    trace: Mapped[dict | None] = mapped_column(JSONB, default=None)
    # Set on role=TOOL messages: which tool_calls[].id this message answers.
    tool_call_id: Mapped[str | None] = mapped_column(String(255), default=None)
    # Set by the application (microsecond resolution) rather than by SQL now(), which is
    # the same for every row of a transaction: messages are ordered, and paged, by this.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC)
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    # Optional per-message scope: the user can aim one question at several collections and/or specific files.
    # selectin: async sessions can't lazy-load, and the agent always needs the scope with the message.
    collections: Mapped[list["Collection"]] = relationship(secondary=message_collections, lazy="selectin")
    files: Mapped[list["File"]] = relationship(secondary=message_files, lazy="selectin")
