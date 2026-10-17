import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AccessCollection(Base):
    """Read access to a collection granted to someone by email (the owner is Collection.created_by).

    Keyed by email rather than user id so a collection can be shared with someone who has not logged in
    yet; matched against the email claim of the Keycloak identity (always stored lowercased)."""

    __tablename__ = "access_collection"
    __table_args__ = (UniqueConstraint("collection_id", "email", name="uq_access_collection_collection_id_email"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id", ondelete="CASCADE")
    )
    email: Mapped[str] = mapped_column(String(320), index=True)
    # Keycloak user_id (sub claim) of the owner who shared the collection.
    granted_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
