import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.file import File


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    # Keycloak user_id (sub claim) - no local users table, see app/core/security.
    created_by: Mapped[str] = mapped_column(String(255), index=True)
    # Owner's email when the collection was created (shown in the admin page; null for older rows).
    created_by_email: Mapped[str | None] = mapped_column(String(320), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Ephemeral analysis (POST /api/ephemeral/analyses): a collection nobody lists, purged after `expires_at`.
    # Null for a normal collection.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, index=True)
    # How long to keep it after each run: the expiry moves forward with the activity.
    ttl_hours: Mapped[int | None] = mapped_column(Integer, default=None)

    files: Mapped[list["File"]] = relationship(back_populates="collection", cascade="all, delete-orphan")
