import uuid
from datetime import datetime

from sqlalchemy import or_, select, update

from app.models import AccessCollection, Collection
from app.repositories.base import BaseRepository


class CollectionRepository(BaseRepository[Collection]):
    model = Collection

    async def list_accessible(self, user_id: str, email: str) -> list[Collection]:
        """Collections owned by `user_id` or shared with `email` (already normalized)."""
        shared = select(AccessCollection.collection_id).where(AccessCollection.email == email)
        return await self._all(
            self._select()
            .where(or_(Collection.created_by == user_id, Collection.id.in_(shared)), Collection.expires_at.is_(None))
            .order_by(Collection.created_at.desc())
        )

    async def list_all(self) -> list[Collection]:
        return await self._all(
            self._select().where(Collection.expires_at.is_(None)).order_by(Collection.name, Collection.created_at)
        )

    async def list_expired(self, now: datetime) -> list[Collection]:
        return await self._all(self._select().where(Collection.expires_at < now).order_by(Collection.expires_at))

    async def backfill_owner_email(self, user_id: str, email: str) -> int:
        """Records the owner's email on their collections created before emails were stored. Returns how many."""
        result = await self.session.execute(
            update(Collection)
            .where(Collection.created_by == user_id, Collection.created_by_email.is_(None))
            .values(created_by_email=email)
        )
        return result.rowcount or 0

    async def ids_readable_by_email(self, email: str) -> list[uuid.UUID]:
        """Collections a person can read, identified by email only: the ones they own and the ones shared with them."""
        shared = select(AccessCollection.collection_id).where(AccessCollection.email == email)
        rows = await self.session.scalars(
            select(Collection.id).where(
                or_(Collection.created_by_email == email, Collection.id.in_(shared)), Collection.expires_at.is_(None)
            )
        )
        return list(rows.all())
