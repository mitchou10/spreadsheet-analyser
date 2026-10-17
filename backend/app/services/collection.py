import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AccessCollection, Collection
from app.repositories import AccessCollectionRepository, CollectionRepository
from app.services.access import CollectionAccessPolicy
from app.services.actor import Actor, normalize_email
from app.services.errors import ForbiddenError, NotFoundError
from app.services.storage import StorageService


class CollectionService:
    """Owner = Collection.created_by (full control). Anyone listed in access_collection by email can read
    the collection and its files/analyses, nothing else."""

    def __init__(self, session: AsyncSession, storage: StorageService) -> None:
        self.session = session
        self.storage = storage
        self.collections = CollectionRepository(session)
        self.accesses = AccessCollectionRepository(session)
        self.policy = CollectionAccessPolicy(session)

    async def create(self, actor: Actor, name: str, description: str | None = None) -> Collection:
        collection = await self.collections.add(
            Collection(name=name, description=description, created_by=actor.user_id)
        )
        await self.session.commit()
        return collection

    async def list_for_user(self, actor: Actor) -> list[Collection]:
        """Owned and shared-with-me collections."""
        return await self.collections.list_accessible(actor.user_id, normalize_email(actor.email))

    async def get(self, actor: Actor, collection_id: uuid.UUID) -> Collection:
        """Readable by the owner or anyone it was shared with."""
        collection = await self.collections.get(collection_id)
        if collection is None or not await self.policy.can_read(actor, collection):
            raise NotFoundError(f"Collection {collection_id} not found")
        return collection

    async def get_owned(self, actor: Actor, collection_id: uuid.UUID) -> Collection:
        collection = await self.get(actor, collection_id)
        if collection.created_by != actor.user_id:
            raise ForbiddenError("Only the owner of the collection can do this")
        return collection

    async def update(
        self, actor: Actor, collection_id: uuid.UUID, name: str | None = None, description: str | None = None
    ) -> Collection:
        collection = await self.get_owned(actor, collection_id)
        if name is not None:
            collection.name = name
        if description is not None:
            collection.description = description
        await self.session.commit()
        return collection

    async def delete(self, actor: Actor, collection_id: uuid.UUID) -> None:
        collection = await self.get_owned(actor, collection_id)
        await self.collections.delete(collection)
        await self.session.commit()
        # After the commit: a failed S3 cleanup leaves orphan objects, never dangling DB rows.
        await self.storage.delete_prefix(f"{collection_id}/")

    # --- Sharing (owner only) ---

    async def share(self, actor: Actor, collection_id: uuid.UUID, email: str) -> AccessCollection:
        """Grants read access to `email`. Idempotent."""
        collection = await self.get_owned(actor, collection_id)
        email = normalize_email(email)
        if not email:
            raise ValueError("email is required")
        existing = await self.accesses.get_by_email(collection.id, email)
        if existing is not None:
            return existing
        access = await self.accesses.add(
            AccessCollection(collection_id=collection.id, email=email, granted_by=actor.user_id)
        )
        await self.session.commit()
        return access

    async def revoke(self, actor: Actor, collection_id: uuid.UUID, email: str) -> None:
        collection = await self.get_owned(actor, collection_id)
        access = await self.accesses.get_by_email(collection.id, normalize_email(email))
        if access is None:
            raise NotFoundError(f"No access for {email} on collection {collection_id}")
        await self.accesses.delete(access)
        await self.session.commit()

    async def list_access(self, actor: Actor, collection_id: uuid.UUID) -> list[AccessCollection]:
        await self.get_owned(actor, collection_id)
        return await self.accesses.list_by_collection(collection_id)
