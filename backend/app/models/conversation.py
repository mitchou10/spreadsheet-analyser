import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, pg_enum

if TYPE_CHECKING:
    from app.models.message import Message


DEFAULT_CONVERSATION_TITLE = "Nouvelle conversation"


class ConversationStatus(enum.StrEnum):
    ACTIVE = "active"
    # Agent run paused on a tool call awaiting human approval (HITL) - the actual
    # pause/resume checkpoint lives in the agent worker's own store, this is just
    # what the API/UI needs to know a conversation is blocked on a human.
    AWAITING_HUMAN = "awaiting_human"
    COMPLETED = "completed"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), default=DEFAULT_CONVERSATION_TITLE)
    status: Mapped[ConversationStatus] = mapped_column(
        pg_enum(ConversationStatus, "conversation_status"), default=ConversationStatus.ACTIVE
    )
    # LLM chosen for this conversation (an id from GET /models); None = the default model.
    # Every run of the conversation is executed by the worker with it.
    model: Mapped[str | None] = mapped_column(String(255), default=None)
    # Keycloak user_id (sub claim) of the owner - no local users table, see app/core/security.
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    # The conversation of an ephemeral analysis: not listed, and deleted with that collection.
    ephemeral_collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id", ondelete="CASCADE"), default=None, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )
