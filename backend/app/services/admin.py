import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AccessCollection, Collection
from app.repositories import AccessCollectionRepository, CollectionRepository, FileRepository
from app.services.actor import Actor, normalize_email
from app.services.errors import ConflictError, NotFoundError


@dataclass
class AccessEntry:
    email: str
    granted_by: str
    created_at: datetime


@dataclass
class CollectionAccess:
    collection_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    owner_id: str
    owner_email: str | None  # null for collections created before emails were recorded
    file_count: int
    shared_with: list[AccessEntry] = field(default_factory=list)


@dataclass
class PersonCollection:
    collection_id: uuid.UUID
    name: str
    role: str  # "owner" | "viewer"


@dataclass
class PersonAccess:
    email: str | None  # null: an owner whose email was never recorded, identified by `user_id` only
    user_id: str | None
    collections: list[PersonCollection] = field(default_factory=list)


class AdminService:
    """Who can read what, across every collection, and granting/revoking read access by email.

    Callers must already have checked the caller is an administrator: nothing here is scoped to a user."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.collections = CollectionRepository(session)
        self.accesses = AccessCollectionRepository(session)
        self.files = FileRepository(session)

    async def collection_access(self) -> list[CollectionAccess]:
        collections = await self.collections.list_all()
        ids = [collection.id for collection in collections]
        counts = await self.files.count_by_collections(ids)
        shared: dict[uuid.UUID, list[AccessEntry]] = {}
        for access in await self.accesses.list_for_collections(ids):
            shared.setdefault(access.collection_id, []).append(
                AccessEntry(access.email, access.granted_by, access.created_at)
            )
        return [
            CollectionAccess(
                collection_id=collection.id,
                name=collection.name,
                description=collection.description,
                created_at=collection.created_at,
                owner_id=collection.created_by,
                owner_email=collection.created_by_email,
                file_count=counts.get(collection.id, 0),
                shared_with=shared.get(collection.id, []),
            )
            for collection in collections
        ]

    async def people_access(self) -> list[PersonAccess]:
        """The same data seen from the people: each email with the collections they own or can read."""
        people: dict[str, PersonAccess] = {}

        def person(email: str | None, user_id: str | None) -> PersonAccess:
            key = email or f"user:{user_id}"
            return people.setdefault(key, PersonAccess(email=email, user_id=user_id if not email else None))

        for item in await self.collection_access():
            entry = PersonCollection(item.collection_id, item.name, "owner")
            person(item.owner_email, item.owner_id).collections.append(entry)
            for access in item.shared_with:
                if access.email != item.owner_email:
                    person(access.email, None).collections.append(
                        PersonCollection(item.collection_id, item.name, "viewer")
                    )
        return sorted(people.values(), key=lambda p: (p.email is None, p.email or p.user_id or ""))

    async def grant(self, admin: Actor, collection_id: uuid.UUID, email: str) -> AccessCollection:
        """Gives `email` read access to any collection (idempotent)."""
        collection = await self._collection(collection_id)
        email = normalize_email(email)
        if not email:
            raise ValueError("email is required")
        if email == collection.created_by_email:
            raise ConflictError(f"{email} already owns this collection")
        existing = await self.accesses.get_by_email(collection.id, email)
        if existing is not None:
            return existing
        access = await self.accesses.add(
            AccessCollection(collection_id=collection.id, email=email, granted_by=admin.user_id)
        )
        await self.session.commit()
        return access

    async def revoke(self, collection_id: uuid.UUID, email: str) -> None:
        collection = await self._collection(collection_id)
        access = await self.accesses.get_by_email(collection.id, normalize_email(email))
        if access is None:
            raise NotFoundError(f"No access for {email} on collection {collection_id}")
        await self.accesses.delete(access)
        await self.session.commit()

    async def get_collection(self, collection_id: uuid.UUID) -> Collection:
        return await self._collection(collection_id)

    async def _collection(self, collection_id: uuid.UUID) -> Collection:
        collection = await self.collections.get(collection_id)
        if collection is None:
            raise NotFoundError(f"Collection {collection_id} not found")
        return collection
