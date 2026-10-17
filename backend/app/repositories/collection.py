from sqlalchemy import or_, select

from app.models import AccessCollection, Collection
from app.repositories.base import BaseRepository


class CollectionRepository(BaseRepository[Collection]):
    model = Collection

    async def list_accessible(self, user_id: str, email: str) -> list[Collection]:
        """Collections owned by `user_id` or shared with `email` (already normalized)."""
        shared = select(AccessCollection.collection_id).where(AccessCollection.email == email)
        return await self._all(
            self._select()
            .where(or_(Collection.created_by == user_id, Collection.id.in_(shared)))
            .order_by(Collection.created_at.desc())
        )
