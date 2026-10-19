import uuid
from collections.abc import Sequence

from sqlalchemy import func, or_, select

from app.models import AccessCollection, Collection, File
from app.repositories.base import BaseRepository


class FileRepository(BaseRepository[File]):
    model = File

    async def list_by_collection(self, collection_id: uuid.UUID) -> list[File]:
        return await self._all(self._select().where(File.collection_id == collection_id).order_by(File.name))

    async def list_readable_by_hashes(self, hashes: Sequence[str], user_id: str, email: str) -> list[File]:
        """Files with one of these contents (sha256) in a collection the person owns or that was shared with them,
        in the ephemeral analyses they created too. Never a file of someone else: a hash alone gives no access."""
        if not hashes:
            return []
        shared = select(AccessCollection.collection_id).where(AccessCollection.email == email)
        return await self._all(
            self._select()
            .join(Collection, Collection.id == File.collection_id)
            .where(File.file_hash.in_(hashes), or_(Collection.created_by == user_id, Collection.id.in_(shared)))
            .order_by(File.uploaded_at.desc())
        )

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
