import uuid
from collections.abc import Sequence

from sqlalchemy import func, select

from app.models import File
from app.repositories.base import BaseRepository


class FileRepository(BaseRepository[File]):
    model = File

    async def list_by_collection(self, collection_id: uuid.UUID) -> list[File]:
        return await self._all(self._select().where(File.collection_id == collection_id).order_by(File.name))

    async def get_by_name(self, collection_id: uuid.UUID, name: str) -> File | None:
        return await self._first(self._select().where(File.collection_id == collection_id, File.name == name))

    async def count_by_collections(self, collection_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not collection_ids:
            return {}
        rows = await self.session.execute(
            select(File.collection_id, func.count(File.id))
            .where(File.collection_id.in_(collection_ids))
            .group_by(File.collection_id)
        )
        return {collection_id: count for collection_id, count in rows}
