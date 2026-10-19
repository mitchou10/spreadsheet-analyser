import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, pg_enum


class FeedbackRating(enum.StrEnum):
    UP = "up"
    DOWN = "down"


class FeedbackReason(enum.StrEnum):
    """Why an answer was not good: a short list to count, the comment is for the details."""

    WRONG_RESULT = "wrong_result"
    WRONG_FILES = "wrong_files"
    INCOMPLETE = "incomplete"
    UNCLEAR = "unclear"
    OTHER = "other"


class MessageFeedback(Base):
    """The thumbs up/down a person gave to an assistant answer, with an optional reason and comment.
    One per person and message: voting again replaces it."""

    __tablename__ = "message_feedback"
    __table_args__ = (UniqueConstraint("message_id", "user_id", name="uq_message_feedback_message_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(255))
    rating: Mapped[FeedbackRating] = mapped_column(pg_enum(FeedbackRating, "feedback_rating"))
    reason: Mapped[FeedbackReason | None] = mapped_column(pg_enum(FeedbackReason, "feedback_reason"), default=None)
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
