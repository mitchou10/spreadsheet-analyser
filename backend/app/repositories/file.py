import uuid

from app.models import File
from app.repositories.base import BaseRepository


class FileRepository(BaseRepository[File]):
    model = File

    async def list_by_collection(self, collection_id: uuid.UUID) -> list[File]:
        return await self._all(self._select().where(File.collection_id == collection_id).order_by(File.name))

    async def get_by_name(self, collection_id: uuid.UUID, name: str) -> File | None:
        return await self._first(self._select().where(File.collection_id == collection_id, File.name == name))
