import uuid
from collections.abc import Sequence

from app.models import AccessCollection
from app.repositories.base import BaseRepository


class AccessCollectionRepository(BaseRepository[AccessCollection]):
    model = AccessCollection

    async def list_by_collection(self, collection_id: uuid.UUID) -> list[AccessCollection]:
        return await self._all(
            self._select().where(AccessCollection.collection_id == collection_id).order_by(AccessCollection.email)
        )

    async def get_by_email(self, collection_id: uuid.UUID, email: str) -> AccessCollection | None:
        return await self._first(
            self._select().where(AccessCollection.collection_id == collection_id, AccessCollection.email == email)
        )

    async def list_for_collections(self, collection_ids: Sequence[uuid.UUID]) -> list[AccessCollection]:
        if not collection_ids:
            return []
        return await self._all(
            self._select().where(AccessCollection.collection_id.in_(collection_ids)).order_by(AccessCollection.email)
        )
