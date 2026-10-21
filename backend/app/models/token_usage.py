import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TokenUsage(Base):
    """Tokens one LLM call of a run consumed, i.e. one execution of an agent graph node ("plan", "agent"...).

    Written when the run completes, from the usage the model reported; the sums per user, per node and per day
    show who and what consumes the most."""

    __tablename__ = "token_usage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    # Keycloak user_id (sub claim) of whoever asked, kept with the email so the figures stay readable.
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    user_email: Mapped[str | None] = mapped_column(String(320), default=None)
    model: Mapped[str | None] = mapped_column(String(255), default=None)
    node: Mapped[str] = mapped_column(String(100), index=True)
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    total_tokens: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
