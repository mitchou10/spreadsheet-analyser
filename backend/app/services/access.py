from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Collection
from app.repositories import AccessCollectionRepository
from app.services.actor import Actor, normalize_email


class CollectionAccessPolicy:
    """Single place deciding who may read a collection: its owner, or an email listed in access_collection."""

    def __init__(self, session: AsyncSession) -> None:
        self.accesses = AccessCollectionRepository(session)

    async def can_read(self, actor: Actor, collection: Collection) -> bool:
        if collection.created_by == actor.user_id:
            return True
        email = normalize_email(actor.email)
        return bool(email) and await self.accesses.get_by_email(collection.id, email) is not None
