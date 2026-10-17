import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AccessCollection, Collection
from app.repositories import AccessCollectionRepository, CollectionRepository, FileRepository
from app.services.access import CollectionAccessPolicy
from app.services.actor import Actor, normalize_email
from app.services.dispatcher import RunDispatcher
from app.services.errors import ForbiddenError, NotFoundError
from app.services.storage import StorageService

logger = logging.getLogger(__name__)


class CollectionService:
    """Owner = Collection.created_by (full control). Anyone listed in access_collection by email can read
    the collection and its files/analyses, nothing else."""

    def __init__(self, session: AsyncSession, storage: StorageService, dispatcher: RunDispatcher | None = None) -> None:
        self.session = session
        self.storage = storage
        # None (tests, scripts): nothing is sent to the index worker.
        self.dispatcher = dispatcher
        self.collections = CollectionRepository(session)
        self.accesses = AccessCollectionRepository(session)
        self.files = FileRepository(session)
        self.policy = CollectionAccessPolicy(session)

    async def create(self, actor: Actor, name: str, description: str | None = None) -> Collection:
        collection = await self.collections.add(
            Collection(
                name=name,
                description=description,
                created_by=actor.user_id,
                created_by_email=normalize_email(actor.email) or None,
            )
        )
        await self.session.commit()
        return collection

    async def list_for_user(self, actor: Actor) -> list[Collection]:
        """Owned and shared-with-me collections."""
        email = normalize_email(actor.email)
        if email and await self.collections.backfill_owner_email(actor.user_id, email):
            # Collections created before emails were recorded are now attributed to their owner: their
            # readers are found by email, so the owner's search index has to be rebuilt.
            await self.session.commit()
            await self.user_indexes_changed([email])
        return await self.collections.list_accessible(actor.user_id, email)

    async def file_counts(self, collections: list[Collection]) -> dict[uuid.UUID, int]:
        return await self.files.count_by_collections([collection.id for collection in collections])

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
        readers = await self.reader_emails(collection)  # asked before the rows are gone
        await self.collections.delete(collection)
        await self.session.commit()
        # After the commit: a failed S3 cleanup leaves orphan objects, never dangling DB rows.
        await self.storage.delete_prefix(f"{collection_id}/")
        await self.user_indexes_changed(readers)  # the collection's index went with its S3 prefix

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
        await self.user_indexes_changed([email])  # the person can now search this collection
        return access

    async def revoke(self, actor: Actor, collection_id: uuid.UUID, email: str) -> None:
        collection = await self.get_owned(actor, collection_id)
        access = await self.accesses.get_by_email(collection.id, normalize_email(email))
        if access is None:
            raise NotFoundError(f"No access for {email} on collection {collection_id}")
        await self.accesses.delete(access)
        await self.session.commit()
        await self.user_indexes_changed([normalize_email(email)])  # ... and can no longer search it

    async def list_access(self, actor: Actor, collection_id: uuid.UUID) -> list[AccessCollection]:
        await self.get_owned(actor, collection_id)
        return await self.accesses.list_by_collection(collection_id)

    # --- Who reads what (for the search indexes) ---

    async def reader_emails(self, collection: Collection) -> list[str]:
        """The owner's email (if known) and the emails the collection is shared with."""
        shared = [access.email for access in await self.accesses.list_by_collection(collection.id)]
        owner = collection.created_by_email
        return sorted({email for email in [owner, *shared] if email})

    async def audience(self, collection_id: uuid.UUID) -> tuple[str | None, list[str]]:
        """(owner's email or None, emails it is shared with), worker side: no user check."""
        collection = await self.collections.get(collection_id)
        if collection is None:
            raise NotFoundError(f"Collection {collection_id} not found")
        shared = [access.email for access in await self.accesses.list_by_collection(collection_id)]
        return collection.created_by_email, shared

    async def readable_collection_ids(self, email: str) -> list[uuid.UUID]:
        """Collections a person can read, identified by email (worker side)."""
        return await self.collections.ids_readable_by_email(normalize_email(email))

    async def user_indexes_changed(self, emails: list[str]) -> None:
        """Asks the index worker to rebuild these people's search indexes. Best effort: the agent only searches
        what the backend says a person may read, so a late rebuild never lets anyone see more than they should."""
        if self.dispatcher is None:
            return
        for email in emails:
            try:
                await self.dispatcher.enqueue_user_index_rebuild(email)
            except Exception:
                logger.exception("Could not enqueue the rebuild of a user's search index")
